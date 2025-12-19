from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
import httpx
import json

from config import TOKEN, PHONE_NUMBER_ID
from languages import WELCOME_MENU, DISCLAIMER
from features.grok import ask_grok
from features.pharmacies import handle_pharmacies
from features.cycle import handle_cycle
from utils import is_spam, update_last_used

app = FastAPI()

# =========================
# CONFIG
# =========================
VERIFY_TOKEN = "lafiyabot123"
GRAPH_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

DEBUG = True
DISABLE_SPAM = False  # set True temporarily for debugging

# =========================
# STATE (in-memory)
# =========================
user_language: dict[str, str | None] = {}
last_used: dict[str, float] = {}
cycle_data: dict[str, dict] = {}  # per user

# =========================
# STABLE IDs
# =========================
LANG_FR = "LANG_FR"
LANG_EN = "LANG_EN"
LANG_HA = "LANG_HA"

MENU_LANG = "MENU_LANG"

MENU_CHAT_MEDICAL = "MENU_CHAT_MEDICAL"  # top of menu
MENU_CYCLE = "MENU_CYCLE"
MENU_PHARM = "MENU_PHARM"
MENU_CLINIC = "MENU_CLINIC"
MENU_URGENCY = "MENU_URGENCY"
MENU_DOCTOR = "MENU_DOCTOR"


def log(*args):
    if DEBUG:
        print(*args)


def get_lang(sender: str) -> str:
    return user_language.get(sender) or "fr"


def append_disclaimer(text: str, lang: str) -> str:
    d = DISCLAIMER.get(lang, DISCLAIMER.get("fr", ""))
    return (text or "") + d


def normalize(s: str) -> str:
    return (s or "").strip()


def is_language_text_choice(text_lower: str) -> str | None:
    """
    Fallback language selection by text. Exact match only.
    """
    tl = (text_lower or "").strip().lower()
    if tl in {"1", "fr", "français", "francais", "french"}:
        return "fr"
    if tl in {"2", "en", "english", "anglais"}:
        return "en"
    if tl in {"3", "ha", "hausa"}:
        return "ha"
    return None


def extract_incoming(msg: dict) -> tuple[str, str]:
    """
    Returns (kind, content):
      kind in {"text","interactive","other"}
      content = text body OR interactive id/title (prefer id)
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
            return "interactive", (br.get("id") or br.get("title") or "").strip()

        if itype == "list_reply":
            lr = inter.get("list_reply") or {}
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
        log("SEND_TEXT status:", r.status_code)
        if r.status_code >= 400:
            log("SEND_TEXT error:", r.text)
        r.raise_for_status()


async def wa_send_list_language(to: str) -> None:
    """
    Language menu (LIST). ASCII-only to avoid strict validation edge cases.
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "Welcome to LafiyaBot. Choose a language / Choisis une langue."},
            "action": {
                "button": "Languages",
                "sections": [
                    {
                        "title": "Language",
                        "rows": [
                            {"id": LANG_FR, "title": "Francais", "description": "Infos sante en francais"},
                            {"id": LANG_EN, "title": "English", "description": "Health info in English"},
                            {"id": LANG_HA, "title": "Hausa", "description": "Bayanan lafiya a Hausa"},
                        ],
                    }
                ],
            },
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        log("LANG_LIST status:", r.status_code)
        if r.status_code >= 400:
            log("LANG_LIST error:", r.text)
            fallback = WELCOME_MENU["fr"] if isinstance(WELCOME_MENU, dict) else str(WELCOME_MENU)
            await wa_send_text(to, fallback)
            return
        r.raise_for_status()


async def wa_send_list_main_menu(to: str, lang: str) -> None:
    """
    Main menu (LIST) - strict payload + logs + text fallback.
    Includes 'Medical chat' at top.
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}

    if lang == "en":
        body_text = "Main menu. Choose an option."
        button_text = "Menu"
        section_title = "Options"
        rows = [
            {"id": MENU_CHAT_MEDICAL, "title": "Medical chat",       "description": "Ask a health question"},
            {"id": MENU_CYCLE,        "title": "Cycle / period",     "description": "Next period, delay"},
            {"id": MENU_PHARM,        "title": "Duty pharmacies",    "description": "Find nearby pharmacy"},
            {"id": MENU_CLINIC,       "title": "Nearby clinics",     "description": "Health facilities"},
            {"id": MENU_URGENCY,      "title": "Emergency",          "description": "Warning signs"},
            {"id": MENU_DOCTOR,       "title": "Contact a doctor",   "description": "Feature in progress"},
            {"id": MENU_LANG,         "title": "Change language",    "description": "FR / EN / HA"},
        ]
    elif lang == "ha":
        # ASCII-only Hausa for interactive list stability
        body_text = "Babban menu. Zabi abin da kake so."
        button_text = "Menu"
        section_title = "Zabuka"
        rows = [
            {"id": MENU_CHAT_MEDICAL, "title": "Tattaunawar lafiya", "description": "Tambayi matsalar lafiya"},
            {"id": MENU_CYCLE,        "title": "Haila / cycle",      "description": "Ranar gaba, jinkiri"},
            {"id": MENU_PHARM,        "title": "Pharmacy na gaggawa","description": "Nemo kusa"},
            {"id": MENU_CLINIC,       "title": "Asibitoci kusa",     "description": "Cibiyoyin lafiya"},
            {"id": MENU_URGENCY,      "title": "Gaggawa",            "description": "Alamun hadari"},
            {"id": MENU_DOCTOR,       "title": "Tuntubi likita",     "description": "Ana shiryawa"},
            {"id": MENU_LANG,         "title": "Canza yare",         "description": "FR / EN / HA"},
        ]
    else:
        body_text = "Menu principal. Choisis une option."
        button_text = "Menu"
        section_title = "Options"
        rows = [
            {"id": MENU_CHAT_MEDICAL, "title": "Chat medical",        "description": "Poser une question sante"},
            {"id": MENU_CYCLE,        "title": "Cycle / regles",      "description": "Prochaines regles, retard"},
            {"id": MENU_PHARM,        "title": "Pharmacies de garde", "description": "Trouver une pharmacie"},
            {"id": MENU_CLINIC,       "title": "Cliniques proches",   "description": "Centres de sante"},
            {"id": MENU_URGENCY,      "title": "Urgence",            "description": "Signes d'alerte"},
            {"id": MENU_DOCTOR,       "title": "Contacter medecin",   "description": "Fonction en cours"},
            {"id": MENU_LANG,         "title": "Changer de langue",  "description": "FR / EN / HA"},
        ]

    # Enforce WhatsApp constraints: title <= 24, description <= 72, non-empty
    safe_rows = []
    for r in rows:
        title = (r.get("title") or "").strip()[:24] or "Option"
        desc = (r.get("description") or "").strip()[:72]
        safe_rows.append({"id": r["id"], "title": title, "description": desc})

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text[:1024]},
            "action": {
                "button": (button_text[:20] or "Menu"),
                "sections": [
                    {"title": (section_title[:24] or "Options"), "rows": safe_rows}
                ],
            },
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        log("MAIN_MENU status:", r.status_code)
        if r.status_code >= 400:
            log("MAIN_MENU error:", r.text)

        # Text fallback if interactive fails
        if r.status_code >= 400:
            fallback = {
                "fr": (
                    "Menu:\n"
                    "0) Chat medical\n"
                    "4) Cycle / regles\n"
                    "5) Pharmacies de garde\n"
                    "6) Cliniques proches\n"
                    "7) Urgence\n"
                    "8) Contacter medecin\n"
                    "Tape 'langue' pour changer."
                ),
                "en": (
                    "Menu:\n"
                    "0) Medical chat\n"
                    "4) Cycle / period\n"
                    "5) Duty pharmacies\n"
                    "6) Nearby clinics\n"
                    "7) Emergency\n"
                    "8) Contact a doctor\n"
                    "Type 'language' to change."
                ),
                "ha": (
                    "Menu:\n"
                    "0) Tattaunawar lafiya\n"
                    "4) Haila / cycle\n"
                    "5) Pharmacy na gaggawa\n"
                    "6) Asibitoci kusa\n"
                    "7) Gaggawa\n"
                    "8) Tuntubi likita\n"
                    "Rubuta 'langue' don canza yare."
                ),
            }.get(lang, "")
            await wa_send_text(to, append_disclaimer(fallback, lang))
            return

        r.raise_for_status()


def ack_for_menu(menu_id: str, lang: str) -> str:
    """
    ACK message for each menu option (single message that both confirms selection and guides next action).
    Keep ASCII-friendly for maximum WhatsApp compatibility.
    """
    if menu_id == MENU_CHAT_MEDICAL:
        return {
            "fr": "✅ Merci d'avoir choisi *Chat medical*.\nAvez-vous une question a me poser dans le cadre de la sante ?",
            "en": "✅ Thank you for choosing *Medical chat*.\nDo you have a health question to ask?",
            "ha": "✅ Na gode da zabar *Tattaunawar lafiya*.\nKana da tambayar lafiya da kake so ka yi?",
        }.get(lang, "")

    if menu_id == MENU_CYCLE:
        return {
            "fr": "✅ Vous avez choisi *Cycle / regles*.\nEcris: 'mes regles ont commence le 12/12' ou 'retard de 5 jours'.",
            "en": "✅ You chose *Cycle / period*.\nTry: 'my period started 12/12' or '5 days late'.",
            "ha": "✅ Ka zabi *Haila / cycle*.\nRubuta: 'haila ta fara 12/12' ko 'jinkiri kwana 5'.",
        }.get(lang, "")

    if menu_id == MENU_PHARM:
        return {
            "fr": "✅ Vous avez choisi *Pharmacies de garde*.\nEcris: 'pharmacie de garde + ville' (ex: Niamey).",
            "en": "✅ You chose *Duty pharmacies*.\nType: 'duty pharmacy + city' (e.g., Niamey).",
            "ha": "✅ Ka zabi *Pharmacy na gaggawa*.\nRubuta: 'pharmacy na gaggawa + gari' (misali: Niamey).",
        }.get(lang, "")

    if menu_id == MENU_CLINIC:
        return {
            "fr": "✅ Vous avez choisi *Cliniques proches*.\nFonctionnalite en cours. Dis-moi ta ville pour commencer.",
            "en": "✅ You chose *Nearby clinics*.\nFeature in progress. Tell me your city to start.",
            "ha": "✅ Ka zabi *Asibitoci kusa*.\nAna aiki a kai. Fadi garinka.",
        }.get(lang, "")

    if menu_id == MENU_URGENCY:
        return {
            "fr": "✅ Vous avez choisi *Urgence*.\nDecris les signes (douleur, fievre, saignement, etc.). Si danger, va au centre de sante.",
            "en": "✅ You chose *Emergency*.\nDescribe symptoms. If severe, go to a health facility immediately.",
            "ha": "✅ Ka zabi *Gaggawa*.\nBayyana alamun. Idan ya tsananta, je asibiti nan da nan.",
        }.get(lang, "")

    if menu_id == MENU_DOCTOR:
        return {
            "fr": "✅ Vous avez choisi *Contacter medecin*.\nFonction en cours. En attendant, decris tes symptomes.",
            "en": "✅ You chose *Contact a doctor*.\nFeature in progress. For now, describe your symptoms.",
            "ha": "✅ Ka zabi *Tuntubi likita*.\nAna shiryawa. A yanzu, bayyana alamunka.",
        }.get(lang, "")

    if menu_id == MENU_LANG:
        return {
            "fr": "✅ Vous avez choisi *Changer de langue*.",
            "en": "✅ You chose *Change language*.",
            "ha": "✅ Ka zabi *Canza yare*.",
        }.get(lang, "")

    return ""


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
    log("INCOMING RAW:", json.dumps(data)[:1200])

    entries = data.get("entry") or []
    if not isinstance(entries, list) or not entries:
        return JSONResponse({"status": "ignored", "reason": "no entry"}, status_code=200)

    try:
        for entry in entries:
            for change in (entry.get("changes") or []):
                value = change.get("value") or {}
                messages = value.get("messages") or []

                if not messages:
                    log("No messages. Keys:", list(value.keys()))
                    continue

                for msg in messages:
                    sender = msg.get("from")
                    if not sender:
                        continue

                    # Anti-spam
                    if not DISABLE_SPAM:
                        if is_spam(sender, last_used):
                            log("Blocked by spam:", sender)
                            continue
                        update_last_used(sender, last_used)

                    # Init states
                    user_language.setdefault(sender, None)
                    cycle_data.setdefault(sender, {})

                    kind, content = extract_incoming(msg)
                    if kind not in {"text", "interactive"}:
                        log("Ignored msg type:", msg.get("type"))
                        continue

                    text_original = normalize(content)
                    if not text_original:
                        continue
                    text_lower = text_original.lower().strip()

                    log("IN:", sender, kind, text_original)

                    # =========================
                    # 1) Language selection (interactive IDs)
                    # =========================
                    if text_original in {LANG_FR, LANG_EN, LANG_HA}:
                        lang = {LANG_FR: "fr", LANG_EN: "en", LANG_HA: "ha"}[text_original]
                        user_language[sender] = lang

                        # Optional ACK for language choice
                        ack = {
                            "fr": "✅ Langue definie : Francais. Voici le menu.",
                            "en": "✅ Language set: English. Here is the menu.",
                            "ha": "✅ An zabi Hausa. Ga menu.",
                        }.get(lang, "")
                        await wa_send_text(sender, append_disclaimer(ack, lang))

                        await wa_send_list_main_menu(sender, lang)
                        continue

                    # =========================
                    # 2) Back to language menu
                    # =========================
                    if text_original == MENU_LANG or text_lower in {"langue", "language", "change langue", "change language"}:
                        lang = get_lang(sender)
                        ack = ack_for_menu(MENU_LANG, lang)
                        # Send ACK first
                        await wa_send_text(sender, append_disclaimer(ack, lang))

                        user_language[sender] = None
                        await wa_send_list_language(sender)
                        continue

                    # =========================
                    # 3) First contact (language not set)
                    # =========================
                    if user_language.get(sender) is None:
                        lang_choice = is_language_text_choice(text_lower)
                        if lang_choice:
                            user_language[sender] = lang_choice

                            ack = {
                                "fr": "✅ Langue definie : Francais. Voici le menu.",
                                "en": "✅ Language set: English. Here is the menu.",
                                "ha": "✅ An zabi Hausa. Ga menu.",
                            }.get(lang_choice, "")
                            await wa_send_text(sender, append_disclaimer(ack, lang_choice))

                            await wa_send_list_main_menu(sender, lang_choice)
                        else:
                            await wa_send_list_language(sender)
                        continue

                    # =========================
                    # 4) Menu routing by IDs + ACK
                    # =========================
                    lang = get_lang(sender)

                    if text_original in {
                        MENU_CHAT_MEDICAL, MENU_CYCLE, MENU_PHARM,
                        MENU_CLINIC, MENU_URGENCY, MENU_DOCTOR
                    }:
                        ack = ack_for_menu(text_original, lang)
                        await wa_send_text(sender, append_disclaimer(ack, lang))
                        continue

                    # =========================
                    # 5) Existing text features
                    # =========================
                    if "pharmacie" in text_lower and "garde" in text_lower:
                        reply = handle_pharmacies(text_original, sender, user_language)
                        await wa_send_text(sender, append_disclaimer(reply, lang))
                        continue

                    if any(w in text_lower for w in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                        reply, updated = handle_cycle(text_original, sender, user_language, cycle_data.get(sender, {}))
                        if isinstance(updated, dict):
                            cycle_data[sender] = updated
                        await wa_send_text(sender, append_disclaimer(reply, lang))
                        continue

                    # Default: Grok
                    reply = await ask_grok(text_original, lang)
                    await wa_send_text(sender, append_disclaimer(reply, lang))

    except httpx.HTTPStatusError as e:
        log("WhatsApp API error:", str(e))
    except Exception as e:
        log("Erreur:", str(e))

    return {"status": "ok"}
