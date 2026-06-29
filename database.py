# database.py
import sqlite3
from config import DATABASE_PATH


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table tontines
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tontines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            amount_sats INTEGER NOT NULL,
            max_members INTEGER NOT NULL,
            current_round INTEGER DEFAULT 0,
            status TEXT DEFAULT 'waiting',
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # status : waiting (en attente membres) | active (en cours) | completed (terminée)

    # Table tontine_members
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

    # Table tontine_rounds
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
    # status : pending | active | completed

    # Table tontine_payments
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
    # status : pending | paid | failed

    conn.commit()
    conn.close()
    print("[DB] Base de données TontineBot initialisée ✅")


# ==============================================================
# TONTINES
# ==============================================================

def create_tontine(name, code, amount_sats, max_members, created_by):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO tontines (name, code, amount_sats, max_members, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (name, code, amount_sats, max_members, created_by))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_tontine_by_code(code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tontines WHERE code = ?", (code,))
    tontine = cursor.fetchone()
    conn.close()
    return tontine


def get_tontine_by_id(tontine_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tontines WHERE id = ?", (tontine_id,))
    tontine = cursor.fetchone()
    conn.close()
    return tontine


def get_tontine_by_member(whatsapp_number):
    """Retourne la tontine active d'un membre."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.* FROM tontines t
        JOIN tontine_members m ON m.tontine_id = t.id
        WHERE m.whatsapp_number = ?
        AND t.status IN ('waiting', 'active')
        ORDER BY t.created_at DESC
        LIMIT 1
    """, (whatsapp_number,))
    tontine = cursor.fetchone()
    conn.close()
    return tontine


def update_tontine(tontine_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [tontine_id]
    cursor.execute(f"UPDATE tontines SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_all_active_tontines():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tontines WHERE status = 'active'")
    tontines = cursor.fetchall()
    conn.close()
    return tontines


# ==============================================================
# MEMBRES
# ==============================================================

def add_member(tontine_id, whatsapp_number, lightning_wallet, turn_order):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO tontine_members 
            (tontine_id, whatsapp_number, lightning_wallet, turn_order)
            VALUES (?, ?, ?, ?)
        """, (tontine_id, whatsapp_number, lightning_wallet, turn_order))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_members(tontine_id):
    """Retourne tous les membres dans l'ordre d'inscription."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tontine_members 
        WHERE tontine_id = ? 
        ORDER BY turn_order ASC
    """, (tontine_id,))
    members = cursor.fetchall()
    conn.close()
    return members


def get_member(tontine_id, whatsapp_number):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tontine_members 
        WHERE tontine_id = ? AND whatsapp_number = ?
    """, (tontine_id, whatsapp_number))
    member = cursor.fetchone()
    conn.close()
    return member


def get_member_by_id(member_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tontine_members WHERE id = ?", (member_id,))
    member = cursor.fetchone()
    conn.close()
    return member


def count_members(tontine_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as count FROM tontine_members WHERE tontine_id = ?",
        (tontine_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result["count"]


# ==============================================================
# ROUNDS
# ==============================================================

def create_round(tontine_id, round_number, beneficiary_member_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tontine_rounds 
        (tontine_id, round_number, beneficiary_member_id, status)
        VALUES (?, ?, ?, 'active')
    """, (tontine_id, round_number, beneficiary_member_id))
    conn.commit()
    round_id = cursor.lastrowid
    conn.close()
    return round_id


def get_current_round(tontine_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tontine_rounds 
        WHERE tontine_id = ? AND status = 'active'
        ORDER BY round_number DESC
        LIMIT 1
    """, (tontine_id,))
    round_ = cursor.fetchone()
    conn.close()
    return round_


def get_all_rounds(tontine_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tontine_rounds 
        WHERE tontine_id = ?
        ORDER BY round_number ASC
    """, (tontine_id,))
    rounds = cursor.fetchall()
    conn.close()
    return rounds


def update_round(round_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [round_id]
    cursor.execute(f"UPDATE tontine_rounds SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ==============================================================
# PAIEMENTS
# ==============================================================

def create_payment(round_id, member_id, amount_sats, invoice, payment_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tontine_payments 
        (round_id, member_id, amount_sats, invoice, payment_hash, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (round_id, member_id, amount_sats, invoice, payment_hash))
    conn.commit()
    payment_id = cursor.lastrowid
    conn.close()
    return payment_id


def get_payment_by_hash(payment_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM tontine_payments WHERE payment_hash = ?",
        (payment_hash,)
    )
    payment = cursor.fetchone()
    conn.close()
    return payment


def get_payments_for_round(round_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, m.whatsapp_number, m.lightning_wallet 
        FROM tontine_payments p
        JOIN tontine_members m ON m.id = p.member_id
        WHERE p.round_id = ?
        ORDER BY m.turn_order ASC
    """, (round_id,))
    payments = cursor.fetchall()
    conn.close()
    return payments


def update_payment(payment_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [payment_id]
    cursor.execute(f"UPDATE tontine_payments SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def count_paid_in_round(round_id):
    """Compte combien de membres ont payé dans ce round."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM tontine_payments 
        WHERE round_id = ? AND status = 'paid'
    """, (round_id,))
    result = cursor.fetchone()
    conn.close()
    return result["count"]


def get_pending_payments_in_round(round_id):
    """Retourne les paiements encore en attente dans ce round."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, m.whatsapp_number FROM tontine_payments p
        JOIN tontine_members m ON m.id = p.member_id
        WHERE p.round_id = ? AND p.status = 'pending'
    """, (round_id,))
    payments = cursor.fetchall()
    conn.close()
    return payments
