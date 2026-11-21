"""Tests for Tally. Run with: python -m pytest"""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.analysis import (clean_category, filter_expenses, parse_csv, savings_tips,
                          summarize)
from app.main import app

SAMPLE = (Path(__file__).resolve().parent.parent / "sample_data" / "sample_expenses.csv").read_text()
client = TestClient(app)

SMALL_CSV = """date,description,category,amount
2026-01-01,Rent,Rent,800
2026-01-05,Groceries,Groceries,60
2026-01-06,Coffee,Eating out,5
2026-01-20,Movie night,Fun,35
2026-02-01,Rent,Rent,800
2026-02-03,Shoes,Shopping,100
"""


def add(**fields):
    data = {"description": "Groceries", "amount": "54.20", "category": "Groceries",
            "day": "2026-11-20"}
    data.update(fields)
    return client.post("/expenses", data=data)


# ---------- reading files ----------

def test_parse_sample_file():
    expenses = parse_csv(SAMPLE)
    assert len(expenses) == 229
    assert {e["category"] for e in expenses} <= {
        "Rent", "Groceries", "Bills", "Transport", "School", "Health",
        "Eating out", "Shopping", "Fun", "Other"}


def test_category_is_optional_and_matched_loosely():
    expenses = parse_csv("date,description,amount,category\n"
                         "2026-03-01,Bus,3.50,transport\n"
                         "2026-03-02,Gift,20,presents\n"
                         "2026-03-03,Snack,2.50,\n")
    assert [e["category"] for e in expenses] == ["Transport", "Other", "Other"]
    assert clean_category("  GROCERIES ") == "Groceries"


def test_old_bitebudget_delivery_csv_still_imports():
    expenses = parse_csv("date,restaurant,total\n2026-03-01 18:00,Taco Loco,22.10\n")
    assert expenses[0]["description"] == "Taco Loco"
    assert expenses[0]["category"] == "Eating out"
    assert expenses[0]["amount"] == 22.10


def test_other_date_formats_and_dollar_signs():
    expenses = parse_csv('date,description,amount\n03/02/2026,Books,"$1,020.00"\n2026-03-05 7:30,Bus,3\n')
    assert expenses[0]["date"].month == 3 and expenses[0]["amount"] == 1020.0
    assert expenses[1]["date"].day == 5


def test_empty_file_does_not_crash():
    expenses = parse_csv("date,description,amount\n")
    assert summarize(expenses)["count"] == 0
    assert savings_tips(expenses) == []


# ---------- maths ----------

def test_summary_totals_and_needs_vs_wants():
    stats = summarize(parse_csv(SMALL_CSV))
    assert stats["count"] == 6
    assert stats["total"] == 1800.0
    assert stats["needs"] == 1660.0     # rent x2 + groceries
    assert stats["wants"] == 140.0      # coffee + movie + shoes
    assert stats["needs_percent"] == 92
    assert stats["categories"][0] == {"name": "Rent", "amount": 1600.0, "kind": "need", "percent": 89}
    assert stats["monthly"] == [("2026-01", 900.0), ("2026-02", 900.0)]
    assert stats["monthly_split"] == [("2026-01", 860.0, 40.0), ("2026-02", 800.0, 100.0)]


def test_weekly_totals_start_on_monday():
    stats = summarize(parse_csv(SMALL_CSV))
    # Jan 1 2026 is a Thursday, so it falls in the week starting Monday Dec 29
    assert stats["weekly_split"][0] == ("2025-12-29", 800.0, 0.0)
    assert stats["weekly_split"][1] == ("2026-01-05", 60.0, 5.0)


def test_filter_by_category_and_date():
    expenses = parse_csv(SMALL_CSV)
    assert len(filter_expenses(expenses, category="Rent")) == 2
    assert len(filter_expenses(expenses, start=date(2026, 2, 1))) == 2
    assert len(filter_expenses(expenses, end=date(2026, 1, 5))) == 2


def test_budget_flags_months_over():
    stats = summarize(parse_csv(SMALL_CSV), budget=880)
    assert stats["over_budget"] == [("2026-01", 20.0), ("2026-02", 20.0)]


def test_tips_leave_needs_alone():
    tips = " ".join(savings_tips(parse_csv(SMALL_CSV)))
    assert "under the 30%" in tips              # wants are only 8%
    assert "biggest want is shopping" in tips
    assert "rent" not in tips.lower()           # never tells you to cut rent


def test_tips_flag_high_wants_and_small_purchases():
    rows = ["date,description,category,amount", "2026-01-01,Rent,Rent,100"]
    rows += [f"2026-01-{d:02d},Coffee,Eating out,6" for d in range(2, 22)]
    tips = " ".join(savings_tips(parse_csv("\n".join(rows))))
    assert "were 55% of your spending" in tips
    assert "20 small purchases under $10" in tips


def test_month_comparison_says_so_far_for_current_month():
    this_month = datetime.now().strftime("%Y-%m")
    last = (datetime.now().replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m")
    text = f"date,description,amount\n{last}-10,A,100\n{this_month}-01,B,50\n"
    tips = " ".join(savings_tips(parse_csv(text)))
    assert "50% less" in tips and "so far" in tips


# ---------- saved expenses ----------

def test_welcome_page_when_empty():
    r = client.get("/")
    assert r.status_code == 200
    assert "Add your first expense" in r.text


def test_add_expense():
    r = add()
    assert r.status_code == 200
    assert "Added Groceries, $54.20 (Groceries)" in r.text
    saved = db.get_expenses()
    assert len(saved) == 1 and saved[0]["date"] == datetime(2026, 11, 20)


def test_dashboard_after_first_expense():
    add()
    r = client.get("/")
    assert "Recent expenses" in r.text
    assert "$54.20" in r.text


def test_add_expense_validation():
    assert "Enter what the expense was for" in add(description="  ").text
    assert "amount should be a number" in add(amount="abc").text
    assert "more than $0" in add(amount="0").text
    assert "Enter the amount" in add(amount="").text
    assert "Pick a category" in add(category="Snacks").text
    assert "date doesn" in add(day="not-a-date").text
    assert db.get_expenses() == []


def test_bad_input_keeps_what_was_typed():
    r = add(description="Bus pass", amount="abc", category="Transport")
    assert 'value="Bus pass"' in r.text
    assert "<option selected>Transport</option>" in r.text


def test_amount_accepts_dollar_sign_and_commas():
    add(description="Rent", category="Rent", amount="$1,250")
    assert db.get_expenses()[0]["amount"] == 1250.0


def test_delete_expense_and_message_survives_last_delete():
    add()
    expense_id = db.get_expenses()[0]["id"]
    r = client.post(f"/expenses/{expense_id}/delete")
    assert "Expense deleted" in r.text
    assert db.get_expenses() == []


def test_delete_all():
    add()
    add(description="Rent", category="Rent", amount="850")
    client.post("/expenses/delete-all")
    assert db.get_expenses() == []


def test_past_descriptions_remember_category():
    add(description="Phone bill", category="Bills", amount="45")
    add(description="Groceries")
    add(description="Groceries")
    assert db.past_descriptions() == [("Groceries", "Groceries"), ("Phone bill", "Bills")]


def test_import_adds_to_saved_expenses():
    add()
    r = client.post("/import", files={"file": ("bank.csv", SMALL_CSV, "text/csv")})
    assert "Imported 6 expenses" in r.text
    assert len(db.get_expenses()) == 7


def test_import_wrong_columns_shows_error():
    r = client.post("/import", files={"file": ("bad.csv", "name,price\nfries,3\n", "text/csv")})
    assert r.status_code == 400
    assert "missing these columns" in r.text


def test_import_non_csv_file():
    r = client.post("/import", files={"file": ("pic.png", bytes(range(256)), "image/png")})
    assert r.status_code == 400
    assert "look like a CSV" in r.text


def test_old_bitebudget_orders_are_moved_once(tmp_path, monkeypatch):
    old = tmp_path / "bitebudget.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE orders (date TEXT, restaurant TEXT, total REAL)")
    conn.execute("INSERT INTO orders VALUES ('2026-11-03T13:10', 'Campus Shawarma', 21.32)")
    conn.commit()
    conn.close()

    monkeypatch.delenv("TALLY_DB")
    monkeypatch.setattr(db, "DEFAULT_PATH", tmp_path / "tally.db")
    monkeypatch.setattr(db, "OLD_PATH", old)

    moved = db.get_expenses()
    assert [(e["description"], e["category"], e["amount"]) for e in moved] == \
        [("Campus Shawarma", "Eating out", 21.32)]
    db.delete_all()
    assert db.get_expenses() == []   # clearing your data doesn't bring the old orders back


# ---------- sample demo and filters ----------

def test_sample_demo():
    r = client.get("/sample")
    assert r.status_code == 200
    assert "made-up sample data" in r.text
    assert "Where you could save" in r.text
    assert db.get_expenses() == []


def test_empty_form_fields_are_ignored():
    r = client.get("/sample?start=&end=&category=&budget=")
    assert r.status_code == 200


def test_filter_with_no_matches_shows_message():
    r = client.get("/sample?start=2020-01-01&end=2020-01-31")
    assert "No expenses match" in r.text


def test_bad_filter_value_is_400():
    assert client.get("/sample?start=yesterday").status_code == 400
