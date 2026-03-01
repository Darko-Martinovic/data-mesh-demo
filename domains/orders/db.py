"""SQLite helpers for the orders domain."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

DB_FILE = "orders.db"


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
            CREATE TABLE IF NOT EXISTS orders (
                id          TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                sku         TEXT NOT NULL,
                quantity    INTEGER NOT NULL,
                total       REAL NOT NULL,
                status      TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)


def get_all() -> List[Dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY created_at DESC")]


def get_by_id(order_id: str) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def insert(order_id: str, customer_id: str, sku: str, quantity: int, total: float) -> Dict:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,'confirmed',?)",
            (order_id, customer_id, sku, quantity, total, now),
        )
    return get_by_id(order_id)  # type: ignore[return-value]


def revenue_summary() -> Dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT sku, SUM(total) as rev, COUNT(*) as cnt FROM orders GROUP BY sku"
        ).fetchall()
        by_sku = {r["sku"]: {"revenue": round(r["rev"], 2), "orders": r["cnt"]} for r in rows}
        totals = c.execute("SELECT SUM(total), COUNT(*) FROM orders").fetchone()
        total_rev = totals[0] or 0.0
        total_cnt = totals[1] or 0
    return {
        "total_revenue": round(total_rev, 2),
        "total_orders": total_cnt,
        "average_order_value": round(total_rev / total_cnt, 2) if total_cnt else 0.0,
        "by_sku": by_sku,
    }
