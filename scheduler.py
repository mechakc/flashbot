# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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
    msg_distribution, msg_payout_recu, msg_tontine_terminee,
    msg_paiement_recu_perso, msg_paiement_recu_autres
)

TIMEZONE = pytz.timezone("Africa/Porto-Novo")
scheduler = BackgroundScheduler(timezone=TIMEZONE)


def start_scheduler():
    # Vérifie les paiements en attente toutes les 30 secondes
    scheduler.add_job(
        func=check_pending_payments,
        trigger="interval",
        seconds=30,
        id="check_payments",
        replace_existing=True
    )

    # Vérifie chaque minute si un round doit démarrer
    scheduler.add_job(
        func=check_scheduled_rounds,
        trigger="interval",
        minutes=1,
        id="check_rounds",
        replace_existing=True
    )

    # Rappels toutes les 12h
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
# SCHEDULE_NEXT_ROUND — appelé depuis commands.py
# ==============================================================

def schedule_next_round(tontine_id, round_number):
    """
    Programme le démarrage du round selon la fréquence de la tontine.
    - daily  → démarre immédiatement (pour les tests et démo)
    - weekly → démarre au prochain jour/heure configuré
    - monthly → démarre le 1er du mois prochain à l'heure configurée
    """
    tontine = get_tontine_by_id(tontine_id)
    frequency = tontine["frequency"]

    if frequency == "daily":
        # Pour la démo : démarre immédiatement
        print(f"[SCHEDULER] Round {round_number} démarre immédiatement (daily)")
        _start_round(tontine_id, round_number)

    elif frequency == "weekly":
        # Programme via APScheduler au bon jour/heure
        schedule_time = tontine["schedule_time"]
        schedule_day = tontine["schedule_day"]
        h, m = schedule_time.split(":")

        job_id = f"round_{tontine_id}_{round_number}"
        scheduler.add_job(
            func=_start_round,
            args=[tontine_id, round_number],
            trigger=CronTrigger(
                day_of_week=schedule_day[:3],  # "monday" → "mon"
                hour=int(h),
                minute=int(m),
                timezone=TIMEZONE
            ),
            id=job_id,
            replace_existing=True
        )
        print(f"[SCHEDULER] Round {round_number} programmé pour {schedule_day} à {schedule_time}")

    elif frequency == "monthly":
        h, m = tontine["schedule_time"].split(":")
        job_id = f"round_{tontine_id}_{round_number}"
        scheduler.add_job(
            func=_start_round,
            args=[tontine_id, round_number],
            trigger=CronTrigger(
                day=1,
                hour=int(h),
                minute=int(m),
                timezone=TIMEZONE
            ),
            id=job_id,
            replace_existing=True
        )
        print(f"[SCHEDULER] Round {round_number} programmé pour le 1er du mois à {tontine['schedule_time']}")


# ==============================================================
# VÉRIFICATION ROUNDS (chaque minute)
# ==============================================================

def check_scheduled_rounds():
    """
    Backup : vérifie si un round devrait avoir démarré.
    Utile si le scheduler a raté un déclenchement.
    """
    pass  # APScheduler gère ça via les jobs cron


# ==============================================================
# DÉMARRER UN ROUND
# ==============================================================

def start_first_round(tontine_id):
    """Appelé depuis commands.py quand la tontine est complète."""
    schedule_next_round(tontine_id, round_number=1)


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

    # Vérifier qu'il n'y a pas déjà un round actif
    existing = get_current_round(tontine_id)
    if existing:
        print(f"[SCHEDULER] Round déjà actif pour tontine {tontine_id}, skip")
        return

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

        create_payment(
            round_id=round_id,
            member_id=member["id"],
            amount_sats=tontine["amount_sats"],
            invoice=invoice_data["payment_request"],
            payment_hash=invoice_data["payment_hash"]
        )

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
    """Vérifie si des invoices en attente ont été payées."""
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
    """Confirme un paiement et notifie tous les membres."""
    from database import update_payment

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

    if paid_count >= total:
        _complete_round(tontine_id, current_round)


def _complete_round(tontine_id, current_round):
    """Termine un round et démarre le suivant ou distribue."""
    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    total_rounds = len(members)
    round_number = current_round["round_number"]

    update_round(
        current_round["id"],
        status="completed",
        completed_at=datetime.now(TIMEZONE).isoformat()
    )

    for member in members:
        send_message(
            member["whatsapp_number"],
            msg_round_complet(tontine["name"], round_number, total_rounds)
        )

    print(f"[SCHEDULER] Tour {round_number}/{total_rounds} complété ✅")

    if round_number >= total_rounds:
        _distribute_funds(tontine_id)
    else:
        import time
        time.sleep(2)
        schedule_next_round(tontine_id, round_number + 1)


# ==============================================================
# DISTRIBUTION FINALE
# ==============================================================

def _distribute_funds(tontine_id):
    """Envoie les sats à chaque membre après tous les tours."""
    from lnbits import send_payment, get_wallet_balance

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)
    nb_members = len(members)
    amount_sats = tontine["amount_sats"]
    total_per_member = amount_sats * nb_members

    print(f"[SCHEDULER] Distribution — {tontine['name']} — {total_per_member} sats/membre")

    for member in members:
        send_message(
            member["whatsapp_number"],
            msg_distribution(tontine["name"], amount_sats, nb_members)
        )

    for member in members:
        result = send_payment(
            lightning_address=member["lightning_wallet"],
            amount_sats=total_per_member,
            memo=f"TontineBot {tontine['name']} payout"
        )

        if result and result.get("success"):
            send_message(
                member["whatsapp_number"],
                msg_payout_recu(tontine["name"], amount_sats, nb_members)
            )
            print(f"[SCHEDULER] Payout ✅ → {member['whatsapp_number']}")
        else:
            send_message(
                member["whatsapp_number"],
                f"❌ Erreur envoi sats. Contacte le support.\nMontant dû : *{total_per_member} sats*"
            )

    update_tontine(tontine_id, status="completed")

    for member in members:
        send_message(member["whatsapp_number"], msg_tontine_terminee(tontine["name"]))

    print(f"[SCHEDULER] Distribution terminée ✅")


# ==============================================================
# RAPPELS
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
            print(f"[SCHEDULER] Rappel → {payment['whatsapp_number']}")
