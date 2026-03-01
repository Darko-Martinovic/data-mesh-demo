"""SQLite helpers for the customer domain."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

DB_FILE = "customers.db"

_SAMPLE_CUSTOMERS = [
    ("C001", "Alice Johnson",  "alice@example.com",  "premium"),
    ("C002", "Bob Smith",      "bob@example.com",    "standard"),
    ("C003", "Carol White",    "carol@example.com",  "basic"),
    ("C004", "David Brown",    "david@example.com",  "premium"),
    ("C005", "Eve Davis",      "eve@example.com",    "standard"),
    ("C006", "Frank Miller",   "frank@example.com",  "basic"),
    ("C007", "Grace Wilson",   "grace@example.com",  "premium"),
    ("C008", "Henry Taylor",   "henry@example.com",  "standard"),
    ("C009", "Iris Anderson",  "iris@example.com",   "basic"),
    ("C010", "Jack Thomas",    "jack@example.com",   "standard"),
]


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                segment    TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)


def seed() -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        for cid, name, email, segment in _SAMPLE_CUSTOMERS:
            c.execute(
                "INSERT OR IGNORE INTO customers VALUES (?,?,?,?,'active',?)",
                (cid, name, email, segment, now),
            )


def get_all() -> List[Dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM customers ORDER BY id")]


def get_by_id(customer_id: str) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        return dict(row) if row else None


def insert(customer_id: str, name: str, email: str, segment: str) -> Dict:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO customers VALUES (?,?,?,?,'active',?)",
            (customer_id, name, email, segment, now),
        )
    return get_by_id(customer_id)  # type: ignore[return-value]
