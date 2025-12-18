from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
import httpx

from config import TOKEN, PHONE_NUMBER_ID
from languages import WELCOME_MENU, DISCLAIMER, change_language
from features.grok import ask_grok
from features.pharmacies import handle_pharmacies
from features.cycle import handle_cycle
from utils import is_spam, update_last_used


app = FastAPI()

# In-memory state (single process only). Use Redis/DB if you run multiple workers.
user_language: dict[str, str | None] = {}
last_used: dict[str, float] = {}
cycle_data: dict[str, dict] = {}  # per-sender cycle state

VERIFY_TOKEN = "lafiyabot123"
GRAPH_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"


def get_lang(sender: str) -> str:
    lang = user_language.get(sender)
    return lang if lang else "fr"


def append_disclaimer(reply: str, lang: str) -> str:
    disclaimer = DISCLAIMER.get(lang, DISCLAIMER.get("fr", ""))
    return (reply or "") + disclaimer


def detect_language_choice(text_lower: str) -> str | None:
    """
    Returns "1" for FR, "2" for EN, "3" for HA.
    Uses exact matching to avoid false positives (e.g., dates/codes with digits).
    Also supports deterministic interactive IDs: LANG_FR/LANG_EN/LANG_HA.
    """
    tl = (text_lower or "").strip().lower()

    # Interactive IDs (recommended)
    if tl in {"lang_fr", "langue_fr", "lang-fr", "fr_lang"}:
        return "1"
    if tl in {"lang_en", "langue_en", "lang-en", "en_lang"}:
        return "2"
    if tl in {"lang_ha", "langue_ha", "lang-ha", "ha_lang"}:
        return "3"

    # Text tokens (exact)
    french_tokens = {"1", "fr", "français", "francais", "french"}
    english_tokens = {"2", "en", "english", "anglais"}
    hausa_tokens = {"3", "ha", "hausa"}

    if tl in french_tokens:
        return "1"
    if tl in english_tokens:
        return "2"
    if tl in hausa_tokens:
        return "3"

    return None


def is_language_menu_request(text_lower: str) -> bool:
    tl = (text_lower or "").strip().lower()
    return tl in {"langue", "language", "change langue", "change language", "menu_lang", "menu_language"}


def extract_incoming_content(msg: dict) -> tuple[str, str, dict]:
    """
    Normalizes inbound WhatsApp messages.

    Returns:
      (content_type, content_text, meta)

    content_type: "text" | "interactive" | "other"
    content_text: a single string we can route on (prefer stable IDs)
    meta: useful extracted metadata (id/title/type)
    """
    msg_type = (msg.get("type") or "").strip().lower()

    # Plain text
    if msg_type == "text":
        body = (msg.get("text", {}).get("body") or "").strip()
        return "text", body, {}

    # Interactive responses (button / list)
    if msg_type == "interactive":
        inter = msg.get("interactive") or {}
        inter_type = (inter.get("type") or "").strip().lower()

        # button_reply
        if inter_type == "button_reply":
            br = inter.get("button_reply") or {}
            btn_id = (br.get("id") or "").strip()
            title = (br.get("title") or "").strip()
            # Prefer id if present; else fallback to title
            chosen = btn_id if btn_id else title
            return "interactive", chosen, {"interactive_type": "button_reply", "id": btn_id, "title": title}

        # list_reply
        if inter_type == "list_reply":
            lr = inter.get("list_reply") or {}
            item_id = (lr.get("id") or "").strip()
            title = (lr.get("title") or "").strip()
            chosen = item_id if item_id else title
            return "interactive", chosen, {"interactive_type": "list_reply", "id": item_id, "title": title}

        # Unknown interactive subtype
        return "interactive", "", {"interactive_type": inter_type}

    # Other message types you may want to support later: image, audio, document, location, etc.
    return "other", "", {"msg_type": msg_type}


async def send_whatsapp_message(to: str, body: str) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GRAPH_URL, headers=headers, json=payload)
        resp.raise_for_status()


@app.get("/webhook")
async def verify(request: Request):
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if token == VERIFY_TOKEN and challenge is not None:
        return PlainTextResponse(content=str(challenge), status_code=200)

    raise HTTPException(status_code=403, detail="Wrong token")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    entries = data.get("entry") or []
    if not isinstance(entries, list) or not entries:
        return JSONResponse({"status": "ignored", "reason": "no entry"}, status_code=200)

    try:
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = change.get("value") or {}
                messages = value.get("messages") or []
                if not isinstance(messages, list):
                    continue

                for msg in messages:
                    sender = msg.get("from")
                    if not sender:
                        continue

                    # Anti-spam / rate limit
                    if is_spam(sender, last_used):
                        continue
                    update_last_used(sender, last_used)

                    # Initialize sender state
                    user_language.setdefault(sender, None)
                    cycle_data.setdefault(sender, {})

                    content_type, content_text, meta = extract_incoming_content(msg)

                    # If it's not text/interactive, ignore for now (no crash)
                    if content_type not in {"text", "interactive"}:
                        continue

                    text_original = (content_text or "").strip()
                    if not text_original:
                        continue

                    text_lower = text_original.lower().strip()

                    # === PRIORITY 1: Language selection ===
                    choice = detect_language_choice(text_lower)
                    if choice is not None:
                        reply = change_language(choice, sender, user_language)
                        lang = get_lang(sender)
                        reply = append_disclaimer(reply, lang)
                        await send_whatsapp_message(sender, reply)
                        continue

                    # === Back to language menu ===
                    if is_language_menu_request(text_lower):
                        user_language.pop(sender, None)
                        user_language.setdefault(sender, None)
                        reply = append_disclaimer(WELCOME_MENU, "fr")
                        await send_whatsapp_message(sender, reply)
                        continue

                    # === First contact (language not set yet) ===
                    if user_language.get(sender) is None:
                        reply = append_disclaimer(WELCOME_MENU, "fr")
                        await send_whatsapp_message(sender, reply)
                        continue

                    # Determine language
                    lang = get_lang(sender)

                    # === Pharmacies de garde ===
                    if "pharmacie" in text_lower and "garde" in text_lower:
                        reply = handle_pharmacies(text_original, sender, user_language)

                    # === Cycle tracking ===
                    elif any(word in text_lower for word in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                        reply, updated = handle_cycle(
                            text_original,
                            sender,
                            user_language,
                            cycle_data.get(sender, {})
                        )
                        cycle_data[sender] = updated if isinstance(updated, dict) else cycle_data.get(sender, {})

                    # === Default: Grok ===
                    else:
                        reply = await ask_grok(text_original, lang)

                    # Append disclaimer + send
                    reply = append_disclaimer(reply, lang)
                    await send_whatsapp_message(sender, reply)

    except httpx.HTTPStatusError as e:
        print("WhatsApp API error:", str(e))
    except Exception as e:
        print("Erreur:", e)

    return {"status": "ok"}
