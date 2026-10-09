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
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  due TEXT,
  done_on TEXT,
  created TEXT NOT NULL DEFAULT (date('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS habits (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS habit_logs (
  habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  PRIMARY KEY (habit_id, date)
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
