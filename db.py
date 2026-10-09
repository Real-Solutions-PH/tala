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
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  category TEXT NOT NULL DEFAULT 'Others',
  unit TEXT NOT NULL DEFAULT 'pc',
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  cost_cents INTEGER NOT NULL DEFAULT 0 CHECK (cost_cents >= 0),
  stock INTEGER NOT NULL DEFAULT 0,
  reorder_at INTEGER NOT NULL DEFAULT 5
);
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL CHECK (qty > 0),
  price_cents INTEGER NOT NULL,
  cost_cents INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'chat'
);
CREATE TABLE IF NOT EXISTS restocks (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL CHECK (qty > 0),
  cost_cents INTEGER NOT NULL DEFAULT 0,
  supplier TEXT
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
