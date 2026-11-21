"""Reads an order history CSV and works out spending stats."""

import csv
import io
from collections import defaultdict


def parse_orders(text):
    """Turn CSV text into a list of order dicts."""
    reader = csv.DictReader(io.StringIO(text))
    orders = []
    for row in reader:
        orders.append({
            "date": row["date"],
            "restaurant": row["restaurant"],
            "total": float(row["total"]),
        })
    return orders


def summarize(orders):
    """Basic totals plus the restaurants you spend the most at."""
    total = sum(o["total"] for o in orders)
    by_place = defaultdict(float)
    for o in orders:
        by_place[o["restaurant"]] += o["total"]
    top = sorted(by_place.items(), key=lambda x: x[1], reverse=True)
    return {
        "order_count": len(orders),
        "total_spent": round(total, 2),
        "average_order": round(total / len(orders), 2),
        "top_restaurants": [(name, round(amt, 2)) for name, amt in top[:5]],
    }
