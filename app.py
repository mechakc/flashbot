# app.py
import threading
from flask import Flask, request, jsonify

from config import VERIFY_TOKEN, PORT, DEBUG
from database import init_db
from whatsapp import parse_incoming_message, is_valid_message, mark_as_read
from commands import handle_message, PENDING_STACKS
from scheduler import start_scheduler, stop_scheduler, is_stack_pending, clear_pending_stack
from momo import wait_for_payment
from flash import buy_sats
from database import get_user, update_user, create_transaction, update_transaction
from whatsapp import send_message
from messages import msg_achat_reussi, msg_paiement_echoue

app = Flask(__name__)


# --- Webhook Meta WhatsApp ---

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """
    Vérification du webhook par Meta.
    Meta envoie un GET avec hub.challenge — on doit répondre avec ce challenge.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[WEBHOOK] Vérification réussie ✅")
        return challenge, 200
    else:
        print("[WEBHOOK] Vérification échouée ❌")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """
    Réception des messages WhatsApp entrants.
    Meta envoie un POST pour chaque message reçu.
    """
    data = request.get_json()

    if not data:
        return jsonify({"status": "no data"}), 400

    # Parser le message entrant
    parsed = parse_incoming_message(data)

    if not is_valid_message(parsed):
        # Pas un message texte exploitable — on répond 200 quand même
        # (Meta renvoie si on ne répond pas 200)
        return jsonify({"status": "ignored"}), 200

    from_number = parsed["from"]
    text = parsed["text"]            # majuscules
    raw_text = parsed["raw_text"]    # brut
    message_id = parsed["message_id"]

    # Marquer comme lu immédiatement
    mark_as_read(message_id)

    print(f"[WEBHOOK] Message reçu de {from_number} : '{text}'")

    # Si c'est un STACK → traitement spécial avec MoMo dans un thread séparé
    if text == "STACK":
        user = get_user(from_number)
        if user and user["is_active"]:
            threading.Thread(
                target=_process_stack_payment,
                args=(from_number, user),
                daemon=True
            ).start()
            return jsonify({"status": "stack_processing"}), 200

    # Tous les autres messages → handler normal
    handle_message(from_number, text, raw_text)

    return jsonify({"status": "ok"}), 200


# --- Traitement paiement STACK dans un thread ---

def _process_stack_payment(from_number, user):
    """
    Traite le paiement MoMo + achat Flash dans un thread séparé.
    Nécessaire pour ne pas bloquer le webhook (Meta timeout à 20s).
    """
    from momo import request_to_pay

    amount = user["dca_amount_fcfa"]

    # Envoyer message d'attente
    send_message(from_number, f"📲 Demande de paiement envoyée !\n\nVérifie ton téléphone MTN MoMo pour *{amount} FCFA* et entre ton PIN. J'attends... ⏳")

    # Créer transaction en base
    tx_id = create_transaction(user["id"], amount)

    # Request to Pay MoMo
    momo_result = request_to_pay(
        amount=amount,
        phone_number=user["momo_number"],
        tx_id=str(tx_id)
    )

    if not momo_result["success"]:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        return

    momo_ref = momo_result["transaction_id"]
    update_transaction(tx_id, momo_tx_id=momo_ref, status="momo_pending")

    # Polling statut paiement (max 50 secondes)
    payment_confirmed = wait_for_payment(momo_ref, max_attempts=10, delay=5)

    if not payment_confirmed:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        return

    update_transaction(tx_id, status="momo_success")

    # Achat sats sur Flash
    flash_result = buy_sats(amount, user["lightning_wallet"])

    if not flash_result:
        update_transaction(tx_id, status="flash_failed")
        send_message(from_number, f"❌ Paiement MoMo reçu mais erreur côté Flash. Contacte le support. (ref: {tx_id})")
        return

    sats_received = flash_result.get("sats", 0)
    flash_tx_id = flash_result.get("tx_id", "")

    # Mise à jour base de données
    update_transaction(tx_id, sats_received=sats_received, flash_tx_id=flash_tx_id, status="success")
    new_total = (user["total_sats"] or 0) + sats_received
    update_user(from_number, total_sats=new_total)

    # Nettoyer le pending stack
    clear_pending_stack(from_number)

    # Confirmation finale
    send_message(from_number, msg_achat_reussi(sats_received, new_total, amount))
    print(f"[STACK] Transaction complète ✅ — {from_number} — {sats_received} sats")


# --- Route de santé ---

@app.route("/health", methods=["GET"])
def health():
    """Vérifie que le serveur tourne — utile pour Railway/Render."""
    return jsonify({
        "status": "ok",
        "service": "FlashBot DCA",
        "pending_stacks": len(PENDING_STACKS)
    }), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "FlashBot DCA ⚡",
        "status": "running",
        "version": "1.0"
    }), 200


# --- Démarrage ---

if __name__ == "__main__":
    print("⚡ Démarrage FlashBot DCA...")

    # Initialiser la base de données
    init_db()

    # Démarrer le scheduler
    start_scheduler()

    try:
        app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
    except KeyboardInterrupt:
        print("\n[APP] Arrêt demandé...")
        stop_scheduler()
        print("[APP] FlashBot arrêté proprement ✅")