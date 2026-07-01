# app.py
import threading
from flask import Flask, request, jsonify, render_template

from config import VERIFY_TOKEN, PORT, DEBUG
from database import init_db, get_payment_by_hash, update_payment, get_tontine_by_id
from database import get_current_round, count_paid_in_round, get_members
from whatsapp import parse_incoming_message, is_valid_message, mark_as_read
from commands import handle_message
from scheduler import start_scheduler, stop_scheduler, _confirm_payment
from whatsapp import send_message
from api_routes import register_api_routes

app = Flask(__name__)

PROCESSED_MESSAGE_IDS = set()


# ==============================================================
# DASHBOARD WEB
# ==============================================================

@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


# Enregistre toutes les routes /api/*
register_api_routes(app)


# ==============================================================
# WEBHOOK WHATSAPP
# ==============================================================

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[WEBHOOK] Vérification réussie ✅")
        return challenge, 200
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

    if message_id in PROCESSED_MESSAGE_IDS:
        return jsonify({"status": "duplicate"}), 200
    PROCESSED_MESSAGE_IDS.add(message_id)
    if len(PROCESSED_MESSAGE_IDS) > 1000:
        PROCESSED_MESSAGE_IDS.clear()

    mark_as_read(message_id)
    print(f"[WEBHOOK] Message de {from_number} : '{text}'")

    threading.Thread(
        target=handle_message,
        args=(from_number, text, raw_text),
        daemon=True
    ).start()

    return jsonify({"status": "ok"}), 200


# ==============================================================
# WEBHOOK LNBITS — confirmation paiement
# ==============================================================

@app.route("/lnbits/webhook", methods=["POST"])
def lnbits_webhook():
    data = request.get_json()
    if not data:
        return jsonify({"status": "no data"}), 400

    payment_hash = data.get("payment_hash")
    if not payment_hash:
        return jsonify({"status": "no hash"}), 400

    print(f"[LNBITS WEBHOOK] Paiement reçu — hash: {payment_hash[:16]}...")

    try:
        payment = get_payment_by_hash(payment_hash)
    except Exception as e:
        print(f"[LNBITS WEBHOOK] Erreur DB recherche paiement : {e}")
        return jsonify({"status": "error", "detail": "database error"}), 500

    if not payment:
        print(f"[LNBITS WEBHOOK] Paiement introuvable en DB")
        return jsonify({"status": "not found"}), 200

    if payment["status"] == "paid":
        return jsonify({"status": "already_paid"}), 200

    try:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tontine_rounds WHERE id = ?", (payment["round_id"],))
        current_round = cursor.fetchone()
        conn.close()
    except Exception as e:
        print(f"[LNBITS WEBHOOK] Erreur DB recherche round : {e}")
        return jsonify({"status": "error", "detail": "database error"}), 500

    if not current_round:
        return jsonify({"status": "round not found"}), 200

    tontine_id = current_round["tontine_id"]

    threading.Thread(
        target=_confirm_payment,
        args=(tontine_id, current_round, payment),
        daemon=True
    ).start()

    return jsonify({"status": "ok"}), 200


# ==============================================================
# ROUTES UTILITAIRES
# ==============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "TontineBot", "version": "1.0"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "TontineBot ⚡", "status": "running", "dashboard": "/dashboard"}), 200


# ==============================================================
# DÉMARRAGE
# ==============================================================

if __name__ == "__main__":
    print("⚡ Démarrage TontineBot...")
    init_db()
    start_scheduler()
    try:
        app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[APP] Arrêt...")
        stop_scheduler()
        print("[APP] TontineBot arrêté ✅")
