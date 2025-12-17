WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* for English
🇳🇬 Tapez *3* pour Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

DISCLAIMER = {
    "fr": "\n\nLafiyaBot n’est pas un médecin · Information générale uniquement.",
    "en": "\n\nLafiyaBot is not a doctor · General information only.",
    "ha": "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai."
}

def change_language(text: str, sender: str, user_language: dict) -> str:
    if text in ["1", "fr", "français"]:
        user_language[sender] = "fr"
        return "🇫🇷 Français activé ! Comment puis-je vous aider ?"
    elif text in ["2", "en", "english"]:
        user_language[sender] = "en"
        return "🇬🇧 English activated! How can I help you?"
    elif text in ["3", "ha", "hausa"]:
        user_language[sender] = "ha"
        return "🇳🇬 Sannu! Yanzu zan yi magana da Hausa na Kano."
    return WELCOME_MENU
