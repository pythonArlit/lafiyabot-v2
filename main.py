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
user_in_menu = {}  # Pour savoir si l'utilisateur est dans le menu avancé

# MENU AVANCÉ APRÈS CHOIX DE LANGUE
MENU_PRINCIPAL = {
    "fr": """😊 Merci d’avoir choisi le français !

Choisissez une option :

1. Chat santé (questions générales)
2. Pharmacies de garde
3. Gestion des menstruations
4. Cliniques ou centres de santé proches
5. Urgence médicale
6. Être mis en contact avec un médecin

Tapez le numéro (1 à 6) ou posez votre question directement.""",

    "en": """😊 Thank you for choosing English!

Choose an option:

1. Health chat (general questions)
2. On-duty pharmacies
3. Menstruation management
4. Nearby clinics or health centers
5. Medical emergency
6. Connect with a doctor

Type the number (1 to 6) or ask directly.""",

    "ha": """😊 Na gode da zaɓin Hausa!

Zaɓi zaɓi:

1. Magana game da lafiya
2. Magungunan gadi
3. Bin diddigin haila
4. Asibiti kusa da kai
5. Gaggawa ta lafiya
6. Sadarwa da likita

Rubuta lamba (1 zuwa 6) ko tambaya kai tsaye."""
}

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

            # === CHOIX DE LANGUE ===
            if text.lower() in ["1", "2", "3", "fr", "en", "ha", "menu", "langue", "change"]:
                reply = change_language(text.lower(), sender, user_language)
                user_in_menu[sender] = True  # Active le menu avancé après choix langue

            # === PREMIER MESSAGE ===
            elif sender not in user_language:
                reply = WELCOME_MENU

            # === MENU AVANCÉ (après choix langue) ===
            elif user_in_menu.get(sender, False):
                choix = text.strip()
                langue = user_language.get(sender, "fr")

                if choix == "1":
                    reply = {"fr": "Posez-moi votre question santé !", "en": "Ask me your health question!", "ha": "Tambaye ni tambayar lafiya!"][langue]
                    user_in_menu[sender] = False
                elif choix == "2":
                    reply = handle_pharmacies(text, sender, user_language)
                    user_in_menu[sender] = False
                elif choix == "3":
                    reply, cycle_data = handle_cycle(text, sender, user_language, cycle_data)
                    user_in_menu[sender] = False
                elif choix == "4":
                    reply = {"fr": "Envoyez-moi votre ville pour trouver les centres proches.", "en": "Send me your city to find nearby clinics.", "ha": "Aika mini birnin ka don nemo asibiti kusa."}[langue]
                    user_in_menu[sender] = False
                elif choix == "5":
                    reply = {"fr": "URGENCE : Appelez le 15 (Niger) ou 112.\nDites-moi vos symptômes.", "en": "EMERGENCY: Call 15 (Niger) or 112.\nTell me your symptoms.", "ha": "GAGGAWA: Kira 15 nan take.\nFaɗa mini alamomin."}[langue]
                    user_in_menu[sender] = False
                elif choix == "6":
                    reply = {"fr": "Service en développement. Bientôt disponible !", "en": "Service in development. Coming soon!", "ha": "Sabis na ci gaba. Za a samu nan ba da jimawa ba."}[langue]
                    user_in_menu[sender] = False
                else:
                    reply = MENU_PRINCIPAL.get(langue, MENU_PRINCIPAL["fr"])

            # === FONCTIONNALITÉS PRIORITAIRES (pharmacie + règles) ===
            elif "pharmacie" in text.lower() and "garde" in text.lower():
                reply = handle_pharmacies(text, sender, user_language)
            elif any(word in text.lower() for word in ["règle", "règles", "cycle", "retard", "période", "mens"]):
                reply, cycle_data = handle_cycle(text, sender, user_language, cycle_data)

            # === CHAT NORMAL ===
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
