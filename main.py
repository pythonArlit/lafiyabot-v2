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
user_in_menu = {}  # Pour savoir si l'utilisateur est dans le menu avancé

# Disclaimer
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

# Menu de bienvenue
WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* for English
🇳🇬 Tapez *3* pour Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

# Menu avancé après choix de langue
MENU_PRINCIPAL = {
    "fr": """😊 Merci d'avoir choisi le français !

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
4. Asibiti kusa
5. Gaggawa ta lafiya
6. Sadarwa da likita

Rubuta lamba (1 zuwa 6) ko tambaya kai tsaye."""
}

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
        # Ligne corrigée : parenthèses équilibrées
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

            # === CHOIX DE LANGUE (priorité maximale) ===
            if text_lower in ["1", "français", "francais", "fr", "french"]:
                user_language[sender] = "fr"
                reply = MENU_PRINCIPAL["fr"]
                user_in_menu[sender] = True
            elif text_lower in ["2", "english", "anglais", "en"]:
                user_language[sender] = "en"
                reply = MENU_PRINCIPAL["en"]
                user_in_menu[sender] = True
            elif text_lower in ["3", "hausa", "ha"]:
                user_language[sender] = "ha"
                reply = MENU_PRINCIPAL["ha"]
                user_in_menu[sender] = True
            # === RETOUR AU MENU ===
            elif text_lower in ["menu", "m"]:
                reply = MENU_PRINCIPAL.get(user_language.get(sender, "fr"), MENU_PRINCIPAL["fr"])
                user_in_menu[sender] = True
            # === PREMIER MESSAGE ===
            elif sender not in user_language:
                reply = WELCOME_MENU
            # === MENU AVANCÉ ===
            elif user_in_menu.get(sender, False):
                choix = text.strip()
                if choix == "1":
                    reply = "Posez-moi votre question santé !"
                    user_in_menu[sender] = False
                elif choix == "2":
                    reply = "Fonctionnalité pharmacies de garde en cours de développement."
                    user_in_menu[sender] = False
                elif choix == "3":
                    reply = "Fonctionnalité suivi menstruations en cours de développement."
                    user_in_menu[sender] = False
                elif choix == "4":
                    reply = "Envoyez-moi votre ville pour trouver les centres proches."
                    user_in_menu[sender] = False
                elif choix == "5":
                    reply = "URGENCE : Appelez le 15 (Niger) ou 112 immédiatement.\nDites-moi vos symptômes pour des conseils."
                    user_in_menu[sender] = False
                elif choix == "6":
                    reply = "Service en développement. Bientôt disponible !"
                    user_in_menu[sender] = False
                else:
                    reply = "Choisissez un numéro de 1 à 6 ou tapez 'menu'."
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
