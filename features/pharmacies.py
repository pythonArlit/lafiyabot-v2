# features/pharmacies.py

PHARMACIES_DE_GARDE = [
    {"ville": "niamey", "quartier": "Plateau", "nom": "Pharmacie du Plateau", "tel": "+227 90 12 34 56"},
    {"ville": "niamey", "quartier": "Lazaret", "nom": "Pharmacie Lazaret", "tel": "+227 96 55 44 33"},
    {"ville": "niamey", "quartier": "Karo", "nom": "Pharmacie Karo", "tel": "+227 90 99 88 77"},
    {"ville": "kano", "quartier": "Sabon Gari", "nom": "Alheri Pharmacy", "tel": "+234 803 123 4567"},
    {"ville": "kano", "quartier": "Kofar Mata", "nom": "Kofar Pharmacy", "tel": "+234 801 234 5678"},
    {"ville": "zinder", "quartier": "Birni", "nom": "Pharmacie Centrale Zinder", "tel": "+227 92 11 22 33"},
    {"ville": "maradi", "quartier": "Centre Ville", "nom": "Pharmacie El Hadj", "tel": "+227 91 00 11 22"},
    # Ajoute autant que tu veux ici – facile à mettre à jour !
]

def handle_pharmacies(text: str, sender: str, user_language: dict) -> str:
    langue = user_language.get(sender, "fr")
    text_lower = text.lower()

    # Extraction de la ville (priorité)
    ville = "niamey"  # défaut
    for v in ["niamey", "kano", "zinder", "maradi", "tahoua", "agadez", "diffa", "dosso", "tillaberi"]:
        if v in text_lower:
            ville = v
            break

    # Filtre les pharmacies de la ville
    resultats = [p for p in PHARMACIES_DE_GARDE if ville in p["ville"].lower()]

    if not resultats:
        return {
            "fr": f"Aucune pharmacie de garde trouvée pour {ville.title()}. Essayez une autre ville.",
            "en": f"No on-duty pharmacies found for {ville.title()}. Try another city.",
            "ha": f"Ba a sami magunguna na gadi ba a {ville.title()}. Gwada wani birni."
        }[langue]

    # Formatage par langue
    if langue == "fr":
        reply = f"Pharmacies de garde à {ville.title()} ce soir :\n\n"
        for p in resultats:
            reply += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']}\n\n"
    elif langue == "en":
        reply = f"On-duty pharmacies in {ville.title()} tonight:\n\n"
        for p in resultats:
            reply += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']}\n\n"
    else:  # Hausa
        reply = f"Magungunan gadi a {ville.title()} yau da daddare :\n\n"
        for p in resultats:
            reply += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']}\n\n"

    reply += "Appelle directement en cas d'urgence."
    return reply
