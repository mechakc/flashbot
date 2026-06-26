from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "flashbot_secret_2026"

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    print(f"Mode: {mode}, Token: {token}, Challenge: {challenge}")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook vérifié !")
        return challenge, 200
    return "Erreur token", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    return "OK", 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)