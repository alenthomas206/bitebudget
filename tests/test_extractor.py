"""Tests for the paste-text extractor (V8)."""

from datetime import date

from fastapi.testclient import TestClient

from app import db
from app.extractor import extract, find_amount, find_date
from app.main import app

client = TestClient(app)
TODAY = date(2026, 11, 21)


def one(text, **kw):
    found, problem = extract(text, today=TODAY, **kw)
    assert problem is None, problem
    assert len(found) == 1
    return found[0]


# ---------- single expenses ----------

def test_bank_alert():
    e = one("RBC: You spent $23.40 at NORTHSIDE MARKET on Nov 20 with your Visa ending 4417.")
    assert e == {"description": "Northside Market", "amount": 23.40,
                 "date": "2026-11-20", "category": "Groceries"}


def test_alert_with_store_number_and_slash_date():
    e = one("TD Alert: A purchase of $58.15 was made at SHOPPERS DRUG MART #1234 using your card on 11/18/2026.")
    assert (e["description"], e["amount"], e["date"], e["category"]) == \
        ("Shoppers Drug Mart", 58.15, "2026-11-18", "Health")


def test_delivery_email_uses_total_not_subtotal_or_tip():
    e = one("""Subject: Your Sunday evening order with Uber Eats
Thanks for ordering, Alen
Here's your receipt for Pizza Palace.
Subtotal $31.50
Delivery Fee $3.99
Service Fee $4.73
Tip $4.00
Total CA$44.22
November 15, 2026""")
    assert (e["description"], e["amount"], e["date"], e["category"]) == \
        ("Pizza Palace", 44.22, "2026-11-15", "Eating out")


def test_store_receipt_picks_total_over_tax_and_change():
    e = one("""BURGER BARN
123 Main St, Barrie
11/12/2026 7:05 PM
Classic Burger 12.99
Fries 4.49
Subtotal 17.48
HST 2.27
TOTAL 19.75
VISA 19.75
Change 0.00""")
    assert (e["description"], e["amount"], e["date"]) == ("Burger Barn", 19.75, "2026-11-12")


def test_etransfer_rent():
    e = one("INTERAC e-Transfer: Your payment to Mike Landlord for $850.00 was sent on 2026-11-01. Memo: rent nov")
    assert (e["amount"], e["category"], e["date"]) == (850.0, "Rent", "2026-11-01")


def test_subscription_receipt():
    e = one("Your Spotify Premium receipt. Amount paid: $11.99. Date: Nov 20, 2026")
    assert (e["description"], e["category"]) == ("Spotify Premium", "Fun")


def test_yesterday_and_no_date():
    assert one("You paid $14.20 at Campus Shawarma yesterday")["date"] == "2026-11-20"
    e = one("Charged $9.99 at Corner Store")
    assert e["date"] == "2026-11-21"           # no date in the text -> today
    assert e["category"] == "Other"            # no keyword matched


def test_known_store_keeps_your_category():
    e = one("You spent $40.00 at Mike's Place", known={"mike's place": "Groceries"})
    assert e["category"] == "Groceries"


def test_store_not_found_still_returns_amount():
    e = one("$12.00\n$3.00")
    assert e["amount"] == 12.0 and e["description"] == "Unknown"


# ---------- several transactions ----------

def test_statement_lines():
    found, _ = extract("""Nov 18  NORTHSIDE MARKET  $58.15
Nov 19  SPOTIFY P1234  $11.99
Nov 19  PRESTO AUTOLOAD  $40.00
Nov 20  TIM HORTONS #4412  $6.45
Available balance $1,204.33""", today=TODAY)
    assert [(e["description"], e["amount"], e["category"]) for e in found] == [
        ("Northside Market", 58.15, "Groceries"),
        ("Spotify", 11.99, "Fun"),
        ("Presto Autoload", 40.0, "Transport"),
        ("Tim Hortons", 6.45, "Eating out"),
    ]


def test_comma_separated_lines():
    found, _ = extract("2026-11-18, Value Foods, 42.10\n2026-11-19, Petro-Canada, 55.00", today=TODAY)
    assert [(e["description"], e["date"]) for e in found] == \
        [("Value Foods", "2026-11-18"), ("Petro-Canada", "2026-11-19")]


# ---------- helpers and edge cases ----------

def test_find_amount_and_date_helpers():
    assert find_amount("Total: $1,250.00") == 1250.0
    assert find_amount("no money here") is None
    assert find_date("on 20 Nov 2026", TODAY) == date(2026, 11, 20)
    # a date without a year that would be in the future means last year
    assert find_date("Dec 25", TODAY) == date(2025, 12, 25)


def test_nothing_useful():
    assert extract("", today=TODAY) == ([], "Paste some text first.")
    found, problem = extract("are we still on for dinner tomorrow", today=TODAY)
    assert found == [] and "Couldn't find an amount" in problem
    assert "too much text" in extract("a" * 20001, today=TODAY)[1]


# ---------- routes ----------

def test_extract_route_saves_nothing():
    r = client.post("/extract", data={"text": "You spent $23.40 at NORTHSIDE MARKET on Nov 20"})
    assert r.status_code == 200
    assert r.json()["expenses"][0]["amount"] == 23.40
    assert db.get_expenses() == []


def test_extract_route_error():
    r = client.post("/extract", data={"text": "hello"})
    assert r.status_code == 422
    assert "amount" in r.json()["error"]


def test_bulk_add():
    rows = [{"date": "2026-11-18", "description": "Northside Market", "category": "Groceries", "amount": "58.15"},
            {"date": "2026-11-19", "description": "Spotify", "category": "Fun", "amount": 11.99}]
    r = client.post("/expenses/bulk", json=rows)
    assert r.json() == {"added": 2, "redirect": "/?bulk=2"}
    assert len(db.get_expenses()) == 2
    assert "Added 2 expenses from your pasted text" in client.get("/?bulk=2").text


def test_bulk_add_checks_every_row_and_saves_nothing_if_one_is_bad():
    rows = [{"date": "2026-11-18", "description": "Fine", "category": "Groceries", "amount": "5"},
            {"date": "2026-11-19", "description": "Bad", "category": "Snacks", "amount": "5"}]
    r = client.post("/expenses/bulk", json=rows)
    assert r.status_code == 422
    assert r.json()["error"] == "Row 2: Pick a category."
    assert db.get_expenses() == []


def test_bulk_add_limits():
    assert client.post("/expenses/bulk", json=[]).status_code == 422
    assert client.post("/expenses/bulk", json=["not a dict"]).status_code == 422


def test_paste_box_is_on_the_page():
    assert "Paste a bank alert, receipt or email instead" in client.get("/").text
