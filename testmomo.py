# test_momo.py
import uuid
import base64
import requests
from config import MOMO_SUBSCRIPTION_KEY, MOMO_API_USER, MOMO_API_KEY, MOMO_ENVIRONMENT

MOMO_BASE_URL = "https://sandbox.momodeveloper.mtn.com"
COLLECTION_URL = f"{MOMO_BASE_URL}/collection/v1_0"

# Étape 1 — Token
print("\n[1] Test obtention token...")
credentials = f"{MOMO_API_USER}:{MOMO_API_KEY}"
encoded = base64.b64encode(credentials.encode()).decode()

token_headers = {
    "Authorization": f"Basic {encoded}",
    "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
}

response = requests.post(f"{MOMO_BASE_URL}/collection/token/", headers=token_headers)
print(f"Status token : {response.status_code}")
print(f"Body token : {response.text}")

if response.status_code != 200:
    print("❌ Échec token")
    exit()

token = response.json().get("access_token")
print(f"✅ Token obtenu : {token[:30]}...")

# Étape 2 — Request to Pay
print("\n[2] Test Request to Pay...")
momo_ref = str(uuid.uuid4())

headers = {
    "Authorization": f"Bearer {token}",
    "X-Reference-Id": momo_ref,
    "X-Target-Environment": MOMO_ENVIRONMENT,
    "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
    "Content-Type": "application/json"
}

payload = {
    "amount": "100",
    "currency": "EUR",
    "externalId": "test_001",
    "payer": {
        "partyIdType": "MSISDN",
        "partyId": "46733123454"
    },
    "payerMessage": "Test FlashBot",
    "payeeNote": "Test"
}

print(f"Référence : {momo_ref}")
response = requests.post(f"{COLLECTION_URL}/requesttopay", headers=headers, json=payload)
print(f"Status : {response.status_code}")
print(f"Body : {response.text}")

if response.status_code == 202:
    print("✅ Request to Pay envoyée !")
    
    # Étape 3 — Vérification statut
    import time
    print("\n[3] Vérification statut dans 3 secondes...")
    time.sleep(3)
    
    status_response = requests.get(
        f"{COLLECTION_URL}/requesttopay/{momo_ref}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": MOMO_ENVIRONMENT,
            "Ocp-Apim-Subscription-Key": MOMO_SUBSCRIPTION_KEY,
        }
    )
    print(f"Status : {status_response.status_code}")
    print(f"Body : {status_response.text}")
else:
    print("❌ Échec Request to Pay")