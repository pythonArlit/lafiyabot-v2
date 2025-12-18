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

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* for English
🇳🇬 Tapez *3* pour Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

MENU_PRINCIPAL = {
    "fr": """😊 Merci d'avoir choisi le français !

Que voulez-vous faire ?

1. Chat santé (questions générales)
2. Pharmacies de garde
3. Suivi des règles
4. Centres de santé proches
5. Urgence médicale
6. Contact avec un médecin

Tapez le numéro ou posez votre question.""",

    "en": """😊 Thank you for choosing English!

What do you want to do?

1. Health chat
2. On-duty pharmacies
3. Period tracking
4. Nearby health centers
5. Medical emergency
6. Contact a doctor

Type the number or ask your question.""",

    "ha": """😊 Na gode da zaɓin Hausa!

Menene kake so ka yi?

1. Magana game da lafiya
2. Magungunan gadi
3. Bin diddigin haila
4. Asibiti kusa
5. Gaggawa ta lafiya
6. Sadarwa da likita

Rubuta lamba ko tambaya kai tsaye."""
}

async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={"model":"grok-3","messages":[
                    {"role":"system","content":"Ka amsa a harshen Hausa na Kano da kyau da takaice."},
                    {"role":"user","content":text}
                ],"temperature":0.7}
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return "Na ji tambayarka, za mu ba ka amsa nan take."

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

            text_lower = text.lower()

            # === CHOIX DE LANGUE (priorité absolue) ===
            if text_lower in ["1", "français", "francais", "fr"]:
                user_language[sender] = "fr"
                reply = MENU_PRINCIPAL["fr"]
            elif text_lower in ["2", "english", "anglais", "en"]:
                user_language[sender] = "en"
                reply = MENU_PRINCIPAL["en"]
            elif text_lower in ["3", "hausa", "ha"]:
                user_language[sender] = "ha"
                reply = MENU_PRINCIPAL["ha"]
            # === RETOUR AU MENU ===
            elif text_lower in ["menu", "m"]:
                if sender in user_language:
                    reply = MENU_PRINCIPAL[user_language[sender]]
                else:
                    reply = WELCOME_MENU
            # === PREMIER MESSAGE ===
            elif sender not in user_language:
                reply = WELCOME_MENU
            # === RÉPONSE NORMALE ===
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
