# PROMPT.md: Development Log

This is the full log of how BiteBudget was built with AI (Claude). Each step lists the prompt or request, what the AI produced, and what happened when it was run and tested. The matching commits are in the GitHub history.

**How this was run:** Step 0 is my own messages. After that I had Claude build the app as an agent on my laptop while I was away, one version at a time. The prompts in Steps 1–6 are the instructions for each step, which Claude wrote based on my request and the assignment brief and then carried out. Whenever something broke, the follow-up prompt describes the bug that was found and what to do about it.

---

## Step 0: Getting started

**Prompt:**
> Since u have access to my lap there is a vibe coding assignment that needs to be done
>
> *(attached the assignment PDF)*

**Follow-up answers to the AI's questions:**
> - App idea: no preference
> - Due: tomorrow
> - Stack: Python + Flask/FastAPI

**AI response:** Suggested a food delivery spending analyzer called **BiteBudget**, because I already wanted to build an Uber Eats spending analyzer. It planned four versions to match the assignment's iteration requirement: basic app → better UI → new features → tests and fixes.

> okay so lets begin

---

## Step 1: V1, basic working app

**Prompt:**
> Build a FastAPI web app where I upload my food delivery order history as a CSV and it shows total spent, number of orders, average order and my top 5 restaurants. Include sample data so it can be tried without a real file.

**What AI generated:**
- `app/main.py`: routes for the home page, `POST /analyze` (upload) and `/sample`
- `app/analysis.py`: `parse_orders()` with the `csv` module and `summarize()` for the totals
- `scripts/make_sample_data.py`: generates 140 fake orders over 6 months, weighted so lunch and late night are more common
- Plain HTML templates

**Testing:** Ran it with `uvicorn` and loaded `/sample`. It showed 140 orders, $4733.77 total, $33.81 average, with Pizza Palace on top. The upload worked with the same file.

**Commit:** `V1: basic working app - CSV upload, totals and top restaurants`

---

## Step 2: V2, improved interface and charts

**Prompt:**
> Make it look like a real app instead of plain HTML. Add a shared layout, stat cards, a monthly spending bar chart and a chart showing how much went to food vs delivery fees vs service fees vs tips. Make it work on mobile.

**What AI generated:** `base.html` layout, `style.css` (cards, orange theme, responsive grid), Chart.js bar and doughnut charts, and parsing of dates and fee columns.

**Problem found:** The page loaded, but both charts were **completely blank**. Chart.js was loaded from a CDN link and the browser couldn't reach it.

**Follow-up prompt:**
> The charts are blank because the CDN didn't load. Bundle Chart.js in the project so it works offline.

**Fix:** Downloaded Chart.js 4.6.1 into `app/static/vendor/` and pointed the template at the local file. The charts render now.

**Commit:** `V2: improved interface and charts`

---

## Step 3: V3, new features

**Prompt:**
> Add filters for date range and restaurant, a monthly budget that shows which months I went over, and savings tips based on my own orders like fees, late night orders and my most ordered restaurant.

**What AI generated:**
- `filter_orders()` and `savings_tips()` in `analysis.py`
- Uploads stored in memory under a short report id (`/report/<id>`), so the filter form can re-use the data
- Budget line on the chart, with over-budget months turned red
- Four rule-based tips (fees, late night, favourite spot, small orders with high fees)

**Problem found:** Pressing **Apply** with empty date boxes gave a **422 Unprocessable Content** error. The AI had typed the query parameters as `date`, but an empty form field sends `start=` (an empty string), which FastAPI can't convert.

**Follow-up prompt:**
> Pressing Apply with empty date fields gives a 422 error. Empty fields should just mean no filter.

**Fix:** Take the parameters as strings and only convert them when they're not empty (`_to_date`, `_to_float`).

**Commit:** `V3: filters, monthly budget and savings tips`

**Noticed while checking the screenshot (saved for V4):** the budget shows as "600.0", there are no thousands separators ($4733.77), and the chart legend shows the wrong colour for "Spent".

---

## Step 4: Tests

**Prompt:**
> Write pytest tests for the parsing, the maths, the filters and the web pages, including edge cases like an empty file, a CSV with the wrong columns, other date formats and filters that match nothing. Then fix whatever fails.

**Result: 15 tests, 5 failed.**

| Failing test | Error |
|---|---|
| empty CSV | `ZeroDivisionError` (average = total / 0) |
| date like `03/02/2026 7:15 PM` | `ValueError`, only one date format supported |
| filters that match nothing | `ZeroDivisionError` |
| CSV with wrong columns | `KeyError`, shows a 500 server error |
| unknown report id | `KeyError` instead of 404 |

The failing tests were committed first so the history shows the bugs before the fixes.

**Commit:** `Add pytest tests (5 failing)`

---

## Step 5: V4, bug fixes and polish

**Prompt:**
> Fix all 5 failing tests. Show friendly error messages on the home page instead of crashes, show a "no orders match" message for empty filters, and fix the money formatting, the budget showing 600.0 and the chart legend.

**What changed:**
- Required columns are checked first, with a readable error ("Your file is missing these columns: ...")
- Several date formats are accepted
- Empty files and empty filter results are handled
- 404 for unknown report ids, and a friendly message for non-CSV uploads (tested with a random binary file)
- `utf-8-sig` decoding, so CSVs saved from Excel (which start with a hidden BOM character) still work
- `money` template filter → `$4,733.77`
- The budget shows as `600`, and the legend only shows the budget line

**Testing:** All 15 tests pass. Also checked by hand: the binary upload shows the error, the Excel-style CSV works, the empty filter shows the message, and the wrong-columns file shows the error banner.

**Commit:** `V4: fix bugs found by tests, polish`

---

## Step 6: Documentation

**Prompt:**
> Write the README with all the sections from the assignment, take screenshots of the app working, and write this PROMPT.md log.

Screenshots were taken with a headless browser against the running app (`docs/screenshots/`).

---

## Step 7: Running it myself (next day)

I set it up on my own laptop. Two problems came up:

1. I ran `pip install -r requirements.txt` before creating the virtual environment, so the packages went into my main Python. Fixed by creating `.venv`, activating it and installing again.
2. `uvicorn app.main:app --reload` failed with **`[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`**. Port 8000 was already being used by another project I had running in Docker. Running with `--port 8080` fixed it, and the README now explains this.

---

## Step 8: V5, redesign

**My prompt:**
> Ok it runs the ui look to simple fix it

**What the AI did:**
- Proposed a design idea first: since the app is about delivery bills, show the results as one big itemized **receipt** with a torn paper edge, using a "condiments" colour scheme (mustard background, ketchup red for over budget, pickle green for savings)
- New fonts (Bricolage Grotesque for headings, IBM Plex Mono for the receipt), bundled locally like Chart.js
- Home page: big headline, drag-and-drop upload box and an example receipt built from the real sample data numbers
- Results: receipt pinned on the left with a bar for each part of the bill; on the right, the filters, the monthly chart, top restaurants as bars and the savings tips
- Months show as "May 2026" instead of "2026-05", and the tips use thousands separators

**Problem found:** On the phone layout, the receipt's torn-edge decoration showed up in the middle of the filter box. The mobile CSS changed the receipt from `sticky` to `static`, so the decoration lost its anchor. Changing it to `position: relative` fixed it.

**Testing:** All 15 tests still pass. Checked desktop and phone screenshots, the error message and the empty filter state.

---

## Step 9: V6, making it practical

**My prompt:**
> ok so this is v5 but now lets make it practical

**AI response:** It asked what "practical" should mean and gave options: read real Uber Eats/DoorDash export files, add orders by hand, save the data, or export a report.

**My answer:**
> i mean who would carry a lot of csv for their data

**What the AI did:** It agreed the CSV-first idea doesn't match real life, since nobody keeps a CSV of their orders, and changed the app into an order tracker:
- `app/db.py`: orders are saved in a SQLite database (`data/bitebudget.db`, added to `.gitignore` because it's personal data)
- Quick add form: restaurant (with suggestions from past orders), time (defaults to now), food price, delivery fee, service fee and tip, plus a live total. The server works out the total again when saving.
- The home page is now your own dashboard. With no orders yet, it shows a welcome page with the form.
- Recent orders list with delete buttons, and "delete all" behind a confirm
- CSV import still works but now adds to your saved orders. The sample data became a read-only demo.
- Validation with clear messages ("The food price should be a number, like 12.50.") that keeps what you typed
- Tests use a throwaway database (`tests/conftest.py`), and 11 new tests were added

**Problems found:**
1. The recent orders list used `%-I` in the time format, which works on Linux but **crashes on Windows**, and I run it on Windows. It was caught before running and changed to `%I`.
2. A new test failed: **deleting your last order** sent you back to the welcome page and the "Order deleted" message disappeared. Fixed by showing messages on the welcome page too.
3. After logging 6 orders by hand, "Spending by month" was a single bar because they were all in November. The chart now shows **spending by week** when there are only 1–2 months of orders.
4. On a phone, the add form was below the whole receipt, so a "+ Add order" button was added to the top bar that jumps to it.

**Testing:** 26 tests pass. Logged 6 orders through the form in a real browser and checked the dashboard, the weekly chart, the error message and the phone layout.

---

## Step 10: V7, from delivery tracker to Tally

**My prompt:**
> see firstly a budgeting app is not just about delivery prices if people want it to their house they should pay it its a necessity this app should track all expence instead of making delivery the big picture

**AI response:** It agreed and proposed turning the app into a general expense tracker with categories grouped into **needs** (rent, groceries, bills, transport, school, health) and **wants** (eating out, shopping, fun, other), with tips that only target wants. It pointed out that "BiteBudget" sounds food-specific and asked about renaming.

> *(picked "Rename it")*
>
> if i change the name will i have to change repo and everything

**AI response:** No. The app's name is just text in the code. The GitHub repo and the folder on my laptop can keep the name `bitebudget`, and if I ever rename the repo GitHub redirects the old URL.

> tally is good

**What the AI did:**
- Renamed the app to **Tally** (logo, titles, receipt, README). The repo and folder stayed `bitebudget`.
- New data model: an `expenses` table (date, description, category, amount) in `data/tally.db`
- **Moved my old delivery orders over automatically** as "Eating out" expenses, one time only (marked with SQLite's `user_version`, so clearing my data later doesn't bring them back)
- Add form: description, amount, category (grouped into needs and wants) and date. Typing something I've logged before picks its category automatically.
- Receipt shows spending by category plus a needs and wants subtotal. The chart stacks needs and wants in each bar.
- New tips: wants compared with the 50/30/20 rule of thumb, the biggest want and what cutting it by a fifth saves, small purchases under $10 that add up, and this month vs last month
- CSV import now takes `date, description, amount` (+ optional `category`), and the old delivery CSV format still works
- New sample data: six months of made-up student expenses (rent, transit pass, groceries, coffee, textbooks in September, ...)

**Problems found:**
1. **Month comparison was misleading.** Comparing November to October on November 21st said I spent "23% less", but November wasn't over. It now says "so far" when the latest month is the current one.
2. **Budget line would stack on the bars.** With stacked bars in Chart.js, the budget line would have been added on top of the needs and wants. It was put in its own stack so it stays at the budget amount.
3. A test failed because the page shows "doesn't" as `doesn&#39;t` (HTML escaping). The app was right and the test was wrong, so the test was fixed.

**Testing:** 29 tests pass. Also tested the real upgrade path: started Tally with a V6 database containing 6 delivery orders. They showed up as "Eating out" expenses, then I added rent, transit, groceries, a phone bill, a movie and an online order through the form in a browser.
