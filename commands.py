# commands.py
import random
import string
from database import (
    create_tontine, get_tontine_by_code, get_tontine_by_id,
    get_tontine_by_member, update_tontine,
    add_member, get_members, get_member, count_members,
    get_member_by_id, get_all_rounds, get_current_round,
    get_payments_for_round, count_paid_in_round
)
from whatsapp import send_message
from messages import *

# États en attente de réponse
# { "2290123456": {"step": "await_wallet", "tontine_id": 3} }
PENDING_JOINS = {}

# { "2290123456": {"step": "await_name", ...} }
PENDING_CREATES = {}


def handle_message(from_number, text, raw_text):

    # Priorité aux états en cours
    if from_number in PENDING_CREATES:
        return handle_create_step(from_number, text, raw_text)

    if from_number in PENDING_JOINS:
        return handle_join_step(from_number, text, raw_text)

    # Commandes principales
    if text == "AIDE":
        return send_message(from_number, MSG_AIDE)

    if text.startswith("CREER"):
        return handle_creer(from_number, text, raw_text)

    if text.startswith("REJOINDRE"):
        return handle_rejoindre(from_number, text, raw_text)

    if text == "TONTINE":
        return handle_tontine(from_number)

    if text == "MEMBRES":
        return handle_membres(from_number)

    if text == "HISTORIQUE":
        return handle_historique(from_number)

    return send_message(from_number, MSG_COMMANDE_INCONNUE)


# ==============================================================
# CREER
# ==============================================================

def handle_creer(from_number, text, raw_text):
    """
    Syntaxe : CREER NOM MONTANT MEMBRES
    Ex : CREER MaFamille 5000 3
    """
    # Vérifier si déjà dans une tontine active
    existing = get_tontine_by_member(from_number)
    if existing:
        send_message(from_number, f"⚠️ Tu es déjà dans une tontine active (*{existing['name']}*).\n\nTape *TONTINE* pour voir son statut.")
        return

    parts = raw_text.strip().split()

    # Si la commande est complète : CREER NOM MONTANT MEMBRES
    if len(parts) == 4:
        _, name, amount_str, members_str = parts
        error = _validate_creer(name, amount_str, members_str)
        if error:
            send_message(from_number, error)
            return
        _do_create_tontine(from_number, name, int(amount_str), int(members_str))
        return

    # Sinon flux conversationnel
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
        if not raw_text.isdigit() or not (2 <= int(raw_text) <= 10):
            send_message(from_number, "⚠️ Nombre de membres invalide. Entre 2 et 10.")
            return
        state = PENDING_CREATES[from_number]
        del PENDING_CREATES[from_number]
        _do_create_tontine(from_number, state["name"], state["amount"], int(raw_text))


def _validate_creer(name, amount_str, members_str):
    if len(name) < 2 or len(name) > 30:
        return "⚠️ Nom invalide (2-30 caractères)."
    if not amount_str.isdigit() or int(amount_str) < 100:
        return "⚠️ Montant invalide. Minimum 100 sats."
    if not members_str.isdigit() or not (2 <= int(members_str) <= 10):
        return "⚠️ Nombre de membres invalide (2-10)."
    return None


def _do_create_tontine(from_number, name, amount_sats, max_members):
    """Crée la tontine + ajoute le créateur comme membre #1."""
    code = _generate_code()

    tontine_id = create_tontine(
        name=name,
        code=code,
        amount_sats=amount_sats,
        max_members=max_members,
        created_by=from_number
    )

    if not tontine_id:
        send_message(from_number, "❌ Erreur lors de la création. Réessaie.")
        return

    # Demander le wallet du créateur
    PENDING_JOINS[from_number] = {
        "step": "await_wallet",
        "tontine_id": tontine_id,
        "code": code,
        "name": name,
        "amount_sats": amount_sats,
        "max_members": max_members,
        "is_creator": True
    }

    send_message(from_number, f"✅ Tontine *{name}* créée !\n\n⚡ *Quel est ton wallet Lightning ?*\n(Ex: tonnom@cake.cash)")


# ==============================================================
# REJOINDRE
# ==============================================================

def handle_rejoindre(from_number, text, raw_text):
    """
    Syntaxe : REJOINDRE CODE
    Ex : REJOINDRE TONT-4X7K
    """
    # Déjà dans une tontine ?
    existing = get_tontine_by_member(from_number)
    if existing:
        send_message(from_number, f"⚠️ Tu es déjà dans une tontine active (*{existing['name']}*).\n\nTape *TONTINE* pour voir son statut.")
        return

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

    # Déjà membre ?
    if get_member(tontine["id"], from_number):
        send_message(from_number, "⚠️ Tu es déjà membre de cette tontine.")
        return

    # Demander le wallet
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
        code = tontine["code"]

        # Message de confirmation au nouveau membre
        if state["is_creator"]:
            send_message(from_number, msg_tontine_creee(name, code, state["amount_sats"], max_members))
        else:
            send_message(from_number, msg_membre_rejoint(name, current_count, max_members))

        # Notifier les autres membres
        if not state["is_creator"]:
            _notify_all_members(tontine_id, from_number,
                f"👋 Un nouveau membre a rejoint *{name}* ! ({current_count}/{max_members})")

        # Lancement automatique si tontine complète
        if current_count >= max_members:
            _launch_tontine(tontine_id)


# ==============================================================
# LANCEMENT AUTOMATIQUE
# ==============================================================

def _launch_tontine(tontine_id):
    """Lance la tontine dès que tous les membres sont inscrits."""
    from scheduler import start_first_round

    tontine = get_tontine_by_id(tontine_id)
    members = get_members(tontine_id)

    update_tontine(tontine_id, status="active", current_round=0)

    # Construire la liste des tours
    ordre = "\n".join([
        f"   Tour {m['turn_order']} → {'toi' if False else 'membre ' + str(m['turn_order'])}"
        for m in members
    ])

    # Notifier chaque membre avec son ordre personnalisé
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
            ordre_perso
        ))

    print(f"[TONTINE] Tontine {tontine['name']} lancée ✅")

    # Démarrer le premier round via le scheduler
    start_first_round(tontine_id)


# ==============================================================
# TONTINE — voir statut
# ==============================================================

def handle_tontine(from_number):
    tontine = get_tontine_by_member(from_number)
    if not tontine:
        send_message(from_number, "❌ Tu n'es dans aucune tontine active.\n\nTape *CREER* ou *REJOINDRE CODE* pour commencer.")
        return

    members = get_members(tontine["id"])
    current_round = get_current_round(tontine["id"])

    if tontine["status"] == "waiting":
        current_count = len(members)
        send_message(from_number, msg_statut_waiting(
            tontine["name"],
            tontine["code"],
            current_count,
            tontine["max_members"],
            tontine["amount_sats"]
        ))
        return

    if tontine["status"] == "active" and current_round:
        payments = get_payments_for_round(current_round["id"])
        paid_count = count_paid_in_round(current_round["id"])
        total = len(members)

        # Trouver le bénéficiaire de ce tour
        beneficiary = get_member_by_id(current_round["beneficiary_member_id"])

        # Savoir si ce membre a payé
        member = get_member(tontine["id"], from_number)
        my_payment = next(
            (p for p in payments if p["member_id"] == member["id"]),
            None
        ) if member else None

        send_message(from_number, msg_statut_active(
            tontine["name"],
            current_round["round_number"],
            tontine["current_round"],  # total rounds = nb membres
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

def handle_membres(from_number):
    tontine = get_tontine_by_member(from_number)
    if not tontine:
        send_message(from_number, "❌ Tu n'es dans aucune tontine active.")
        return

    members = get_members(tontine["id"])
    send_message(from_number, msg_liste_membres(tontine["name"], members, from_number))


# ==============================================================
# HISTORIQUE
# ==============================================================

def handle_historique(from_number):
    tontine = get_tontine_by_member(from_number)

    # Chercher aussi les tontines terminées
    if not tontine:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.* FROM tontines t
            JOIN tontine_members m ON m.tontine_id = t.id
            WHERE m.whatsapp_number = ?
            ORDER BY t.created_at DESC LIMIT 1
        """, (from_number,))
        tontine = cursor.fetchone()
        conn.close()

    if not tontine:
        send_message(from_number, "❌ Aucune tontine trouvée.")
        return

    rounds = get_all_rounds(tontine["id"])
    send_message(from_number, msg_historique(tontine["name"], rounds, tontine["amount_sats"]))


# ==============================================================
# UTILITAIRES
# ==============================================================

def _generate_code():
    """Génère un code unique type TONT-XXXX."""
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


def _notify_all_members(tontine_id, exclude_number, message):
    """Envoie un message à tous les membres sauf un."""
    members = get_members(tontine_id)
    for member in members:
        if member["whatsapp_number"] != exclude_number:
            send_message(member["whatsapp_number"], message)


def notify_all_members_payment(tontine_id, payer_number, paid_count, total):
    """Notifie tous les membres qu'un paiement a été reçu."""
    members = get_members(tontine_id)
    tontine = get_tontine_by_id(tontine_id)

    for member in members:
        if member["whatsapp_number"] == payer_number:
            send_message(payer_number, f"✅ Paiement reçu ! ({paid_count}/{total})\n\nMerci, on attend les autres membres.")
        else:
            send_message(member["whatsapp_number"],
                f"✅ Paiement reçu pour *{tontine['name']}* ({paid_count}/{total})"
            )
