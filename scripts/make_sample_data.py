"""Generates six months of made-up student expenses so Tally can be tried
without entering real data. Run: python scripts/make_sample_data.py"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

START = date(2026, 5, 1)
END = date(2026, 11, 20)


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def make_expenses(seed=7):
    random.seed(seed)
    rows = []

    def add(d, desc, cat, low, high=None):
        amount = low if high is None else round(random.uniform(low, high), 2)
        rows.append([d.isoformat(), desc, cat, f"{amount:.2f}"])

    for d in days():
        # fixed monthly costs
        if d.day == 1:
            add(d, "Rent", "Rent", 850)
            add(d, "Monthly transit pass", "Transport", 92)
        if d.day == 5:
            add(d, "Internet (my half)", "Bills", 40)
        if d.day == 15:
            add(d, "Phone bill", "Bills", 45)
        if d.day == 20:
            add(d, "Music streaming", "Fun", 11.99)

        # groceries about once a week
        if d.weekday() == 5:
            add(d, random.choice(["Northside Market", "Value Foods"]), "Groceries", 38, 95)

        # coffee and eating out
        if random.random() < 0.35:
            add(d, "Morning Grind Cafe", "Eating out", 4.25, 8.50)
        if random.random() < 0.18:
            place = random.choice(["Campus Shawarma", "Burger Barn", "Pizza Palace",
                                   "Pho Saigon House", "Taco Loco"])
            add(d, place, "Eating out", 13, 34)

        # the occasional ride, shopping trip, night out or pharmacy run
        if random.random() < 0.05:
            add(d, "Ride share", "Transport", 12, 26)
        if random.random() < 0.06:
            add(d, random.choice(["Clothing store", "Online order", "Dollar store"]),
                "Shopping", 9, 70)
        if random.random() < 0.05:
            add(d, random.choice(["Movie night", "Bowling with friends", "New game"]),
                "Fun", 12, 45)
        if random.random() < 0.02:
            add(d, "Pharmacy", "Health", 8, 30)

    # back to school
    add(date(2026, 9, 3), "Textbooks", "School", 186.40)
    add(date(2026, 9, 10), "Printing credits", "School", 15)
    add(date(2026, 10, 30), "Halloween party", "Fun", 35)

    rows.sort(key=lambda r: r[0])
    return rows


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "sample_data" / "sample_expenses.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "category", "amount"])
        w.writerows(make_expenses())
    print(f"wrote {out}")
