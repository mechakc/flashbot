import sqlite3
from config import DATABASE_PATH
from utils import db_connection, db_fetch_one, db_fetch_all, db_execute, db_update


def get_connection():
    """Legacy helper — prefer db_connection() context manager in new code."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tontines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                amount_sats INTEGER NOT NULL,
                max_members INTEGER NOT NULL,
                frequency TEXT DEFAULT 'weekly',
                schedule_day TEXT DEFAULT 'monday',
                schedule_time TEXT DEFAULT '08:00',
                current_round INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                created_by TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tontine_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tontine_id INTEGER NOT NULL,
                whatsapp_number TEXT NOT NULL,
                lightning_wallet TEXT NOT NULL,
                turn_order INTEGER NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tontine_id) REFERENCES tontines(id),
                UNIQUE(tontine_id, whatsapp_number)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tontine_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tontine_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                beneficiary_member_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (tontine_id) REFERENCES tontines(id),
                FOREIGN KEY (beneficiary_member_id) REFERENCES tontine_members(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tontine_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                amount_sats INTEGER NOT NULL,
                invoice TEXT,
                payment_hash TEXT,
                status TEXT DEFAULT 'pending',
                paid_at DATETIME,
                FOREIGN KEY (round_id) REFERENCES tontine_rounds(id),
                FOREIGN KEY (member_id) REFERENCES tontine_members(id)
            )
        """)

        conn.commit()
    print("[DB] Base de données TontineBot initialisée ✅")


# ==============================================================
# TONTINES
# ==============================================================

def create_tontine(name, code, amount_sats, max_members, created_by,
                   frequency='weekly', schedule_day='monday', schedule_time='08:00'):
    try:
        return db_execute("""
            INSERT INTO tontines 
            (name, code, amount_sats, max_members, created_by, frequency, schedule_day, schedule_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, code, amount_sats, max_members, created_by, frequency, schedule_day, schedule_time))
    except sqlite3.IntegrityError:
        return None


def get_tontine_by_code(code):
    return db_fetch_one("SELECT * FROM tontines WHERE code = ?", (code,))


def get_tontine_by_id(tontine_id):
    return db_fetch_one("SELECT * FROM tontines WHERE id = ?", (tontine_id,))


def get_tontine_by_member(whatsapp_number):
    return db_fetch_one("""
        SELECT t.* FROM tontines t
        JOIN tontine_members m ON m.tontine_id = t.id
        WHERE m.whatsapp_number = ?
        AND t.status IN ('waiting', 'active')
        ORDER BY t.created_at DESC
        LIMIT 1
    """, (whatsapp_number,))


def get_tontines_by_member(whatsapp_number):
    """Retourne TOUTES les tontines actives/en attente dont l'utilisateur est membre."""
    return db_fetch_all("""
        SELECT t.* FROM tontines t
        JOIN tontine_members m ON m.tontine_id = t.id
        WHERE m.whatsapp_number = ?
        AND t.status IN ('waiting', 'active')
        ORDER BY t.created_at DESC
    """, (whatsapp_number,))


def get_all_tontines_by_member(whatsapp_number):
    """Retourne TOUTES les tontines (peu importe le statut) dont l'utilisateur est/était membre."""
    return db_fetch_all("""
        SELECT t.* FROM tontines t
        JOIN tontine_members m ON m.tontine_id = t.id
        WHERE m.whatsapp_number = ?
        ORDER BY t.created_at DESC
    """, (whatsapp_number,))


def update_tontine(tontine_id, **kwargs):
    db_update("tontines", tontine_id, **kwargs)


def get_all_active_tontines():
    return db_fetch_all("SELECT * FROM tontines WHERE status = 'active'")


# ==============================================================
# MEMBRES
# ==============================================================

def add_member(tontine_id, whatsapp_number, lightning_wallet, turn_order):
    try:
        return db_execute("""
            INSERT INTO tontine_members 
            (tontine_id, whatsapp_number, lightning_wallet, turn_order)
            VALUES (?, ?, ?, ?)
        """, (tontine_id, whatsapp_number, lightning_wallet, turn_order))
    except sqlite3.IntegrityError:
        return None


def get_members(tontine_id):
    return db_fetch_all("""
        SELECT * FROM tontine_members 
        WHERE tontine_id = ? 
        ORDER BY turn_order ASC
    """, (tontine_id,))


def get_member(tontine_id, whatsapp_number):
    return db_fetch_one("""
        SELECT * FROM tontine_members 
        WHERE tontine_id = ? AND whatsapp_number = ?
    """, (tontine_id, whatsapp_number))


def get_member_by_id(member_id):
    return db_fetch_one("SELECT * FROM tontine_members WHERE id = ?", (member_id,))


def count_members(tontine_id):
    result = db_fetch_one(
        "SELECT COUNT(*) as count FROM tontine_members WHERE tontine_id = ?",
        (tontine_id,)
    )
    return result["count"]


# ==============================================================
# ROUNDS
# ==============================================================

def create_round(tontine_id, round_number, beneficiary_member_id):
    return db_execute("""
        INSERT INTO tontine_rounds 
        (tontine_id, round_number, beneficiary_member_id, status)
        VALUES (?, ?, ?, 'active')
    """, (tontine_id, round_number, beneficiary_member_id))


def get_current_round(tontine_id):
    return db_fetch_one("""
        SELECT * FROM tontine_rounds 
        WHERE tontine_id = ? AND status = 'active'
        ORDER BY round_number DESC
        LIMIT 1
    """, (tontine_id,))


def get_all_rounds(tontine_id):
    return db_fetch_all("""
        SELECT * FROM tontine_rounds 
        WHERE tontine_id = ?
        ORDER BY round_number ASC
    """, (tontine_id,))


def update_round(round_id, **kwargs):
    db_update("tontine_rounds", round_id, **kwargs)


# ==============================================================
# PAIEMENTS
# ==============================================================

def create_payment(round_id, member_id, amount_sats, invoice, payment_hash):
    return db_execute("""
        INSERT INTO tontine_payments 
        (round_id, member_id, amount_sats, invoice, payment_hash, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (round_id, member_id, amount_sats, invoice, payment_hash))


def get_payment_by_hash(payment_hash):
    return db_fetch_one(
        "SELECT * FROM tontine_payments WHERE payment_hash = ?",
        (payment_hash,)
    )


def get_payments_for_round(round_id):
    return db_fetch_all("""
        SELECT p.*, m.whatsapp_number, m.lightning_wallet 
        FROM tontine_payments p
        JOIN tontine_members m ON m.id = p.member_id
        WHERE p.round_id = ?
        ORDER BY m.turn_order ASC
    """, (round_id,))


def update_payment(payment_id, **kwargs):
    db_update("tontine_payments", payment_id, **kwargs)


def count_paid_in_round(round_id):
    result = db_fetch_one("""
        SELECT COUNT(*) as count FROM tontine_payments 
        WHERE round_id = ? AND status = 'paid'
    """, (round_id,))
    return result["count"]


def get_pending_payments_in_round(round_id):
    return db_fetch_all("""
        SELECT p.*, m.whatsapp_number FROM tontine_payments p
        JOIN tontine_members m ON m.id = p.member_id
        WHERE p.round_id = ? AND p.status = 'pending'
    """, (round_id,))
