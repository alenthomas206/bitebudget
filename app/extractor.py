"""Pulls expenses out of text you paste in: bank alerts, order emails, receipts,
or lines copied from online banking. Plain rules (regular expressions), no AI.

extract(text) returns a list of expenses it found, each a dict with
description, amount, date and category. Nothing is saved here; the user
checks the result first.
"""

import re
from datetime import date, datetime, timedelta

# ---------- amounts ----------

# $23.40, CA$23.40, CAD 23.40, 23.40 CAD, $1,250, -$23.40
MONEY = re.compile(
    r"(?P<neg>-)?\s?(?:CA\$|C\$|US\$|\$|CAD\s?)\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)"
    r"|(?P<num2>\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})\s?(?:CAD|\$)?",
    re.IGNORECASE,
)

GOOD_WORDS = re.compile(r"\b(total|charged|spent|paid|purchase|amount|debit|payment of|you paid|order total|grand total)\b", re.I)
BAD_WORDS = re.compile(r"\b(sub\s?-?total|tax|hst|gst|pst|tip|fee|discount|saving|savings|balance|available|"
                       r"credit limit|credits?|earned|points|reward|cashback|change|tendered|promo)\b", re.I)


def _amounts(line):
    """All dollar amounts on one line."""
    found = []
    for m in MONEY.finditer(line):
        num = m.group("num") or m.group("num2")
        if num:
            found.append(float(num.replace(",", "")))
    return found


def find_amount(text):
    """Pick the amount that's most likely what was actually paid.
    Lines that say 'total' or 'spent' win; subtotal, tax, tip and balance lines lose.
    If it's still a tie, the biggest amount wins (a receipt's total is its largest number)."""
    best = None
    label = ""
    for line in text.splitlines():
        amounts = _amounts(line)
        if not amounts:
            if line.strip():
                label = line          # remember it in case the amount is on the next line
            continue
        # copied emails often split "Total" and "$5.81" onto separate lines,
        # so a line that's only an amount is judged by the label above it
        if not re.search(r"[A-Za-z]{2}", MONEY.sub("", line)):
            line = label + " " + line
        label = ""
        score = 0
        if GOOD_WORDS.search(line):
            score += 2
        if BAD_WORDS.search(line):
            score -= 3
        if re.search(r"\btotal\b", line, re.I) and not re.search(r"sub\s?-?total", line, re.I):
            score += 2
        for amount in amounts:
            key = (score, amount)
            if amount > 0 and (best is None or key > best):
                best = key
    return best[1] if best else None


# ---------- dates ----------

MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
MONTH_WORD = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"

DATE_PATTERNS = [
    # 2026-11-20
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    # 11/20/2026 or 11/20/26 (North American month first)
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b"),
     lambda m: (_year(m[3]), int(m[1]), int(m[2]))),
    # Nov 20, 2026 / November 20 2026 / Nov 20
    (re.compile(r"\b" + MONTH_WORD + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(\d{4}))?\b", re.I),
     lambda m: (int(m[3]) if m[3] else None, MONTHS[m[1][:3].lower()], int(m[2]))),
    # 20 Nov 2026 / 20 November
    (re.compile(r"\b(\d{1,2})\s+" + MONTH_WORD + r"(?:\s+(\d{4}))?\b", re.I),
     lambda m: (int(m[3]) if m[3] else None, MONTHS[m[2][:3].lower()], int(m[1]))),
]


def _year(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def find_date(text, today=None):
    """First date in the text. 'today' and 'yesterday' work too. None if there isn't one."""
    today = today or date.today()
    lowered = text.lower()
    for pattern, build in DATE_PATTERNS:
        for m in pattern.finditer(text):
            try:
                year, month, day = build(m)
                if year is None:
                    # no year given: assume the most recent one that isn't in the future
                    year = today.year if (month, day) <= (today.month, today.day) else today.year - 1
                return date(year, month, day)
            except (ValueError, KeyError):
                continue
    if re.search(r"\byesterday\b", lowered):
        return today - timedelta(days=1)
    if re.search(r"\btoday\b", lowered):
        return today
    return None


# ---------- merchant / description ----------

STOP = r"(?=\s+(?:on|for|using|with|via|was|has|is|card|ending|today|yesterday|tonight)\b|[.,;!\n(]|\s+\$|\s+\d{1,2}/|\s*$)"
MERCHANT_PATTERNS = [
    re.compile(r"\b(?:spent|purchase|paid|charge|transaction|payment)\b[^\n]*?\bat\s+(?P<m>[A-Z0-9][^\n]{1,40}?)" + STOP, re.I),
    re.compile(r"\b(?:order|receipt|purchase)\s+from\s+(?P<m>[A-Z0-9][^\n]{1,40}?)" + STOP, re.I),
    # "Here's your receipt for Pizza Palace" (delivery apps name the restaurant this way)
    re.compile(r"\breceipt for\s+(?P<m>[A-Z0-9][^\n]{1,40}?)" + STOP, re.I),
    # "Your Spotify Premium receipt"
    re.compile(r"\b[Yy]our\s+(?P<m>[A-Z][A-Za-z0-9'&+\- ]{1,40}?)\s+(?:receipt|invoice|bill|subscription)\b"),
    re.compile(r"\bthanks? for (?:ordering|shopping|your order|visiting)(?: from| at| with)?\s+(?P<m>[A-Z0-9][^\n]{1,40}?)" + STOP, re.I),
    re.compile(r"\b(?:payment|e-?transfer|transfer)\s+to\s+(?P<m>[A-Z0-9][^\n]{1,40}?)" + STOP, re.I),
    re.compile(r"\bmerchant(?:\s+name)?\s*[:\-]\s*(?P<m>[^\n]{2,40}?)" + STOP, re.I),
    re.compile(r"\bat\s+(?P<m>[A-Z][A-Za-z0-9'&\- ]{1,40}?)" + STOP),
]
SKIP_LINE = re.compile(r"^(subject|from|to|date|sent|re|fw|fwd)\s*:|receipt|invoice|order #|order number|"
                       r"thank|hello|hi |dear|total|subtotal|tax|tip|card|visa|mastercard|debit|"
                       r"credit|earned|points|reward|support|help|forgot|lost|enjoy|hope|rate |"
                       r"@|https?://|www\.", re.I)

# Well-known companies, recognized anywhere in the text. Used when no "at X" /
# "receipt for X" pattern names the store (e.g. an Uber ride receipt never says "at Uber").
# Delivery apps come first and are only used if no restaurant name was found.
BRANDS = [
    ("Uber Eats", r"uber ?eats"), ("DoorDash", r"door ?dash"), ("SkipTheDishes", r"skip ?the ?dishes"),
    ("Uber", r"\buber\b"), ("Lyft", r"\blyft\b"), ("Amazon", r"\bamazon\b"),
    ("Spotify", r"\bspotify\b"), ("Netflix", r"\bnetflix\b"), ("Apple", r"\bapple\.com|\bitunes\b"),
    ("Steam", r"\bsteam(?:powered)?\b"), ("Tim Hortons", r"tim horton"), ("Starbucks", r"\bstarbucks\b"),
    ("McDonald's", r"mcdonald"), ("Presto", r"\bpresto\b"), ("Walmart", r"\bwalmart\b"),
    ("Costco", r"\bcostco\b"), ("Best Buy", r"best ?buy"), ("Dollarama", r"\bdollarama\b"),
]
# names that a pattern can catch but that aren't a store
NOT_A_STORE = re.compile(r"^(your|my|the|this|our)\b|^(ride|trip|order|purchase|payment)$", re.I)


def _tidy(name):
    name = re.sub(r"\s+", " ", name).strip(" -:*#'\"")
    name = re.sub(r"\s*#\d+$", "", name)                # "STARBUCKS #1234" -> "STARBUCKS"
    # bank codes at the end: "SPOTIFY P1234" -> "SPOTIFY" (only if a real word is left)
    trimmed = re.sub(r"(\s+[A-Z]*\d[\w\-]*)+$", "", name)
    if re.search(r"[A-Za-z]{2}", trimmed):
        name = trimmed
    if name.isupper() and len(name) > 3:                 # "NORTHSIDE MARKET" -> "Northside Market"
        name = name.title()
    return name[:80]


def find_merchant(text):
    for pattern in MERCHANT_PATTERNS:
        for m in pattern.finditer(text):
            name = _tidy(m.group("m"))
            if len(name) >= 2 and not MONEY.fullmatch(name) and not NOT_A_STORE.search(name):
                return name
    for name, pattern in BRANDS:
        if re.search(pattern, text, re.I):
            return name
    # fallback: first short line that isn't a heading, amount, date or greeting
    for line in text.splitlines():
        line = line.strip()
        if 2 <= len(line) <= 40 and not SKIP_LINE.search(line) and not _amounts(line) \
                and not find_date(line) and re.search(r"[A-Za-z]{2}", line):
            return _tidy(line)
    return None


# ---------- category ----------

KEYWORDS = [
    ("Rent", r"\brent\b|landlord|property management|apartment|residence fee"),
    ("Groceries", r"grocer|supermarket|market\b|foods\b|no ?frills|freshco|food basics|superstore|"
                  r"sobeys|metro\b|loblaw|zehrs|farm boy|costco|walmart|bulk barn"),
    ("Eating out", r"uber ?eats|doordash|skip ?the ?dishes|restaurant|pizza|burger|cafe|coffee|"
                   r"tim horton|starbucks|mcdonald|subway|a&w|wendy|kfc|shawarma|sushi|pho|taco|"
                   r"diner|grill|bar\b|pub\b|bakery|bubble tea"),
    ("Transport", r"uber(?! ?eats)|lyft|transit|presto|bus\b|train|go transit|via rail|parking|"
                  r"gas\b|fuel|petro|esso|shell|pioneer|ultramar|taxi|ride"),
    ("Bills", r"\bphone\b|mobile|wireless|internet|hydro|electric|water bill|utilities|rogers|"
              r"\bbell\b|telus|fido|koodo|freedom mobile|virgin|insurance"),
    ("School", r"tuition|textbook|bookstore|college|university|campus store|printing|course|"
               r"georgian|student fee"),
    ("Health", r"pharmacy|shoppers drug|rexall|drug mart|clinic|dental|dentist|doctor|"
               r"physio|optometr|prescription|medical"),
    ("Fun", r"netflix|spotify|disney|crave|prime video|steam|playstation|xbox|nintendo|"
            r"cinema|cineplex|movie|concert|ticket|bowling|game|youtube premium|apple music"),
    ("Shopping", r"amazon|best buy|winners|h&m|zara|uniqlo|old navy|clothing|mall|"
                 r"dollarama|dollar store|ikea|canadian tire|online order|shein|temu"),
]


def guess_category(*texts, known=None):
    """Use what you've logged before first, then keywords. 'Other' if nothing fits."""
    known = known or {}
    for t in texts:
        if t and t.strip().lower() in known:
            return known[t.strip().lower()]
    # check the store name first, then the rest of the text
    for t in texts:
        for category, pattern in KEYWORDS:
            if t and re.search(pattern, t, re.I):
                return category
    return "Other"


# ---------- putting it together ----------

# one transaction per line, like text copied from online banking:
# "Nov 18  NORTHSIDE MARKET  $58.15"  or  "2026-11-18, Spotify, 11.99"
STATEMENT_LINE = re.compile(r"\d")


def _statement_rows(text, known, today):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not STATEMENT_LINE.search(line):
            continue
        when = find_date(line, today)
        amounts = _amounts(line)
        if not when or not amounts or BAD_WORDS.search(line):
            continue
        # the description is what's left once the date and amount are removed
        desc = line
        for pattern, _ in DATE_PATTERNS:
            desc = pattern.sub(" ", desc)
        desc = MONEY.sub(" ", desc)
        desc = re.sub(r"[,|\t;]+", " ", desc)
        desc = _tidy(desc)
        if not re.search(r"[A-Za-z]{2}", desc):
            continue
        rows.append({"description": desc, "amount": amounts[-1], "date": when.isoformat(),
                     "category": guess_category(desc, known=known)})
    return rows


def extract(text, known=None, today=None):
    """Find expenses in pasted text.

    known: {description.lower(): category} from past expenses, so a store you've
    logged before keeps the category you used.
    Returns (expenses, problem). problem is a message when nothing could be found.
    """
    today = today or date.today()
    text = (text or "").strip()
    if not text:
        return [], "Paste some text first."
    if len(text) > 20000:
        return [], "That's too much text. Paste one receipt or up to a page of transactions."

    # several lines that each have a date and an amount: treat it as a list of transactions
    rows = _statement_rows(text, known, today)
    if len(rows) >= 2:
        return rows, None

    amount = find_amount(text)
    if amount is None:
        return [], "Couldn't find an amount in that text. Check it has a price like $12.50."
    merchant = find_merchant(text) or "Unknown"
    when = find_date(text, today) or today
    return [{
        "description": merchant,
        "amount": round(amount, 2),
        "date": when.isoformat(),
        "category": guess_category(merchant, text, known=known),
    }], None
