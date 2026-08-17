"""
Shares a subscription's billing schedule (as an .ics file, RRULE matching
its frequency) through Android's share sheet, so the user's calendar app
handles the actual import through its own logic. Two earlier approaches
were tried and dropped: writing straight to CalendarContract via
ContentValues crashed (pyjnius overload resolution is fragile there), and
tapping an .ics file from Downloads routed to Google Calendar's "view an
existing event" handler instead of its importer ("event not found"), and a
plain ACTION_INSERT intent opened a blank compose screen on this device.
Sharing the file via ACTION_SEND hands it to the calendar app's own share
target instead, which is the mechanism calendar apps actually support.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone


def is_supported():
    try:
        import android  # noqa: F401
        from jnius import autoclass  # noqa: F401
        return True
    except ImportError:
        return False


_RRULE = {
    "monthly": "FREQ=MONTHLY;INTERVAL=1",
    "quarterly": "FREQ=MONTHLY;INTERVAL=3",
    "yearly": "FREQ=YEARLY;INTERVAL=1",
}


def _rrule_for(frequency, interval_days):
    if frequency == "custom":
        return f"FREQ=DAILY;INTERVAL={interval_days or 1}"
    return _RRULE.get(frequency, _RRULE["monthly"])


def _escape_ics_text(text):
    return (text.replace("\\", "\\\\").replace(",", "\\,")
                .replace(";", "\\;").replace("\n", "\\n"))


def _ics_content(name, price_usd, frequency, interval_days, start_date):
    dtstart = start_date.strftime("%Y%m%d")
    dtend = (start_date + timedelta(days=1)).strftime("%Y%m%d")
    uid = f"{uuid.uuid4()}@subscriptiontracker"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = _escape_ics_text(name)
    description = _escape_ics_text(f"Price: {price_usd:.2f}")
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Subscription Tracker//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{stamp}\r\n"
        f"DTSTART;VALUE=DATE:{dtstart}\r\n"
        f"DTEND;VALUE=DATE:{dtend}\r\n"
        f"RRULE:{_rrule_for(frequency, interval_days)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def _safe_filename(name):
    kept = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    kept = kept.strip().replace(" ", "_")
    return f"{kept or 'subscription'}.ics"


def share_event(name, price_usd, frequency, interval_days, start_date):
    """Write an .ics file into the app's private storage and hand it to
    the calendar app via the Android share sheet."""
    from jnius import autoclass, cast
    Intent = autoclass("android.content.Intent")
    FileProvider = autoclass("androidx.core.content.FileProvider")
    File = autoclass("java.io.File")
    String = autoclass("java.lang.String")
    activity = autoclass("org.kivy.android.PythonActivity").mActivity

    calendar_dir = os.path.join(
        activity.getFilesDir().getAbsolutePath(), "calendar")
    os.makedirs(calendar_dir, exist_ok=True)
    filename = _safe_filename(name)
    path = os.path.join(calendar_dir, filename)
    content = _ics_content(name, price_usd, frequency, interval_days,
                           start_date)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    authority = f"{activity.getPackageName()}.fileprovider"
    uri = FileProvider.getUriForFile(activity, authority, File(path))

    intent = Intent(Intent.ACTION_SEND)
    intent.setType("text/calendar")
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    title = cast("java.lang.CharSequence", String("Add to calendar"))
    chooser = Intent.createChooser(intent, title)
    activity.startActivity(chooser)
