# commands.py
from database import (
    get_user, create_user, update_user,
    create_transaction, update_transaction, get_user_stats
)
from whatsapp import send_message
from messages import *
from momo import request_to_pay
from flash import buy_sats

# --- États d'inscription (conversation multi-étapes) ---
# On stocke en mémoire l'étape où en est chaque utilisateur
# Format : { "2250701234567": { "step": "await_momo", ... } }
PENDING_REGISTRATIONS = {}
PENDING_MODIFICATIONS = {}

JOURS_MAP = {
    "LUNDI": "monday", "MARDI": "tuesday", "MERCREDI": "wednesday",
    "JEUDI": "thursday", "VENDREDI": "friday", "SAMEDI": "saturday",
    "DIMANCHE": "sunday"
}

def handle_message(from_number, text, raw_text):
    """
    Point d'entrée principal — reçoit chaque message et route vers la bonne fonction.
    """
    user = get_user(from_number)

    # Priorité 1 : si l'utilisateur est en cours d'inscription
    if from_number in PENDING_REGISTRATIONS:
        return handle_registration_step(from_number, text, raw_text)

    # Priorité 2 : si l'utilisateur est en cours de modification
    if from_number in PENDING_MODIFICATIONS:
        return handle_modification_step(from_number, text, raw_text)

    # Priorité 3 : commandes globales
    if text == "DEMARRER":
        return handle_demarrer(from_number, user)

    if text == "STACK":
        return handle_stack(from_number, user)

    if text == "SOLDE":
        return handle_solde(from_number, user)

    if text == "PAUSE":
        return handle_pause(from_number, user)

    if text == "REPRENDRE":
        return handle_reprendre(from_number, user)

    if text == "MODIFIER":
        return handle_modifier(from_number, user)

    if text == "AIDE":
        return send_message(from_number, MSG_AIDE)

    # Commande inconnue
    return send_message(from_number, MSG_COMMANDE_INCONNUE)


# --- DEMARRER ---

def handle_demarrer(from_number, user):
    """Démarre le flux d'inscription."""
    if user:
        # Déjà inscrit → proposer reconfiguration
        send_message(from_number, f"Tu es déjà inscrit ! ⚡\n\nTape *MODIFIER* pour changer tes paramètres ou *AIDE* pour voir les commandes.")
        return

    # Nouvel utilisateur
    create_user(from_number)
    PENDING_REGISTRATIONS[from_number] = {"step": "await_momo"}
    send_message(from_number, MSG_BIENVENUE)


# --- FLUX D'INSCRIPTION ---

def handle_registration_step(from_number, text, raw_text):
    """Gère les étapes d'inscription une par une."""
    state = PENDING_REGISTRATIONS[from_number]
    step = state["step"]

    # Étape 1 : numéro MoMo
    if step == "await_momo":
        if not _is_valid_phone(raw_text):
            send_message(from_number, "⚠️ Numéro invalide. Entre ton numéro avec l'indicatif pays.\n(Ex: 2250701234567)")
            return
        update_user(from_number, momo_number=raw_text)
        PENDING_REGISTRATIONS[from_number]["step"] = "await_wallet"
        send_message(from_number, MSG_DEMANDE_WALLET)

    # Étape 2 : wallet Lightning
    elif step == "await_wallet":
        if not _is_valid_wallet(raw_text):
            send_message(from_number, "⚠️ Adresse wallet invalide.\nExemple valide : ton_nom@walletofsatoshi.com")
            return
        update_user(from_number, lightning_wallet=raw_text)
        PENDING_REGISTRATIONS[from_number]["step"] = "await_amount"
        send_message(from_number, MSG_DEMANDE_MONTANT)

    # Étape 3 : montant FCFA
    elif step == "await_amount":
        if not _is_valid_amount(raw_text):
            send_message(from_number, "⚠️ Montant invalide. Entre un nombre entier (minimum 100).\nEx: 500")
            return
        update_user(from_number, dca_amount_fcfa=int(raw_text))
        PENDING_REGISTRATIONS[from_number]["step"] = "await_frequency"
        send_message(from_number, MSG_DEMANDE_FREQUENCE)

    # Étape 4 : fréquence
    elif step == "await_frequency":
        if text not in ("DAILY", "WEEKLY", "MONTHLY"):
            send_message(from_number, "⚠️ Réponds avec DAILY, WEEKLY ou MONTHLY.")
            return
        freq_map = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}
        update_user(from_number, frequency=freq_map[text])
        PENDING_REGISTRATIONS[from_number]["step"] = "await_time"
        send_message(from_number, MSG_DEMANDE_HEURE)

    # Étape 5 : heure
    elif step == "await_time":
        if not _is_valid_time(raw_text):
            send_message(from_number, "⚠️ Format invalide. Entre l'heure au format HH:MM.\nEx: 08:00")
            return
        update_user(from_number, schedule_time=raw_text)
        user = get_user(from_number)

        # Si daily ou monthly, pas besoin du jour
        if user["frequency"] in ("daily", "monthly"):
            del PENDING_REGISTRATIONS[from_number]
            user = get_user(from_number)
            send_message(from_number, msg_confirmation_inscription(user))
        else:
            PENDING_REGISTRATIONS[from_number]["step"] = "await_day"
            send_message(from_number, MSG_DEMANDE_JOUR)

    # Étape 6 : jour de la semaine (weekly seulement)
    elif step == "await_day":
        if text not in JOURS_MAP:
            send_message(from_number, "⚠️ Réponds avec LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI, SAMEDI ou DIMANCHE.")
            return
        update_user(from_number, schedule_day=JOURS_MAP[text])
        del PENDING_REGISTRATIONS[from_number]
        user = get_user(from_number)
        send_message(from_number, msg_confirmation_inscription(user))


# --- STACK ---

def handle_stack(from_number, user):
    """Déclenche un achat DCA immédiat."""
    if not user:
        send_message(from_number, "Tu n'es pas encore inscrit. Tape *DEMARRER* pour commencer !")
        return

    if not user["is_active"]:
        send_message(from_number, "Ton DCA est en pause. Tape *REPRENDRE* pour le réactiver.")
        return

    amount = user["dca_amount_fcfa"]
    send_message(from_number, msg_paiement_envoye(amount))

    # Créer une transaction en attente
    tx_id = create_transaction(user["id"], amount)

    # Appel MoMo Request to Pay
    momo_result = request_to_pay(
        amount=amount,
        phone_number=user["momo_number"],
        tx_id=str(tx_id)
    )

    if not momo_result["success"]:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        return

    momo_tx_id = momo_result.get("transaction_id", "")
    update_transaction(tx_id, momo_tx_id=momo_tx_id, status="momo_pending")

    # Achat sats sur Flash
    flash_result = buy_sats(amount, user["lightning_wallet"])

    if not flash_result:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        return

    sats_received = flash_result.get("sats", 0)
    flash_tx_id = flash_result.get("tx_id", "")

    # Mise à jour transaction + total sats utilisateur
    update_transaction(tx_id, sats_received=sats_received, flash_tx_id=flash_tx_id, status="success")
    new_total = (user["total_sats"] or 0) + sats_received
    update_user(from_number, total_sats=new_total)

    send_message(from_number, msg_achat_reussi(sats_received, new_total, amount))


# --- SOLDE ---

def handle_solde(from_number, user):
    if not user:
        send_message(from_number, "Tu n'es pas encore inscrit. Tape *DEMARRER* pour commencer !")
        return
    stats = get_user_stats(user["id"])
    send_message(from_number, msg_solde(
        total_sats=stats["total_sats"] or 0,
        total_fcfa=stats["total_fcfa"] or 0,
        total_transactions=stats["total_transactions"] or 0
    ))


# --- PAUSE ---

def handle_pause(from_number, user):
    if not user:
        send_message(from_number, "Tu n'es pas encore inscrit. Tape *DEMARRER* pour commencer !")
        return
    update_user(from_number, is_active=0)
    send_message(from_number, MSG_PAUSE)


# --- REPRENDRE ---

def handle_reprendre(from_number, user):
    if not user:
        send_message(from_number, "Tu n'es pas encore inscrit. Tape *DEMARRER* pour commencer !")
        return
    update_user(from_number, is_active=1)
    send_message(from_number, MSG_REPRENDRE)


# --- MODIFIER ---

def handle_modifier(from_number, user):
    if not user:
        send_message(from_number, "Tu n'es pas encore inscrit. Tape *DEMARRER* pour commencer !")
        return
    PENDING_MODIFICATIONS[from_number] = {"step": "await_choice"}
    send_message(from_number, MSG_MODIFIER)

def handle_modification_step(from_number, text, raw_text):
    state = PENDING_MODIFICATIONS[from_number]
    step = state["step"]

    if step == "await_choice":
        if text == "MONTANT":
            PENDING_MODIFICATIONS[from_number]["step"] = "await_new_amount"
            send_message(from_number, "💰 Nouveau montant en FCFA ? (minimum 100)")
        elif text == "FREQUENCE":
            PENDING_MODIFICATIONS[from_number]["step"] = "await_new_frequency"
            send_message(from_number, MSG_DEMANDE_FREQUENCE)
        elif text == "WALLET":
            PENDING_MODIFICATIONS[from_number]["step"] = "await_new_wallet"
            send_message(from_number, "⚡ Nouvelle adresse Lightning ?")
        elif text == "MOMO":
            PENDING_MODIFICATIONS[from_number]["step"] = "await_new_momo"
            send_message(from_number, "📱 Nouveau numéro MTN MoMo ? (avec indicatif pays)")
        else:
            send_message(from_number, "⚠️ Réponds avec MONTANT, FREQUENCE, WALLET ou MOMO.")

    elif step == "await_new_amount":
        if not _is_valid_amount(raw_text):
            send_message(from_number, "⚠️ Montant invalide. Entre un nombre entier (minimum 100).")
            return
        update_user(from_number, dca_amount_fcfa=int(raw_text))
        del PENDING_MODIFICATIONS[from_number]
        send_message(from_number, f"✅ Montant mis à jour : *{raw_text} FCFA* par cycle.")

    elif step == "await_new_frequency":
        if text not in ("DAILY", "WEEKLY", "MONTHLY"):
            send_message(from_number, "⚠️ Réponds avec DAILY, WEEKLY ou MONTHLY.")
            return
        freq_map = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}
        update_user(from_number, frequency=freq_map[text])
        del PENDING_MODIFICATIONS[from_number]
        send_message(from_number, f"✅ Fréquence mise à jour : *{raw_text}*.")

    elif step == "await_new_wallet":
        if not _is_valid_wallet(raw_text):
            send_message(from_number, "⚠️ Adresse wallet invalide.")
            return
        update_user(from_number, lightning_wallet=raw_text)
        del PENDING_MODIFICATIONS[from_number]
        send_message(from_number, f"✅ Wallet mis à jour : `{raw_text}`.")

    elif step == "await_new_momo":
        if not _is_valid_phone(raw_text):
            send_message(from_number, "⚠️ Numéro invalide. Entre ton numéro avec l'indicatif pays.")
            return
        update_user(from_number, momo_number=raw_text)
        del PENDING_MODIFICATIONS[from_number]
        send_message(from_number, f"✅ Numéro MoMo mis à jour : *{raw_text}*.")


# --- Validations ---

def _is_valid_phone(text):
    """Numéro international : commence par un chiffre, 10-15 chiffres."""
    return text.isdigit() and 10 <= len(text) <= 15

def _is_valid_wallet(text):
    """Adresse Lightning : doit contenir @ ou commencer par lnurl/ln."""
    text_lower = text.lower()
    return "@" in text_lower or text_lower.startswith("lnurl") or text_lower.startswith("ln")

def _is_valid_amount(text):
    """Montant : entier >= 100."""
    return text.isdigit() and int(text) >= 100

def _is_valid_time(text):
    """Heure au format HH:MM."""
    parts = text.split(":")
    if len(parts) != 2:
        return False
    h, m = parts
    return h.isdigit() and m.isdigit() and 0 <= int(h) <= 23 and 0 <= int(m) <= 59