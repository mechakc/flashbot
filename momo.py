# momo.py
import requests
import uuid
import base64
from config import MOMO_SUBSCRIPTION_KEY, MOMO_API_USER, MOMO_API_KEY, MOMO_ENVIRONMENT, MOMO_BASE_URL

COLLECTION_URL = f"{MOMO_BASE_URL}/collection/v1_0"

def _get_auth_token():
    """Génère un token d'accès OAuth2 via les credentials MoMo."""
    credentials = f"{MOMO_API_USER}:{MOMO_API_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded}",
        "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
    }

    try:
        response = requests.post(
            f"{MOMO_BASE_URL}/collection/token/",
            headers=headers
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        print(f"[MOMO] Token obtenu ✅")
        return token
    except requests.exceptions.RequestException as e:
        print(f"[MOMO] Erreur obtention token : {e}")
        return None


def request_to_pay(amount, phone_number, tx_id):
    """
    Envoie une demande de paiement MoMo (Request to Pay).
    Retourne dict avec success + transaction_id.
    """
    token = _get_auth_token()
    if not token:
        return {"success": False, "error": "Token MoMo indisponible"}

    # En sandbox, le seul numéro accepté est le numéro de test MTN
    if MOMO_ENVIRONMENT == "sandbox":
        phone_number = "46733123454"

    # Référence unique pour cette transaction
    momo_ref = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": momo_ref,
        "X-Target-Environment": MOMO_ENVIRONMENT,
        "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "amount": str(amount),
        "currency": "EUR" if MOMO_ENVIRONMENT == "sandbox" else "XOF",
        "externalId": str(uuid.uuid4()),  # UUID requis par MTN sandbox
        "payer": {
            "partyIdType": "MSISDN",
            "partyId": phone_number
        },
        "payerMessage": f"FlashBot DCA {amount} FCFA",
        "payeeNote": "Achat sats Bitcoin"
    }

    try:
        response = requests.post(
            f"{COLLECTION_URL}/requesttopay",
            headers=headers,
            json=payload
        )

        # 202 Accepted = demande envoyée, en attente de confirmation PIN
        if response.status_code == 202:
            print(f"[MOMO] Request to Pay envoyée ✅ ref={momo_ref}")
            return {"success": True, "transaction_id": momo_ref}
        else:
            print(f"[MOMO] Erreur Request to Pay : {response.status_code}")
            print(f"[MOMO] Headers réponse : {dict(response.headers)}")
            print(f"[MOMO] Body réponse : {response.text}")
            return {"success": False, "error": response.text}

    except requests.exceptions.RequestException as e:
        print(f"[MOMO] Erreur réseau : {e}")
        return {"success": False, "error": str(e)}


def check_payment_status(momo_ref):
    """
    Vérifie le statut d'une transaction MoMo par sa référence.
    Retourne : 'SUCCESSFUL', 'FAILED', ou 'PENDING'
    """
    token = _get_auth_token()
    if not token:
        return "FAILED"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Target-Environment": MOMO_ENVIRONMENT,
        "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
    }

    try:
        response = requests.get(
            f"{COLLECTION_URL}/requesttopay/{momo_ref}",
            headers=headers
        )
        response.raise_for_status()
        status = response.json().get("status", "FAILED")
        print(f"[MOMO] Statut transaction {momo_ref} : {status}")
        return status

    except requests.exceptions.RequestException as e:
        print(f"[MOMO] Erreur vérification statut : {e}")
        return "FAILED"


def wait_for_payment(momo_ref, max_attempts=10, delay=5):
    """
    Polling du statut de paiement jusqu'à confirmation ou échec.
    Attend max max_attempts * delay secondes.
    """
    import time

    for attempt in range(max_attempts):
        status = check_payment_status(momo_ref)

        if status == "SUCCESSFUL":
            print(f"[MOMO] Paiement confirmé ✅ après {attempt + 1} tentative(s)")
            return True

        if status == "FAILED":
            print(f"[MOMO] Paiement échoué ❌")
            return False

        print(f"[MOMO] En attente... tentative {attempt + 1}/{max_attempts}")
        time.sleep(delay)

    print(f"[MOMO] Timeout — paiement non confirmé après {max_attempts * delay}s")
    return False