# api_routes.py
import time
import requests
from flask import jsonify
from database import (
    get_connection, get_members,
    get_current_round, get_all_rounds, get_payments_for_round,
    count_paid_in_round, get_tontine_by_code
)

# Cache simple en mémoire pour éviter de spammer CoinGecko à chaque refresh
_btc_rate_cache = {"data": None, "fetched_at": 0}
BTC_RATE_CACHE_SECONDS = 60


def _get_btc_rate():
    """
    Récupère le taux BTC/FCFA.
    CoinGecko ne supporte pas XOF directement, donc on passe par EUR
    puis on convertit avec le taux fixe légal : 1 EUR = 655.957 FCFA
    (parité fixe de la zone UEMOA, ne change jamais).
    """
    now = time.time()
    if _btc_rate_cache["data"] and (now - _btc_rate_cache["fetched_at"]) < BTC_RATE_CACHE_SECONDS:
        return _btc_rate_cache["data"]

    EUR_TO_XOF = 655.957

    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin",
                "vs_currencies": "eur",
                "include_24hr_change": "true"
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        btc_eur = data["bitcoin"]["eur"]
        change_24h = data["bitcoin"].get("eur_24h_change", 0)

        btc_xof = btc_eur * EUR_TO_XOF

        result = {
            "btc_fcfa": btc_xof,
            "sat_fcfa": btc_xof / 100_000_000,
            "change_24h": round(change_24h, 2),
            "source": "CoinGecko (EUR -> XOF taux fixe UEMOA)",
            "fetched_at": now
        }

        _btc_rate_cache["data"] = result
        _btc_rate_cache["fetched_at"] = now
        return result

    except Exception as e:
        print(f"[BTC RATE] Erreur CoinGecko : {e}")
        if _btc_rate_cache["data"]:
            return _btc_rate_cache["data"]
        return None


def register_api_routes(app):

    @app.route("/api/btc-rate", methods=["GET"])
    def api_btc_rate():
        rate = _get_btc_rate()
        if not rate:
            return jsonify({"error": "Taux indisponible"}), 503
        return jsonify(rate)

    @app.route("/api/stats", methods=["GET"])
    def api_stats():
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM tontines")
        total_tontines = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tontines WHERE status = 'active'")
        active_tontines = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tontines WHERE status = 'waiting'")
        waiting_tontines = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tontines WHERE status = 'completed'")
        completed_tontines = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tontine_members")
        total_members = cursor.fetchone()["count"]

        cursor.execute("SELECT SUM(amount_sats) as total FROM tontine_payments WHERE status = 'paid'")
        result = cursor.fetchone()
        total_sats = result["total"] or 0

        cursor.execute("SELECT COUNT(*) as count FROM tontine_payments WHERE status = 'paid'")
        total_payments = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tontine_payments WHERE status = 'pending'")
        pending_payments = cursor.fetchone()["count"]

        # Wallet bot en temps réel
        wallet_balance = None
        try:
            from lnbits import get_wallet_balance
            wallet_balance = get_wallet_balance()
        except Exception:
            pass

        conn.close()

        return jsonify({
            "total_tontines": total_tontines,
            "active_tontines": active_tontines,
            "waiting_tontines": waiting_tontines,
            "completed_tontines": completed_tontines,
            "total_members": total_members,
            "total_sats_managed": total_sats,
            "total_payments": total_payments,
            "pending_payments": pending_payments,
            "wallet_balance": wallet_balance
        })


    @app.route("/api/tontine/<code>", methods=["GET"])
    def api_tontine(code):
        tontine = get_tontine_by_code(code.upper())
        if not tontine:
            return jsonify({"error": "Tontine introuvable"}), 404

        tontine_dict = dict(tontine)
        members = get_members(tontine["id"])
        members_list = [dict(m) for m in members]
        for m in members_list:
            m["display"] = f"...{m['whatsapp_number'][-4:]}"

        current_round = get_current_round(tontine["id"])
        rounds = get_all_rounds(tontine["id"])

        current_round_data = None
        if current_round:
            payments = get_payments_for_round(current_round["id"])
            paid_count = count_paid_in_round(current_round["id"])
            current_round_data = {
                "round_number": current_round["round_number"],
                "status": current_round["status"],
                "started_at": current_round["started_at"],
                "paid_count": paid_count,
                "total_members": len(members),
                "payments": [
                    {
                        "display": f"...{p['whatsapp_number'][-4:]}",
                        "status": p["status"],
                        "amount_sats": p["amount_sats"],
                        "paid_at": p["paid_at"]
                    }
                    for p in payments
                ]
            }

        # Historique complet avec tous les paiements de chaque round
        rounds_history = []
        for r in rounds:
            round_payments = get_payments_for_round(r["id"])
            rounds_history.append({
                "round_number": r["round_number"],
                "status": r["status"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "payments": [
                    {
                        "display": f"...{p['whatsapp_number'][-4:]}",
                        "status": p["status"],
                        "amount_sats": p["amount_sats"],
                        "paid_at": p["paid_at"]
                    }
                    for p in round_payments
                ]
            })

        # Timeline chronologique de tous les événements (pour le graphe)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.amount_sats, p.paid_at, p.status
            FROM tontine_payments p
            JOIN tontine_rounds r ON r.id = p.round_id
            WHERE r.tontine_id = ? AND p.status = 'paid'
            ORDER BY p.paid_at ASC
        """, (tontine["id"],))
        timeline_raw = cursor.fetchall()
        conn.close()

        timeline = []
        running_total = 0
        for row in timeline_raw:
            running_total += row["amount_sats"]
            timeline.append({
                "timestamp": row["paid_at"],
                "amount": row["amount_sats"],
                "cumulative": running_total
            })

        return jsonify({
            "id": tontine_dict["id"],
            "name": tontine_dict["name"],
            "code": tontine_dict["code"],
            "amount_sats": tontine_dict["amount_sats"],
            "max_members": tontine_dict["max_members"],
            "current_round": tontine_dict["current_round"],
            "status": tontine_dict["status"],
            "frequency": tontine_dict["frequency"],
            "schedule_time": tontine_dict["schedule_time"],
            "created_at": tontine_dict["created_at"],
            "members": members_list,
            "current_round_data": current_round_data,
            "rounds_history": rounds_history,
            "timeline": timeline,
            "total_pot": tontine_dict["amount_sats"] * len(members) * len(members)
        })


    @app.route("/api/tontines/recent", methods=["GET"])
    def api_recent_tontines():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, COUNT(m.id) as member_count
            FROM tontines t
            LEFT JOIN tontine_members m ON m.tontine_id = t.id
            GROUP BY t.id
            ORDER BY t.created_at DESC
            LIMIT 10
        """)
        tontines = cursor.fetchall()
        conn.close()

        return jsonify([
            {
                "name": t["name"],
                "code": t["code"],
                "status": t["status"],
                "amount_sats": t["amount_sats"],
                "member_count": t["member_count"],
                "max_members": t["max_members"],
                "current_round": t["current_round"],
                "created_at": t["created_at"]
            }
            for t in tontines
        ])


    @app.route("/api/activity", methods=["GET"])
    def api_activity():
        """Flux d'activité récente toutes tontines confondues — pour le live feed."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.amount_sats, p.paid_at, p.status, m.whatsapp_number, t.name as tontine_name, t.code
            FROM tontine_payments p
            JOIN tontine_members m ON m.id = p.member_id
            JOIN tontine_rounds r ON r.id = p.round_id
            JOIN tontines t ON t.id = r.tontine_id
            WHERE p.status = 'paid'
            ORDER BY p.paid_at DESC
            LIMIT 15
        """)
        rows = cursor.fetchall()
        conn.close()

        return jsonify([
            {
                "display": f"...{row['whatsapp_number'][-4:]}",
                "amount_sats": row["amount_sats"],
                "paid_at": row["paid_at"],
                "tontine_name": row["tontine_name"],
                "tontine_code": row["code"]
            }
            for row in rows
        ])

    return app