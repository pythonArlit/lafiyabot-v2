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

# In-memory state (OK for a single process; use Redis/DB if you scale horizontally)
user_language: dict[str, str | None] = {}
last_used: dict[str, float] = {}
cycle_data: dict[str, dict] = {}   # per-sender state


VERIFY_TOKEN = "lafiyabot123"
GRAPH_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"


def get_lang(sender: str) -> str:
    """Return sender language or default French."""
    lang = user_language.get(sender)
    return lang if lang else "fr"


def append_disclaimer(reply: str, lang: str) -> str:
    """Append disclaimer safely."""
    disclaimer = DISCLAIMER.get(lang, DISCLAIMER.get("fr", ""))
    return (reply or "") + disclaimer


def normalize_choice(text: str) -> str:
    return (text or "").strip().lower()


def detect_language_choice(text_lower: str) -> str | None:
    """
    Returns:
      "1" for French, "2" for English, "3" for Hausa, None if not a language selection message.
    Uses exact matching only (prevents false positives like '2025' or 'AR-xxxxx-1').
    """
    # Accept common variants, but exact tokens only.
    french_tokens = {"1", "fr", "français", "francais", "french"}
    english_tokens = {"2", "en", "english", "anglais"}
    hausa_tokens = {"3", "ha", "hausa"}

    if text_lower in french_tokens:
        return "1"
    if text_lower in english_tokens:
        return "2"
    if text_lower in hausa_tokens:
        return "3"
    return None


async def send_whatsapp_message(to: str, body: str) -> None:
    """Send message to WhatsApp Cloud API (async)."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GRAPH_URL, headers=headers, json=payload)
        # Optional: raise for better debugging
        resp.raise_for_status()


@app.get("/webhook")
async def verify(request: Request):
    """
    WhatsApp webhook verification.
    Meta expects:
      - hub.verify_token == your token
      - return hub.challenge as plain text with 200
    """
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if token == VERIFY_TOKEN and challenge is not None:
        return PlainTextResponse(content=str(challenge), status_code=200)

    raise HTTPException(status_code=403, detail="Wrong token")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Basic shape guard
    entries = data.get("entry") or []
    if not isinstance(entries, list) or not entries:
        return JSONResponse({"status": "ignored", "reason": "no entry"}, status_code=200)

    try:
        # Iterate over all entries/changes/messages (more robust than [0])
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = (change.get("value") or {})
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

                    # Ensure sender is initialized
                    user_language.setdefault(sender, None)
                    cycle_data.setdefault(sender, {})  # per-user

                    # Handle only text messages safely
                    msg_type = msg.get("type")
                    if msg_type != "text":
                        # You can expand here: interactive/button/audio/image handling
                        continue

                    text_original = (msg.get("text", {}).get("body") or "").strip()
                    text_lower = text_original.lower().strip()

                    # === PRIORITY 1: language choice (exact matching) ===
                    choice = detect_language_choice(text_lower)
                    if choice is not None:
                        reply = change_language(choice, sender, user_language)
                        lang = get_lang(sender)
                        reply = append_disclaimer(reply, lang)
                        await send_whatsapp_message(sender, reply)
                        continue

                    # === Return to language menu ===
                    if text_lower in {"langue", "language", "change langue", "change language"}:
                        user_language.pop(sender, None)  # reset
                        user_language.setdefault(sender, None)
                        reply = append_disclaimer(WELCOME_MENU, "fr")
                        await send_whatsapp_message(sender, reply)
                        continue

                    # === First contact / language not set yet ===
                    if user_language.get(sender) is None:
                        reply = append_disclaimer(WELCOME_MENU, "fr")
                        await send_whatsapp_message(sender, reply)
                        continue

                    # Determine current language
                    lang = get_lang(sender)

                    # === Pharmacies de garde ===
                    if "pharmacie" in text_lower and "garde" in text_lower:
                        reply = handle_pharmacies(text_original, sender, user_language)

                    # === Cycle tracking ===
                    elif any(word in text_lower for word in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                        # handle_cycle returns (reply, updated_user_cycle_data)
                        reply, updated = handle_cycle(
                            text_original,
                            sender,
                            user_language,
                            cycle_data.get(sender, {})
                        )
                        # Store per-user state safely
                        cycle_data[sender] = updated if isinstance(updated, dict) else cycle_data.get(sender, {})

                    # === Default: Grok ===
                    else:
                        reply = await ask_grok(text_original, lang)

                    # Append disclaimer + send
                    reply = append_disclaimer(reply, lang)
                    await send_whatsapp_message(sender, reply)

    except httpx.HTTPStatusError as e:
        # Meta API error. Log details if needed.
        print("WhatsApp API error:", str(e))
    except Exception as e:
        # Any other error
        print("Erreur:", e)

    return {"status": "ok"}
