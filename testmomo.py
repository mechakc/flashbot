# test_momo.py
from momo import _get_auth_token, request_to_pay, check_payment_status

print("\n[1] Test obtention token...")
token = _get_auth_token()
if token:
    print(f"✅ Token obtenu : {token[:30]}...")
else:
    print("❌ Échec token")
    exit()

print("\n[2] Test Request to Pay...")
result = request_to_pay(
    amount=100,
    phone_number="22994300874",
    tx_id="test_manual_001"
)
print(f"Résultat : {result}")

if result["success"]:
    momo_ref = result["transaction_id"]
    print(f"\n[3] Vérification statut ({momo_ref})...")
    status = check_payment_status(momo_ref)
    print(f"Statut : {status}")
else:
    print("❌ Request to Pay échoué")