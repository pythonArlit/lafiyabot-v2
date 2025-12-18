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
            text = msg["text"]["body"].strip()

            if is_spam(sender, last_used):
                continue
            update_last_used(sender, last_used)

            text_lower = text.lower().strip()

            # === PRIORITÉ 1 : CHOIX DE LANGUE (toujours en premier) ===
            if text_lower in ["1", "2", "3", "fr", "français", "francais", "en", "english", "anglais", "ha", "hausa"]:
                reply = change_language(text_lower, sender, user_language)
            # === RETOUR AU MENU LANGUE ===
            elif text_lower in ["langue", "language", "change langue"]:
                user_language.pop(sender, None)
                reply = WELCOME_MENU
            # === PREMIER MESSAGE ===
            elif sender not in user_language:
                reply = WELCOME_MENU
            # === PHARMACIES DE GARDE ===
            elif "pharmacie" in text_lower and "garde" in text_lower:
                reply = handle_pharmacies(text, sender, user_language)
            # === SUIVI DES RÈGLES ===
            elif any(word in text_lower for word in ["règle", "règles", "cycle", "retard", "période", "mens", "period"]):
                reply, cycle_data = handle_cycle(text, sender, user_language, cycle_data)
            # === RÉPONSE NORMALE ===
            else:
                langue = user_language.get(sender, "fr")
                reply = await ask_grok(text, langue)

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
