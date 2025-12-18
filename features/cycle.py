# features/cycle.py
from datetime import datetime, timedelta

def handle_cycle(text: str, sender: str, user_language: dict, data: dict):
    lang = user_language.get(sender, "fr")
    today = datetime.today().date()

    if "retard" in text.lower():
        msg = {
            "fr": "Un retard peut avoir plusieurs causes. Consulte un centre de santé si cela persiste.",
            "en": "A delay can have many causes. See a health professional if it continues.",
            "ha": "Jinkiri na iya samun dalilai da dama. Idan ya ci gaba, je asibiti.",
        }
        return msg[lang], data

    next_cycle = today + timedelta(days=28)
    msg = {
        "fr": f"📅 Prochain cycle estimé : {next_cycle.strftime('%d/%m/%Y')}",
        "en": f"📅 Estimated next period: {next_cycle.strftime('%d/%m/%Y')}",
        "ha": f"📅 Ana tsammanin haila ta gaba: {next_cycle.strftime('%d/%m/%Y')}",
    }

    data["last_check"] = str(today)
    return msg[lang], data
