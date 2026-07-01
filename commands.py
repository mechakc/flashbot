import random
import string
from database import (
    create_tontine, get_tontine_by_code, get_tontine_by_id,
    get_tontines_by_member, get_all_tontines_by_member, update_tontine,
    add_member, get_members, get_member, count_members,
    get_member_by_id, get_all_rounds, get_current_round,
    get_payments_for_round, count_paid_in_round
)
from whatsapp import send_message
from messages import *

PENDING_JOINS = {}
PENDING_CREATES = {}

JOURS_MAP = {
    "LUNDI": "monday", "MARDI": "tuesday", "MERCREDI": "wednesday",
    "JEUDI": "thursday", "VENDREDI": "friday", "SAMEDI": "saturday",
    "DIMANCHE": "sunday"
}

JOURS_FR = {
    "monday": "lundi", "tuesday": "mardi", "wednesday": "mercredi",
    "thursday": "jeudi", "friday": "vendredi", "saturday": "samedi",
    "sunday": "dimanche"
}

FREQ_FR = {
    "daily": "chaque jour",
    "weekly": "chaque semaine",
    "monthly": "chaque mois"
}


def handle_message(from_number, text, raw_text):
    if from_number in PENDING_CREATES:
        return handle_create_step(from_number, text, raw_text)

    if from_number in PENDING_JOINS:
        return handle_join_step(from_number, text, raw_text)

    if text == "AIDE":
        return send_message(from_number, MSG_AIDE)

    if text.startswith("CREER"):
        return handle_creer(from_number, text, raw_text)

    if text.startswith("REJOINDRE"):
        return handle_rejoindre(from_number, text, raw_text)

    if text.startswith("TONTINE"):
        return handle_tontine(from_number, text, raw_text)

    if text.startswith("MEMBRES"):
        return handle_membres(from_number, text, raw_text)

    if text.startswith("HISTORIQUE"):
        return handle_historique(from_number, text, raw_text)

    return send_message(from_number, MSG_COMMANDE_INCONNUE)


# ==============================================================
# CREER
# ==============================================================

def handle_creer(from_number, text, raw_text):
    # Un membre déjà présent dans une tontine peut quand même en créer une nouvelle.
    # (Seul REJOINDRE reste bloqué pour éviter la double-participation à une même tontine.)
    PENDING_CREATES[from_number] = {"step": "await_name"}
    send_message(from_number, MSG_CREER_NOM)


def handle_create_step(from_number, text, raw_text):
    state = PENDING_CREATES[from_number]
    step = state["step"]

    if step == "await_name":
        name = raw_text.strip()
        if len(name) < 2 or len(name) > 30:
            send_message(from_number, "⚠️ Le nom doit faire entre 2 et 30 caractères.")
            return
        PENDING_CREATES[from_number]["name"] = name
        PENDING_CREATES[from_number]["step"] = "await_amount"
        send_message(from_number, MSG_CREER_MONTANT)

    elif step == "await_amount":
        if not raw_text.isdigit() or int(raw_text) < 100:
            send_message(from_number, "⚠️ Montant invalide. Minimum 100 sats.\nEx: 5000")
            return
        PENDING_CREATES[from_number]["amount"] = int(raw_text)
        PENDING_CREATES[from_number]["step"] = "await_members"
        send_message(from_number, MSG_CREER_MEMBRES)

    elif step == "await_members":
        if not raw_text.isdigit() or not (1 <= int(raw_text) <= 20):
            send_message(from_number, "⚠️ Nombre de membres invalide. Entre 1 et 20.")
            return
        PENDING_CREATES[from_number]["max_members"] = int(raw_text)
        PENDING_CREATES[from_number]["step"] = "await_frequency"
        send_message(from_number, MSG_CREER_FREQUENCE)

    elif step == "await_frequency":
        if text not in ("DAILY", "WEEKLY", "MONTHLY"):
            send_message(from_number, "⚠️ Réponds avec DAILY, WEEKLY ou MONTHLY.")
            return
        freq_map = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}
        PENDING_CREATES[from_number]["frequency"] = freq_map[text]

        if text == "WEEKLY":
            PENDING_CREATES[from_number]["step"] = "await_day"
            send_message(from_number, MSG_CREER_JOUR)
        else:
            PENDING_CREATES[from_number]["step"] = "await_time"
            send_message(from_number, MSG_CREER_HEURE)

    elif step == "await_day":
        if text not in JOURS_MAP:
            send_message(from_number, "⚠️ Réponds avec LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI, SAMEDI ou DIMANCHE.")
            return
        PENDING_CREATES[from_number]["schedule_day"] = JOURS_MAP[text]
        PENDING_CREATES[from_number]["step"] = "await_time"
        send_message(from_number, MSG_CREER_HEURE)

    elif step == "await_time":
        if not _is_valid_time(raw_text):
            send_message(from_number, "⚠️ Format invalide. Entre l'heure au format HH:MM.\nEx: 08:00")
            return
        PENDING_CREATES[from_number]["schedule_time"] = raw_text
        PENDING_CREATES[from_number]["step"] = "await_wallet"
        send_message(from_number, MSG_CREER_WALLET)

    elif step == "await_wallet":
        wallet = raw_text.strip()
        if not _is_valid_wallet(wallet):
            send_message(from_number, "⚠️ Adresse wallet invalide.\nEx: tonnom@cake.cash ou lnbc...")
            return
        state = PENDING_CREATES[from_number]
        del PENDING_CREATES[from_number]
        _do_create_tontine(
            from_number=from_number,
            name=state["name"],
            amount_sats=state["amount"],
            max_members=state["max_members"],
            frequency=state.get("frequency", "weekly"),
            schedule_day=state.get("schedule_day", "monday"),
            schedule_time=state.get("schedule_time", "08:00"),
            wallet=wallet
        )


def _do_create_tontine(from_number, name, amount_sats, max_members,
                        frequency, schedule_day, schedule_time, wallet):
    code = _generate_code()

    tontine_id = create_tontine(
        name=name,
        code=code,
        amount_sats=amount_sats,
        max_members=max_members,
        created_by=from_number,
        frequency=frequency,
        schedule_day=schedule_day,
        schedule_time=schedule_time
    )

    if not tontine_id:
        send_message(from_number, "❌ Erreur lors de la création. Réessaie.")
        return

    turn_order = 1
    add_member(
        tontine_id=tontine_id,
        whatsapp_number=from_number,
        lightning_wallet=wallet,
        turn_order=turn_order
    )

    tontine = get_tontine_by_id(tontine_id)
    freq_txt = FREQ_FR.get(frequency, frequency)
    jour_txt = JOURS_FR.get(schedule_day, schedule_day)

    send_message(from_number, msg_tontine_creee(
        name, code, amount_sats, max_members,
        freq_txt, jour_txt, schedule_time
    ))

    # Si 1 seul membre → lancer immédiatement
    if max_members == 1:
        _launch_tontine(tontine_id)


# ==============================================================
# REJOINDRE
# ==============================================================

def handle_rejoindre(from_number, text, raw_text):
    # Un membre déjà dans une (ou plusieurs) tontine(s) peut aussi en rejoindre une nouvelle.
    # La vérification plus bas empêche seulement de rejoindre deux fois LA MÊME tontine.
    parts = raw_text.strip().split()
    if len(parts) < 2:
        send_message(from_number, "⚠️ Indique le code de la tontine.\nEx: *REJOINDRE TONT-4X7K*")
        return

    code = parts[1].upper()
    tontine = get_tontine_by_code(code)

    if not tontine:
        send_message(from_number, f"❌ Code *{code}* introuvable. Vérifie le code et réessaie.")
        return

    if tontine["status"] != "waiting":
        send_message(from_number, "❌ Cette tontine est déjà lancée ou terminée.")
        return

    current_count = count_members(tontine["id"])
    if current_count >= tontine["max_members"]:
        send_message(from_number, "❌ Cette tontine est complète.")
        return

    if get_member(tontine["id"], from_number):
        send_message(from_number, "⚠️ Tu es déjà membre de cette tontine.")
        return

    PENDING_JOINS[from_number] = {
        "step": "await_wallet",
        "tontine_id": tontine["id"],
        "code": code,
        "name": tontine["name"],
        "amount_sats": tontine["amount_sats"],
        "max_members": tontine["max_members"],
        "is_creator": False
    }

    send_message(from_number, f"✅ Tontine *{tontine['name']}* trouvée !\n{current_count}/{tontine['max_members']} membres\n\n⚡ *Quel est ton wallet Lightning ?*\n(Ex: tonnom@cake.cash)")


def handle_join_step(from_number, text, raw_text):
    state = PENDING_JOINS[from_number]
    step = state["step"]

    if step == "await_wallet":
        wallet = raw_text.strip()
        if not _is_valid_wallet(wallet):
            send_message(from_number, "⚠️ Adresse wallet invalide.\nEx: tonnom@cake.cash ou lnbc...")
            return

        tontine_id = state["tontine_id"]
        turn_order = count_members(tontine_id) + 1

        member_id = add_member(
            tontine_id=tontine_id,
            whatsapp_number=from_number,
            lightning_wallet=wallet,
            turn_order=turn_order
        )

        if not member_id:
            send_message(from_number, "❌ Erreur lors de l'inscription. Réessaie.")
            del PENDING_JOINS[from_number]
            return

        del PENDING_JOINS[from_number]

        tontine = get_tontine_by_id(tontine_id)
        current_count = count_members(tontine_id)
        max_members = tontine["max_members"]
        name = tontine["name"]

        send_message(from_number, msg_membre_rejoint(name, current_count, max_members))

        _notify_all_members(tontine_id, from_number,
            f"👋 Un nouveau membre a rejoint *{name}* ! ({current_count}/{max_members})")

        if current_count >= max_members:
            _launch_tontine(tontine_id)


# ==============================================================
# LANCEMENT
# ==============================================================

def _launch_tontine(tontine_id):
    from scheduler import schedule_next_round

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)

    update_tontine(tontine_id, status="active", current_round=0)

    freq_txt = FREQ_FR.get(tontine["frequency"], tontine["frequency"])
    jour_txt = JOURS_FR.get(tontine["schedule_day"], tontine["schedule_day"])

    for member in members:
        lignes = []
        for m in members:
            if m["whatsapp_number"] == member["whatsapp_number"]:
                lignes.append(f"   Tour {m['turn_order']} → *toi* ⭐")
            else:
                lignes.append(f"   Tour {m['turn_order']} → membre {m['turn_order']}")
        ordre_perso = "\n".join(lignes)

        send_message(member["whatsapp_number"], msg_tontine_lancee(
            tontine["name"],
            len(members),
            tontine["amount_sats"],
            ordre_perso,
            freq_txt,
            jour_txt,
            tontine["schedule_time"]
        ))

    print(f"[TONTINE] {tontine['name']} lancée ✅ — premier round programmé à {tontine['schedule_time']}")

    schedule_next_round(tontine_id, round_number=1)


# ==============================================================
# TONTINE
# ==============================================================

def _resolve_user_tontine(from_number, raw_text, cmd_hint="TONTINE", include_completed=False):
    """
    Détermine la tontine visée par une commande du type 'COMMANDE [CODE]'.
    - Si un CODE est fourni, vérifie que l'utilisateur en est membre.
    - Sinon, cherche parmi les tontines de l'utilisateur : s'il n'y en a qu'une,
      elle est retournée directement ; s'il y en a plusieurs, une liste est
      envoyée pour lui demander de préciser le code.
    Retourne le dict tontine, ou None (un message d'erreur/liste a déjà été envoyé).
    """
    parts = raw_text.strip().split()
    code = parts[1].upper() if len(parts) >= 2 else None

    if code:
        tontine = get_tontine_by_code(code)
        if not tontine:
            send_message(from_number, f"❌ Code *{code}* introuvable.")
            return None
        if not get_member(tontine["id"], from_number):
            send_message(from_number, f"❌ Tu n'es pas membre de la tontine *{code}*.")
            return None
        return tontine

    mine = get_all_tontines_by_member(from_number) if include_completed else get_tontines_by_member(from_number)
    if not mine:
        if include_completed:
            send_message(from_number, "❌ Aucune tontine trouvée.")
        else:
            send_message(from_number, "❌ Tu n'es dans aucune tontine active.\n\nTape *CREER* ou *REJOINDRE CODE* pour commencer.")
        return None

    if len(mine) > 1:
        liste = "\n".join(f"  🔹 *{t['name']}* — {t['code']}" for t in mine)
        send_message(from_number, f"📋 Tu es dans plusieurs tontines :\n\n{liste}\n\nTape *{cmd_hint} CODE* pour préciser.\nEx: *{cmd_hint} {mine[0]['code']}*")
        return None

    return mine[0]


def handle_tontine(from_number, text="TONTINE", raw_text="TONTINE"):
    tontine = _resolve_user_tontine(from_number, raw_text, cmd_hint="TONTINE")
    if not tontine:
        return

    members = get_members(tontine["id"])
    current_round = get_current_round(tontine["id"])

    if tontine["status"] == "waiting":
        current_count = len(members)
        freq_txt = FREQ_FR.get(tontine["frequency"], tontine["frequency"])
        jour_txt = JOURS_FR.get(tontine["schedule_day"], tontine["schedule_day"])
        send_message(from_number, msg_statut_waiting(
            tontine["name"],
            tontine["code"],
            current_count,
            tontine["max_members"],
            tontine["amount_sats"],
            freq_txt,
            jour_txt,
            tontine["schedule_time"]
        ))
        return

    if tontine["status"] == "active" and current_round:
        payments = get_payments_for_round(current_round["id"])
        paid_count = count_paid_in_round(current_round["id"])
        total = len(members)
        beneficiary = get_member_by_id(current_round["beneficiary_member_id"])
        member = get_member(tontine["id"], from_number)
        my_payment = next(
            (p for p in payments if p["member_id"] == member["id"]),
            None
        ) if member else None

        send_message(from_number, msg_statut_active(
            tontine["name"],
            current_round["round_number"],
            len(members),
            beneficiary["whatsapp_number"],
            beneficiary["whatsapp_number"] == from_number,
            paid_count,
            total,
            my_payment["status"] if my_payment else "pending"
        ))
        return

    if tontine["status"] == "completed":
        send_message(from_number, f"✅ La tontine *{tontine['name']}* est terminée !\n\nTape *HISTORIQUE* pour voir le résumé.")


# ==============================================================
# MEMBRES
# ==============================================================

def handle_membres(from_number, text="MEMBRES", raw_text="MEMBRES"):
    tontine = _resolve_user_tontine(from_number, raw_text, cmd_hint="MEMBRES")
    if not tontine:
        return
    members = get_members(tontine["id"])
    send_message(from_number, msg_liste_membres(tontine["name"], members, from_number))


# ==============================================================
# HISTORIQUE
# ==============================================================

def handle_historique(from_number, text="HISTORIQUE", raw_text="HISTORIQUE"):
    tontine = _resolve_user_tontine(from_number, raw_text, cmd_hint="HISTORIQUE", include_completed=True)
    if not tontine:
        return

    rounds = get_all_rounds(tontine["id"])
    send_message(from_number, msg_historique(tontine["name"], rounds, tontine["amount_sats"]))


# ==============================================================
# UTILITAIRES
# ==============================================================

def _generate_code():
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"TONT-{suffix}"


def _is_valid_wallet(text):
    text_lower = text.lower()
    return (
        "@" in text_lower or
        text_lower.startswith("lnurl") or
        text_lower.startswith("lnbc") or
        text_lower.startswith("lightning:")
    )


def _is_valid_time(text):
    parts = text.split(":")
    if len(parts) != 2:
        return False
    h, m = parts
    if not h.isdigit() or not m.isdigit():
        return False
    return len(h) == 2 and 0 <= int(h) <= 23 and 0 <= int(m) <= 59


def _notify_all_members(tontine_id, exclude_number, message):
    members = get_members(tontine_id)
    for member in members:
        if member["whatsapp_number"] != exclude_number:
            send_message(member["whatsapp_number"], message)


def notify_all_members_payment(tontine_id, payer_number, paid_count, total):
    members = get_members(tontine_id)
    tontine = get_tontine_by_id(tontine_id)
    for member in members:
        if member["whatsapp_number"] == payer_number:
            send_message(payer_number, f"✅ Paiement reçu ! ({paid_count}/{total})\n\nMerci, on attend les autres membres.")
        else:
            send_message(member["whatsapp_number"],
                f"✅ Paiement reçu pour *{tontine['name']}* ({paid_count}/{total})")
