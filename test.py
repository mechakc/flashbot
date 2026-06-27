# test.py
import sys
import time
from datetime import datetime

# ============================================================
# FLASHBOT — Suite de tests complète
# ============================================================

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results = []

def test(name, fn):
    try:
        result = fn()
        if result is True:
            print(f"{PASS} {name}")
            results.append((name, "PASS"))
        elif result == "skip":
            print(f"{SKIP} {name} (ignoré)")
            results.append((name, "SKIP"))
        else:
            print(f"{FAIL} {name} — résultat inattendu : {result}")
            results.append((name, "FAIL"))
    except Exception as e:
        print(f"{FAIL} {name} — exception : {e}")
        results.append((name, "FAIL"))


# ============================================================
# 1. CONFIG
# ============================================================
print("\n📋 [1/7] TEST CONFIG")
print("-" * 40)

def test_config_import():
    from config import (
        WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN,
        MOMO_SUBSCRIPTION_KEY, MOMO_API_USER, MOMO_API_KEY,
        MOMO_ENVIRONMENT, MOMO_BASE_URL,
        FLASH_API_KEY, FLASH_API_URL,
        PORT, DEBUG, DATABASE_PATH
    )
    assert VERIFY_TOKEN == "flashbot_verify_2026", "VERIFY_TOKEN incorrect"
    assert PORT == 5000, "PORT incorrect"
    assert MOMO_ENVIRONMENT == "sandbox", "MOMO_ENVIRONMENT incorrect"
    return True

def test_config_momo_credentials():
    from config import MOMO_API_USER, MOMO_SUBSCRIPTION_KEY
    assert MOMO_API_USER and len(MOMO_API_USER) > 10, "MOMO_API_USER manquant"
    assert MOMO_SUBSCRIPTION_KEY and len(MOMO_SUBSCRIPTION_KEY) > 5, "MOMO_SUBSCRIPTION_KEY manquant"
    return True

def test_config_whatsapp():
    from config import WHATSAPP_TOKEN, PHONE_NUMBER_ID
    if not WHATSAPP_TOKEN or "xxx" in WHATSAPP_TOKEN:
        return "skip"
    assert PHONE_NUMBER_ID, "PHONE_NUMBER_ID manquant"
    return True

test("Import config complet", test_config_import)
test("Credentials MoMo présents", test_config_momo_credentials)
test("Credentials WhatsApp présents", test_config_whatsapp)


# ============================================================
# 2. BASE DE DONNÉES
# ============================================================
print("\n🗄️  [2/7] TEST BASE DE DONNÉES")
print("-" * 40)

def test_db_init():
    from database import init_db
    init_db()
    return True

def test_db_create_user():
    from database import create_user, get_user
    test_number = "2250700000001"
    create_user(test_number)
    user = get_user(test_number)
    assert user is not None, "Utilisateur non trouvé après création"
    assert user["whatsapp_number"] == test_number
    return True

def test_db_duplicate_user():
    from database import create_user
    result = create_user("2250700000001")
    assert result is None, "Devrait retourner None pour un doublon"
    return True

def test_db_update_user():
    from database import update_user, get_user
    number = "2250700000001"
    update_user(number,
        momo_number="2250700000001",
        lightning_wallet="test@walletofsatoshi.com",
        dca_amount_fcfa=500,
        frequency="weekly",
        schedule_time="08:00",
        schedule_day="monday"
    )
    user = get_user(number)
    assert user["dca_amount_fcfa"] == 500
    assert user["lightning_wallet"] == "test@walletofsatoshi.com"
    assert user["frequency"] == "weekly"
    return True

def test_db_create_transaction():
    from database import create_transaction, update_transaction, get_user
    user = get_user("2250700000001")
    tx_id = create_transaction(user["id"], 500)
    assert tx_id is not None and tx_id > 0
    update_transaction(tx_id,
        sats_received=900,
        momo_tx_id="momo_test_123",
        flash_tx_id="flash_test_123",
        status="success"
    )
    return True

def test_db_user_stats():
    from database import get_user_stats, get_user
    user = get_user("2250700000001")
    stats = get_user_stats(user["id"])
    assert stats["total_transactions"] >= 1
    assert stats["total_fcfa"] >= 500
    assert stats["total_sats"] >= 900
    return True

def test_db_active_users():
    from database import get_all_active_users
    users = get_all_active_users()
    assert len(users) >= 1
    return True

def test_db_cleanup():
    """Nettoie les données de test."""
    import sqlite3
    from config import DATABASE_PATH
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("DELETE FROM transactions WHERE momo_tx_id = 'momo_test_123'")
    conn.execute("DELETE FROM users WHERE whatsapp_number = '2250700000001'")
    conn.commit()
    conn.close()
    return True

test("Initialisation base de données", test_db_init)
test("Création utilisateur", test_db_create_user)
test("Doublon utilisateur bloqué", test_db_duplicate_user)
test("Mise à jour utilisateur", test_db_update_user)
test("Création transaction", test_db_create_transaction)
test("Statistiques utilisateur", test_db_user_stats)
test("Liste utilisateurs actifs", test_db_active_users)
test("Nettoyage données de test", test_db_cleanup)


# ============================================================
# 3. MESSAGES
# ============================================================
print("\n💬 [3/7] TEST MESSAGES")
print("-" * 40)

def test_messages_import():
    from messages import (
        MSG_BIENVENUE, MSG_AIDE, MSG_PAUSE, MSG_REPRENDRE,
        MSG_COMMANDE_INCONNUE, MSG_MODIFIER, MSG_TIMEOUT_CONFIRMATION
    )
    assert len(MSG_BIENVENUE) > 10
    assert len(MSG_AIDE) > 10
    return True

def test_messages_dynamic():
    from messages import (
        msg_rappel_dca, msg_paiement_envoye, msg_achat_reussi,
        msg_paiement_echoue, msg_solde, msg_rapport_hebdo
    )
    assert "500" in msg_rappel_dca(500)
    assert "500" in msg_paiement_envoye(500)
    assert "900" in msg_achat_reussi(900, 1800, 500)
    assert "1800" in msg_achat_reussi(900, 1800, 500)
    assert "500" in msg_paiement_echoue(500)
    assert "1800" in msg_solde(1800, 1000, 5)
    assert "900" in msg_rapport_hebdo(900, 500, 1, 1800)
    return True

def test_messages_confirmation_inscription():
    from messages import msg_confirmation_inscription
    fake_user = {
        "dca_amount_fcfa": 500,
        "frequency": "weekly",
        "schedule_day": "monday",
        "schedule_time": "08:00",
        "lightning_wallet": "test@walletofsatoshi.com"
    }
    msg = msg_confirmation_inscription(fake_user)
    assert "500" in msg
    assert "lundi" in msg
    assert "08:00" in msg
    return True

test("Import messages statiques", test_messages_import)
test("Messages dynamiques", test_messages_dynamic)
test("Message confirmation inscription", test_messages_confirmation_inscription)


# ============================================================
# 4. WHATSAPP (parse uniquement — pas d'envoi réel)
# ============================================================
print("\n📱 [4/7] TEST WHATSAPP (parse)")
print("-" * 40)

def test_whatsapp_parse_valid():
    from whatsapp import parse_incoming_message, is_valid_message
    fake_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "2250701234567",
                        "id": "msg_abc123",
                        "type": "text",
                        "text": {"body": "stack"},
                        "timestamp": "1234567890"
                    }],
                    "contacts": [{
                        "profile": {"name": "Kofi"}
                    }]
                }
            }]
        }]
    }
    parsed = parse_incoming_message(fake_payload)
    assert parsed is not None
    assert parsed["from"] == "2250701234567"
    assert parsed["text"] == "STACK"          # normalisé en majuscules
    assert parsed["raw_text"] == "stack"      # brut conservé
    assert parsed["name"] == "Kofi"
    assert is_valid_message(parsed) is True
    return True

def test_whatsapp_parse_no_message():
    from whatsapp import parse_incoming_message
    fake_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"status": "delivered"}]
                }
            }]
        }]
    }
    parsed = parse_incoming_message(fake_payload)
    assert parsed is None
    return True

def test_whatsapp_parse_empty():
    from whatsapp import parse_incoming_message, is_valid_message
    assert parse_incoming_message({}) is None
    assert parse_incoming_message(None) is None
    assert is_valid_message(None) is False
    return True

def test_whatsapp_parse_image():
    from whatsapp import parse_incoming_message, is_valid_message
    fake_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "2250701234567",
                        "id": "msg_img123",
                        "type": "image",
                        "timestamp": "1234567890"
                    }],
                    "contacts": [{"profile": {"name": "Kofi"}}]
                }
            }]
        }]
    }
    parsed = parse_incoming_message(fake_payload)
    assert parsed is not None
    assert is_valid_message(parsed) is False   # image → ignoré
    return True

test("Parse message valide", test_whatsapp_parse_valid)
test("Parse payload sans message", test_whatsapp_parse_no_message)
test("Parse payload vide/None", test_whatsapp_parse_empty)
test("Parse message image ignoré", test_whatsapp_parse_image)


# ============================================================
# 5. VALIDATIONS (commands.py)
# ============================================================
print("\n🔍 [5/7] TEST VALIDATIONS")
print("-" * 40)

def test_valid_phone():
    from commands import _is_valid_phone
    assert _is_valid_phone("2250701234567") is True
    assert _is_valid_phone("0701234567") is True
    assert _is_valid_phone("123") is False
    assert _is_valid_phone("abc") is False
    assert _is_valid_phone("") is False
    return True

def test_valid_wallet():
    from commands import _is_valid_wallet
    assert _is_valid_wallet("test@walletofsatoshi.com") is True
    assert _is_valid_wallet("kofi@bitcoin.lightning") is True
    assert _is_valid_wallet("lnurl1234abc") is True
    assert _is_valid_wallet("lnbc500...") is True
    assert _is_valid_wallet("pasunwallet") is False
    assert _is_valid_wallet("") is False
    return True

def test_valid_amount():
    from commands import _is_valid_amount
    assert _is_valid_amount("500") is True
    assert _is_valid_amount("100") is True
    assert _is_valid_amount("99") is False
    assert _is_valid_amount("0") is False
    assert _is_valid_amount("abc") is False
    assert _is_valid_amount("-500") is False
    return True

def test_valid_time():
    from commands import _is_valid_time
    assert _is_valid_time("08:00") is True
    assert _is_valid_time("23:59") is True
    assert _is_valid_time("00:00") is True
    assert _is_valid_time("24:00") is False
    assert _is_valid_time("8:00") is False
    assert _is_valid_time("abc") is False
    return True

test("Validation numéro téléphone", test_valid_phone)
test("Validation wallet Lightning", test_valid_wallet)
test("Validation montant FCFA", test_valid_amount)
test("Validation format heure", test_valid_time)


# ============================================================
# 6. FLASH (placeholder)
# ============================================================
print("\n⚡ [6/7] TEST FLASH (placeholder)")
print("-" * 40)

def test_flash_placeholder():
    from flash import buy_sats
    result = buy_sats(500, "test@walletofsatoshi.com")
    assert result is not None
    assert result["success"] is True
    assert result["sats"] > 0
    assert "tx_id" in result
    print(f"       → 500 FCFA = {result['sats']} sats (taux estimé)")
    return True

def test_flash_rate():
    from flash import get_btc_rate
    rate = get_btc_rate()
    assert rate > 0
    print(f"       → Taux BTC/FCFA : {rate:,}")
    return True

def test_flash_sats_calcul():
    from flash import buy_sats
    result_100 = buy_sats(100, "test@walletofsatoshi.com")
    result_1000 = buy_sats(1000, "test@walletofsatoshi.com")
    assert result_1000["sats"] > result_100["sats"]
    # Marge de 5% pour les arrondis
    ratio = result_1000["sats"] / result_100["sats"]
    assert 9.5 <= ratio <= 10.5, f"Ratio inattendu : {ratio}"
    return True

test("Placeholder buy_sats()", test_flash_placeholder)
test("Placeholder get_btc_rate()", test_flash_rate)
test("Calcul sats proportionnel", test_flash_sats_calcul)


# ============================================================
# 7. SCHEDULER
# ============================================================
print("\n⏰ [7/7] TEST SCHEDULER")
print("-" * 40)

def test_scheduler_import():
    from scheduler import (
        start_scheduler, stop_scheduler,
        is_stack_pending, clear_pending_stack,
        PENDING_STACKS
    )
    return True

def test_scheduler_pending_stack():
    from scheduler import is_stack_pending, clear_pending_stack, PENDING_STACKS
    from datetime import timedelta

    number = "2250700000099"

    # Pas encore en attente
    assert is_stack_pending(number) is False

    # Simuler un rappel envoyé
    PENDING_STACKS[number] = {
        "expires_at": datetime.now().replace(tzinfo=None),
        "amount": 500
    }

    # Nettoyer
    clear_pending_stack(number)
    assert number not in PENDING_STACKS
    return True

def test_scheduler_should_send():
    from scheduler import _should_send_reminder

    fake_user_weekly = {
        "whatsapp_number": "2250700000099",
        "schedule_time": "08:00",
        "schedule_day": "monday",
        "frequency": "weekly"
    }
    fake_user_daily = {
        "whatsapp_number": "2250700000098",
        "schedule_time": "08:00",
        "schedule_day": "monday",
        "frequency": "daily"
    }

    # Mauvaise heure → False
    assert _should_send_reminder(fake_user_weekly, "09:00", "monday", 1) is False

    # Bonne heure, mauvais jour → False
    assert _should_send_reminder(fake_user_weekly, "08:00", "tuesday", 1) is False

    # Bonne heure, bon jour → True
    assert _should_send_reminder(fake_user_weekly, "08:00", "monday", 1) is True

    # Daily → True peu importe le jour
    assert _should_send_reminder(fake_user_daily, "08:00", "friday", 15) is True

    return True

def test_scheduler_start_stop():
    from scheduler import start_scheduler, stop_scheduler, scheduler
    start_scheduler()
    assert scheduler.running is True
    stop_scheduler()
    assert scheduler.running is False
    return True

test("Import scheduler", test_scheduler_import)
test("Pending stack add/clear", test_scheduler_pending_stack)
test("Logique should_send_reminder", test_scheduler_should_send)
test("Start/stop scheduler", test_scheduler_start_stop)


# ============================================================
# RÉSUMÉ FINAL
# ============================================================
print("\n" + "=" * 40)
print("📊 RÉSUMÉ DES TESTS")
print("=" * 40)

passed = sum(1 for _, r in results if r == "PASS")
failed = sum(1 for _, r in results if r == "FAIL")
skipped = sum(1 for _, r in results if r == "SKIP")
total = len(results)

print(f"{PASS} Réussis  : {passed}/{total}")
print(f"{FAIL} Échoués  : {failed}/{total}")
print(f"{SKIP} Ignorés  : {skipped}/{total}")

if failed > 0:
    print("\nTests échoués :")
    for name, r in results:
        if r == "FAIL":
            print(f"  - {name}")

print()
if failed == 0:
    print("🚀 Tout est prêt — FlashBot peut tourner !")
    print("   Branche l'API Flash et c'est parti. ⚡")
else:
    print("⚠️  Corrige les erreurs avant de continuer.")

sys.exit(0 if failed == 0 else 1)