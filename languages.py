WELCOME_MENU_TEXT = {
    "fr": "Bienvenue sur LafiyaBot.\nChoisis une langue pour commencer.",
    "en": "Welcome to LafiyaBot.\nChoose a language to start.",
    "ha": "Barka da zuwa LafiyaBot.\nZabi yare don farawa.",
}

MAIN_MENU_TEXT = {
    "fr": "Menu principal. Choisis une option.",
    "en": "Main menu. Choose an option.",
    "ha": "Babban menu. Zabi abin da kake so.",
}

DISCLAIMER = {
    "fr": "\n\n⚠️ LafiyaBot n’est pas un médecin. En cas d’urgence, allez au centre de santé.",
    "en": "\n\n⚠️ LafiyaBot is not a doctor. In emergencies, go to a health facility.",
    "ha": "\n\n⚠️ LafiyaBot ba likita ba ne. Idan gaggawa, je asibiti.",
}

TEXTS = {
    "menu_title": {
        "fr": "Options",
        "en": "Options",
        "ha": "Zabuka",
    },
    "menu_button": {
        "fr": "Ouvrir le menu",
        "en": "Open menu",
        "ha": "Bude menu",
    },
    "menu_footer": {
        "fr": "Tape aussi 'langue' pour changer.",
        "en": "Type 'language' to change.",
        "ha": "Rubuta 'langue' don canzawa.",
    },

    "menu_cycle": {"fr": "4) Suivi règles / cycle", "en": "4) Period / cycle tracking", "ha": "4) Bin diddigin haila"},
    "menu_cycle_desc": {"fr": "Prochaines règles, retard, fertilité", "en": "Next period, delay, fertility", "ha": "Ranar haila, jinkiri, haihuwa"},
    "menu_pharm": {"fr": "5) Pharmacies de garde", "en": "5) Duty pharmacies", "ha": "5) Pharmacy na gaggawa"},
    "menu_pharm_desc": {"fr": "Trouver pharmacie proche", "en": "Find a nearby pharmacy", "ha": "Nemo kusa"},
    "menu_clinic": {"fr": "6) Cliniques proches", "en": "6) Nearby clinics", "ha": "6) Asibitoci kusa"},
    "menu_clinic_desc": {"fr": "Centres de santé proches", "en": "Nearby health facilities", "ha": "Cibiyoyin lafiya kusa"},
    "menu_urgency": {"fr": "7) Urgence", "en": "7) Emergency", "ha": "7) Gaggawa"},
    "menu_urgency_desc": {"fr": "Signes d’alerte et actions", "en": "Warning signs and actions", "ha": "Alamun hadari da mataki"},
    "menu_doctor": {"fr": "8) Contacter un médecin", "en": "8) Contact a doctor", "ha": "8) Tuntuɓi likita"},
    "menu_doctor_desc": {"fr": "Fonction en préparation", "en": "Feature in progress", "ha": "Ana shirya"},
    "menu_lang": {"fr": "Changer de langue", "en": "Change language", "ha": "Canza yare"},
    "menu_lang_desc": {"fr": "Français / English / Hausa", "en": "French / English / Hausa", "ha": "Faransanci / Turanci / Hausa"},

    "cycle_hint": {
        "fr": "Pour le suivi du cycle, écris par exemple :\n- 'mes règles ont commencé le 12/12'\n- 'retard de 5 jours'\n- 'prochaine période ?'",
        "en": "For cycle tracking, try:\n- 'my period started 12/12'\n- '5 days late'\n- 'next period?'",
        "ha": "Don bin haila, rubuta:\n- 'haila ta fara 12/12'\n- 'na yi jinkiri kwana 5'\n- 'yaushe na gaba?'",
    },
    "pharm_hint": {
        "fr": "Écris : 'pharmacie de garde + ville' (ex: 'pharmacie de garde Niamey').",
        "en": "Type: 'duty pharmacy + city' (e.g., 'duty pharmacy Niamey').",
        "ha": "Rubuta: 'pharmacy na gaggawa + gari' (misali: 'pharmacy na gaggawa Niamey').",
    },
    "clinic_placeholder": {
        "fr": "Cliniques proches : fonctionnalité en cours d’intégration. Dis-moi ta ville pour préparer la recherche.",
        "en": "Nearby clinics: feature in progress. Tell me your city to prepare the search.",
        "ha": "Asibitoci kusa: ana aiki a kai. Fadi garinka.",
    },
    "doctor_placeholder": {
        "fr": "Contact médecin : fonctionnalité en cours (partenaires). En attendant, décris tes symptômes.",
        "en": "Doctor contact: in progress (partners). For now, describe your symptoms.",
        "ha": "Tuntuɓar likita: ana shirya. A yanzu, bayyana alamunka.",
    },
    "urgency_message": {
        "fr": "URGENCE : si douleur thoracique, difficulté à respirer, convulsions, saignement important, perte de conscience, fièvre élevée chez enfant — va immédiatement au centre de santé ou appelle les urgences locales.",
        "en": "EMERGENCY: chest pain, breathing difficulty, seizures, heavy bleeding, fainting, high fever in a child — go immediately to a health facility or call local emergency services.",
        "ha": "GAGGAWA: ciwon kirji, wahalar numfashi, kamu, zubar jini mai yawa, suma, zazzabi mai tsanani ga yaro — je asibiti nan da nan.",
    },
}

def get_text(key: str, lang: str) -> str:
    return TEXTS.get(key, {}).get(lang) or TEXTS.get(key, {}).get("fr") or ""

def set_language(sender: str, lang: str, user_language: dict) -> None:
    user_language[sender] = lang
