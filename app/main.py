from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.analysis import parse_orders, summarize

BASE = Path(__file__).resolve().parent
SAMPLE = BASE.parent / "sample_data" / "sample_orders.csv"

app = FastAPI(title="BiteBudget")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8")
    stats = summarize(parse_orders(text))
    return templates.TemplateResponse(request, "results.html", {"stats": stats})


@app.get("/sample", response_class=HTMLResponse)
def sample(request: Request):
    stats = summarize(parse_orders(SAMPLE.read_text()))
    return templates.TemplateResponse(request, "results.html", {"stats": stats})
