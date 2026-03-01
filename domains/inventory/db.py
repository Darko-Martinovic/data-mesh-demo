"""SQLite helpers for the inventory domain."""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

DB_FILE = "inventory.db"

_SAMPLE_PRODUCTS = [
    ("SKU-A", "Widget Alpha",    50, 5),
    ("SKU-B", "Gadget Beta",     50, 5),
    ("SKU-C", "Component Gamma", 50, 5),
    ("SKU-D", "Device Delta",    50, 5),
    ("SKU-E", "Module Epsilon",  50, 5),
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
            CREATE TABLE IF NOT EXISTS products (
                sku       TEXT PRIMARY KEY,
                name      TEXT NOT NULL,
                stock_qty INTEGER NOT NULL,
                threshold INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id         TEXT PRIMARY KEY,
                sku        TEXT NOT NULL,
                delta      INTEGER NOT NULL,
                reason     TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def seed() -> None:
    with _conn() as c:
        for sku, name, qty, thresh in _SAMPLE_PRODUCTS:
            c.execute(
                "INSERT OR IGNORE INTO products VALUES (?,?,?,?)",
                (sku, name, qty, thresh),
            )


def get_all_products() -> List[Dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM products ORDER BY sku")]


def get_product(sku: str) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        return dict(row) if row else None


def reserve_stock(sku: str, quantity: int) -> Dict:
    """
    Atomically reserve *quantity* units of *sku*.

    Returns a dict with keys:
      success  bool
      product  dict | None   (state after the operation)
      reason   'ok' | 'not_found' | 'insufficient'
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.execute("BEGIN EXCLUSIVE")
        row = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        if not row:
            conn.rollback()
            return {"success": False, "product": None, "reason": "not_found"}
        if row["stock_qty"] < quantity:
            conn.rollback()
            return {"success": False, "product": dict(row), "reason": "insufficient"}

        conn.execute(
            "UPDATE products SET stock_qty = stock_qty - ? WHERE sku = ?",
            (quantity, sku),
        )
        conn.execute(
            "INSERT INTO stock_movements VALUES (?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                sku,
                -quantity,
                "order_reserve",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        updated = dict(conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone())
        return {"success": True, "product": updated, "reason": "ok"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_low_stock() -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM products WHERE stock_qty < threshold ORDER BY stock_qty"
        ).fetchall()
        return [dict(r) for r in rows]
