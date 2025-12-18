from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}        # Anti-spam
user_language = {}    # Langue choisie
user_in_menu = {}     # État du menu avancé

# Disclaimer
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

# Menu de bienvenue (choix langue)
MENU_LANGUE = """Sannu ! Bienvenue ! Welcome ! 😊

Choisissez votre langue :

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* for English
🇳🇬 Tapez *3* pour Hausa

(ou tapez 'langue' pour changer à tout moment)"""

# Menu avancé après choix langue
MENU_AVANCE = {
    "fr": """😊 Vous avez choisi le français !

Menu principal :

4. Pharmacies de garde
5. Suivi des menstruations
6. Cliniques ou centres de santé proches
7. Urgence médicale
8. Contact avec un médecin

Tapez le numéro (4 à 8) ou posez votre question directement.

Tapez *menu* pour revenir ici
Tapez *langue* pour changer de langue""",

    "en": """😊 You have chosen English!

Main menu:

4. On-duty pharmacies
5. Period tracking
6. Nearby clinics or health centers
7. Medical emergency
8. Contact a doctor

Type the number (4 to 8) or ask your question.

Type *menu* to return here
Type *langue* to change language""",

    "ha": """😊 Ka zaɓi Hausa!

Menu na farko:

4. Magungunan gadi
5. Bin diddigin haila
6. Asibiti ko cibiyoyin lafiya kusa
7. Gaggawa ta lafiya
8. Sadarwa da likita

Rubuta lambar (4 zuwa 8) ko tambaya kai tsaye.

Rubuta *menu* don komawa nan
Rubuta *langue* don canza harshe"""
}

# Réponse Grok
async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "Réponds en français, anglais ou hausa selon le choix de l'utilisateur. Sois clair et poli."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.7
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print("Erreur Grok:", e)
            return "Je n’ai pas pu répondre pour le moment. Réessayez."

@app.get("/webhook")
async def verify(r: Request):
    if r.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(r.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def receive(r: Request):
    data = await r.json()
    print("Message →", data)
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

            text_clean = text.strip().lower()

            # === RETOUR AU CHOIX LANGUE ===
            if text_clean in ["langue", "language"]:
                user_language.pop(sender, None)
                user_in_menu[sender] = False
                reply = MENU_LANGUE

            # === CHOIX DE LANGUE ===
            elif text_clean in ["1", "français", "francais", "fr", "french"]:
                user_language[sender] = "fr"
                reply = MENU_AVANCE["fr"]
                user_in_menu[sender] = True
            elif text_clean in ["2", "english", "anglais", "en"]:
                user_language[sender] = "en"
                reply = MENU_AVANCE["en"]
                user_in_menu[sender] = True
            elif text_clean in ["3", "hausa", "ha"]:
                user_language[sender] = "ha"
                reply = MENU_AVANCE["ha"]
                user_in_menu[sender] = True

            # === RETOUR AU MENU AVANCÉ ===
            elif text_clean in ["menu", "m"]:
                if sender in user_language:
                    reply = MENU_AVANCE[user_language[sender]]
                    user_in_menu[sender] = True
                else:
                    reply = MENU_LANGUE

            # === PREMIER MESSAGE ===
            elif sender not in user_language:
                reply = MENU_LANGUE

            # === MENU AVANCÉ (options 4 à 8) ===
            elif user_in_menu.get(sender, False):
                choix = text.strip()
                if choix in ["4", "5", "6", "7", "8"]:
                    reply = f"Option {choix} sélectionnée – fonctionnalité en développement. Bientôt disponible !"
                    user_in_menu[sender] = False  # sort du menu pour chat libre
                else:
                    reply = await ask_grok(text)

            # === CHAT NORMAL ===
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
