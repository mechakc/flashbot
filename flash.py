# flash.py
from config import FLASH_API_KEY, FLASH_API_URL
from utils import http_get, http_post

TAG = "FLASH"


def buy_sats(amount_fcfa, lightning_wallet):
    """
    Achète des sats via l'API Flash et les envoie sur le wallet Lightning.

    PLACEHOLDER ACTIF — API Flash non encore intégrée.
    Retourne des valeurs fictives pour permettre les tests end-to-end.
    """
    if not FLASH_API_KEY:
        return _placeholder(amount_fcfa, lightning_wallet)

    return _real_api(amount_fcfa, lightning_wallet)


def _placeholder(amount_fcfa, lightning_wallet):
    """Simule un achat réussi pour les tests sans API Flash."""
    taux_sats_par_fcfa = 100_000_000 / 55_000_000
    sats_estimes = int(amount_fcfa * taux_sats_par_fcfa)

    print(f"[FLASH][PLACEHOLDER] Achat simulé : {amount_fcfa} FCFA → {sats_estimes} sats → {lightning_wallet}")

    return {
        "success": True,
        "sats": sats_estimes,
        "tx_id": "test_tx_placeholder_123",
        "wallet": lightning_wallet,
        "rate": taux_sats_par_fcfa
    }


def _real_api(amount_fcfa, lightning_wallet):
    """Intégration réelle API Flash."""
    headers = {
        "Authorization": f"Bearer {FLASH_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount_fcfa": amount_fcfa,
        "lightning_address": lightning_wallet,
        "currency": "XOF"
    }

    data = http_post(
        f"{FLASH_API_URL}/buy",
        headers=headers,
        json=payload,
        tag=TAG
    )

    if not data:
        return None

    print(f"[FLASH] Achat réel réussi ✅ : {data.get('sats')} sats")

    return {
        "success": True,
        "sats": data.get("sats", 0),
        "tx_id": data.get("transaction_id", ""),
        "wallet": lightning_wallet,
        "rate": data.get("rate", 0)
    }


def get_btc_rate():
    """Récupère le taux BTC/FCFA actuel depuis Flash."""
    if not FLASH_API_KEY:
        return _placeholder_rate()

    headers = {
        "Authorization": f"Bearer {FLASH_API_KEY}",
        "Content-Type": "application/json"
    }

    data = http_get(
        f"{FLASH_API_URL}/rate",
        headers=headers,
        tag=TAG
    )

    if not data:
        return _placeholder_rate()

    return data.get("fcfa_per_btc", 55_000_000)


def _placeholder_rate():
    """Taux fictif pour les tests."""
    print("[FLASH][PLACEHOLDER] Taux fictif utilisé : 55 000 000 FCFA/BTC")
    return 55_000_000
