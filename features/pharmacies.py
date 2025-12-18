# features/pharmacies.py

def handle_pharmacies(text: str, sender: str, user_language: dict) -> str:
    lang = user_language.get(sender, "fr")

    if lang == "en":
        return "🟢 Duty pharmacy:\nPharmacie Centrale – Open 24/7"
    if lang == "ha":
        return "🟢 Pharmacy na gaggawa:\nPharmacie Centrale – A bude koyaushe"
    return "🟢 Pharmacie de garde :\nPharmacie Centrale – Ouverte 24h/24"
