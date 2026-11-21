"""Saves expenses in a small SQLite database file so they're kept between visits.

The file lives in data/tally.db (ignored by git). Set the TALLY_DB
environment variable to use a different file, e.g. for tests.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PATH = DATA_DIR / "tally.db"
OLD_PATH = DATA_DIR / "bitebudget.db"   # from V6, when the app only tracked delivery orders


def db_path():
    return Path(os.environ.get("TALLY_DB", DEFAULT_PATH))


def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)
    _move_old_orders(conn)
    return conn


def _move_old_orders(conn):
    """One time only: copy delivery orders saved by V6 (BiteBudget) into expenses
    as 'Eating out'. user_version marks that it's done, so clearing your expenses
    later doesn't bring the old orders back."""
    if conn.execute("PRAGMA user_version").fetchone()[0] >= 1:
        return
    if "TALLY_DB" not in os.environ and OLD_PATH.exists():
        old = sqlite3.connect(OLD_PATH)
        try:
            rows = old.execute("SELECT date, restaurant, total FROM orders").fetchall()
        except sqlite3.OperationalError:
            rows = []
        old.close()
        conn.executemany(
            "INSERT INTO expenses (date, description, category, amount) VALUES (?, ?, 'Eating out', ?)",
            [(d[:10], r, t) for d, r, t in rows],
        )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()


def _row_to_expense(row):
    e = dict(row)
    e["date"] = datetime.fromisoformat(e["date"])
    return e


def add_expense(expense):
    """Save one expense and return its id."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (date, description, category, amount) VALUES (?, ?, ?, ?)",
            (expense["date"].date().isoformat(), expense["description"],
             expense["category"], expense["amount"]),
        )
        return cur.lastrowid


def add_expenses(expenses):
    for e in expenses:
        add_expense(e)
    return len(expenses)


def get_expenses():
    """All saved expenses, oldest first."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM expenses ORDER BY date, id").fetchall()
    return [_row_to_expense(r) for r in rows]


def get_expense(expense_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return _row_to_expense(row) if row else None


def delete_expense(expense_id):
    with connect() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


def delete_all():
    with connect() as conn:
        conn.execute("DELETE FROM expenses")


def past_descriptions():
    """Descriptions used before, most used first, each with the category it was last
    saved under. The add form uses this to suggest a category as you type."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT description,
                   (SELECT category FROM expenses e2 WHERE e2.description = e1.description
                    ORDER BY id DESC LIMIT 1) AS category
            FROM expenses e1
            GROUP BY description
            ORDER BY COUNT(*) DESC
            LIMIT 50
        """).fetchall()
    return [(r["description"], r["category"]) for r in rows]
