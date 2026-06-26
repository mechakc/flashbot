# whatsapp.py
import requests
from config import WHATSAPP_TOKEN, PHONE_NUMBER_ID

BASE_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

def send_message(to, text):
    """Envoie un message texte WhatsApp à un numéro."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        response = requests.post(BASE_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"[WA] Message envoyé à {to} ✅")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WA] Erreur envoi message à {to} : {e}")
        return None

def send_typing(to):
    """Envoie un indicateur 'en train d'écrire' (bonne pratique UX)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "reaction",
        "reaction": {"message_id": "", "emoji": "⚡"}
    }
    # Note : le vrai typing indicator nécessite l'API Business avancée
    # On skip silencieusement si ça échoue
    try:
        requests.post(BASE_URL, headers=HEADERS, json=payload)
    except Exception:
        pass

def mark_as_read(message_id):
    """Marque un message comme lu (double coche bleue)."""
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    try:
        requests.post(BASE_URL, headers=HEADERS, json=payload)
    except Exception:
        pass

def parse_incoming_message(data):
    """
    Parse le payload webhook Meta et extrait les infos essentielles.
    Retourne un dict ou None si ce n'est pas un message utilisateur.
    """
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Vérifier que c'est bien un message entrant
        if "messages" not in value:
            return None

        message = value["messages"][0]
        contact = value["contacts"][0]

        return {
            "from": message["from"],                        # numéro expéditeur
            "name": contact["profile"]["name"],             # prénom WhatsApp
            "message_id": message["id"],                    # ID du message
            "text": message.get("text", {}).get("body", "").strip().upper(),  # texte normalisé
            "raw_text": message.get("text", {}).get("body", "").strip(),      # texte brut
            "type": message["type"],                        # text / image / audio...
            "timestamp": message["timestamp"]
        }

    except (KeyError, IndexError, TypeError):
        return None

def is_valid_message(parsed):
    """Vérifie que le message est bien un message texte exploitable."""
    if parsed is None:
        return False
    if parsed["type"] != "text":
        return False
    if not parsed["text"]:
        return False
    return True