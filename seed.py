"""Seed a sari-sari store with ~8 weeks of sales and restocks. Wipes existing data. Run: uv run python seed.py"""

import datetime as dt
import random

from db import DB_PATH, connect, to_cents

random.seed(11)
DB_PATH.unlink(missing_ok=True)
con = connect()
end = dt.date.today()

# name, category, unit, price, cost, daily demand (avg pcs), reorder_at, start stock
PRODUCTS = [
    ("Lucky Me Pancit Canton", "Noodles & Canned", "pack", 16, 13, 9, 12, 60),
    ("Lucky Me Beef Mami", "Noodles & Canned", "pack", 12, 9.5, 5, 10, 40),
    ("Ligo Sardines", "Noodles & Canned", "can", 26, 22, 4, 8, 30),
    ("Argentina Corned Beef", "Noodles & Canned", "can", 42, 36, 2, 5, 18),
    ("Coke Mismo", "Drinks", "bottle", 20, 16, 10, 12, 48),
    ("C2 Apple", "Drinks", "bottle", 25, 20, 4, 8, 24),
    ("Royal Mismo", "Drinks", "bottle", 20, 16, 3, 8, 24),
    ("Kopiko 3-in-1", "Coffee & Milk", "sachet", 10, 7.5, 14, 20, 100),
    ("Nescafe Classic Stick", "Coffee & Milk", "sachet", 8, 6, 6, 15, 60),
    ("Bear Brand Sachet", "Coffee & Milk", "sachet", 13, 10.5, 7, 15, 60),
    ("Skyflakes", "Snacks", "pack", 9, 7, 6, 12, 50),
    ("Piattos", "Snacks", "pack", 18, 14.5, 4, 8, 30),
    ("Choc Nut", "Snacks", "pc", 3, 2, 10, 30, 150),
    ("Egg", "Rice & Basics", "pc", 9, 7.5, 12, 24, 90),
    ("Rice (per kilo)", "Rice & Basics", "kilo", 52, 45, 6, 10, 50),
    ("Pandesal", "Rice & Basics", "pc", 3, 2.2, 25, 0, 0),
    ("Silver Swan Soy Sauce", "Condiments", "sachet", 6, 4.5, 3, 10, 40),
    ("Datu Puti Vinegar", "Condiments", "sachet", 6, 4.5, 3, 10, 40),
    ("Cooking Oil (sachet)", "Condiments", "sachet", 14, 11, 4, 10, 40),
    ("Sugar (1/4 kilo)", "Condiments", "pack", 22, 18, 3, 8, 30),
    ("Safeguard Soap", "Toiletries", "bar", 32, 27, 1.5, 5, 15),
    ("Palmolive Shampoo Sachet", "Toiletries", "sachet", 7, 5.5, 6, 15, 60),
    ("Colgate Sachet", "Toiletries", "sachet", 10, 8, 3, 10, 40),
    ("Tide Bar", "Household", "bar", 15, 12, 3, 8, 30),
    ("Downy Sachet", "Household", "sachet", 8, 6.5, 4, 10, 40),
    ("Ice (yelo)", "Others", "pack", 5, 2, 8, 0, 0),
]
ids = {}
for name, cat, unit, price, cost, _, reorder, stock in PRODUCTS:
    ids[name] = con.execute(
        "INSERT INTO products (name, category, unit, price_cents, cost_cents, stock, reorder_at) VALUES (?,?,?,?,?,?,?)",
        (name, cat, unit, to_cents(price), to_cents(cost), stock, reorder),
    ).lastrowid

sales, restocks = [], []
for i in range(56, -1, -1):
    d = end - dt.timedelta(days=i)
    boost = 1.35 if d.weekday() >= 5 else 1.0          # weekends are busier
    boost *= 1.25 if d.day in (15, 30, 31, 1) else 1.0  # sweldo (payday)
    growth = 1 + (56 - i) * 0.004                        # slowly growing store
    for name, _, _, price, cost, demand, reorder, _ in PRODUCTS:
        if name == "Royal Mismo" and i < 16:
            demand = 0                                   # a slow mover for the insights demo
        q = max(0, round(random.gauss(demand * boost * growth, demand * 0.35)))
        if i == 0:
            q = round(q * 0.55)                          # today is still in progress
        if q:
            sales.append((d.isoformat(), ids[name], q, to_cents(price), to_cents(cost), "seed"))
    if d.weekday() == 1 and i > 0:                       # Tuesday grocery run
        for name, _, _, _, cost, demand, reorder, start in PRODUCTS:
            if reorder:
                restocks.append((d.isoformat(), ids[name], max(start, round(demand * 9)), to_cents(cost), "Puregold"))

con.executemany("INSERT INTO sales (date, product_id, qty, price_cents, cost_cents, source) VALUES (?,?,?,?,?,?)", sales)
con.executemany("INSERT INTO restocks (date, product_id, qty, cost_cents, supplier) VALUES (?,?,?,?,?)", restocks)
# Stock on hand today: healthy, except three fast movers running low (the demo's restock moment).
LOW = {"Coke Mismo": 6, "Kopiko 3-in-1": 9, "Egg": 10}
for name, _, _, _, _, demand, reorder, _ in PRODUCTS:
    left = LOW.get(name, round(reorder * random.uniform(1.6, 3.2)) if reorder else 0)
    con.execute("UPDATE products SET stock = ? WHERE id = ?", (left, ids[name]))
con.commit()
print(f"seeded {len(PRODUCTS)} products, {len(sales)} sale lines, {len(restocks)} restocks into {DB_PATH.name}")
