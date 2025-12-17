# features/cycle.py
# Module de suivi des règles (mensurations) pour LafiyaBot

from datetime import datetime

# Stockage en mémoire : { sender_id: {"derniere_regle": "YYYY-MM-DD", "cycle_moyen": 28} }
cycle_data = {}

def handle_cycle(text: str, sender: str, user_language: dict, cycle_data_dict: dict) -> tuple:
    """
    Gère le suivi des règles.
    Retourne (reply: str, cycle_data_dict mis à jour)
    """
    langue = user_language.get(sender, "fr")
    text_lower = text.lower()

    # Si l'utilisateur demande le suivi ou le statut
    if sender in cycle_data_dict:
        info = cycle_data_dict[sender]
        derniere_str = info["derniere_regle"]
        cycle_moyen = info.get("cycle_moyen", 28)

        try:
            derniere = datetime.strptime(derniere_str, "%Y-%m-%d")
            aujourd_hui = datetime.now()
            jours_ecoules = (aujourd_hui - derniere).days
            jours_restants = cycle_moyen - (jours_ecoules % cycle_moyen)
            if jours_restants <= 0:
                jours_restants += cycle_moyen

            fertile = "OUI" if 10 <= (jours_ecoules % cycle_moyen) <= 16 else "NON"
            retard = "OUI" if jours_ecoules > cycle_moyen else "NON"

            if langue == "fr":
                reply = f"Votre suivi de cycle :\n\n"
                reply += f"• Dernières règles : {derniere.strftime('%d %B %Y')}\n"
                reply += f"• Jour {jours_ecoules} du cycle\n"
                reply += f"• Prochaines règles prévues dans {jours_restants} jours\n"
                reply += f"• Période fertile : {fertile}\n"
                reply += f"• Retard : {retard}\n\n"
                reply += "Tapez 'règles' pour rafraîchir ou 'nouvelle date' pour mettre à jour."
            elif langue == "en":
                reply = f"Your cycle tracking:\n\n"
                reply += f"• Last period: {derniere.strftime('%B %d, %Y')}\n"
                reply += f"• Day {jours_ecoules} of cycle\n"
                reply += f"• Next period in {jours_restants} days\n"
                reply += f"• Fertile period: {fertile}\n"
                reply += f"• Delay: {retard}\n\n"
                reply += "Type 'period' to refresh or 'new date' to update."
            else:  # Hausa
                reply = f"Bin diddigin haila :\n\n"
                reply += f"• Haila na ƙarshe: {derniere.strftime('%d %B %Y')}\n"
                reply += f"• Rana {jours_ecoules} na cycle\n"
                reply += f"• Haila na gaba a cikin kwana {jours_restants}\n"
                reply += f"• Lokacin haihuwa: {fertile}\n"
                reply += f"• Jinkiri: {retard}\n\n"
                reply += "Rubuta 'règles' don sabunta ko 'sabo kwana' don canza."
            return reply, cycle_data_dict
        except:
            pass

    # Demande de nouvelle date ou première utilisation
    if "date" in text_lower or "kwana" in text_lower or "jour" in text_lower or sender not in cycle_data_dict:
        if langue == "fr":
            reply = "À quelle date avez-vous eu vos dernières règles ?\nFormat : 5 décembre 2025 ou 05-12-2025"
        elif langue == "en":
            reply = "When was your last period?\nFormat: December 5, 2025 or 12-05-2025"
        else:
            reply = "A wace rana ka samu haila na ƙarshe?\nMisali: 5 Disamba 2025 ko 05-12-2025"
        # On marque que le bot attend la date
        cycle_data_dict[sender] = {"attente_date": True}
        return reply, cycle_data_dict

    # Enregistrement de la date
    if cycle_data_dict.get(sender, {}).get("attente_date"):
        # On accepte des formats simples – pour simplifier on prend la texte brut (tu peux améliorer avec dateparser plus tard)
        cycle_data_dict[sender] = {"derniere_regle": text.strip(), "cycle_moyen": 28, "attente_date": False}
        if langue == "fr":
            reply = "Merci ! Je suis maintenant votre cycle.\nTapez « règles » pour voir votre statut à tout moment."
        elif langue == "en":
            reply = "Thank you! I’m now tracking your cycle.\nType « period » anytime to see your status."
        else:
            reply = "Na gode! Yanzu ina bin diddigin haila.\nRubuta « règles » don ganin halin ki a kowane lokaci."
        return reply, cycle_data_dict

    # Fallback
    return "Tapez « règles » pour commencer le suivi.", cycle_data_dict
