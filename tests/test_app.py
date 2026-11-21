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
    assert "Add your last order" in r.text


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


# ---------- saved orders (V6) ----------

from app import db  # noqa: E402


def add(**fields):
    data = {"restaurant": "Burger Barn", "when": "2026-11-20T19:30",
            "subtotal": "18.50", "delivery_fee": "2.99", "service_fee": "2.78", "tip": "3"}
    data.update(fields)
    return client.post("/orders", data=data)


def test_add_order_saves_and_works_out_total():
    r = add()
    assert r.status_code == 200
    assert "Added Burger Barn, $27.27" in r.text
    orders = db.get_orders()
    assert len(orders) == 1
    assert orders[0]["total"] == 27.27
    assert orders[0]["date"].hour == 19


def test_dashboard_shows_after_first_order():
    add()
    r = client.get("/")
    assert "Recent orders" in r.text
    assert "$27.27" in r.text


def test_add_order_accepts_dollar_signs_and_blank_fees():
    add(subtotal="$1,020.00", delivery_fee="", service_fee="", tip="")
    assert db.get_orders()[0]["total"] == 1020.0


def test_add_order_validation():
    assert "Enter the restaurant name" in add(restaurant="   ").text
    assert "food price should be a number" in add(subtotal="abc").text
    assert "between $0 and $10,000" in add(tip="-5").text
    assert "Enter the food price" in add(subtotal="").text
    assert "date doesn" in add(when="not-a-date").text
    assert db.get_orders() == []


def test_bad_input_keeps_what_was_typed():
    r = add(restaurant="Taco Loco", subtotal="abc")
    assert 'value="Taco Loco"' in r.text


def test_delete_order():
    add()
    order_id = db.get_orders()[0]["id"]
    r = client.post(f"/orders/{order_id}/delete")
    assert "Order deleted" in r.text
    assert db.get_orders() == []


def test_delete_all():
    add()
    add(restaurant="Pizza Palace")
    client.post("/orders/delete-all")
    assert db.get_orders() == []


def test_import_adds_to_saved_orders():
    add()
    r = client.post("/analyze", files={"file": ("orders.csv", SMALL_CSV, "text/csv")})
    assert "Imported 3 orders" in r.text
    assert len(db.get_orders()) == 4


def test_restaurant_suggestions_most_used_first():
    add(restaurant="Pizza Palace")
    add(restaurant="Burger Barn")
    add(restaurant="Burger Barn")
    assert db.restaurant_names() == ["Burger Barn", "Pizza Palace"]
    assert '<option value="Burger Barn">' in client.get("/").text


def test_sample_demo_does_not_touch_saved_orders():
    r = client.get("/sample")
    assert "made-up sample data" in r.text
    assert db.get_orders() == []


def test_weekly_totals_start_on_monday():
    stats = summarize(parse_orders(SMALL_CSV))
    # Jan 5 2026 is a Monday, Jan 20 is in the week of Jan 19, Feb 3 in the week of Feb 2
    assert stats["weekly"] == [("2026-01-05", 25.0), ("2026-01-19", 15.5), ("2026-02-02", 39.5)]
