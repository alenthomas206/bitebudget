# BiteBudget 🍔

A small web app that tracks how much you're actually spending on food delivery.

## Description

Every time you order food (Uber Eats, DoorDash, Skip, etc.) you log it in BiteBudget in a few seconds: the restaurant, the food price, the fees and the tip. Your orders are saved on your computer, and BiteBudget turns them into a spending dashboard:

- total spent, number of orders and average order
- a monthly spending chart
- how much of your money went to food vs delivery fees, service fees and tips
- your top 5 restaurants
- savings tips based on your own orders

You can filter by date range or restaurant and set a monthly budget to see which months you went over.

If you already have an export file from a delivery app you can import it as a CSV, and there's a **demo with sample data** (140 made-up orders) to try the dashboard first.

## Purpose

I order food a lot, like most students, and I never really knew what it added up to. The apps show you one order at a time, not the total. I had already wanted to build an Uber Eats spending analyzer as a side project, so this assignment was a good excuse to actually build it. It's meant for students or anyone who orders delivery often and wants to cut back.

## Features

- **Quick add form**: restaurant, time, food price, delivery fee, service fee and tip, with a live total and suggestions for restaurants you've ordered from before
- **Saved orders** in a local SQLite database (`data/bitebudget.db`), so they're still there next time
- **Recent orders** list with a delete button for mistakes, plus "delete all"
- **Dashboard**: an itemized receipt, a spending chart (by week when you only have a month or two of orders, by month after that), top restaurants and savings tips
- **CSV import** (optional) with checks: missing columns, wrong file types and bad dates show a clear error instead of crashing
- **Filters** by date range and restaurant
- **Monthly budget**: months over budget turn red on the chart and are listed with how much you went over
- **Savings tips** worked out from your data (fees you'd skip by picking up, late night orders, your most ordered spot, small orders with high fees)
- **Sample data** so the app can be tried without a real export
- Accepts a few date formats (`2026-03-01 18:00`, `03/01/2026 6:00 PM`, ...) and CSVs saved from Excel
- Works on phones, with an "Add order" button at the top that jumps to the form

## Technologies

- **Python 3.10+**
- **FastAPI**: web server and routes
- **SQLite** (Python's built-in `sqlite3`): saves your orders
- **Jinja2**: HTML templates
- **Chart.js 4.6.1**: charts (bundled in `app/static/vendor` so it works offline)
- **Bricolage Grotesque** and **IBM Plex Mono** fonts (bundled in `app/static/fonts`, SIL Open Font License)
- **pytest**: tests (15 tests)
- Plain HTML and CSS, no frontend framework

## AI Tools Used

- **Claude (Anthropic)**: planning the app, generating and refactoring code, writing tests, debugging, and drafting documentation

## Project Structure

```
bitebudget/
├── app/
│   ├── main.py            # FastAPI routes (add/delete orders, import, dashboard)
│   ├── db.py              # saving and loading orders (SQLite)
│   ├── analysis.py        # CSV parsing, stats, budget check, savings tips
│   ├── templates/         # pages plus the add-order and import forms
│   └── static/            # CSS, fonts and bundled Chart.js
├── sample_data/
│   └── sample_orders.csv  # 140 fake orders
├── scripts/
│   └── make_sample_data.py
├── data/                  # your saved orders (created on first run, not in git)
├── tests/
│   ├── conftest.py        # gives each test an empty database
│   └── test_app.py
├── docs/screenshots/
├── requirements.txt
├── requirements-dev.txt
└── PROMPT.md              # full log of how the app was built with AI
```

## Installation

You need Python 3.10 or newer.

```bash
git clone https://github.com/alenthomas206/bitebudget.git
cd bitebudget
python -m venv .venv
```

Activate the virtual environment:

- Windows: `.venv\Scripts\activate`
- Mac/Linux: `source .venv/bin/activate`

Then install the dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** in your browser and add your first order, or click "See a demo with sample data".

Your orders are saved in `data/bitebudget.db`. Delete that file to start fresh.

If you get `[WinError 10013] An attempt was made to access a socket...`, something else is already using port 8000. Use another port:

```bash
uvicorn app.main:app --reload --port 8080
```

Then open http://127.0.0.1:8080.

### CSV import format (optional)

Required columns: `date, restaurant, total`
Optional columns: `subtotal, delivery_fee, service_fee, tip`

```
date,restaurant,subtotal,delivery_fee,service_fee,tip,total
2026-05-01 12:30,Burger Barn,18.50,2.99,2.78,3,27.27
```

### Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## How AI Was Used

Almost all of the code was generated by AI from natural-language prompts, then run, tested and fixed in steps. The app was built in six versions (see the commit history):

1. **V1**: basic upload and totals
2. **V2**: better design and charts
3. **V3**: filters, budget and savings tips
4. **V4**: tests, then fixes for every bug the tests found
5. **V5**: full UI redesign after I ran it myself and thought it looked too simple
6. **V6**: switched from "upload a CSV" to logging orders by hand and saving them, after I realized nobody actually has a CSV of their orders

The full prompt log is in [PROMPT.md](PROMPT.md). Three prompts that shaped the app the most:

> **1.** "Build a FastAPI web app where I upload my food delivery order history as a CSV and it shows total spent, number of orders, average order and my top 5 restaurants. Include sample data so it can be tried without a real file."

This gave the base app (V1) and the sample data generator.

> **2.** "Write pytest tests for the parsing, the maths, the filters and the web pages, including edge cases like an empty file, a CSV with the wrong columns, other date formats and filters that match nothing. Then fix whatever fails."

5 of the 15 tests failed at first, and fixing them is what V4 is about.

> **3.** "ok so this is v5 but now lets make it practical" ... "i mean who would carry a lot of csv for their data"

This was the biggest change. The AI first asked what "practical" meant and suggested options like reading real app exports. My answer changed the whole idea: instead of analyzing a file once, BiteBudget became a tracker where you log each order and it's saved (V6). Testing it caught a bug where deleting your last order sent you back to the welcome page with no "Order deleted" message.

## Screenshots

**Welcome page with the add-order form**

![Home page](docs/screenshots/home.png)

**My orders dashboard** after logging 6 orders (weekly chart, recent orders with delete)

![My orders](docs/screenshots/my-orders.png)

**Sample data demo with a $700 monthly budget** (red months are over budget)

![Dashboard](docs/screenshots/dashboard.png)

**Filtered to one restaurant and date range**

![Filtered](docs/screenshots/filtered.png)

**Clear error when the food price isn't a number** (what you typed is kept)

![Error](docs/screenshots/error.png)

**On a phone**

<img src="docs/screenshots/mobile.png" width="300" alt="Mobile view">

## Future Improvements

1. **Fill the form from a receipt.** Paste the order confirmation email or a screenshot of the receipt and have it read the restaurant, fees and tip automatically, so logging takes one step.
2. **Accounts and hosting.** Right now it's one person's orders on one computer. Logins and putting it online would let you log orders from your phone anywhere.
3. **Read real Uber Eats / DoorDash exports directly.** The CSV import needs my column names, so a real export has to be renamed first.
4. **AI-written tips.** The savings tips are fixed rules. Sending the summary to an AI model (with the API key in an environment variable) could give more personal advice.
5. **Export.** Download the report as a PDF or share a link.
6. **Category tags.** Group restaurants into fast food, coffee, etc. to see which type of food costs the most.

## Vibe Coding Reflection

> ✏️ **Draft. Alen: rewrite this in your own words before submitting.** The facts below are what actually happened during development. Add your own opinions and anything you noticed when you tried the app.

### 1. What did AI do particularly well?

It was really fast at the boring setup parts. The whole first version (FastAPI routes, templates, sample data generator) came from one prompt and worked the first time. It also wrote the 15 tests in one go, which I probably wouldn't have bothered doing that thoroughly myself. *[Add your own example]*

### 2. What did AI do poorly?

- In V2 it loaded Chart.js from a CDN link and the charts came out completely blank when the browser couldn't reach the internet. It had to be changed to a local copy of Chart.js.
- In V3 it typed the date filters as `date` in FastAPI, but an empty date box sends an empty string, so pressing "Apply" without picking dates gave a 422 error.
- The original code assumed every file would be perfect. An empty file or a file with different columns just crashed the app (5 tests failed).

### 3. How did you verify AI-generated code?

- Ran the app after every version and clicked through it with the sample data
- Took screenshots to check the charts and layout actually rendered
- Wrote pytest tests, including edge cases, and only moved on once they all passed
- Checked a few numbers by hand (for example, the small test CSV: 25 + 15.50 + 39.50 = $80.00)

*[Add anything you tested yourself]*

### 4. How did your prompts evolve?

Early prompts were broad, like "build an app that analyzes my delivery spending". Later prompts got much more specific: they named the exact bug (empty date fields cause a 422), listed the edge cases to test, and said exactly how something should look (months over budget in red with a dashed budget line). Specific prompts got the right result the first time; vague ones needed more back and forth.

### 5. What did you learn?

*[Your own words. Ideas: how FastAPI handles query parameters, why testing edge cases matters, how Jinja templates work, or that AI code "working" on the happy path doesn't mean it's finished.]*

### 6. Would you trust AI to build the entire application without human supervision?

*[Your opinion.]* Things to consider: the app looked finished after V3 but still crashed on empty files and on an empty form field. Those only got caught because tests and manual checks were asked for. Without someone checking, those bugs would have gone straight to users.
