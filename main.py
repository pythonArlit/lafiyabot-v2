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
        # Ligne corrigée ici !
        for msg in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", []):
            sender = msg["from"]
            text = msg["text"]["body"].strip()

            if is_spam(sender, last_used):
                continue
            update_last_used(sender, last_used)

            # Priorité : pharmacie de garde
            if "pharmacie" in text.lower() and "garde" in text.lower():
                reply = handle_pharmacies(text, sender, user_language)
            # Suivi règles
            elif any(word in text.lower() for word in ["règle", "règles", "cycle", "retard", "période"]):
                reply, cycle_data = handle_cycle(text, sender, user_language, cycle_data)
            # Langue
            elif text.lower() in ["1", "2", "3", "fr", "en", "ha", "menu", "langue", "change"]:
                reply = change_language(text.lower(), sender, user_language)
            # Premier message
            elif sender not in user_language:
                reply = WELCOME_MENU
            # Réponse Grok
            else:
                langue = user_language.get(sender, "fr")
                reply = await ask_grok(text, langue)

            reply += DISCLAIMER.get(user_language.get(sender, "fr"), DISCLAIMER["fr"])

            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product": "whatsapp", "to": sender, "type": "text", "text": {"body": reply}}
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status": "ok"}
