"""Seed ~75 days of realistic demo spending. Wipes existing data. Run: uv run python seed.py"""

import datetime as dt
import random

from db import DB_PATH, connect, to_cents

random.seed(7)
DB_PATH.unlink(missing_ok=True)
con = connect()
end = dt.date.today()
rows = []


def add(day: dt.date, pesos: float, cat: str, merchant: str, note: str) -> None:
    rows.append((day.isoformat(), to_cents(pesos), cat, merchant, note, "seed"))


for i in range(75, 0, -1):
    d = end - dt.timedelta(days=i)
    weekday = d.weekday() < 5
    if weekday:
        add(d, random.choice([13, 15, 26, 30]), "Transport", "Jeepney", "commute")
        if random.random() < 0.35:
            add(d, random.randint(180, 420), "Transport", "Grab", "ride home")
        add(d, random.randint(110, 260), "Food", random.choice(["Jollibee", "Mang Inasal", "Karinderya", "7-Eleven", "Chowking"]), "lunch")
    if random.random() < 0.45:
        add(d, random.randint(120, 220), "Food", random.choice(["Starbucks", "Tim Hortons", "Bo's Coffee"]), "coffee")
    if d.weekday() == 5:
        add(d, random.randint(1400, 2800), "Groceries", random.choice(["SM Supermarket", "Puregold", "Robinsons Supermarket"]), "weekly groceries")
        if random.random() < 0.5:
            add(d, random.randint(450, 1500), "Entertainment", random.choice(["SM Cinema", "Netflix", "Timezone"]), "weekend")
    if d.weekday() == 6 and random.random() < 0.4:
        add(d, random.randint(600, 3500), "Shopping", random.choice(["Shopee", "Lazada", "Uniqlo"]), "order")
    if d.day == 5:
        add(d, random.randint(2300, 3400), "Bills", "Meralco", "electricity")
    if d.day == 8:
        add(d, random.randint(380, 650), "Bills", "Maynilad", "water")
    if d.day == 12:
        add(d, 1699, "Load/Internet", "PLDT Home", "fiber")
    if d.day in (1, 16):
        add(d, 299, "Load/Internet", "GCash Load", "Globe GoSURF")
    if random.random() < 0.05:
        add(d, random.randint(150, 900), "Health", "Mercury Drug", "medicine")

con.executemany(
    "INSERT INTO expenses (date, cents, category, merchant, note, source) VALUES (?,?,?,?,?,?)", rows
)
con.executemany(
    "INSERT INTO budgets (category, cents) VALUES (?, ?)",
    [("Food", to_cents(7000)), ("Transport", to_cents(3500)), ("Groceries", to_cents(9000)), ("Shopping", to_cents(2500))],
)
tasks = [("Pay Meralco bill", 2), ("Renew Grab Pay", None), ("Buy gift for Mama's birthday", 5), ("Submit BIR form", -1)]
for title, due in tasks:
    con.execute("INSERT INTO tasks (title, due) VALUES (?, ?)", (title, (end + dt.timedelta(days=due)).isoformat() if due is not None else None))
con.execute("INSERT INTO tasks (title, due, done_on) VALUES ('Book dentist', ?, ?)", ((end - dt.timedelta(days=2)).isoformat(),) * 2)
for name, rate in [("Workout", 0.55), ("Read", 0.7), ("Water", 0.8), ("Meditate", 0.35)]:
    hid = con.execute("INSERT INTO habits (name) VALUES (?)", (name,)).lastrowid
    for i in range(45, 0, -1):
        if random.random() < rate or (name == "Read" and i <= 6):
            con.execute("INSERT INTO habit_logs VALUES (?, ?)", (hid, (end - dt.timedelta(days=i)).isoformat()))
con.commit()
print(f"seeded {len(rows)} expenses into {DB_PATH.name}")
