# languages.py

WELCOME_MENU = {
    "fr": "Bienvenue sur *LafiyaBot* 🇳🇪\n\nChoisis une langue :\n1️⃣ Français\n2️⃣ English\n3️⃣ Hausa",
    "en": "Welcome to *LafiyaBot* 🇳🇬\n\nChoose a language:\n1️⃣ French\n2️⃣ English\n3️⃣ Hausa",
    "ha": "Barka da zuwa *LafiyaBot* 🇳🇪\n\nZabi yare:\n1️⃣ Faransanci\n2️⃣ Turanci\n3️⃣ Hausa",
}

DISCLAIMER = {
    "fr": "\n\n⚠️ LafiyaBot n’est pas un médecin.",
    "en": "\n\n⚠️ LafiyaBot is not a doctor.",
    "ha": "\n\n⚠️ LafiyaBot ba likita ba ne.",
}

def change_language(choice: str, sender: str, user_language: dict) -> str:
    if choice == "1":
        user_language[sender] = "fr"
        return "✅ Langue définie : Français"
    if choice == "2":
        user_language[sender] = "en"
        return "✅ Language set: English"
    if choice == "3":
        user_language[sender] = "ha"
        return "✅ An zabi Hausa"
    return WELCOME_MENU["fr"]
