"""Reads an order history CSV and works out spending stats and savings tips."""

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta

REQUIRED_COLUMNS = ["date", "restaurant", "total"]
FEE_COLUMNS = ["subtotal", "delivery_fee", "service_fee", "tip"]
LATE_NIGHT_HOURS = {22, 23, 0, 1, 2, 3}
DATE_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
]


def parse_date(value):
    """Try a few common date formats (apps export dates differently)."""
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"Couldn't read the date '{value}'")


def parse_orders(text):
    """Turn CSV text into a list of order dicts.
    Raises ValueError with a readable message if the file isn't usable."""
    reader = csv.DictReader(io.StringIO(text))
    columns = [c.strip().lower() for c in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise ValueError(f"Your file is missing these columns: {', '.join(missing)}")

    orders = []
    for line_no, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            order = {
                "date": parse_date(row["date"]),
                "restaurant": row["restaurant"],
                "total": float(row["total"].replace("$", "")),
            }
        except ValueError as e:
            raise ValueError(f"Problem on line {line_no}: {e}")
        for col in FEE_COLUMNS:
            order[col] = float((row.get(col) or "0").replace("$", ""))
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

    # spending per week (starting Monday), used when there are only 1-2 months of orders
    by_week = defaultdict(float)
    for o in orders:
        monday = (o["date"] - timedelta(days=o["date"].weekday())).date()
        by_week[monday] += o["total"]
    weeks = [(d.isoformat(), round(amt, 2)) for d, amt in sorted(by_week.items())]

    # share of the total for each part of the bill (used on the receipt)
    bill_total = sum(breakdown.values())
    percents = {col: round(v / bill_total * 100) if bill_total else 0
                for col, v in breakdown.items()}
    dates = [o["date"] for o in orders]

    return {
        "order_count": len(orders),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "percents": percents,
        "total_spent": round(total, 2),
        "average_order": round(total / len(orders), 2) if orders else 0,
        "top_restaurants": [(name, round(amt, 2)) for name, amt in top[:5]],
        "monthly": [(m, round(amt, 2)) for m, amt in months],
        "weekly": weeks,
        "breakdown": breakdown,
        "budget": budget,
        "over_budget": over_budget,
    }


def savings_tips(orders):
    """Simple rules that look at the orders and suggest ways to spend less."""
    tips = []
    if not orders:
        return tips
    total = sum(o["total"] for o in orders)
    months = len({o["date"].strftime("%Y-%m") for o in orders})

    # 1. fees you'd skip by picking up
    fees = sum(o["delivery_fee"] + o["service_fee"] for o in orders)
    if fees > 0 and total > 0:
        tips.append(
            f"You paid ${fees:,.2f} in delivery and service fees "
            f"({fees / total * 100:.0f}% of everything you spent). "
            f"Picking up even half your orders would save about ${fees / 2 / months:,.2f} a month."
        )

    # 2. late night ordering
    late = [o for o in orders if o["date"].hour in LATE_NIGHT_HOURS]
    if late:
        late_total = sum(o["total"] for o in late)
        tips.append(
            f"{len(late)} orders were placed between 10pm and 4am, costing ${late_total:,.2f}. "
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
            f"Your most ordered spot is {fav} ({n} orders, ${spent:,.2f}). "
            f"Skipping 1 in 3 of those orders would save about ${spent / 3 / months:,.2f} a month."
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
