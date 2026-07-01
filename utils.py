# utils.py
"""Shared utilities to eliminate duplicated patterns across the codebase."""

import os
import requests
from contextlib import contextmanager
import sqlite3

from config import DATABASE_PATH


# ==============================================================
# DATABASE UTILITIES
# ==============================================================

@contextmanager
def db_connection():
    """Context manager for database connections — auto-closes on exit."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def db_fetch_one(query, params=()):
    """Execute a query and return a single row."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()


def db_fetch_all(query, params=()):
    """Execute a query and return all rows."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def db_execute(query, params=()):
    """Execute a write query (INSERT/UPDATE/DELETE) and return lastrowid."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid


def db_update(table, record_id, **kwargs):
    """
    Generic UPDATE for any table by primary key `id`.
    Usage: db_update("tontines", tontine_id, status="active", current_round=1)
    """
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [record_id]
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table} SET {fields} WHERE id = ?", values)
        conn.commit()


# ==============================================================
# HTTP REQUEST UTILITIES
# ==============================================================

def http_request(method, url, headers=None, json=None, params=None,
                 timeout=10, tag="HTTP"):
    """
    Shared HTTP request wrapper with consistent error handling and logging.

    Returns response.json() on success, or None on failure.
    For non-JSON responses (e.g. 202 Accepted with no body), returns the
    raw Response object — caller can check via isinstance().
    """
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            params=params,
            timeout=timeout
        )
        response.raise_for_status()

        # Some endpoints return no body (e.g. 202 Accepted)
        if not response.content:
            return response

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"[{tag}] Erreur {method.upper()} {url} : {e}")
        return None


def http_get(url, headers=None, params=None, timeout=10, tag="HTTP"):
    """Shortcut for GET requests."""
    return http_request("GET", url, headers=headers, params=params,
                        timeout=timeout, tag=tag)


def http_post(url, headers=None, json=None, timeout=10, tag="HTTP"):
    """Shortcut for POST requests."""
    return http_request("POST", url, headers=headers, json=json,
                        timeout=timeout, tag=tag)


# ==============================================================
# NOTIFICATION UTILITIES
# ==============================================================

def notify_members(members, message_fn, exclude_number=None):
    """
    Send a message to each member, optionally excluding one number.

    message_fn: callable(member) -> str  (the message text to send)
                OR a plain str (same message for everyone)
    """
    from whatsapp import send_message

    for member in members:
        if exclude_number and member["whatsapp_number"] == exclude_number:
            continue
        text = message_fn if isinstance(message_fn, str) else message_fn(member)
        send_message(member["whatsapp_number"], text)


# ==============================================================
# FORMATTING UTILITIES
# ==============================================================

def format_phone_display(phone_number):
    """Format a phone number for display: '...1234' (last 4 digits)."""
    return f"...{phone_number[-4:]}"


def get_webhook_url():
    """Build the LNbits webhook URL from BASE_URL config."""
    base_url = os.getenv("BASE_URL", "http://localhost:5000")
    return f"{base_url}/lnbits/webhook"
