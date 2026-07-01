# lnbits.py
import requests
from config import LNBITS_URL, LNBITS_API_KEY, LNBITS_WALLET_ID
from utils import http_get, http_post

HEADERS = {
    "X-Api-Key": LNBITS_API_KEY,
    "Content-Type": "application/json"
}

TAG = "LNBITS"


def create_invoice(amount_sats, memo, webhook_url=None):
    """
    Crée une invoice Lightning pour qu'un membre paie.
    Retourne { success, payment_request, payment_hash } ou None.
    """
    payload = {
        "out": False,
        "amount": amount_sats,
        "memo": memo,
        "webhook": webhook_url
    }

    data = http_post(
        f"{LNBITS_URL}/api/v1/payments",
        headers=HEADERS,
        json=payload,
        timeout=15,
        tag=TAG
    )

    if not data:
        return None

    print(f"[LNBITS] Invoice créée ✅ hash={data['payment_hash'][:16]}...")

    return {
        "success": True,
        "payment_request": data["payment_request"],
        "payment_hash": data["payment_hash"]
    }


def check_invoice(payment_hash):
    """
    Vérifie si une invoice a été payée.
    Retourne :
      - True  → payée
      - False → en attente (ou erreur réseau transitoire, on réessaiera)
      - None  → invoice introuvable côté LNbits (404, probablement orpheline)
    """
    try:
        response = requests.get(
            f"{LNBITS_URL}/api/v1/payments/{payment_hash}",
            headers=HEADERS,
            timeout=10
        )

        if response.status_code == 404:
            print(f"[LNBITS] Invoice {payment_hash[:16]}... introuvable côté LNbits (404) — probablement orpheline")
            return None

        response.raise_for_status()
        data = response.json()

        paid = data.get("paid", False)
        print(f"[LNBITS] Statut invoice {payment_hash[:16]}... : {'PAID' if paid else 'PENDING'}")
        return paid

    except requests.exceptions.RequestException as e:
        print(f"[LNBITS] Erreur vérification invoice : {e}")
        return False


def send_payment(lightning_address, amount_sats, memo="TontineBot payout"):
    """
    Envoie des sats à une adresse Lightning (lightning address ou invoice).
    Retourne { success, payment_hash } ou None.
    """
    try:
        if "@" in lightning_address and not lightning_address.startswith("lnbc"):
            invoice = _resolve_lightning_address(lightning_address, amount_sats, memo)
            if not invoice:
                print(f"[LNBITS] Impossible de résoudre l'adresse {lightning_address}")
                return None
        else:
            invoice = lightning_address

        payload = {
            "out": True,
            "bolt11": invoice
        }

        data = http_post(
            f"{LNBITS_URL}/api/v1/payments",
            headers=HEADERS,
            json=payload,
            timeout=15,
            tag=TAG
        )

        if not data:
            return None

        print(f"[LNBITS] Paiement envoyé ✅ vers {lightning_address}")

        return {
            "success": True,
            "payment_hash": data.get("payment_hash", "")
        }

    except Exception as e:
        print(f"[LNBITS] Erreur envoi paiement : {e}")
        return None


def _resolve_lightning_address(lightning_address, amount_sats, memo):
    """
    Résout une Lightning Address (user@domain.com) en invoice payable.
    Protocol : https://lightningaddress.com
    """
    try:
        user, domain = lightning_address.split("@")
        amount_msats = amount_sats * 1000

        lnurl_data = http_get(
            f"https://{domain}/.well-known/lnurlp/{user}",
            timeout=10,
            tag=TAG
        )

        if not lnurl_data:
            return None

        min_sendable = lnurl_data.get("minSendable", 0)
        max_sendable = lnurl_data.get("maxSendable", float("inf"))

        if not (min_sendable <= amount_msats <= max_sendable):
            print(f"[LNBITS] Montant hors limites : {amount_msats} msats")
            return None

        callback = lnurl_data["callback"]
        invoice_data = http_get(
            callback,
            params={"amount": amount_msats, "comment": memo},
            timeout=10,
            tag=TAG
        )

        if not invoice_data:
            return None

        return invoice_data.get("pr")

    except Exception as e:
        print(f"[LNBITS] Erreur résolution Lightning Address : {e}")
        return None


def get_wallet_balance():
    """Retourne le solde du wallet bot en satoshis."""
    data = http_get(
        f"{LNBITS_URL}/api/v1/wallet",
        headers=HEADERS,
        timeout=10,
        tag=TAG
    )

    if not data:
        return None

    balance_sats = data["balance"] // 1000
    print(f"[LNBITS] Solde wallet : {balance_sats} sats")
    return balance_sats


def test_connection():
    """Teste la connexion à LNbits. Retourne True si OK, False sinon."""
    balance = get_wallet_balance()
    if balance is not None:
        print(f"[LNBITS] Connexion OK ✅ — solde : {balance} sats")
        return True
    print("[LNBITS] Connexion échouée ❌")
    return False
