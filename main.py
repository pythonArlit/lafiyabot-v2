from fastapi import FastAPI, Request
import httpx
import os
from config import TOKEN, PHONE_NUMBER_ID, GROK_KEY
from languages import WELCOME_MENU, DISCLAIMER, change_language
from features.grok import ask_grok
from features.pharmacies import handle_pharmacies
from features.cycle import handle_cycle
from utils import is_spam, update_last_used

app = FastAPI()

# Mémoire globale
user_language = {}
last_used = {}
cycle_data = {}

@app.get("/webhook")
async def verify(request: Request):
    if request.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(request.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    try:
        for msg in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", []):
            sender = msg["from"]
            text_original = msg["text"]["body"].strip()  # Texte original pour Grok
            text_lower = text_original.lower().strip()   # Version minuscule pour détection

            if is_spam(sender, last_used):
                continue
            update_last_used(sender, last_used)

            # Initialisation si premier contact
            if sender not in user_language:
                user_language[sender] = None

            # === PRIORITÉ 1 : CHOIX DE LANGUE (toujours en premier) ===
            if any(k in text_lower for k in ["1", "français", "francais", "fr", "french"]):
                reply = change_language("1", sender, user_language)
            elif any(k in text_lower for k in ["2", "english", "anglais", "en"]):
                reply = change_language("2", sender, user_language)
            elif any(k in text_lower for k in ["3", "hausa", "ha"]):
                reply = change_language("3", sender, user_language)
            # === RETOUR AU MENU LANGUE ===
            elif text_lower in ["langue", "language", "change langue", "change language"]:
                user_language.pop(sender, None)
                reply = WELCOME_MENU
            # === PREMIER MESSAGE ===
            elif user_language[sender] is None:
                reply = WELCOME_MENU
            # === PHARMACIES DE GARDE ===
            elif "pharmacie" in text_lower and "garde" in text_lower:
                reply = handle_pharmacies(text_original, sender, user_language)
            # === SUIVI DES RÈGLES ===
            elif any(word in text_lower for word in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                reply, cycle_data = handle_cycle(text_original, sender, user_language, cycle_data)
            # === RÉPONSE NORMALE VIA GROK ===
            else:
                langue = user_language.get(sender, "fr")
                reply = await ask_grok(text_original, langue)

            reply += DISCLAIMER.get(user_language.get(sender, "fr"), DISCLAIMER["fr"])

            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "text",
                    "text": {"body": reply}
                }
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status": "ok"}
