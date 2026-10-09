"""SQLite storage. Amounts are integer centavos; pesos only at the edges."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("tala.db")

CATEGORIES = [
    "Food",
    "Groceries",
    "Transport",
    "Bills",
    "Load/Internet",
    "Shopping",
    "Health",
    "Entertainment",
    "Others",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  cents INTEGER NOT NULL CHECK (cents > 0),
  category TEXT NOT NULL,
  merchant TEXT,
  note TEXT,
  source TEXT NOT NULL DEFAULT 'chat'
);
CREATE TABLE IF NOT EXISTS budgets (
  category TEXT PRIMARY KEY,
  cents INTEGER NOT NULL CHECK (cents > 0)
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def to_cents(pesos: float) -> int:
    return round(float(pesos) * 100)


def to_pesos(cents: int) -> float:
    return cents / 100
