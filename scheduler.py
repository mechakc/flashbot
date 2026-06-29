# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz

from database import (
    get_tontine_by_id, get_members, get_member_by_id,
    get_current_round, create_round, update_round, update_tontine,
    create_payment, get_payments_for_round, count_paid_in_round,
    get_pending_payments_in_round, get_all_active_tontines
)
from whatsapp import send_message
from messages import (
    msg_invoice_tour, msg_rappel_paiement, msg_round_complet,
    msg_distribution, msg_payout_recu, msg_tontine_terminee
)

TIMEZONE = pytz.timezone("Africa/Porto-Novo")
scheduler = BackgroundScheduler(timezone=TIMEZONE)


def start_scheduler():
    # Job 1 : vérifie les paiements en attente toutes les 30 secondes
    scheduler.add_job(
        func=check_pending_payments,
        trigger="interval",
        seconds=30,
        id="check_payments",
        replace_existing=True
    )

    # Job 2 : envoie des rappels aux membres en retard toutes les 12h
    scheduler.add_job(
        func=send_payment_reminders,
        trigger="interval",
        hours=12,
        id="send_reminders",
        replace_existing=True
    )

    scheduler.start()
    print("[SCHEDULER] TontineBot démarré ✅")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] Arrêté ✅")


# ==============================================================
# DÉMARRER UN ROUND
# ==============================================================

def start_first_round(tontine_id):
    """Appelé depuis commands.py quand la tontine est complète."""
    _start_round(tontine_id, round_number=1)


def _start_round(tontine_id, round_number):
    """
    Démarre un round :
    1. Crée le round en DB
    2. Génère une invoice LNbits pour chaque membre
    3. Envoie l'invoice à chaque membre par DM
    """
    from lnbits import create_invoice
    import os

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    total_rounds = len(members)

    # Le bénéficiaire = membre dont turn_order == round_number
    beneficiary = next(
        (m for m in members if m["turn_order"] == round_number), None
    )
    if not beneficiary:
        print(f"[SCHEDULER] Bénéficiaire introuvable pour round {round_number}")
        return

    # Créer le round en DB
    round_id = create_round(
        tontine_id=tontine_id,
        round_number=round_number,
        beneficiary_member_id=beneficiary["id"]
    )

    update_tontine(tontine_id, current_round=round_number)

    # URL webhook Railway (ou localhost pour les tests)
    base_url = os.getenv("BASE_URL", "http://localhost:5000")
    webhook_url = f"{base_url}/lnbits/webhook"

    print(f"[SCHEDULER] Démarrage Tour {round_number}/{total_rounds} — {tontine['name']}")

    # Générer une invoice pour chaque membre
    for member in members:
        memo = f"TontineBot {tontine['name']} Tour {round_number}"

        invoice_data = create_invoice(
            amount_sats=tontine["amount_sats"],
            memo=memo,
            webhook_url=webhook_url
        )

        if not invoice_data:
            print(f"[SCHEDULER] Erreur invoice pour {member['whatsapp_number']}")
            continue

        # Enregistrer le paiement en DB
        create_payment(
            round_id=round_id,
            member_id=member["id"],
            amount_sats=tontine["amount_sats"],
            invoice=invoice_data["payment_request"],
            payment_hash=invoice_data["payment_hash"]
        )

        # Envoyer l'invoice au membre par DM
        is_beneficiary = member["id"] == beneficiary["id"]

        send_message(
            member["whatsapp_number"],
            msg_invoice_tour(
                name=tontine["name"],
                round_number=round_number,
                total_rounds=total_rounds,
                amount_sats=tontine["amount_sats"],
                invoice=invoice_data["payment_request"],
                beneficiary_is_you=is_beneficiary
            )
        )

        print(f"[SCHEDULER] Invoice envoyée à {member['whatsapp_number']} ✅")


# ==============================================================
# VÉRIFICATION PAIEMENTS (toutes les 30 secondes)
# ==============================================================

def check_pending_payments():
    """
    Vérifie si des invoices en attente ont été payées.
    Appelé toutes les 30 secondes par le scheduler.
    """
    from lnbits import check_invoice

    tontines = get_all_active_tontines()

    for tontine in tontines:
        current_round = get_current_round(tontine["id"])
        if not current_round:
            continue

        pending = get_pending_payments_in_round(current_round["id"])

        for payment in pending:
            paid = check_invoice(payment["payment_hash"])

            if paid:
                print(f"[SCHEDULER] Paiement confirmé ✅ — {payment['whatsapp_number']}")
                _confirm_payment(tontine["id"], current_round, payment)


def _confirm_payment(tontine_id, current_round, payment):
    """
    Confirme un paiement :
    1. Met à jour le statut en DB
    2. Notifie tous les membres
    3. Vérifie si le round est complet
    """
    from database import update_payment, get_connection
    from messages import msg_paiement_recu_perso, msg_paiement_recu_autres

    # Mettre à jour le paiement
    update_payment(
        payment["id"],
        status="paid",
        paid_at=datetime.now(TIMEZONE).isoformat()
    )

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    paid_count = count_paid_in_round(current_round["id"])
    total = len(members)
    round_number = current_round["round_number"]

    # Notifier tous les membres
    for member in members:
        if member["whatsapp_number"] == payment["whatsapp_number"]:
            send_message(
                member["whatsapp_number"],
                msg_paiement_recu_perso(tontine["name"], round_number, paid_count, total)
            )
        else:
            send_message(
                member["whatsapp_number"],
                msg_paiement_recu_autres(
                    tontine["name"], round_number, paid_count, total,
                    payment["whatsapp_number"]
                )
            )

    # Round complet ?
    if paid_count >= total:
        _complete_round(tontine_id, current_round)


def _complete_round(tontine_id, current_round):
    """
    Termine un round :
    1. Marque le round comme completed
    2. Démarre le round suivant OU distribue si c'était le dernier
    """
    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    total_rounds = len(members)
    round_number = current_round["round_number"]

    # Marquer le round comme terminé
    update_round(
        current_round["id"],
        status="completed",
        completed_at=datetime.now(TIMEZONE).isoformat()
    )

    # Notifier tout le monde
    for member in members:
        send_message(
            member["whatsapp_number"],
            msg_round_complet(tontine["name"], round_number, total_rounds)
        )

    print(f"[SCHEDULER] Tour {round_number}/{total_rounds} complété ✅")

    # Dernier round → distribution finale
    if round_number >= total_rounds:
        _distribute_funds(tontine_id)
    else:
        # Démarrer le round suivant
        import time
        time.sleep(3)  # petite pause pour que les messages arrivent
        _start_round(tontine_id, round_number + 1)


# ==============================================================
# DISTRIBUTION FINALE
# ==============================================================

def _distribute_funds(tontine_id):
    """
    Envoie les sats à chaque membre après tous les tours.
    Chaque membre reçoit : amount_sats * nb_membres
    """
    from lnbits import send_payment, get_wallet_balance

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    nb_members = len(members)
    amount_sats = tontine["amount_sats"]
    total_per_member = amount_sats * nb_members

    print(f"[SCHEDULER] Distribution finale — {tontine['name']}")
    print(f"[SCHEDULER] {nb_members} membres x {amount_sats} sats = {total_per_member} sats chacun")

    # Vérifier le solde du wallet bot
    balance = get_wallet_balance()
    expected = total_per_member * nb_members

    if balance is not None and balance < expected:
        print(f"[SCHEDULER] ⚠️ Solde insuffisant : {balance} sats (besoin : {expected} sats)")

    # Notifier le début de la distribution
    for member in members:
        send_message(
            member["whatsapp_number"],
            msg_distribution(tontine["name"], amount_sats, nb_members)
        )

    # Envoyer les sats à chaque membre
    success_count = 0
    for member in members:
        result = send_payment(
            lightning_address=member["lightning_wallet"],
            amount_sats=total_per_member,
            memo=f"TontineBot {tontine['name']} — payout final"
        )

        if result and result.get("success"):
            success_count += 1
            send_message(
                member["whatsapp_number"],
                msg_payout_recu(tontine["name"], amount_sats, nb_members)
            )
            print(f"[SCHEDULER] Payout envoyé à {member['whatsapp_number']} ✅")
        else:
            send_message(
                member["whatsapp_number"],
                f"❌ Erreur envoi de tes sats. Contacte le support.\nMontant dû : *{total_per_member} sats*"
            )
            print(f"[SCHEDULER] ⚠️ Erreur payout pour {member['whatsapp_number']}")

    # Marquer la tontine comme terminée
    update_tontine(tontine_id, status="completed")

    # Message final
    for member in members:
        send_message(member["whatsapp_number"], msg_tontine_terminee(tontine["name"]))

    print(f"[SCHEDULER] Distribution terminée — {success_count}/{nb_members} réussis")


# ==============================================================
# RAPPELS (toutes les 12h)
# ==============================================================

def send_payment_reminders():
    """Envoie des rappels aux membres qui n'ont pas encore payé."""
    tontines = get_all_active_tontines()

    for tontine in tontines:
        current_round = get_current_round(tontine["id"])
        if not current_round:
            continue

        pending = get_pending_payments_in_round(current_round["id"])

        for payment in pending:
            send_message(
                payment["whatsapp_number"],
                msg_rappel_paiement(
                    tontine["name"],
                    current_round["round_number"],
                    tontine["amount_sats"],
                    payment["invoice"]
                )
            )
            print(f"[SCHEDULER] Rappel envoyé à {payment['whatsapp_number']}")
