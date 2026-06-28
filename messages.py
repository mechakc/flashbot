# messages.py

# --- Inscription ---

MSG_BIENVENUE = """⚡ *Bienvenue sur FlashBot DCA !*

Je suis ton assistant d'épargne Bitcoin automatique.

Je vais t'aider à acheter des sats régulièrement via MTN MoMo — sans effort.

Pour commencer, j'ai besoin de quelques infos.

*Quel est ton numéro MTN MoMo ?*
(Ex: 2250701234567 — avec l'indicatif pays)"""

MSG_DEMANDE_WALLET = """✅ Numéro MoMo enregistré !

*Quelle est ton adresse wallet Lightning ?*
(Ex: ton_nom@bitcoin.lightning ou une adresse LNURL)

Si tu n'en as pas encore, crée-en une gratuitement sur *Wallet of Satoshi* ou *Phoenix*."""

MSG_DEMANDE_MONTANT = """✅ Wallet enregistré !

*Quel montant veux-tu investir à chaque cycle ?*
(Minimum : 100 FCFA — Ex: 500, 1000, 2000)

Réponds juste avec le montant en chiffres."""

MSG_DEMANDE_FREQUENCE = """✅ Montant enregistré !

*À quelle fréquence veux-tu acheter des sats ?*

Réponds avec :
- *DAILY* — Chaque jour
- *WEEKLY* — Chaque semaine  
- *MONTHLY* — Chaque mois"""

MSG_DEMANDE_HEURE = """✅ Fréquence enregistrée !

*À quelle heure veux-tu recevoir ton rappel ?*
(Ex: 08:00, 12:30, 20:00 — format HH:MM)"""

MSG_DEMANDE_JOUR = """✅ Heure enregistrée !

*Quel jour de la semaine ?*

Réponds avec :
- *LUNDI*
- *MARDI*
- *MERCREDI*
- *JEUDI*
- *VENDREDI*
- *SAMEDI*
- *DIMANCHE*"""

def msg_confirmation_inscription(user):
    jours = {
        "monday": "lundi", "tuesday": "mardi", "wednesday": "mercredi",
        "thursday": "jeudi", "friday": "vendredi", "saturday": "samedi",
        "sunday": "dimanche"
    }
    frequences = {"daily": "chaque jour", "weekly": "chaque semaine", "monthly": "chaque mois"}
    jour = jours.get(user["schedule_day"], user["schedule_day"])
    freq = frequences.get(user["frequency"], user["frequency"])

    return f"""🎉 *Configuration terminée !*

Voici ton profil DCA :
- 💰 Montant : *{user["dca_amount_fcfa"]} FCFA*
- 🔁 Fréquence : *{freq}*
- 📅 Jour : *{jour}*
- ⏰ Heure : *{user["schedule_time"]}*
- ⚡ Wallet : `{user["lightning_wallet"]}`

À chaque cycle, je t'enverrai un rappel. Tu réponds *STACK* et je m'occupe du reste !

_Tape AIDE pour voir toutes les commandes._"""

# --- Cycle DCA ---

def msg_rappel_dca(amount_fcfa):
    return f"""⏰ *C'est l'heure de ton DCA !*

Tape *STACK* pour acheter *{amount_fcfa} FCFA* de sats maintenant.

_(Tu as 30 minutes pour confirmer)_"""

def msg_paiement_envoye(amount_fcfa):
    return f"""📲 *Demande de paiement envoyée !*

Vérifie ton téléphone — tu devrais recevoir une notification MTN MoMo pour *{amount_fcfa} FCFA*.

Entre ton code PIN pour valider. J'attends la confirmation... ⏳"""

def msg_achat_reussi(sats_received, total_sats, amount_fcfa):
    return f"""✅ *Achat réussi !*

- 💸 Payé : *{amount_fcfa} FCFA*
- ⚡ Reçu : *{sats_received} sats*
- 🏦 Total stacké : *{total_sats} sats*

Les sats sont sur ton wallet. Continue comme ça ! 🚀"""

# --- Erreurs paiement ---

def msg_paiement_echoue(amount_fcfa):
    return f"""❌ *Paiement échoué*

Ton paiement de *{amount_fcfa} FCFA* n'a pas pu être traité.

Causes possibles :
- Solde MoMo insuffisant
- PIN incorrect ou délai dépassé

Tape *STACK* pour réessayer ou *PAUSE* pour suspendre ton DCA."""

MSG_TIMEOUT_CONFIRMATION = """⏰ *Temps écoulé*

Tu n'as pas répondu à temps pour ce cycle.

Pas de souci — ton prochain rappel arrivera normalement. 
Tape *STACK* si tu veux acheter maintenant quand même."""

# --- Commandes ---

def msg_solde(total_sats, total_fcfa, total_transactions):
    return f"""📊 *Ton bilan FlashBot*

- ⚡ Total sats : *{total_sats} sats*
- 💰 Total investi : *{total_fcfa} FCFA*
- 🔄 Achats effectués : *{total_transactions}*

_Continue à stacker, chaque sat compte !_ ⚡"""

MSG_PAUSE = """⏸ *DCA suspendu*

Tu ne recevras plus de rappels jusqu'à ce que tu tapes *REPRENDRE*.

Tes sats et ton historique sont sauvegardés."""

MSG_REPRENDRE = """▶️ *DCA réactivé !*

Tes rappels automatiques reprennent normalement.
Prêt à stacker des sats ! ⚡"""

MSG_AIDE = """ℹ️ *Commandes FlashBot*

- *DEMARRER* — Créer ou reconfigurer ton profil
- *STACK* — Confirmer un achat DCA
- *SOLDE* — Voir tes sats accumulés
- *PAUSE* — Suspendre les rappels
- *REPRENDRE* — Réactiver les rappels
- *MODIFIER* — Changer montant ou fréquence
- *AIDE* — Afficher ce message
- *PROFIL* — Voir ta configuration actuelle

_Des questions ? Contacte l'équipe FlashBot._ ⚡"""

MSG_COMMANDE_INCONNUE = """❓ Je n'ai pas compris cette commande.

Tape *AIDE* pour voir toutes les commandes disponibles."""

MSG_MODIFIER = """⚙️ *Modification de ton profil*

Que veux-tu changer ?
- *MONTANT* — Changer le montant par cycle
- *FREQUENCE* — Changer la fréquence
- *WALLET* — Changer ton adresse Lightning
- *MOMO* — Changer ton numéro MoMo"""

# --- Rapport hebdomadaire ---

def msg_rapport_hebdo(total_sats_semaine, total_fcfa_semaine, transactions_semaine, total_sats_global):
    return f"""📈 *Rapport hebdomadaire FlashBot*

Cette semaine :
- 💸 Investi : *{total_fcfa_semaine} FCFA*
- ⚡ Sats achetés : *{total_sats_semaine} sats*
- 🔄 Achats : *{transactions_semaine}*

Depuis le début :
- 🏦 Total : *{total_sats_global} sats*

_Bonne semaine et continue à stacker !_ ⚡"""

def msg_profil(user):
    jours = {
        "monday": "lundi", "tuesday": "mardi", "wednesday": "mercredi",
        "thursday": "jeudi", "friday": "vendredi", "saturday": "samedi",
        "sunday": "dimanche"
    }
    frequences = {"daily": "chaque jour", "weekly": "chaque semaine", "monthly": "chaque mois"}
    jour = jours.get(user["schedule_day"], user["schedule_day"])
    freq = frequences.get(user["frequency"], user["frequency"])
    statut = "✅ Actif" if user["is_active"] else "⏸ En pause"

    return f"""👤 *Ton profil FlashBot*
    - 📱 MoMo : *{user["momo_number"]}*
    - ⚡ Wallet : `{user["lightning_wallet"]}`
    - 💰 Montant : *{user["dca_amount_fcfa"]} FCFA*
    - 🔁 Fréquence : *{freq}*
    - 📅 Jour : *{jour}*
    - ⏰ Heure : *{user["schedule_time"]}*
    - 🔆 Statut : *{statut}*"""