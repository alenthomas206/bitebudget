"""Tests for BiteBudget. Run with: python -m pytest"""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis import filter_orders, parse_orders, savings_tips, summarize
from app.main import app

SAMPLE = (Path(__file__).resolve().parent.parent / "sample_data" / "sample_orders.csv").read_text()
client = TestClient(app)

SMALL_CSV = """date,restaurant,subtotal,delivery_fee,service_fee,tip,total
2026-01-05 12:00,Burger Barn,20,2,3,0,25
2026-01-20 23:30,Burger Barn,10,4,1.5,0,15.5
2026-02-03 13:00,Pizza Palace,30,0,4.5,5,39.5
"""


# ---------- analysis ----------

def test_parse_sample_has_all_orders():
    assert len(parse_orders(SAMPLE)) == 140


def test_summary_numbers():
    stats = summarize(parse_orders(SMALL_CSV))
    assert stats["order_count"] == 3
    assert stats["total_spent"] == 80.0
    assert stats["average_order"] == 26.67
    assert stats["top_restaurants"][0] == ("Burger Barn", 40.5)
    assert stats["monthly"] == [("2026-01", 40.5), ("2026-02", 39.5)]


def test_filter_by_restaurant_and_date():
    orders = parse_orders(SMALL_CSV)
    assert len(filter_orders(orders, restaurant="Pizza Palace")) == 1
    assert len(filter_orders(orders, start=date(2026, 1, 10))) == 2
    assert len(filter_orders(orders, end=date(2026, 1, 31))) == 2


def test_budget_flags_months_over():
    stats = summarize(parse_orders(SMALL_CSV), budget=40)
    assert stats["over_budget"] == [("2026-01", 0.5)]


def test_tips_mention_fees_and_late_night():
    tips = " ".join(savings_tips(parse_orders(SMALL_CSV)))
    assert "fees" in tips
    assert "10pm" in tips


def test_only_required_columns_works():
    csv_text = "date,restaurant,total\n2026-03-01 18:00,Taco Loco,22.10\n"
    orders = parse_orders(csv_text)
    stats = summarize(orders)
    assert stats["total_spent"] == 22.10
    savings_tips(orders)  # should not crash without fee columns


def test_empty_file_does_not_crash():
    orders = parse_orders("date,restaurant,total\n")
    stats = summarize(orders)
    assert stats["order_count"] == 0
    assert savings_tips(orders) == []


def test_other_date_formats():
    csv_text = "date,restaurant,total\n2026-03-01,A,10\n03/02/2026 7:15 PM,B,12\n"
    orders = parse_orders(csv_text)
    assert orders[0]["date"].day == 1
    assert orders[1]["date"].month == 3 and orders[1]["date"].hour == 19


# ---------- web pages ----------

def test_home_page_loads():
    r = client.get("/")
    assert r.status_code == 200
    assert "Analyze my orders" in r.text


def test_sample_report_loads():
    r = client.get("/sample")
    assert r.status_code == 200
    assert "Ways to save" in r.text


def test_upload_flow():
    r = client.post("/analyze", files={"file": ("orders.csv", SMALL_CSV, "text/csv")})
    assert r.status_code == 200
    assert "$80.00" in r.text


def test_empty_form_fields_are_ignored():
    r = client.get("/report/sample?start=&end=&restaurant=&budget=")
    assert r.status_code == 200


def test_filter_with_no_matches_shows_message():
    r = client.get("/report/sample?start=2020-01-01&end=2020-01-31")
    assert r.status_code == 200
    assert "No orders match" in r.text


def test_wrong_columns_shows_friendly_error():
    bad = "name,price\nfries,3\n"
    r = client.post("/analyze", files={"file": ("bad.csv", bad, "text/csv")})
    assert r.status_code == 400
    assert "missing" in r.text.lower()


def test_unknown_report_is_404():
    r = client.get("/report/doesnotexist")
    assert r.status_code == 404
