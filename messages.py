# messages.py
from utils import format_phone_display


MSG_AIDE = """⚡ *TontineBot — Commandes*

- *CREER* — Créer une tontine
- *REJOINDRE CODE* — Rejoindre une tontine
  Ex: REJOINDRE TONT-4X7K
- *TONTINE* — Voir le statut de ta tontine
  (ou *TONTINE CODE* si tu es dans plusieurs tontines)
- *MEMBRES* — Voir les membres et l'ordre
- *HISTORIQUE* — Voir les tours passés
- *AIDE* — Afficher ce message

_TontineBot — La tontine de confiance_ ⚡"""

MSG_COMMANDE_INCONNUE = """❓ Commande non reconnue.

Tape *AIDE* pour voir toutes les commandes disponibles."""

MSG_CREER_NOM = """⚡ *Création d'une tontine*

Quel est le *nom* de ta tontine ?
(Entre 2 et 30 caractères — Ex: MaFamille, TontineAmis)"""

MSG_CREER_MONTANT = """✅ Nom enregistré !

*Quel montant* chaque membre doit payer par tour ?
(En satoshis — minimum 100 — Ex: 5000, 10000)"""

MSG_CREER_MEMBRES = """✅ Montant enregistré !

*Combien de membres* dans cette tontine ?
(Entre 2 et 10 membres)"""

MSG_CREER_FREQUENCE = """✅ Membres enregistrés !

*À quelle fréquence* se font les tours ?

Réponds avec :
- *DAILY* — Chaque jour
- *WEEKLY* — Chaque semaine
- *MONTHLY* — Chaque mois"""

MSG_CREER_JOUR = """✅ Fréquence enregistrée !

*Quel jour de la semaine ?*

Réponds avec :
LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI, SAMEDI ou DIMANCHE"""

MSG_CREER_HEURE = """✅ Jour enregistré !

*À quelle heure* doit démarrer chaque tour ?
(Format HH:MM — Ex: 08:00, 18:30)"""

MSG_CREER_WALLET = """✅ Heure enregistrée !

*Quel est ton wallet Lightning ?*
(Ex: tonnom@cake.cash ou lnbc...)"""


def msg_tontine_creee(name, code, amount_sats, max_members, freq_txt, jour_txt, schedule_time):
    return f"""🎉 *Tontine créée avec succès !*

- 📛 Nom : *{name}*
- 🔑 Code : *{code}*
- ⚡ Montant : *{amount_sats} sats* par tour
- 👥 Membres : *1/{max_members}*
- 🔁 Fréquence : *{freq_txt}*
- 📅 Jour : *{jour_txt}*
- ⏰ Heure : *{schedule_time}*

Partage ce code à tes membres :
👉 {code}

Ils tapent : *REJOINDRE {code}*

La tontine démarre automatiquement quand tous les membres sont inscrits !"""


def msg_membre_rejoint(name, current_count, max_members):
    if current_count < max_members:
        return f"""✅ *Tu as rejoint {name} !*

👥 Membres : *{current_count}/{max_members}*

En attente des autres membres...
La tontine démarre automatiquement quand tout le monde est inscrit."""
    else:
        return f"""✅ *Tu as rejoint {name} !*

👥 Membres : *{current_count}/{max_members}* — Complet !

La tontine va démarrer dans quelques secondes... ⚡"""


def msg_tontine_lancee(name, nb_members, amount_sats, ordre_perso, freq_txt, jour_txt, schedule_time):
    return f"""🚀 *{name} est lancée !*

👥 {nb_members} membres — {amount_sats} sats par tour
🔁 {freq_txt} — {jour_txt} à {schedule_time}

*Ordre des bénéficiaires :*
{ordre_perso}

Le premier tour démarre à l'heure programmée.
Tu recevras une invoice Lightning à payer. ⚡"""


def msg_invoice_tour(name, round_number, total_rounds, amount_sats, invoice, beneficiary_is_you):
    benef_txt = "toi ⭐" if beneficiary_is_you else f"tour {round_number}"
    return f"""⏰ *Tour {round_number}/{total_rounds} — {name}*

💰 Envoie *{amount_sats} sats* à cette adresse Lightning :

{invoice}

Scanne ou copie cette invoice depuis ton wallet.

🎯 Bénéficiaire de ce tour : *{benef_txt}*
⏳ Paie dès que possible pour ne pas bloquer la tontine."""


def msg_paiement_recu_perso(name, round_number, paid_count, total):
    return f"""✅ *Paiement reçu !*

Tontine *{name}* — Tour {round_number}
Progression : *{paid_count}/{total}* membres ont payé

{'🎉 Tout le monde a payé !' if paid_count == total else f'En attente de {total - paid_count} membre(s)...'}"""


def msg_paiement_recu_autres(name, round_number, paid_count, total, payer_num):
    num_court = format_phone_display(payer_num)
    return f"""✅ *{num_court} a payé* — {name} Tour {round_number}

Progression : *{paid_count}/{total}* membres ont payé
{'🎉 Tout le monde a payé !' if paid_count == total else f'En attente de {total - paid_count} membre(s)...'}"""


def msg_rappel_paiement(name, round_number, amount_sats, invoice):
    return f"""⚠️ *Rappel — {name} Tour {round_number}*

La tontine attend ton paiement !

💰 Envoie *{amount_sats} sats* :

{invoice}

Sans ton paiement, personne ne peut avancer."""


def msg_round_complet(name, round_number, total_rounds):
    if round_number < total_rounds:
        return f"""🎉 *Tour {round_number} complet !*

Tout le monde a payé pour *{name}*.

➡️ Prochain tour : *Tour {round_number + 1}/{total_rounds}*
Il démarre à l'heure programmée."""
    else:
        return f"""🎉 *Dernier tour complet !*

Tout le monde a payé pour *{name}*.

Distribution des fonds en cours... ⚡"""


def msg_distribution(name, amount_sats, nb_members):
    total = amount_sats * nb_members
    return f"""💸 *Distribution finale — {name}*

Chaque membre reçoit *{total} sats*
({nb_members} tours x {amount_sats} sats)

Envoi en cours sur vos wallets Lightning... ⚡"""


def msg_payout_recu(name, amount_sats, nb_members):
    total = amount_sats * nb_members
    return f"""⚡ *Tu as reçu {total} sats !*

Tontine *{name}* terminée avec succès.

- 💰 Montant reçu : *{total} sats*
- 🔄 Tours complétés : *{nb_members}*

Merci d'avoir utilisé TontineBot ! ⚡"""


def msg_tontine_terminee(name):
    return f"""✅ *Tontine {name} terminée !*

Tout le monde a été payé avec succès.

Tape *CREER* pour démarrer une nouvelle tontine."""


def msg_statut_waiting(name, code, current_count, max_members, amount_sats, freq_txt, jour_txt, schedule_time):
    return f"""📊 *Statut — {name}*

- 🔑 Code : *{code}*
- ⚡ Montant : *{amount_sats} sats/tour*
- 👥 Membres : *{current_count}/{max_members}*
- 🔁 Fréquence : *{freq_txt}*
- 📅 Jour : *{jour_txt}*
- ⏰ Heure : *{schedule_time}*
- 🕐 Statut : *En attente de membres*

Partage le code *{code}* pour inviter les autres !"""


def msg_statut_active(name, round_number, total_rounds, beneficiary_number, is_beneficiary, paid_count, total, my_status):
    benef = "toi ⭐" if is_beneficiary else format_phone_display(beneficiary_number)
    mon_statut = "✅ Payé" if my_status == "paid" else "⏳ En attente"

    return f"""📊 *Statut — {name}*

- 🔄 Tour : *{round_number}/{total_rounds}*
- 🎯 Bénéficiaire : *{benef}*
- 💳 Paiements : *{paid_count}/{total}*
- 👤 Mon statut : *{mon_statut}*"""


def msg_liste_membres(name, members, from_number):
    lignes = []
    for m in members:
        marker = " ⭐ (toi)" if m["whatsapp_number"] == from_number else ""
        lignes.append(f"  Tour {m['turn_order']} → {format_phone_display(m['whatsapp_number'])}{marker}")
    liste = "\n".join(lignes)
    return f"""👥 *Membres — {name}*

{liste}

_L'ordre = ordre d'inscription = ordre des bénéficiaires_"""


def msg_historique(name, rounds, amount_sats):
    if not rounds:
        return f"📜 *Historique — {name}*\n\nAucun tour encore complété."

    lignes = []
    for r in rounds:
        statut = "✅" if r["status"] == "completed" else "🔄" if r["status"] == "active" else "⏳"
        lignes.append(f"  {statut} Tour {r['round_number']} — {r['status']}")

    liste = "\n".join(lignes)
    return f"""📜 *Historique — {name}*

{liste}

⚡ Montant par tour : {amount_sats} sats"""
