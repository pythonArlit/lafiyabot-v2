from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
import httpx

from config import TOKEN, PHONE_NUMBER_ID
from languages import (
    WELCOME_MENU_TEXT,
    MAIN_MENU_TEXT,
    DISCLAIMER,
    set_language,
    get_text,
)
from features.grok import ask_grok
from features.pharmacies import handle_pharmacies
from features.cycle import handle_cycle
from utils import is_spam, update_last_used

app = FastAPI()

VERIFY_TOKEN = "lafiyabot123"
GRAPH_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

# In-memory state (OK single worker; pour scale multi-workers → Redis)
user_language: dict[str, str | None] = {}
last_used: dict[str, float] = {}
cycle_data: dict[str, dict] = {}  # per-sender

# IDs stables
LANG_FR = "LANG_FR"
LANG_EN = "LANG_EN"
LANG_HA = "LANG_HA"
MENU_LANG = "MENU_LANG"

MENU_CYCLE = "MENU_CYCLE"
MENU_PHARM = "MENU_PHARM"
MENU_CLINIC = "MENU_CLINIC"
MENU_URGENCY = "MENU_URGENCY"
MENU_DOCTOR = "MENU_DOCTOR"


def get_lang(sender: str) -> str:
    return user_language.get(sender) or "fr"


def append_disclaimer(text: str, lang: str) -> str:
    d = DISCLAIMER.get(lang, DISCLAIMER.get("fr", ""))
    return (text or "") + d


def normalize(s: str) -> str:
    return (s or "").strip()


def extract_incoming(msg: dict) -> tuple[str, str]:
    """
    Returns (kind, content):
      kind in {"text","interactive","other"}
      content = body or interactive id/title (prefer id)
    """
    msg_type = (msg.get("type") or "").lower().strip()

    if msg_type == "text":
        body = (msg.get("text", {}).get("body") or "").strip()
        return "text", body

    if msg_type == "interactive":
        inter = msg.get("interactive") or {}
        itype = (inter.get("type") or "").lower().strip()

        if itype == "button_reply":
            br = inter.get("button_reply") or {}
            # Prefer id
            return "interactive", (br.get("id") or br.get("title") or "").strip()

        if itype == "list_reply":
            lr = inter.get("list_reply") or {}
            # Prefer id
            return "interactive", (lr.get("id") or lr.get("title") or "").strip()

        return "interactive", ""

    return "other", ""


async def wa_send_text(to: str, body: str) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        r.raise_for_status()


async def wa_send_list_language(to: str) -> None:
    """
    Envoie le menu langue en LIST (recommandé).
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "LafiyaBot"},
            "body": {"text": WELCOME_MENU_TEXT.get("fr")},  # corps neutre
            "footer": {"text": "Choisis une langue / Choose a language"},
            "action": {
                "button": "Langues",
                "sections": [
                    {
                        "title": "Langue",
                        "rows": [
                            {"id": LANG_FR, "title": "Français", "description": "Informations santé en français"},
                            {"id": LANG_EN, "title": "English", "description": "Health info in simple English"},
                            {"id": LANG_HA, "title": "Hausa", "description": "Bayanan lafiya a Hausa"},
                        ],
                    }
                ],
            },
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        r.raise_for_status()


async def wa_send_list_main_menu(to: str, lang: str) -> None:
    """
    Menu principal (options 4 à 8) en LIST.
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body_text = MAIN_MENU_TEXT.get(lang, MAIN_MENU_TEXT["fr"])

    rows = [
        {"id": MENU_CYCLE, "title": get_text("menu_cycle", lang), "description": get_text("menu_cycle_desc", lang)},
        {"id": MENU_PHARM, "title": get_text("menu_pharm", lang), "description": get_text("menu_pharm_desc", lang)},
        {"id": MENU_CLINIC, "title": get_text("menu_clinic", lang), "description": get_text("menu_clinic_desc", lang)},
        {"id": MENU_URGENCY, "title": get_text("menu_urgency", lang), "description": get_text("menu_urgency_desc", lang)},
        {"id": MENU_DOCTOR, "title": get_text("menu_doctor", lang), "description": get_text("menu_doctor_desc", lang)},
        {"id": MENU_LANG, "title": get_text("menu_lang", lang), "description": get_text("menu_lang_desc", lang)},
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "LafiyaBot"},
            "body": {"text": body_text},
            "footer": {"text": get_text("menu_footer", lang)},
            "action": {
                "button": get_text("menu_button", lang),
                "sections": [{"title": get_text("menu_title", lang), "rows": rows}],
            },
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        r.raise_for_status()


def is_language_text_choice(text_lower: str) -> str | None:
    """
    Support fallback texte: '1/2/3', 'fr', 'english', 'hausa', etc.
    IMPORTANT: exact match only.
    """
    tl = (text_lower or "").strip().lower()
    if tl in {"1", "fr", "français", "francais", "french"}:
        return "fr"
    if tl in {"2", "en", "english", "anglais"}:
        return "en"
    if tl in {"3", "ha", "hausa"}:
        return "ha"
    return None


@app.get("/webhook")
async def verify(request: Request):
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if token == VERIFY_TOKEN and challenge is not None:
        return PlainTextResponse(str(challenge), status_code=200)
    raise HTTPException(status_code=403, detail="Wrong token")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    entries = data.get("entry") or []
    if not isinstance(entries, list) or not entries:
        return JSONResponse({"status": "ignored", "reason": "no entry"}, status_code=200)

    try:
        for entry in entries:
            for change in (entry.get("changes") or []):
                value = change.get("value") or {}
                messages = value.get("messages") or []
                if not isinstance(messages, list):
                    continue

                for msg in messages:
                    sender = msg.get("from")
                    if not sender:
                        continue

                    # anti-spam
                    if is_spam(sender, last_used):
                        continue
                    update_last_used(sender, last_used)

                    # init state
                    user_language.setdefault(sender, None)
                    cycle_data.setdefault(sender, {})

                    kind, content = extract_incoming(msg)
                    if kind not in {"text", "interactive"}:
                        continue

                    text_original = normalize(content)
                    if not text_original:
                        continue
                    text_lower = text_original.lower().strip()

                    # ===== 1) ROUTAGE INTERACTIVE PAR IDs =====
                    # Langues
                    if text_original in {LANG_FR, LANG_EN, LANG_HA}:
                        lang = {"LANG_FR": "fr", "LANG_EN": "en", "LANG_HA": "ha"}[text_original]
                        set_language(sender, lang, user_language)
                        await wa_send_list_main_menu(sender, lang)
                        continue

                    # Retour menu langue
                    if text_original == MENU_LANG or text_lower in {"langue", "language", "change langue", "change language"}:
                        user_language[sender] = None
                        await wa_send_list_language(sender)
                        continue

                    # Si langue non choisie → menu langue
                    if user_language.get(sender) is None:
                        # fallback texte 1/2/3
                        lang_choice = is_language_text_choice(text_lower)
                        if lang_choice:
                            set_language(sender, lang_choice, user_language)
                            await wa_send_list_main_menu(sender, lang_choice)
                        else:
                            await wa_send_list_language(sender)
                        continue

                    lang = get_lang(sender)

                    # ===== 2) ROUTAGE MENU PRINCIPAL (IDs) =====
                    if text_original == MENU_CYCLE:
                        # On peut soit afficher une aide, soit lancer handle_cycle avec une phrase guide
                        hint = get_text("cycle_hint", lang)
                        reply = append_disclaimer(hint, lang)
                        await wa_send_text(sender, reply)
                        continue

                    if text_original == MENU_PHARM:
                        hint = get_text("pharm_hint", lang)
                        reply = append_disclaimer(hint, lang)
                        await wa_send_text(sender, reply)
                        continue

                    if text_original == MENU_CLINIC:
                        # Fonctionnalité en cours (placeholder propre)
                        reply = append_disclaimer(get_text("clinic_placeholder", lang), lang)
                        await wa_send_text(sender, reply)
                        continue

                    if text_original == MENU_URGENCY:
                        reply = append_disclaimer(get_text("urgency_message", lang), lang)
                        await wa_send_text(sender, reply)
                        continue

                    if text_original == MENU_DOCTOR:
                        reply = append_disclaimer(get_text("doctor_placeholder", lang), lang)
                        await wa_send_text(sender, reply)
                        continue

                    # ===== 3) ROUTAGE TEXTE LIBRE (features existantes) =====
                    if "pharmacie" in text_lower and "garde" in text_lower:
                        reply = handle_pharmacies(text_original, sender, user_language)
                        reply = append_disclaimer(reply, lang)
                        await wa_send_text(sender, reply)
                        continue

                    if any(w in text_lower for w in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                        reply, updated = handle_cycle(text_original, sender, user_language, cycle_data.get(sender, {}))
                        if isinstance(updated, dict):
                            cycle_data[sender] = updated
                        reply = append_disclaimer(reply, lang)
                        await wa_send_text(sender, reply)
                        continue

                    # défaut: Grok
                    reply = await ask_grok(text_original, lang)
                    reply = append_disclaimer(reply, lang)
                    await wa_send_text(sender, reply)

    except httpx.HTTPStatusError as e:
        print("WhatsApp API error:", str(e))
    except Exception as e:
        print("Erreur:", e)

    return {"status": "ok"}
