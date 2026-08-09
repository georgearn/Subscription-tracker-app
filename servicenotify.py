"""
Background notification service for the Subscription Tracker.

Buildozer runs this as an Android foreground service.  It wakes every
30 minutes, checks the subscription database, and posts notifications:

 * 1st of each month  → monthly summary (all payments + total for the month)
 * Every payment day   → daily reminder (subscriptions due today)

Duplicate notifications are suppressed by a tiny tracking file that
records which (date, type) combos have already been sent.
"""

import os
import sys
import json
import time
import calendar
from datetime import date, datetime

# Ensure the project root is importable so `import logic` works.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logic

# --------------------------------------------------------------------------
# Android notification helpers
# --------------------------------------------------------------------------
CHANNEL_ID = "sub_tracker_notify"
CHANNEL_NAME = "Subscription Tracker"

_channel_created = False


def _get_context():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonService").mService


def _ensure_channel(context):
    """Create the notification channel once (required for API 26+)."""
    global _channel_created
    if _channel_created:
        return
    from jnius import autoclass
    NotificationChannel = autoclass("android.app.NotificationChannel")
    NotificationManager = autoclass("android.app.NotificationManager")
    importance = 3  # IMPORTANCE_DEFAULT
    channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance)
    channel.setDescription("Subscription payment reminders")
    mgr = context.getSystemService("notification")
    mgr.createNotificationChannel(channel)
    _channel_created = True


def notify(context, title, body, notif_id=1):
    """Post an Android notification."""
    from jnius import autoclass
    _ensure_channel(context)

    Builder = autoclass("android.app.Notification$Builder")
    builder = Builder(context, CHANNEL_ID)
    builder.setContentTitle(title)
    builder.setSmallIcon(context.getApplicationInfo().icon)
    builder.setAutoCancel(True)

    # BigTextStyle so the full list is readable
    BigText = autoclass("android.app.Notification$BigTextStyle")
    style = BigText()
    style.bigText(body)
    builder.setStyle(style)

    mgr = context.getSystemService("notification")
    mgr.notify(notif_id, builder.build())


# --------------------------------------------------------------------------
# Duplicate-send tracking
# --------------------------------------------------------------------------
def _tracking_path(context):
    return os.path.join(
        context.getFilesDir().getAbsolutePath(), "notif_tracking.json"
    )


def _load_tracking(context):
    path = _tracking_path(context)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_tracking(context, data):
    with open(_tracking_path(context), "w") as f:
        json.dump(data, f)


def _already_sent(context, key):
    """Return True if `key` (e.g. '2026-06-01:monthly') was already sent."""
    data = _load_tracking(context)
    return key in data


def _mark_sent(context, key):
    data = _load_tracking(context)
    data[key] = True
    # prune entries older than 45 days to stop the file growing forever
    today_str = date.today().isoformat()
    pruned = {k: v for k, v in data.items()
              if k[:10] >= today_str[:7]}  # keep current month + future
    _save_tracking(context, pruned)


# --------------------------------------------------------------------------
# Notification content builders
# --------------------------------------------------------------------------
def _monthly_body(today):
    """Build the text for the monthly overview notification."""
    subs = logic.get_all_subscriptions()
    cur = logic.get_primary_currency()
    y, m = today.year, today.month
    lines = []
    total = 0.0
    for s in subs:
        for d in logic.occurrences_in_month(s, y, m):
            lines.append(f"• {s['name']}  {s['price_usd']:.2f} {cur}  "
                         f"({d.strftime('%b %d')})")
            total += s["price_usd"]

    if not lines:
        return None

    header = (f"{calendar.month_name[m]} {y}: "
              f"{len(lines)} payment{'s' if len(lines) != 1 else ''}, "
              f"{total:.2f} {cur} total\n")
    return header + "\n".join(sorted(lines))


def _daily_body(today):
    """Build the text for a payment-day notification."""
    subs = logic.get_all_subscriptions()
    cur = logic.get_primary_currency()
    lines = []
    total = 0.0
    for s in subs:
        for d in logic.occurrences_in_month(s, today.year, today.month):
            if d == today:
                lines.append(f"• {s['name']}  {s['price_usd']:.2f} {cur}")
                total += s["price_usd"]

    if not lines:
        return None

    header = f"{total:.2f} {cur} in payments today\n"
    return header + "\n".join(lines)


# --------------------------------------------------------------------------
# Main service loop
# --------------------------------------------------------------------------
CHECK_INTERVAL = 30 * 60      # seconds between checks (30 min)
MONTHLY_NOTIF_ID = 9001
DAILY_NOTIF_ID = 9002


def main():
    context = _get_context()

    # point logic at the shared database
    db_path = os.path.join(
        context.getFilesDir().getAbsolutePath(), "subscriptions.db"
    )
    logic.set_db_path(db_path)
    logic.init_db()

    while True:
        try:
            today = date.today()

            # --- monthly summary on the 1st --------------------------------
            if today.day == 1:
                key = f"{today.isoformat()}:monthly"
                if not _already_sent(context, key):
                    body = _monthly_body(today)
                    if body:
                        notify(context,
                               f"📋 {calendar.month_name[today.month]} "
                               f"subscriptions",
                               body, MONTHLY_NOTIF_ID)
                    _mark_sent(context, key)

            # --- daily payment reminder ------------------------------------
            key = f"{today.isoformat()}:daily"
            if not _already_sent(context, key):
                body = _daily_body(today)
                if body:
                    notify(context, "💳 Payments due today",
                           body, DAILY_NOTIF_ID)
                _mark_sent(context, key)

        except Exception as e:
            print(f"[SubTracker service] error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
