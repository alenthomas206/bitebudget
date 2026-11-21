"""Generates a fake food delivery order history so the app can be tried
without uploading real data. Run: python scripts/make_sample_data.py"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

RESTAURANTS = {
    # name: (min subtotal, max subtotal, how often it gets picked)
    "Burger Barn": (14, 32, 9),
    "Pho Saigon House": (16, 30, 6),
    "Pizza Palace": (20, 45, 7),
    "Campus Shawarma": (12, 22, 8),
    "Sushi Wave": (25, 60, 3),
    "Taco Loco": (13, 28, 4),
    "Golden Wok": (18, 38, 5),
    "Morning Grind Cafe": (7, 15, 6),
}


def make_orders(n=140, seed=42):
    random.seed(seed)
    start = datetime(2026, 5, 1)
    names = list(RESTAURANTS)
    weights = [RESTAURANTS[r][2] for r in names]
    rows = []
    for _ in range(n):
        day = start + timedelta(days=random.randint(0, 200))
        # most orders happen at lunch or late night
        hour = random.choice([12, 13, 18, 19, 20, 22, 23, 23, 0, 1])
        when = day.replace(hour=hour, minute=random.randint(0, 59))
        place = random.choices(names, weights)[0]
        low, high, _ = RESTAURANTS[place]
        subtotal = round(random.uniform(low, high), 2)
        delivery = random.choice([0.49, 1.99, 2.99, 3.99, 4.99])
        service = round(subtotal * 0.15, 2)
        tip = random.choice([0, 2, 3, 4, 5])
        total = round(subtotal + delivery + service + tip, 2)
        rows.append([when.strftime("%Y-%m-%d %H:%M"), place, subtotal,
                     delivery, service, tip, total])
    rows.sort(key=lambda r: r[0])
    return rows


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "sample_data" / "sample_orders.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "restaurant", "subtotal", "delivery_fee",
                    "service_fee", "tip", "total"])
        w.writerows(make_orders())
    print(f"wrote {out}")
