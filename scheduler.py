# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from database import get_all_active_users, get_user, update_user, get_user_stats
from whatsapp import send_message
from messages import msg_rappel_dca, msg_rapport_hebdo

# Fuseau horaire Afrique de l'Ouest
TIMEZONE = pytz.timezone("Africa/Porto-Novo")

scheduler = BackgroundScheduler(timezone=TIMEZONE)

# Stocke les utilisateurs qui ont reçu un rappel et attendent STACK
# Format : { "2250701234567": { "expires_at": datetime, "amount": 500 } }
PENDING_STACKS = {}


def start_scheduler():
    """Démarre le scheduler et enregistre les jobs globaux."""

    # Job 1 : vérifie chaque minute si un utilisateur doit recevoir un rappel
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger="interval",
        minutes=1,
        id="check_reminders",
        replace_existing=True
    )

    # Job 2 : rapport hebdomadaire chaque dimanche à 20h
    scheduler.add_job(
        func=send_weekly_reports,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=TIMEZONE),
        id="weekly_report",
        replace_existing=True
    )

    # Job 3 : nettoie les PENDING_STACKS expirés toutes les 10 minutes
    scheduler.add_job(
        func=cleanup_expired_stacks,
        trigger="interval",
        minutes=10,
        id="cleanup_stacks",
        replace_existing=True
    )

    scheduler.start()
    print("[SCHEDULER] Démarré ✅")


def stop_scheduler():
    """Arrête proprement le scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] Arrêté ✅")


# --- Job 1 : Rappels DCA ---

def check_and_send_reminders():
    """
    Vérifie chaque minute si un utilisateur doit recevoir son rappel DCA.
    Compare l'heure actuelle avec schedule_time et schedule_day de chaque user.
    """
    now = datetime.now(TIMEZONE)
    current_time = now.strftime("%H:%M")
    current_day = now.strftime("%A").lower()      # ex: "monday"
    current_date = now.day                         # jour du mois pour monthly

    users = get_all_active_users()

    for user in users:
        if _should_send_reminder(user, current_time, current_day, current_date):
            _send_reminder(user)


def _should_send_reminder(user, current_time, current_day, current_date):
    """
    Retourne True si l'utilisateur doit recevoir un rappel maintenant.
    """
    # Vérifier l'heure
    if user["schedule_time"] != current_time:
        return False

    # Vérifier qu'on n'a pas déjà envoyé un rappel ce cycle
    if _already_pending(user["whatsapp_number"]):
        return False

    frequency = user["frequency"]

    if frequency == "daily":
        return True

    if frequency == "weekly":
        return user["schedule_day"] == current_day

    if frequency == "monthly":
        # Envoie le 1er de chaque mois à l'heure configurée
        return current_date == 1

    return False


def _already_pending(whatsapp_number):
    """Vérifie si un rappel est déjà en attente pour cet utilisateur."""
    if whatsapp_number not in PENDING_STACKS:
        return False
    entry = PENDING_STACKS[whatsapp_number]
    now = datetime.now(TIMEZONE)
    # Si le rappel est encore valide (pas expiré)
    return now < entry["expires_at"]


def _send_reminder(user):
    """Envoie le rappel DCA et enregistre l'attente STACK."""
    from datetime import timedelta

    whatsapp_number = user["whatsapp_number"]
    amount = user["dca_amount_fcfa"]

    send_message(whatsapp_number, msg_rappel_dca(amount))

    # Enregistre l'attente — expire dans 30 minutes
    PENDING_STACKS[whatsapp_number] = {
        "expires_at": datetime.now(TIMEZONE) + timedelta(minutes=30),
        "amount": amount
    }

    print(f"[SCHEDULER] Rappel envoyé à {whatsapp_number} — {amount} FCFA ⏰")


# --- Job 2 : Rapport hebdomadaire ---

def send_weekly_reports():
    """Envoie le rapport hebdo à tous les utilisateurs actifs."""
    from database import get_connection
    from datetime import timedelta

    users = get_all_active_users()
    now = datetime.now(TIMEZONE)
    une_semaine = now - timedelta(days=7)

    print(f"[SCHEDULER] Envoi rapports hebdo à {len(users)} utilisateurs...")

    for user in users:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as transactions_semaine,
                    SUM(amount_fcfa) as total_fcfa_semaine,
                    SUM(sats_received) as total_sats_semaine
                FROM transactions
                WHERE user_id = ?
                  AND status = 'success'
                  AND created_at >= ?
            """, (user["id"], une_semaine.isoformat()))
            stats_semaine = cursor.fetchone()
            conn.close()

            total_sats_global = user["total_sats"] or 0
            total_sats_semaine = stats_semaine["total_sats_semaine"] or 0
            total_fcfa_semaine = stats_semaine["total_fcfa_semaine"] or 0
            transactions_semaine = stats_semaine["transactions_semaine"] or 0

            # N'envoie pas si aucune transaction cette semaine
            if transactions_semaine == 0:
                continue

            send_message(user["whatsapp_number"], msg_rapport_hebdo(
                total_sats_semaine=total_sats_semaine,
                total_fcfa_semaine=total_fcfa_semaine,
                transactions_semaine=transactions_semaine,
                total_sats_global=total_sats_global
            ))

            print(f"[SCHEDULER] Rapport envoyé à {user['whatsapp_number']} ✅")

        except Exception as e:
            print(f"[SCHEDULER] Erreur rapport pour {user['whatsapp_number']} : {e}")


# --- Job 3 : Nettoyage PENDING_STACKS ---

def cleanup_expired_stacks():
    """Supprime les entrées PENDING_STACKS expirées."""
    now = datetime.now(TIMEZONE)
    expired = [
        number for number, entry in PENDING_STACKS.items()
        if now >= entry["expires_at"]
    ]
    for number in expired:
        del PENDING_STACKS[number]
        print(f"[SCHEDULER] Stack expiré nettoyé : {number}")


# --- Utilitaires appelés depuis commands.py ---

def is_stack_pending(whatsapp_number):
    """
    Retourne True si l'utilisateur a un rappel en attente de confirmation STACK.
    Appelé depuis commands.py pour valider que le STACK est légitime.
    """
    return _already_pending(whatsapp_number)


def clear_pending_stack(whatsapp_number):
    """Supprime l'entrée PENDING_STACKS après un STACK confirmé."""
    if whatsapp_number in PENDING_STACKS:
        del PENDING_STACKS[whatsapp_number]