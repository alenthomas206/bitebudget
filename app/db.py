"""Saves orders in a small SQLite database file so they're kept between visits.

The file lives in data/bitebudget.db (ignored by git). Set the BITEBUDGET_DB
environment variable to use a different file, e.g. for tests.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "bitebudget.db"


def db_path():
    return Path(os.environ.get("BITEBUDGET_DB", DEFAULT_PATH))


def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            restaurant TEXT NOT NULL,
            subtotal REAL NOT NULL DEFAULT 0,
            delivery_fee REAL NOT NULL DEFAULT 0,
            service_fee REAL NOT NULL DEFAULT 0,
            tip REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL
        )
    """)
    return conn


def _row_to_order(row):
    order = dict(row)
    order["date"] = datetime.fromisoformat(order["date"])
    return order


def add_order(order):
    """Save one order (same dict shape as analysis.parse_orders) and return its id."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO orders (date, restaurant, subtotal, delivery_fee, service_fee, tip, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order["date"].isoformat(timespec="minutes"), order["restaurant"],
             order.get("subtotal", 0), order.get("delivery_fee", 0),
             order.get("service_fee", 0), order.get("tip", 0), order["total"]),
        )
        return cur.lastrowid


def add_orders(orders):
    for order in orders:
        add_order(order)
    return len(orders)


def get_orders():
    """All saved orders, oldest first."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY date, id").fetchall()
    return [_row_to_order(r) for r in rows]


def get_order(order_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return _row_to_order(row) if row else None


def delete_order(order_id):
    with connect() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))


def delete_all():
    with connect() as conn:
        conn.execute("DELETE FROM orders")


def restaurant_names():
    """Restaurants used before, most ordered first (for the suggestions list)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT restaurant FROM orders GROUP BY restaurant ORDER BY COUNT(*) DESC"
        ).fetchall()
    return [r["restaurant"] for r in rows]
