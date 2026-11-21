import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.analysis import filter_orders, parse_orders, savings_tips, summarize

BASE = Path(__file__).resolve().parent
SAMPLE = BASE.parent / "sample_data" / "sample_orders.csv"

app = FastAPI(title="BiteBudget")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# Uploaded order lists are kept in memory so the filters can re-use them.
# They disappear when the server restarts.
REPORTS = {"sample": parse_orders(SAMPLE.read_text())}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8")
    report_id = uuid.uuid4().hex[:8]
    REPORTS[report_id] = parse_orders(text)
    return RedirectResponse(f"/report/{report_id}", status_code=303)


@app.get("/sample")
def sample():
    return RedirectResponse("/report/sample", status_code=303)


def _to_date(value):
    # empty form fields come through as "" so only parse real values
    return date.fromisoformat(value) if value else None


def _to_float(value):
    return float(value) if value else None


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report(
    request: Request,
    report_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    restaurant: Optional[str] = None,
    budget: Optional[str] = None,
):
    start, end, budget = _to_date(start), _to_date(end), _to_float(budget)
    orders = REPORTS[report_id]
    filtered = filter_orders(orders, start, end, restaurant or None)
    restaurants = sorted({o["restaurant"] for o in orders})
    return templates.TemplateResponse(request, "results.html", {
        "stats": summarize(filtered, budget),
        "tips": savings_tips(filtered),
        "restaurants": restaurants,
        "filters": {"start": start, "end": end, "restaurant": restaurant, "budget": budget},
    })
