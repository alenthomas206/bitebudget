"""Spending maths for Tally: reading CSVs, totals, categories, budget and tips."""

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta

# Categories, and whether each one is a need or a want.
# Needs are things you have to pay for. Wants are where savings usually come from.
CATEGORIES = {
    "Rent": "need",
    "Groceries": "need",
    "Bills": "need",
    "Transport": "need",
    "School": "need",
    "Health": "need",
    "Eating out": "want",
    "Shopping": "want",
    "Fun": "want",
    "Other": "want",
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
]


def parse_date(value):
    """Try a few common date formats (banks and apps export dates differently)."""
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"Couldn't read the date '{value}'")


def clean_category(value):
    """Match a category name loosely ('groceries' -> 'Groceries'), otherwise 'Other'."""
    value = (value or "").strip().lower()
    for name in CATEGORIES:
        if name.lower() == value:
            return name
    return "Other"


def parse_csv(text):
    """Turn CSV text into a list of expense dicts.

    Needs date, description and amount columns (category is optional).
    The old BiteBudget delivery format (restaurant, total) still works too.
    Raises ValueError with a readable message if the file isn't usable.
    """
    reader = csv.DictReader(io.StringIO(text))
    columns = [c.strip().lower() for c in (reader.fieldnames or [])]

    old_format = "restaurant" in columns and "total" in columns
    if old_format:
        desc_col, amount_col = "restaurant", "total"
    else:
        desc_col, amount_col = "description", "amount"
    missing = [c for c in ["date", desc_col, amount_col] if c not in columns]
    if missing:
        raise ValueError(f"Your file is missing these columns: {', '.join(missing)}")

    expenses = []
    for line_no, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            expenses.append({
                "date": parse_date(row["date"]),
                "description": row[desc_col],
                "category": "Eating out" if old_format else clean_category(row.get("category")),
                "amount": float(row[amount_col].replace("$", "").replace(",", "")),
            })
        except ValueError as e:
            raise ValueError(f"Problem on line {line_no}: {e}")
    return expenses


def filter_expenses(expenses, start=None, end=None, category=None):
    """Keep only expenses inside the date range and/or in one category."""
    result = []
    for e in expenses:
        day = e["date"].date()
        if start and day < start:
            continue
        if end and day > end:
            continue
        if category and e["category"] != category:
            continue
        result.append(e)
    return result


def summarize(expenses, budget=None):
    """Totals, categories, needs vs wants, spending over time and the budget check."""
    total = sum(e["amount"] for e in expenses)

    by_category = defaultdict(float)
    by_desc = defaultdict(float)
    by_month = defaultdict(float)
    # needs and wants per month and per week (for the stacked chart)
    month_split = defaultdict(lambda: [0.0, 0.0])
    week_split = defaultdict(lambda: [0.0, 0.0])
    for e in expenses:
        by_category[e["category"]] += e["amount"]
        by_desc[e["description"]] += e["amount"]
        month = e["date"].strftime("%Y-%m")
        by_month[month] += e["amount"]
        monday = (e["date"] - timedelta(days=e["date"].weekday())).date().isoformat()
        slot = 0 if CATEGORIES.get(e["category"], "want") == "need" else 1
        month_split[month][slot] += e["amount"]
        week_split[monday][slot] += e["amount"]

    categories = [
        {"name": name, "amount": round(amt, 2), "kind": CATEGORIES.get(name, "want"),
         "percent": round(amt / total * 100) if total else 0}
        for name, amt in sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    ]
    needs = sum(c["amount"] for c in categories if c["kind"] == "need")
    months = sorted(by_month.items())

    over_budget = []
    if budget:
        over_budget = [(m, round(amt - budget, 2)) for m, amt in months if amt > budget]

    dates = [e["date"] for e in expenses]
    return {
        "count": len(expenses),
        "total": round(total, 2),
        "average": round(total / len(expenses), 2) if expenses else 0,
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "categories": categories,
        "needs": round(needs, 2),
        "wants": round(total - needs, 2),
        "needs_percent": round(needs / total * 100) if total else 0,
        "top_items": [(d, round(a, 2)) for d, a in
                      sorted(by_desc.items(), key=lambda x: x[1], reverse=True)[:5]],
        "monthly": [(m, round(a, 2)) for m, a in months],
        # [period, needs, wants]
        "monthly_split": [(m, round(n, 2), round(w, 2)) for m, (n, w) in sorted(month_split.items())],
        "weekly_split": [(d, round(n, 2), round(w, 2)) for d, (n, w) in sorted(week_split.items())],
        "budget": budget,
        "over_budget": over_budget,
    }


def savings_tips(expenses):
    """Simple rules that look at your spending and point out where money could be saved.
    Needs (rent, groceries, bills...) are left alone; the tips focus on wants."""
    tips = []
    if not expenses:
        return tips
    total = sum(e["amount"] for e in expenses)
    months = len({e["date"].strftime("%Y-%m") for e in expenses})
    wants = [e for e in expenses if CATEGORIES.get(e["category"], "want") == "want"]
    wants_total = sum(e["amount"] for e in wants)

    # 1. needs vs wants, compared with the 50/30/20 guideline
    if total > 0:
        share = wants_total / total * 100
        if share > 30:
            tips.append(
                f"Wants (eating out, shopping, fun, other) were {share:.0f}% of your spending. "
                "The 50/30/20 rule of thumb suggests keeping wants around 30%."
            )
        else:
            tips.append(
                f"Wants were only {share:.0f}% of your spending, under the 30% "
                "the 50/30/20 rule of thumb suggests. Most of your money goes to needs."
            )

    # 2. the biggest want category
    by_cat = defaultdict(float)
    for e in wants:
        by_cat[e["category"]] += e["amount"]
    if by_cat:
        cat, amt = max(by_cat.items(), key=lambda x: x[1])
        tips.append(
            f"Your biggest want is {cat.lower()} at ${amt:,.2f}. "
            f"Cutting it by a fifth would save about ${amt * 0.2 / months:,.2f} a month."
        )

    # 3. small purchases that add up
    small = [e for e in wants if e["amount"] < 10]
    if len(small) >= 5:
        small_total = sum(e["amount"] for e in small)
        tips.append(
            f"{len(small)} small purchases under $10 added up to ${small_total:,.2f}. "
            "They're easy to miss but they add up."
        )

    # 4. this month vs last month
    by_month = defaultdict(float)
    for e in expenses:
        by_month[e["date"].strftime("%Y-%m")] += e["amount"]
    if len(by_month) >= 2:
        (prev_m, prev), (last_m, last) = sorted(by_month.items())[-2:]
        if prev > 0:
            change = (last - prev) / prev * 100
            word = "more" if change > 0 else "less"
            name = datetime.strptime(last_m, "%Y-%m").strftime("%B")
            prev_name = datetime.strptime(prev_m, "%Y-%m").strftime("%B")
            # the current month isn't over yet, so don't compare it like a full month
            so_far = " so far" if last_m == datetime.now().strftime("%Y-%m") else ""
            tips.append(f"You've spent {abs(change):.0f}% {word} in {name}{so_far} than in {prev_name} "
                        f"(${last:,.2f} vs ${prev:,.2f}).")

    return tips
