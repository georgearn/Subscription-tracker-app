"""
Data + date/cost logic for the Subscription Tracker.
Shared by the Kivy UI and the notification service.
"""

import os
import sqlite3
import calendar
from datetime import date, timedelta

FREQUENCIES = ["monthly", "quarterly", "yearly", "custom"]

# Global primary currency choices.
PRIMARY_CURRENCIES = [
    "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "CNY",
    "MDL", "UAH", "RON", "RUB", "PLN", "CZK", "HUF",
    "BRL", "INR", "KRW", "MXN", "SEK", "NOK", "DKK",
    "NZD", "SGD", "HKD", "TRY", "ZAR", "ILS", "AED",
]

# Secondary currency is optional, hence the leading empty entry.
CURRENCIES = [""] + PRIMARY_CURRENCIES

_DB_PATH = "subscriptions.db"


def set_db_path(path):
    global _DB_PATH
    _DB_PATH = path


def android_db_path():
    try:
        from jnius import autoclass
        try:
            ctx = autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception:
            ctx = autoclass("org.kivy.android.PythonService").mService
        return os.path.join(
            ctx.getFilesDir().getAbsolutePath(), "subscriptions.db"
        )
    except Exception:
        return None


def desktop_db_path():
    base = os.path.join(os.path.expanduser("~"), ".subscription_tracker")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "subscriptions.db")


def get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS subscriptions (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                name               TEXT NOT NULL,
                price_usd          REAL NOT NULL,
                secondary_amount   REAL,
                secondary_currency TEXT,
                frequency          TEXT NOT NULL,
                start_date         TEXT NOT NULL,
                interval_days      INTEGER,
                card               TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )"""
        )
        cols = [r[1] for r in conn.execute("PRAGMA table_info(subscriptions)")]
        if "card" not in cols:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN card TEXT")


# ---- Settings (key/value) -------------------------------------------------
def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_primary_currency():
    return get_setting("primary_currency", "USD")


def set_primary_currency(value):
    set_setting("primary_currency", value or "USD")


# ---- Subscriptions --------------------------------------------------------
def add_subscription(name, amount, sec_amount, sec_currency,
                     frequency, start_date, interval_days, card):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO subscriptions
               (name, price_usd, secondary_amount, secondary_currency,
                frequency, start_date, interval_days, card)
               VALUES (?,?,?,?,?,?,?,?)""",
            (name, amount, sec_amount, sec_currency,
             frequency, start_date.isoformat(), interval_days, card),
        )


def get_all_subscriptions():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions ORDER BY name COLLATE NOCASE"
        ).fetchall()


def delete_subscription(sub_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))


def get_subscription(sub_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE id = ?", (sub_id,)
        ).fetchone()


def update_subscription(sub_id, name, amount, sec_amount, sec_currency,
                        frequency, start_date, interval_days, card):
    with get_conn() as conn:
        conn.execute(
            """UPDATE subscriptions
               SET name=?, price_usd=?, secondary_amount=?,
                   secondary_currency=?, frequency=?, start_date=?,
                   interval_days=?, card=?
               WHERE id=?""",
            (name, amount, sec_amount, sec_currency,
             frequency, start_date.isoformat(), interval_days, card, sub_id),
        )


def get_distinct_cards():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT card FROM subscriptions "
            "WHERE card IS NOT NULL AND card != '' ORDER BY card"
        ).fetchall()
        return [r["card"] for r in rows]


# --------------------------------------------------------------------------
# Pure date / cost helpers
# --------------------------------------------------------------------------
def _clamped_date(year, month, day):
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _parse_start(sub):
    return date.fromisoformat(sub["start_date"])


def occurrences_in_month(sub, year, month):
    start = _parse_start(sub)
    freq = sub["frequency"]
    occ = []

    if freq == "monthly":
        if (year, month) >= (start.year, start.month):
            occ.append(_clamped_date(year, month, start.day))
    elif freq == "quarterly":
        diff = (year * 12 + month) - (start.year * 12 + start.month)
        if diff >= 0 and diff % 3 == 0:
            occ.append(_clamped_date(year, month, start.day))
    elif freq == "yearly":
        if month == start.month and year >= start.year:
            occ.append(_clamped_date(year, month, start.day))
    elif freq == "custom":
        step = sub["interval_days"] or 0
        if step > 0:
            month_start = date(year, month, 1)
            month_end = _clamped_date(year, month, 31)
            d = start
            if d < month_start:
                jumps = (month_start - d).days // step
                d = d + timedelta(days=jumps * step)
            while d <= month_end:
                if d >= start and d.year == year and d.month == month:
                    occ.append(d)
                d += timedelta(days=step)
    return sorted(occ)


def payments_per_year(sub):
    freq = sub["frequency"]
    if freq == "monthly":
        return 12
    if freq == "quarterly":
        return 4
    if freq == "yearly":
        return 1
    if freq == "custom" and sub["interval_days"]:
        return 365.25 / sub["interval_days"]
    return 0


def annual_cost(sub):
    return round(sub["price_usd"] * payments_per_year(sub), 2)


annual_cost_usd = annual_cost
