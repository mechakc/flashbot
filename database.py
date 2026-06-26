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

    # Table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp_number TEXT UNIQUE NOT NULL,
            momo_number TEXT,
            lightning_wallet TEXT,
            dca_amount_fcfa INTEGER DEFAULT 500,
            frequency TEXT DEFAULT 'weekly',
            schedule_time TEXT DEFAULT '08:00',
            schedule_day TEXT DEFAULT 'monday',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_sats INTEGER DEFAULT 0
        )
    """)

    # Table transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount_fcfa INTEGER NOT NULL,
            sats_received INTEGER DEFAULT 0,
            momo_tx_id TEXT,
            flash_tx_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Base de données initialisée ✅")

# --- Fonctions Users ---

def create_user(whatsapp_number):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (whatsapp_number) VALUES (?)",
            (whatsapp_number,)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None  # utilisateur déjà existant
    finally:
        conn.close()

def get_user(whatsapp_number):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE whatsapp_number = ?",
        (whatsapp_number,)
    )
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(whatsapp_number, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [whatsapp_number]
    cursor.execute(
        f"UPDATE users SET {fields} WHERE whatsapp_number = ?",
        values
    )
    conn.commit()
    conn.close()

def get_all_active_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE is_active = 1")
    users = cursor.fetchall()
    conn.close()
    return users

# --- Fonctions Transactions ---

def create_transaction(user_id, amount_fcfa):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (user_id, amount_fcfa) VALUES (?, ?)",
        (user_id, amount_fcfa)
    )
    conn.commit()
    tx_id = cursor.lastrowid
    conn.close()
    return tx_id

def update_transaction(tx_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [tx_id]
    cursor.execute(
        f"UPDATE transactions SET {fields} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            SUM(amount_fcfa) as total_fcfa,
            SUM(sats_received) as total_sats
        FROM transactions
        WHERE user_id = ? AND status = 'success'
    """, (user_id,))
    stats = cursor.fetchone()
    conn.close()
    return stats