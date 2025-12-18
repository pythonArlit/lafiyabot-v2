from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}
user_language = {}
user_state = {}  # "choix_langue" ou "menu_avance"

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

# Menu de bienvenue (choix langue)
MENU_LANGUE = """Sannu ! Bienvenue ! Welcome ! 😊

Choisissez votre langue :

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* for English
🇳🇬 Tapez *3* pour Hausa"""

# Menu avancé (après choix langue)
MENU_AVANCE = {
    "fr": """😊 Vous avez choisi le français !

Menu principal :

4. Pharmacies de garde
5. Suivi des menstruations
6. Cliniques ou centres de santé proches
7. Urgence médicale
8. Contact avec un médecin

Tapez le numéro (4 à 8) ou posez votre question directement.

Tapez *menu* pour ce menu
Tapez *langue* pour changer de langue""",

    "en": """😊 You have chosen English!

Main menu:

4. On-duty pharmacies
5. Period tracking
6. Nearby clinics or health centers
7. Medical emergency
8. Contact a doctor

Type the number (4 to 8) or ask your question.

Type *menu* for this menu
Type *langue* to change language""",

    "ha": """😊 Ka zaɓi Hausa!

Menu na farko:

4. Magungunan gadi
5. Bin diddigin haila
6. Asibiti ko cibiyoyin lafiya kusa
7. Gaggawa ta lafiya
8. Sadarwa da likita

Rubuta lambar (4 zuwa 8) ko tambaya kai tsaye.

Rubuta *menu* don wannan menu
Rubuta *langue* don canza harshe"""
}

async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={"model":"grok-3","messages":[
                    {"role":"system","content":"Réponds en français, anglais ou hausa selon le choix de l'utilisateur."},
                    {"role":"user","content":text}
                ],"temperature":0.7}
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return "Je n’ai pas pu répondre pour le moment."

@app.get("/webhook")
async def verify(r: Request):
    if r.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(r.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def receive(r: Request):
    data = await r.json()
    try:
        for msg in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", []):
            sender = msg["from"]
            text = msg["text"]["body"].strip()

            # Anti-spam
            now = time.time()
            if sender not in last_used:
                last_used[sender] = 0
            if now - last_used[sender] < 25:
                continue
            last_used[sender] = now

            text_lower = text.lower()

            # === PREMIER MESSAGE OU RETOUR AU CHOIX LANGUE ===
            if text_lower in ["langue", "language"] or sender not in user_language:
                user_language.pop(sender, None)
                user_state[sender] = "choix_langue"
                reply = MENU_LANGUE

            # === CHOIX DE LANGUE ===
            elif user_state.get(sender) == "choix_langue":
                if text_lower in ["1", "français", "francais", "fr"]:
                    user_language[sender] = "fr"
                    reply = MENU_AVANCE["fr"]
                    user_state[sender] = "menu_avance"
                elif text_lower in ["2", "english", "anglais", "en"]:
                    user_language[sender] = "en"
                    reply = MENU_AVANCE["en"]
                    user_state[sender] = "menu_avance"
                elif text_lower in ["3", "hausa", "ha"]:
                    user_language[sender] = "ha"
                    reply = MENU_AVANCE["ha"]
                    user_state[sender] = "menu_avance"
                else:
                    reply = "Choisissez 1, 2 ou 3 svp / Zaɓi 1, 2 ko 3 / Please choose 1, 2 or 3"

            # === RETOUR AU MENU AVANCÉ ===
            elif text_lower in ["menu"]:
                if sender in user_language:
                    reply = MENU_AVANCE[user_language[sender]]
                    user_state[sender] = "menu_avance"
                else:
                    reply = MENU_LANGUE

            # === GESTION DU MENU AVANCÉ ===
            elif user_state.get(sender) == "menu_avance":
                choix = text.strip()
                if choix in ["4", "5", "6", "7", "8"]:
                    reply = f"Option {choix} sélectionnée – fonctionnalité en développement. Bientôt disponible !"
                else:
                    reply = await ask_grok(text)

            # === CHAT NORMAL (si pas dans le menu) ===
            else:
                reply = await ask_grok(text)

            reply += DISCLAIMER

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
