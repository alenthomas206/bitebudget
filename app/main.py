from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.analysis import CATEGORIES, filter_expenses, parse_csv, savings_tips, summarize
from app.extractor import extract

BASE = Path(__file__).resolve().parent
SAMPLE = BASE.parent / "sample_data" / "sample_expenses.csv"
SAMPLE_EXPENSES = parse_csv(SAMPLE.read_text())

app = FastAPI(title="Tally")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
# money filter: 4733.77 -> $4,733.77
templates.env.filters["money"] = lambda x: f"${x:,.2f}"
# month filter: "2026-05" -> "May 2026"
templates.env.filters["month"] = lambda m: datetime.strptime(m, "%Y-%m").strftime("%b %Y")
# css class for a category: "Eating out" -> "cat-eating-out"
templates.env.filters["catclass"] = lambda c: "cat-" + c.lower().replace(" ", "-")
templates.env.globals["CATEGORIES"] = CATEGORIES


# ---------- helpers ----------

def _to_date(value):
    # empty form fields come through as "" so only parse real values
    return date.fromisoformat(value) if value else None


def _to_float(value):
    return float(value) if value else None


def _money(value):
    """Read a dollar amount typed by the user, e.g. '12.50' or '$1,200'."""
    value = (value or "").replace("$", "").replace(",", "").strip()
    if not value:
        raise ValueError("Enter the amount.")
    try:
        amount = float(value)
    except ValueError:
        raise ValueError("The amount should be a number, like 12.50.")
    if amount <= 0 or amount > 100000:
        raise ValueError("The amount should be more than $0 and at most $100,000.")
    return round(amount, 2)


def _read_filters(start, end, category, budget):
    try:
        return _to_date(start), _to_date(end), category or None, _to_float(budget)
    except ValueError:
        raise HTTPException(400, "Invalid date or budget value.")


def _dashboard_context(expenses, start, end, category, budget):
    filtered = filter_expenses(expenses, start, end, category)
    return {
        "stats": summarize(filtered, budget),
        "tips": savings_tips(filtered),
        "filters": {"start": start, "end": end, "category": category, "budget": budget},
    }


def render_home(request, error=None, form=None, notice=None, status=200,
                start=None, end=None, category=None, budget=None):
    """Your saved expenses as a dashboard, or the welcome page if there are none yet."""
    expenses = db.get_expenses()
    context = {
        "error": error,
        "form": form or {},
        "notice": notice,
        "past": db.past_descriptions(),
        "today": date.today().isoformat(),
    }
    if not expenses:
        return templates.TemplateResponse(request, "index.html", context, status_code=status)

    context.update(_dashboard_context(expenses, start, end, category, budget))
    context["mine"] = True
    context["recent"] = list(reversed(expenses))[:10]
    context["all_count"] = len(expenses)
    return templates.TemplateResponse(request, "results.html", context, status_code=status)


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    category: Optional[str] = None,
    budget: Optional[str] = None,
    added: Optional[int] = None,
    imported: Optional[int] = None,
    deleted: Optional[int] = None,
    bulk: Optional[int] = None,
):
    notice = None
    if added:
        e = db.get_expense(added)
        if e:
            notice = f"Added {e['description']}, ${e['amount']:,.2f} ({e['category']})."
    elif imported:
        notice = f"Imported {imported} expenses."
    elif bulk:
        notice = f"Added {bulk} expense{'s' if bulk != 1 else ''} from your pasted text."
    elif deleted:
        notice = "Expense deleted."
    start, end, category, budget = _read_filters(start, end, category, budget)
    return render_home(request, notice=notice, start=start, end=end,
                       category=category, budget=budget)


@app.post("/expenses")
def add_expense(
    request: Request,
    description: str = Form(""),
    amount: str = Form(""),
    category: str = Form(""),
    day: str = Form(""),
):
    form = {"description": description, "amount": amount, "category": category, "day": day}
    try:
        expense = _check_expense(description, amount, category, day)
    except ValueError as e:
        return render_home(request, error=str(e), form=form, status=400)

    expense_id = db.add_expense(expense)
    return RedirectResponse(f"/?added={expense_id}", status_code=303)


def _check_expense(description, amount, category, day):
    """Validate one expense from a form or from the extractor. Raises ValueError."""
    desc = (description or "").strip()
    if not desc:
        raise ValueError("Enter what the expense was for.")
    if category not in CATEGORIES:
        raise ValueError("Pick a category.")
    try:
        when = datetime.fromisoformat(day) if day else datetime.now()
    except ValueError:
        raise ValueError("That date doesn't look right.")
    return {"description": desc[:80], "amount": _money(str(amount)),
            "category": category, "date": when}


@app.post("/extract")
def extract_text(text: str = Form("")):
    """Read pasted text and return the expenses found. Nothing is saved yet."""
    known = {d.lower(): c for d, c in db.past_descriptions()}
    expenses, problem = extract(text, known=known)
    if problem:
        return JSONResponse({"error": problem}, status_code=422)
    return {"expenses": expenses}


@app.post("/expenses/bulk")
def add_many(items: list = Body(...)):
    """Save several expenses at once (the ones ticked after pasting a statement)."""
    if not items or len(items) > 200:
        return JSONResponse({"error": "Pick between 1 and 200 expenses."}, status_code=422)
    checked = []
    for i, item in enumerate(items, start=1):
        try:
            checked.append(_check_expense(item.get("description"), item.get("amount"),
                                          item.get("category"), item.get("date")))
        except (ValueError, AttributeError) as e:
            return JSONResponse({"error": f"Row {i}: {e}"}, status_code=422)
    count = db.add_expenses(checked)
    return {"added": count, "redirect": f"/?bulk={count}"}


@app.post("/expenses/{expense_id}/delete")
def delete_expense(expense_id: int):
    db.delete_expense(expense_id)
    return RedirectResponse("/?deleted=1", status_code=303)


@app.post("/expenses/delete-all")
def delete_all_expenses():
    db.delete_all()
    return RedirectResponse("/", status_code=303)


@app.post("/import")
async def import_csv(request: Request, file: UploadFile = File(...)):
    """Import a CSV (e.g. exported from a bank). Rows are added to your saved expenses."""
    try:
        # utf-8-sig also handles the hidden BOM character Excel adds to CSVs
        text = (await file.read()).decode("utf-8-sig")
        expenses = parse_csv(text)
    except UnicodeDecodeError:
        return render_home(request, error="That doesn't look like a CSV file. Please upload a .csv file.", status=400)
    except ValueError as e:
        return render_home(request, error=str(e), status=400)
    if not expenses:
        return render_home(request, error="The file has the right columns but no expenses in it.", status=400)

    count = db.add_expenses(expenses)
    return RedirectResponse(f"/?imported={count}", status_code=303)


@app.get("/sample", response_class=HTMLResponse)
def sample(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    category: Optional[str] = None,
    budget: Optional[str] = None,
):
    """Read-only demo dashboard built from the sample data."""
    start, end, category, budget = _read_filters(start, end, category, budget)
    context = _dashboard_context(SAMPLE_EXPENSES, start, end, category, budget)
    context["sample"] = True
    return templates.TemplateResponse(request, "results.html", context)
