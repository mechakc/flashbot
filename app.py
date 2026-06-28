# app.py
import threading
from flask import Flask, request, jsonify

from config import VERIFY_TOKEN, PORT, DEBUG
from database import init_db
from whatsapp import parse_incoming_message, is_valid_message, mark_as_read
from commands import handle_message
from scheduler import PENDING_STACKS
from scheduler import start_scheduler, stop_scheduler, is_stack_pending, clear_pending_stack
from momo import wait_for_payment
from flash import buy_sats
from database import get_user, update_user, create_transaction, update_transaction
from whatsapp import send_message
from messages import msg_achat_reussi, msg_paiement_echoue

app = Flask(__name__)

# Verrou anti-doublon : évite de traiter 2 STACK simultanés pour le même user
PROCESSING_STACKS = set()
PROCESSED_MESSAGE_IDS = set()  # évite de traiter le même message Meta deux fois


# --- Webhook Meta WhatsApp ---

@app.route("/webhook", methods=["GET"])
def webhook_verify():
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
    data = request.get_json()

    if not data:
        return jsonify({"status": "no data"}), 400

    parsed = parse_incoming_message(data)

    if not is_valid_message(parsed):
        return jsonify({"status": "ignored"}), 200

    from_number = parsed["from"]
    text = parsed["text"]
    raw_text = parsed["raw_text"]
    message_id = parsed["message_id"]

    # Dédupliquer — Meta renvoie parfois le même message plusieurs fois
    if message_id in PROCESSED_MESSAGE_IDS:
        print(f"[WEBHOOK] Message {message_id} déjà traité, ignoré")
        return jsonify({"status": "duplicate"}), 200
    PROCESSED_MESSAGE_IDS.add(message_id)
    # Garder max 1000 IDs en mémoire
    if len(PROCESSED_MESSAGE_IDS) > 1000:
        PROCESSED_MESSAGE_IDS.clear()

    mark_as_read(message_id)
    print(f"[WEBHOOK] Message reçu de {from_number} : '{text}'")

    if text == "STACK":
        user = get_user(from_number)
        if user and user["is_active"]:
            # Anti-doublon : si déjà en cours de traitement, ignorer
            if from_number in PROCESSING_STACKS:
                print(f"[WEBHOOK] STACK déjà en cours pour {from_number}, ignoré")
                return jsonify({"status": "already_processing"}), 200

            PROCESSING_STACKS.add(from_number)
            threading.Thread(
                target=_process_stack_payment,
                args=(from_number, user),
                daemon=True
            ).start()
            return jsonify({"status": "stack_processing"}), 200

    handle_message(from_number, text, raw_text)
    return jsonify({"status": "ok"}), 200


# --- Traitement paiement STACK dans un thread ---

def _process_stack_payment(from_number, user):
    from momo import request_to_pay

    amount = user["dca_amount_fcfa"]

    send_message(from_number, f"📲 Demande de paiement envoyée !\n\nVérifie ton téléphone MTN MoMo pour *{amount} FCFA* et entre ton PIN. J'attends... ⏳")

    tx_id = create_transaction(user["id"], amount)

    momo_result = request_to_pay(
        amount=amount,
        phone_number=user["momo_number"],
        tx_id=str(tx_id)
    )

    if not momo_result["success"]:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        PROCESSING_STACKS.discard(from_number)
        return

    momo_ref = momo_result["transaction_id"]
    update_transaction(tx_id, momo_tx_id=momo_ref, status="momo_pending")

    payment_confirmed = wait_for_payment(momo_ref, max_attempts=10, delay=5)

    if not payment_confirmed:
        update_transaction(tx_id, status="failed")
        send_message(from_number, msg_paiement_echoue(amount))
        PROCESSING_STACKS.discard(from_number)
        return

    update_transaction(tx_id, status="momo_success")

    flash_result = buy_sats(amount, user["lightning_wallet"])

    if not flash_result:
        update_transaction(tx_id, status="flash_failed")
        send_message(from_number, f"❌ Paiement MoMo reçu mais erreur côté Flash. Contacte le support. (ref: {tx_id})")
        PROCESSING_STACKS.discard(from_number)
        return

    sats_received = flash_result.get("sats", 0)
    flash_tx_id = flash_result.get("tx_id", "")

    update_transaction(tx_id, sats_received=sats_received, flash_tx_id=flash_tx_id, status="success")
    new_total = (user["total_sats"] or 0) + sats_received
    update_user(from_number, total_sats=new_total)

    clear_pending_stack(from_number)
    PROCESSING_STACKS.discard(from_number)

    send_message(from_number, msg_achat_reussi(sats_received, new_total, amount))
    print(f"[STACK] Transaction complète ✅ — {from_number} — {sats_received} sats")


# --- Routes ---

@app.route("/health", methods=["GET"])
def health():
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
    init_db()
    start_scheduler()
    try:
        app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[APP] Arrêt demandé...")
        stop_scheduler()
        print("[APP] FlashBot arrêté proprement ✅")
