"""Reads an order history CSV and works out spending stats."""

import csv
import io
from collections import defaultdict
from datetime import datetime

FEE_COLUMNS = ["subtotal", "delivery_fee", "service_fee", "tip"]


def parse_orders(text):
    """Turn CSV text into a list of order dicts."""
    reader = csv.DictReader(io.StringIO(text))
    orders = []
    for row in reader:
        order = {
            "date": datetime.strptime(row["date"], "%Y-%m-%d %H:%M"),
            "restaurant": row["restaurant"],
            "total": float(row["total"]),
        }
        for col in FEE_COLUMNS:
            order[col] = float(row.get(col) or 0)
        orders.append(order)
    return orders


def summarize(orders):
    """Totals, top restaurants, spending per month and where the money went."""
    total = sum(o["total"] for o in orders)

    by_place = defaultdict(float)
    by_month = defaultdict(float)
    for o in orders:
        by_place[o["restaurant"]] += o["total"]
        by_month[o["date"].strftime("%Y-%m")] += o["total"]

    top = sorted(by_place.items(), key=lambda x: x[1], reverse=True)
    months = sorted(by_month.items())
    breakdown = {col: round(sum(o[col] for o in orders), 2) for col in FEE_COLUMNS}

    return {
        "order_count": len(orders),
        "total_spent": round(total, 2),
        "average_order": round(total / len(orders), 2),
        "top_restaurants": [(name, round(amt, 2)) for name, amt in top[:5]],
        "monthly": [(m, round(amt, 2)) for m, amt in months],
        "breakdown": breakdown,
    }
