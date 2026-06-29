# lnbits.py
import requests
from config import LNBITS_URL, LNBITS_API_KEY, LNBITS_WALLET_ID

HEADERS = {
    "X-Api-Key": LNBITS_API_KEY,
    "Content-Type": "application/json"
}


def create_invoice(amount_sats, memo, webhook_url=None):
    """
    Crée une invoice Lightning pour qu'un membre paie.
    Retourne { success, payment_request, payment_hash } ou None.
    
    amount_sats  : montant en satoshis
    memo         : description visible par le payeur
    webhook_url  : URL que LNbits appellera quand l'invoice est payée
    """
    payload = {
        "out": False,
        "amount": amount_sats,
        "memo": memo,
        "webhook": webhook_url
    }

    try:
        response = requests.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        print(f"[LNBITS] Invoice créée ✅ hash={data['payment_hash'][:16]}...")

        return {
            "success": True,
            "payment_request": data["payment_request"],  # invoice à scanner
            "payment_hash": data["payment_hash"]          # ID pour vérifier le statut
        }

    except requests.exceptions.RequestException as e:
        print(f"[LNBITS] Erreur création invoice : {e}")
        return None


def check_invoice(payment_hash):
    """
    Vérifie si une invoice a été payée.
    Retourne True si payée, False sinon.
    """
    try:
        response = requests.get(
            f"{LNBITS_URL}/api/v1/payments/{payment_hash}",
            headers=HEADERS
        )
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
    
    Supporte :
    - Lightning Address : user@domain.com
    - LNURL
    - Invoice directe : lnbc...
    """
    try:
        # Si c'est une Lightning Address (user@domain.com), on résout d'abord
        if "@" in lightning_address and not lightning_address.startswith("lnbc"):
            invoice = _resolve_lightning_address(lightning_address, amount_sats, memo)
            if not invoice:
                print(f"[LNBITS] Impossible de résoudre l'adresse {lightning_address}")
                return None
        else:
            invoice = lightning_address  # déjà une invoice

        # Payer l'invoice
        payload = {
            "out": True,
            "bolt11": invoice
        }

        response = requests.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        print(f"[LNBITS] Paiement envoyé ✅ vers {lightning_address}")

        return {
            "success": True,
            "payment_hash": data.get("payment_hash", "")
        }

    except requests.exceptions.RequestException as e:
        print(f"[LNBITS] Erreur envoi paiement : {e}")
        return None


def _resolve_lightning_address(lightning_address, amount_sats, memo):
    """
    Résout une Lightning Address (user@domain.com) en invoice payable.
    Protocol : https://lightningaddress.com
    """
    try:
        user, domain = lightning_address.split("@")
        amount_msats = amount_sats * 1000  # millisatoshis

        # Étape 1 : récupérer le LNURL endpoint
        lnurl_resp = requests.get(
            f"https://{domain}/.well-known/lnurlp/{user}",
            timeout=10
        )
        lnurl_resp.raise_for_status()
        lnurl_data = lnurl_resp.json()

        # Vérifier les limites
        min_sendable = lnurl_data.get("minSendable", 0)
        max_sendable = lnurl_data.get("maxSendable", float("inf"))

        if not (min_sendable <= amount_msats <= max_sendable):
            print(f"[LNBITS] Montant hors limites : {amount_msats} msats")
            return None

        # Étape 2 : demander l'invoice
        callback = lnurl_data["callback"]
        invoice_resp = requests.get(
            callback,
            params={"amount": amount_msats, "comment": memo},
            timeout=10
        )
        invoice_resp.raise_for_status()
        invoice_data = invoice_resp.json()

        return invoice_data.get("pr")  # payment request (invoice)

    except Exception as e:
        print(f"[LNBITS] Erreur résolution Lightning Address : {e}")
        return None


def get_wallet_balance():
    """
    Retourne le solde du wallet bot en satoshis.
    Utile pour vérifier qu'on a assez avant d'envoyer.
    """
    try:
        response = requests.get(
            f"{LNBITS_URL}/api/v1/wallet",
            headers=HEADERS
        )
        response.raise_for_status()
        data = response.json()

        balance_sats = data["balance"] // 1000  # msat → sats
        print(f"[LNBITS] Solde wallet : {balance_sats} sats")
        return balance_sats

    except requests.exceptions.RequestException as e:
        print(f"[LNBITS] Erreur récupération solde : {e}")
        return None


def test_connection():
    """
    Teste la connexion à LNbits.
    Retourne True si OK, False sinon.
    """
    balance = get_wallet_balance()
    if balance is not None:
        print(f"[LNBITS] Connexion OK ✅ — solde : {balance} sats")
        return True
    print("[LNBITS] Connexion échouée ❌")
    return False
