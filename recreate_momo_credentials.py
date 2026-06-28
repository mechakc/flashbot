# recreate_momo_credentials.py
# Lance ce script sur TON terminal local : python3 recreate_momo_credentials.py
import requests
import uuid

SUBSCRIPTION_KEY = "1172ca5aa3cb43afb41aae5fec134f16"
BASE_URL = "https://sandbox.momodeveloper.mtn.com"

print("🔄 Création de nouveaux credentials MoMo sandbox...\n")

# Étape 1 : Créer un nouvel API User
new_uuid = str(uuid.uuid4())
print(f"UUID généré : {new_uuid}")

resp = requests.post(
    f"{BASE_URL}/v1_0/apiuser",
    headers={
        "X-Reference-Id": new_uuid,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Type": "application/json"
    },
    json={"providerCallbackHost": "webhook.site"}
)
print(f"Création API User : {resp.status_code}")

if resp.status_code != 201:
    print(f"❌ Échec : {resp.text}")
    exit()

print("✅ API User créé !")

# Étape 2 : Créer l'API Key
resp2 = requests.post(
    f"{BASE_URL}/v1_0/apiuser/{new_uuid}/apikey",
    headers={
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    }
)
print(f"Création API Key : {resp2.status_code}")

if resp2.status_code != 201:
    print(f"❌ Échec : {resp2.text}")
    exit()

api_key = resp2.json().get("apiKey")
print("✅ API Key créée !")

# Étape 3 : Tester le token
import base64
credentials = f"{new_uuid}:{api_key}"
encoded = base64.b64encode(credentials.encode()).decode()

resp3 = requests.post(
    f"{BASE_URL}/collection/token/",
    headers={
        "Authorization": f"Basic {encoded}",
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    }
)
print(f"Test token : {resp3.status_code}")

if resp3.status_code == 200:
    print("✅ Token OK — credentials valides !\n")
    print("=" * 50)
    print("👇 Mets ces valeurs dans ton .env :")
    print("=" * 50)
    print(f"MOMO_API_USER={new_uuid}")
    print(f"MOMO_API_KEY={api_key}")
    print("=" * 50)
else:
    print(f"❌ Token échoué : {resp3.text}")
