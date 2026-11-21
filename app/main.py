from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.analysis import filter_orders, parse_orders, savings_tips, summarize

BASE = Path(__file__).resolve().parent
SAMPLE = BASE.parent / "sample_data" / "sample_orders.csv"
SAMPLE_ORDERS = parse_orders(SAMPLE.read_text())

app = FastAPI(title="BiteBudget")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
# money filter: 4733.77 -> $4,733.77
templates.env.filters["money"] = lambda x: f"${x:,.2f}"
# month filter: "2026-05" -> "May 2026"
templates.env.filters["month"] = lambda m: datetime.strptime(m, "%Y-%m").strftime("%b %Y")


# ---------- helpers ----------

def _to_date(value):
    # empty form fields come through as "" so only parse real values
    return date.fromisoformat(value) if value else None


def _to_float(value):
    return float(value) if value else None


def _money(value, label, required=False):
    """Read a dollar amount typed by the user, e.g. '12.50', '$12.50' or ''."""
    value = (value or "").replace("$", "").replace(",", "").strip()
    if not value:
        if required:
            raise ValueError(f"Enter the {label}.")
        return 0.0
    try:
        amount = float(value)
    except ValueError:
        raise ValueError(f"The {label} should be a number, like 12.50.")
    if amount < 0 or amount > 10000:
        raise ValueError(f"The {label} should be between $0 and $10,000.")
    return round(amount, 2)


def _read_filters(start, end, restaurant, budget):
    try:
        return _to_date(start), _to_date(end), restaurant or None, _to_float(budget)
    except ValueError:
        raise HTTPException(400, "Invalid date or budget value.")


def _dashboard_context(orders, start, end, restaurant, budget):
    filtered = filter_orders(orders, start, end, restaurant)
    return {
        "stats": summarize(filtered, budget),
        "tips": savings_tips(filtered),
        "restaurants": sorted({o["restaurant"] for o in orders}),
        "filters": {"start": start, "end": end, "restaurant": restaurant, "budget": budget},
    }


def render_home(request, error=None, form=None, notice=None, status=200,
                start=None, end=None, restaurant=None, budget=None):
    """Your saved orders as a dashboard, or the welcome page if there are none yet."""
    orders = db.get_orders()
    context = {
        "error": error,
        "form": form or {},
        "notice": notice,
        "names": db.restaurant_names(),
        "now": datetime.now().strftime("%Y-%m-%dT%H:%M"),
    }
    if not orders:
        return templates.TemplateResponse(request, "index.html", context, status_code=status)

    context.update(_dashboard_context(orders, start, end, restaurant, budget))
    context["mine"] = True
    context["recent"] = list(reversed(orders))[:8]
    context["all_count"] = len(orders)
    return templates.TemplateResponse(request, "results.html", context, status_code=status)


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    restaurant: Optional[str] = None,
    budget: Optional[str] = None,
    added: Optional[int] = None,
    imported: Optional[int] = None,
    deleted: Optional[int] = None,
):
    notice = None
    if added:
        order = db.get_order(added)
        if order:
            notice = f"Added {order['restaurant']}, ${order['total']:,.2f}."
    elif imported:
        notice = f"Imported {imported} orders."
    elif deleted:
        notice = "Order deleted."
    start, end, restaurant, budget = _read_filters(start, end, restaurant, budget)
    return render_home(request, notice=notice, start=start, end=end,
                       restaurant=restaurant, budget=budget)


@app.post("/orders")
def add_order(
    request: Request,
    restaurant: str = Form(""),
    when: str = Form(""),
    subtotal: str = Form(""),
    delivery_fee: str = Form(""),
    service_fee: str = Form(""),
    tip: str = Form(""),
):
    form = {"restaurant": restaurant, "when": when, "subtotal": subtotal,
            "delivery_fee": delivery_fee, "service_fee": service_fee, "tip": tip}
    try:
        name = restaurant.strip()
        if not name:
            raise ValueError("Enter the restaurant name.")
        try:
            when_dt = datetime.fromisoformat(when) if when else datetime.now()
        except ValueError:
            raise ValueError("That date doesn't look right.")
        order = {
            "restaurant": name[:80],
            "date": when_dt.replace(second=0, microsecond=0),
            "subtotal": _money(subtotal, "food price", required=True),
            "delivery_fee": _money(delivery_fee, "delivery fee"),
            "service_fee": _money(service_fee, "service fee"),
            "tip": _money(tip, "tip"),
        }
    except ValueError as e:
        return render_home(request, error=str(e), form=form, status=400)

    order["total"] = round(order["subtotal"] + order["delivery_fee"]
                           + order["service_fee"] + order["tip"], 2)
    order_id = db.add_order(order)
    return RedirectResponse(f"/?added={order_id}", status_code=303)


@app.post("/orders/{order_id}/delete")
def delete_order(order_id: int):
    db.delete_order(order_id)
    return RedirectResponse("/?deleted=1", status_code=303)


@app.post("/orders/delete-all")
def delete_all_orders():
    db.delete_all()
    return RedirectResponse("/", status_code=303)


@app.post("/analyze")
async def import_csv(request: Request, file: UploadFile = File(...)):
    """Import a CSV export. The orders are added to your saved orders."""
    try:
        # utf-8-sig also handles the hidden BOM character Excel adds to CSVs
        text = (await file.read()).decode("utf-8-sig")
        orders = parse_orders(text)
    except UnicodeDecodeError:
        return render_home(request, error="That doesn't look like a CSV file. Please upload a .csv export.", status=400)
    except ValueError as e:
        return render_home(request, error=str(e), status=400)
    if not orders:
        return render_home(request, error="The file has the right columns but no orders in it.", status=400)

    count = db.add_orders(orders)
    return RedirectResponse(f"/?imported={count}", status_code=303)


@app.get("/sample")
def sample():
    return RedirectResponse("/report/sample", status_code=303)


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report(
    request: Request,
    report_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    restaurant: Optional[str] = None,
    budget: Optional[str] = None,
):
    """Read-only demo dashboard built from the sample data."""
    if report_id != "sample":
        raise HTTPException(404, "Report not found.")
    start, end, restaurant, budget = _read_filters(start, end, restaurant, budget)
    context = _dashboard_context(SAMPLE_ORDERS, start, end, restaurant, budget)
    context["sample"] = True
    return templates.TemplateResponse(request, "results.html", context)
