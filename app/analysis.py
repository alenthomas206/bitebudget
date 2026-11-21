"""Reads an order history CSV and works out spending stats and savings tips."""

import csv
import io
from collections import defaultdict
from datetime import datetime

FEE_COLUMNS = ["subtotal", "delivery_fee", "service_fee", "tip"]
LATE_NIGHT_HOURS = {22, 23, 0, 1, 2, 3}


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


def filter_orders(orders, start=None, end=None, restaurant=None):
    """Keep only orders inside the date range and/or from one restaurant."""
    result = []
    for o in orders:
        day = o["date"].date()
        if start and day < start:
            continue
        if end and day > end:
            continue
        if restaurant and o["restaurant"] != restaurant:
            continue
        result.append(o)
    return result


def summarize(orders, budget=None):
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

    over_budget = []
    if budget:
        over_budget = [(m, round(amt - budget, 2)) for m, amt in months if amt > budget]

    return {
        "order_count": len(orders),
        "total_spent": round(total, 2),
        "average_order": round(total / len(orders), 2),
        "top_restaurants": [(name, round(amt, 2)) for name, amt in top[:5]],
        "monthly": [(m, round(amt, 2)) for m, amt in months],
        "breakdown": breakdown,
        "budget": budget,
        "over_budget": over_budget,
    }


def savings_tips(orders):
    """Simple rules that look at the orders and suggest ways to spend less."""
    tips = []
    total = sum(o["total"] for o in orders)
    months = len({o["date"].strftime("%Y-%m") for o in orders})

    # 1. fees you'd skip by picking up
    fees = sum(o["delivery_fee"] + o["service_fee"] for o in orders)
    if fees > 0:
        tips.append(
            f"You paid ${fees:.2f} in delivery and service fees "
            f"({fees / total * 100:.0f}% of everything you spent). "
            f"Picking up even half your orders would save about ${fees / 2 / months:.2f} a month."
        )

    # 2. late night ordering
    late = [o for o in orders if o["date"].hour in LATE_NIGHT_HOURS]
    if late:
        late_total = sum(o["total"] for o in late)
        tips.append(
            f"{len(late)} orders were placed between 10pm and 4am, costing ${late_total:.2f}. "
            "Having snacks at home for late nights could cut a lot of these."
        )

    # 3. favourite restaurant
    counts = defaultdict(lambda: [0, 0.0])
    for o in orders:
        counts[o["restaurant"]][0] += 1
        counts[o["restaurant"]][1] += o["total"]
    fav, (n, spent) = max(counts.items(), key=lambda x: x[1][0])
    if n >= 3:
        tips.append(
            f"Your most ordered spot is {fav} ({n} orders, ${spent:.2f}). "
            f"Skipping 1 in 3 of those orders would save about ${spent / 3 / months:.2f} a month."
        )

    # 4. small orders where fees eat a big chunk
    small = [o for o in orders if o["subtotal"] and
             (o["delivery_fee"] + o["service_fee"]) / o["subtotal"] > 0.3]
    if small:
        tips.append(
            f"{len(small)} orders had fees worth more than 30% of the food price. "
            "Combining small orders or ordering with friends spreads the fees out."
        )

    return tips
