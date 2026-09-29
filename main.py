"""
Subscription Tracker — Kivy app entry point.

Only the App class and platform glue (_is_android/_system_insets) live
here; sizing/colour constants are in theme.py, the icon system is in
icons.py, generic UI chrome is in widgets.py, and the domain-specific
composite widgets (subscription rows, bank cards, schedule cells,
category bars) are in cards.py.
"""

import os
import calendar
from datetime import date
from functools import partial

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.uix.carousel import Carousel
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse

import logic
import android_calendar
import android_downloads

from theme import (
    WINDOW_BG, BRAND, BRAND_DARK, GREEN, BLUE, RED, NEUTRAL, WHITE,
    TAB_ACTIVE, TAB_INACTIVE, TAB_TEXT_ACTIVE, TAB_TEXT_INACTIVE,
    CARD_BG, POPUP_BG, TOTAL_BG, ACCENT, BTN_H, INPUT_H, PADX, NAV_BTN_W,
    category_color, metallic_color,
)
from icons import IconButton, _add_tab_icon, ServiceIcon
from widgets import (
    FloatingActionButton, RowCard, modern_spinner, make_input, make_label,
    flat_button, arrow_button, PillButton, _fmt_group,
)
from cards import (
    SubRow, CardGroupCard, CardPeek, DayCell, MonthSubCard, ArcGauge,
    CategoryBar,
)


def _is_android():
    try:
        from kivy.utils import platform
        return platform == "android"
    except Exception:
        return False


def _system_insets():
    """Status bar / navigation bar heights on Android, else (0, 0)."""
    if not _is_android():
        return 0, 0
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        decor_view = activity.getWindow().getDecorView()
        WindowInsetsCompat = autoclass(
            "androidx.core.view.WindowInsetsCompat")
        insets = WindowInsetsCompat.toWindowInsetsCompat(
            decor_view.getRootWindowInsets(), decor_view)
        Type = autoclass("androidx.core.view.WindowInsetsCompat$Type")
        bars = insets.getInsets(Type.systemBars())
        density = activity.getResources().getDisplayMetrics().density
        top = bars.top / density
        bottom = bars.bottom / density
        return dp(top), dp(bottom)
    except Exception as e:
        print(f"[SubTracker] Could not read system insets: {e}")
        return 0, 0


class SubscriptionApp(App):

    def build(self):
        self.title = "Subscription Tracker"
        Window.clearcolor = WINDOW_BG
        # keep the focused TextInput visible above the on-screen keyboard
        # instead of letting it get covered (Android default is to overlay)
        Window.softinput_mode = "below_target"

        db = logic.android_db_path() or logic.desktop_db_path()
        logic.set_db_path(db)
        logic.init_db()

        today = date.today()
        self.view_month = today.month
        self.view_year = today.year
        self.y_year = today.year
        self.selected_day = None

        # tabs at the BOTTOM
        panel = TabbedPanel(do_default_tab=False, tab_pos="bottom_mid",
                            tab_height=dp(56))
        panel.background_color = WINDOW_BG

        self.tab_subs = TabbedPanelItem(text="Subscriptions", font_size=sp(15))
        self.tab_subs.add_widget(self._build_subs_tab())
        panel.add_widget(self.tab_subs)

        self.tab_overview = TabbedPanelItem(text="Overview", font_size=sp(15))
        self.tab_overview.add_widget(self._build_overview_tab())
        panel.add_widget(self.tab_overview)

        self.tab_analytics = TabbedPanelItem(text="Analytics", font_size=sp(15))
        self.tab_analytics.add_widget(self._build_analytics_tab())
        panel.add_widget(self.tab_analytics)

        tab_icons = {
            self.tab_subs: "list",
            self.tab_overview: "calendar",
            self.tab_analytics: "chart",
        }
        for tab in (self.tab_subs, self.tab_overview, self.tab_analytics):
            tab.background_normal = ""
            tab.background_down = ""
            tab.border = (0, 0, 0, 0)
            tab.bind(state=lambda inst, _v: self._style_tab(inst))
            self._style_tab(tab)
            _add_tab_icon(tab, tab_icons[tab])

        # size each tab to exactly one third of the screen so all three
        # fit snug with no scrolling (and re-fit on rotation)
        def _fit_tabs(*_):
            panel.tab_width = int(Window.width / 3)

        Window.bind(width=lambda *_: _fit_tabs())
        Clock.schedule_once(lambda *_: _fit_tabs(), 0)

        panel.bind(current_tab=self._on_tab_switch)
        self.refresh_all()
        self._request_notification_permission()
        self._start_notification_service()
        self._schedule_daily_check()

        # edge-to-edge: pad around the status bar and navigation pill so
        # nothing is drawn underneath them (Android 15+ / API 35+)
        self.root_box = BoxLayout(orientation="vertical")
        self.root_box.add_widget(panel)
        Window.bind(size=lambda *_: self._apply_insets())
        Clock.schedule_once(self._apply_insets, 0)
        Clock.schedule_once(self._apply_insets, 0.5)

        # outer FloatLayout hosts the FAB above everything, including the
        # tab bar — added last, so it's drawn last (on top of TabbedPanel's
        # own tab strip, which otherwise painted over a FAB nested inside
        # the Subscriptions tab's own content tree)
        outer = FloatLayout()
        outer.add_widget(self.root_box)
        self.root_box.size_hint = (1, 1)
        self.root_box.pos_hint = {"x": 0, "y": 0}

        self.fab = FloatingActionButton(bg=GREEN)
        self.fab.bind(on_release=lambda *_: self._open_popup())
        outer.add_widget(self.fab)

        def place_fab(*_):
            # bottom-right corner, sitting above the tab strip: the
            # strip's top edge is at (bottom inset + tab height) from the
            # window's bottom, since it's inside root_box's padded area
            bottom_inset = self.root_box.padding[3]
            strip_top = outer.y + bottom_inset + panel.tab_height
            self.fab.right = outer.right - dp(16)
            self.fab.y = strip_top + dp(12)

        self._place_fab = place_fab
        outer.bind(size=place_fab, pos=place_fab)
        Clock.schedule_once(lambda *_: place_fab(), 0)

        def _sync_fab(*_):
            self.fab.opacity = 1 if panel.current_tab is self.tab_subs else 0
            self.fab.disabled = panel.current_tab is not self.tab_subs

        panel.bind(current_tab=lambda *_: _sync_fab())
        Clock.schedule_once(lambda *_: _sync_fab(), 0)

        # back button/gesture: close open popup instead of exiting app
        Window.bind(on_keyboard=self._on_keyboard)
        try:
            from android import activity
            activity.bind(on_back_pressed=self._on_back)
        except Exception:
            pass

        return outer

    def _on_back(self, *_args):
        if Window._modal_stack:
            Window._modal_stack[-1].dismiss()
            return True
        return False

    def _on_keyboard(self, _window, key, *_args):
        if key == 27:
            return self._on_back()
        return False

    def _apply_insets(self, *_):
        top, bottom = _system_insets()
        self.root_box.padding = [0, top, 0, bottom]
        if hasattr(self, "_place_fab"):
            self._place_fab()

    @staticmethod
    def _style_tab(tab):
        if tab.state == "down":
            tab.background_color = TAB_ACTIVE
            tab.color = TAB_TEXT_ACTIVE
        else:
            tab.background_color = TAB_INACTIVE
            tab.color = TAB_TEXT_INACTIVE

    # ---- Android notification service -------------------------------------
    def _request_notification_permission(self):
        if not _is_android():
            return
        try:
            from android.permissions import (
                Permission, check_permission, request_permissions,
            )
            if not check_permission(Permission.POST_NOTIFICATIONS):
                request_permissions([Permission.POST_NOTIFICATIONS])
        except Exception as e:
            print(f"[SubTracker] Could not request notification permission: {e}")

    def _start_notification_service(self):
        if not _is_android():
            return
        try:
            from android import mActivity
            from jnius import autoclass
            service = autoclass(
                "com.georgearn.subscriptiontracker.ServiceNotify")
            service.start(mActivity, "Subscription Tracker notifications")
        except Exception as e:
            print(f"[SubTracker] Could not start service: {e}")

    def _schedule_daily_check(self):
        """Wake the notification service once a day via AlarmManager,
        instead of keeping it running (and its mandatory foreground
        notification pinned) all the time. Re-armed on every app launch,
        since alarms don't survive a device reboot and there's no boot
        receiver here."""
        if not _is_android():
            return
        try:
            from jnius import autoclass, cast
            Context = autoclass("android.content.Context")
            PendingIntent = autoclass("android.app.PendingIntent")
            AlarmManager = autoclass("android.app.AlarmManager")
            System = autoclass("java.lang.System")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity

            service_cls = autoclass(
                "com.georgearn.subscriptiontracker.ServiceNotify")
            intent = service_cls.getDefaultIntent(
                activity, "", "Subscription Tracker", "Notify",
                "notifications")

            flags = PendingIntent.FLAG_UPDATE_CURRENT | \
                PendingIntent.FLAG_IMMUTABLE
            pending = PendingIntent.getForegroundService(
                activity, 0, intent, flags)

            alarm_mgr = cast(
                "android.app.AlarmManager",
                activity.getSystemService(Context.ALARM_SERVICE))
            interval = AlarmManager.INTERVAL_HALF_DAY
            trigger_at = System.currentTimeMillis() + interval
            alarm_mgr.setInexactRepeating(
                AlarmManager.RTC_WAKEUP, trigger_at, interval, pending)
        except Exception as e:
            print(f"[SubTracker] Could not schedule daily check: {e}")

    # ---- Subscriptions tab ------------------------------------------------
    def _build_subs_tab(self):
        # FloatLayout lets the FAB float over the list
        root = FloatLayout()

        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=PADX, size_hint=(1, 1),
                            pos_hint={"x": 0, "y": 0})

        # slim header: title + global currency selector + data icon
        header = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        header.add_widget(make_label("Subscriptions", font_size=sp(20),
                                     bold=True))
        self.cur_spinner = modern_spinner(
            logic.PRIMARY_CURRENCIES, text=logic.get_primary_currency(),
            size_hint_x=None, width=dp(100))
        self.cur_spinner.bind(text=self._on_currency_change)
        header.add_widget(self.cur_spinner)
        header.add_widget(IconButton(
            icon="swap", bg=NEUTRAL, size_hint=(None, None),
            size=(NAV_BTN_W, INPUT_H),
            on_release=lambda *_: self._open_data_popup()))
        content.add_widget(header)

        content.add_widget(self._build_hero_card())

        self.subs_area = BoxLayout(orientation="vertical")
        content.add_widget(self.subs_area)
        root.add_widget(content)

        self.empty_label = make_label(
            "Nothing here yet", font_size=sp(22),
            halign="center", valign="middle", color=(0.5, 0.5, 0.5, 1))

        self.subs_list = GridLayout(cols=1, size_hint_y=None, spacing=dp(8),
                                    padding=[0, dp(2), 0, dp(84)])
        self.subs_list.bind(minimum_height=self.subs_list.setter("height"))
        self.subs_scroll = ScrollView()
        self.subs_scroll.add_widget(self.subs_list)

        return root

    def _build_hero_card(self):
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=dp(92), padding=[dp(18), dp(14)],
                         spacing=dp(2))
        with card.canvas.before:
            Color(*BRAND)
            bg = RoundedRectangle(radius=[dp(18)])
            Color(*BRAND_DARK)
            edge = Line(width=dp(1))

        def sync(*_):
            bg.pos = card.pos
            bg.size = card.size
            edge.rounded_rectangle = (card.x, card.y, card.width,
                                      card.height, dp(18))

        card.bind(pos=sync, size=sync)

        self.hero_amount = make_label("", font_size=sp(30), bold=True,
                                      color=WHITE, size_hint_y=None,
                                      height=dp(40))
        self.hero_caption = make_label("This month", font_size=sp(13),
                                       color=(1, 1, 1, 0.78),
                                       size_hint_y=None, height=dp(20))
        card.add_widget(self.hero_amount)
        card.add_widget(self.hero_caption)
        return card

    def refresh_hero(self):
        cur = logic.get_primary_currency()
        subs = logic.get_all_subscriptions()
        today = date.today()
        total = 0.0
        for s in subs:
            for _ in logic.occurrences_in_month(s, today.year, today.month):
                total += s["price_usd"]
        self.hero_amount.text = f"{total:.2f} {cur}"
        self.hero_caption.text = (
            f"This month  ·  {len(subs)} active" if subs else "This month")

    def _on_currency_change(self, _spinner, value):
        logic.set_primary_currency(value)
        self.refresh_all()

    # ---- Add / Edit popup -------------------------------------------------
    def _open_popup(self, existing=None):
        editing = existing is not None
        today = date.today()

        # A Popup attaches to the Window, so it does not inherit the inset
        # padding applied to the main layout. Pad the content itself so
        # nothing sits under the status bar or navigation bar.
        _top, _bottom = _system_insets()
        content = BoxLayout(orientation="vertical", spacing=dp(8),
                            padding=[dp(12), _top + dp(12),
                                     dp(12), _bottom + dp(12)])

        # Everything above the action buttons lives on one soft card, like
        # Trackizer's single-sheet editor, instead of separate boxed
        # sections with a loud divider between them.
        card = BoxLayout(orientation="vertical", spacing=dp(12),
                         padding=dp(14))
        with card.canvas.before:
            Color(*CARD_BG)
            card_bg = RoundedRectangle(radius=[dp(18)])

        def _sync_card(*_):
            card_bg.pos = card.pos
            card_bg.size = card.size

        card.bind(pos=_sync_card, size=_sync_card)
        content.add_widget(card)

        # top bar: chevron-down (dismiss, same job as Cancel) — title —
        # trash, mirrors the reference's "Subscription info" sheet header
        top_bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        close_btn = IconButton(icon="down", bg=NEUTRAL, size_hint=(None, None),
                               size=(dp(36), dp(36)))
        top_bar.add_widget(close_btn)
        top_bar.add_widget(make_label(
            "Subscription info" if editing else "New subscription",
            font_size=sp(16), halign="center", color=(0.85, 0.85, 0.88, 1)))
        trash_btn = None
        if editing:
            trash_btn = IconButton(icon="trash", bg=(0.34, 0.16, 0.16, 1),
                                   size_hint=(None, None),
                                   size=(dp(36), dp(36)))
            top_bar.add_widget(trash_btn)
        else:
            top_bar.add_widget(Widget(size_hint=(None, None),
                                      size=(dp(36), dp(36))))
        card.add_widget(top_bar)

        # hero: big rounded-square app-style icon, name, price — mirrors
        # the reference's Spotify-icon-then-name-then-price block
        hero = BoxLayout(orientation="vertical", spacing=dp(4),
                         size_hint_y=None, height=dp(166),
                         padding=[0, dp(6), 0, 0])
        icon_anchor = AnchorLayout(size_hint_y=None, height=dp(96))
        popup_avatar = ServiceIcon(
            existing["name"] if editing else "",
            category_color((existing["category"] if editing else None)
                           or "Other"), shape="square",
            size=(dp(96), dp(96)))
        icon_anchor.add_widget(popup_avatar)
        hero.add_widget(icon_anchor)
        in_name = make_input(
            text=existing["name"] if editing else "",
            hint_text="New subscription",
            font_size=sp(20), halign="center",
            padding=[dp(8), dp(9)],
            size_hint_y=None, height=dp(44))
        in_name.background_color = (0, 0, 0, 0)
        hero.add_widget(in_name)
        card.add_widget(hero)

        # dashed rule, like the perforated ticket-stub line in the
        # reference, separating the summary from the editable fields
        dash = Widget(size_hint_y=None, height=dp(1))
        with dash.canvas:
            Color(1, 1, 1, 0.14)
            dash_line = Line(width=dp(1), dash_length=dp(6), dash_offset=dp(4))

        def _sync_dash(*_):
            dash_line.points = [dash.x, dash.center_y,
                                dash.x + dash.width, dash.center_y]

        dash.bind(pos=_sync_dash, size=_sync_dash)
        card.add_widget(dash)

        form = GridLayout(cols=2, size_hint_y=None, spacing=dp(6),
                          row_default_height=INPUT_H, row_force_default=True,
                          padding=[0, dp(8), 0, 0])
        form.bind(minimum_height=form.setter("height"))

        def add_row(label, widget):
            form.add_widget(make_label(label, bold=True, font_size=sp(14)))
            form.add_widget(widget)

        in_price = make_input(input_filter="float", hint_text="0.00",
                              halign="center")
        add_row(f"Price ({logic.get_primary_currency()})", in_price)
        in_sec_amt = make_input(input_filter="float", hint_text="optional",
                                halign="center")
        add_row("Secondary amt", in_sec_amt)
        in_sec_cur = modern_spinner(logic.CURRENCIES, text="")
        add_row("Currency", in_sec_cur)
        in_freq = modern_spinner(logic.FREQUENCIES, text="monthly")
        add_row("Frequency", in_freq)
        in_interval = make_input(input_filter="int", hint_text="days",
                                 disabled=True, halign="center")
        add_row("Custom days", in_interval)
        in_freq.bind(text=lambda _s, v:
                     setattr(in_interval, "disabled", v != "custom"))

        in_day = make_input(text=str(today.day), input_filter="int",
                            halign="center", font_size=sp(14),
                            padding=[dp(2), dp(12)])
        in_month = make_input(text=str(today.month), input_filter="int",
                              halign="center", font_size=sp(14),
                              padding=[dp(2), dp(12)])
        in_year = make_input(text=str(today.year), input_filter="int",
                             halign="center", font_size=sp(14),
                             padding=[dp(2), dp(12)])
        date_box = BoxLayout(spacing=dp(4), size_hint_y=None, height=INPUT_H)
        for w in (in_day, in_month, in_year):
            date_box.add_widget(w)
        add_row("Date  D / M / Y", date_box)

        in_card_text = make_input(hint_text="last 4 digits",
                                  input_filter="int", halign="center")
        in_card_text.bind(text=lambda w, v:
                          setattr(w, "text", v[:4]) if len(v) > 4 else None)
        add_row("Card charged", in_card_text)

        in_category = modern_spinner(logic.CATEGORIES, text="Other")
        add_row("Category", in_category)

        if editing:
            in_price.text = str(existing["price_usd"])
            if existing["secondary_amount"] is not None:
                in_sec_amt.text = str(existing["secondary_amount"])
            in_sec_cur.text = existing["secondary_currency"] or ""
            in_freq.text = existing["frequency"]
            if existing["frequency"] == "custom" and existing["interval_days"]:
                in_interval.text = str(existing["interval_days"])
                in_interval.disabled = False
            sd = date.fromisoformat(existing["start_date"])
            in_day.text, in_month.text, in_year.text = \
                str(sd.day), str(sd.month), str(sd.year)
            if existing["card"]:
                in_card_text.text = existing["card"]
            in_category.text = existing["category"] or "Other"

        def _update_avatar(*_):
            name = in_name.text.strip()
            popup_avatar.set_name(name)
            popup_avatar.set_color(category_color(in_category.text))

        in_name.bind(text=_update_avatar)
        in_category.bind(text=_update_avatar)
        _update_avatar()

        form_scroll = ScrollView()
        form_scroll.add_widget(form)
        card.add_widget(form_scroll)

        popup = Popup(title="", separator_height=0,
                      content=content, size_hint=(1, 1),
                      background_color=(0.09, 0.09, 0.11, 1))

        close_btn.bind(on_release=lambda *_: popup.dismiss())

        if trash_btn is not None:
            def do_delete(*_):
                popup.dismiss()
                self._confirm_delete(existing["id"])

            trash_btn.bind(on_release=do_delete)

        def read_form():
            name = in_name.text.strip()
            if not name:
                raise ValueError("Service name required.")
            price = float(in_price.text)
            sec_amt = float(in_sec_amt.text) if in_sec_amt.text.strip() \
                else None
            sec_cur = in_sec_cur.text or None
            freq = in_freq.text
            start = date(int(in_year.text), int(in_month.text),
                         int(in_day.text))
            interval = None
            if freq == "custom":
                interval = int(in_interval.text)
                if interval <= 0:
                    raise ValueError("Interval must be > 0.")
            card = in_card_text.text.strip() or None
            category = in_category.text or "Other"
            return (name, price, sec_amt, sec_cur, freq, start, interval,
                    card, category)

        def submit(*_):
            try:
                (name, price, sec_amt, sec_cur, freq, start, interval,
                 card, category) = read_form()
            except (ValueError, TypeError) as e:
                Popup(title="Error",
                      content=make_label(str(e), halign="center"),
                      size_hint=(0.8, 0.3)).open()
                return

            if editing:
                logic.update_subscription(existing["id"], name, price,
                                          sec_amt, sec_cur, freq, start,
                                          interval, card, category)
            else:
                logic.add_subscription(name, price, sec_amt, sec_cur, freq,
                                       start, interval, card, category)
            popup.dismiss()
            self.refresh_all()

        def add_to_calendar(*_):
            try:
                (name, price, _sec_amt, _sec_cur, freq, start, interval,
                 _card, _category) = read_form()
            except (ValueError, TypeError) as e:
                Popup(title="Error",
                      content=make_label(str(e), halign="center"),
                      size_hint=(0.8, 0.3)).open()
                return
            if not android_calendar.is_supported():
                Popup(title="Calendar",
                      content=make_label(
                          "Calendar integration is only available on "
                          "Android.", halign="center"),
                      size_hint=(0.85, 0.3)).open()
                return
            try:
                android_calendar.share_event(
                    name, price, freq, interval, start)
            except Exception as e:
                Popup(title="Calendar",
                      content=make_label(f"Could not open calendar: {e}",
                                         halign="center"),
                      size_hint=(0.85, 0.3)).open()

        # single full-width Save pill, like the reference — Cancel is the
        # chevron-down in the header now, so it doesn't need its own button
        content.add_widget(flat_button("Save", bg=BRAND, radius=dp(27),
                                       on_release=submit))
        content.add_widget(flat_button("Add to calendar", bg=BLUE,
                                       radius=dp(27),
                                       on_release=add_to_calendar))

        popup.open()
        content.opacity = 0
        Animation(opacity=1, d=0.16, t="out_quad").start(content)

    def _confirm_delete(self, sub_id):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        box.add_widget(make_label("Delete this subscription?",
                                  halign="center"))
        btns = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        popup = Popup(title="Confirm", content=box, size_hint=(0.78, 0.32),
                      title_color=WHITE, separator_color=RED,
                      separator_height=dp(2),
                      background_color=POPUP_BG)

        def do_delete(*_):
            logic.delete_subscription(sub_id)
            popup.dismiss()
            self.refresh_all()

        btns.add_widget(flat_button("Yes", bg=RED, on_release=do_delete))
        btns.add_widget(flat_button("No", bg=NEUTRAL,
                                    on_release=lambda *_: popup.dismiss()))
        box.add_widget(btns)
        popup.open()

    # ---- Import / export (writes/reads the public Downloads folder) -------
    def _desktop_downloads_dir(self):
        path = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(path, exist_ok=True)
        return path

    def _open_data_popup(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        box.add_widget(make_label("Import / export data", bold=True,
                                  halign="center", size_hint_y=None,
                                  height=dp(30)))
        popup = Popup(title="", title_size=0, separator_height=0,
                      content=box, size_hint=(0.85, 0.32),
                      background_color=POPUP_BG)

        def do_export(*_):
            popup.dismiss()
            self._export_now()

        def do_import(*_):
            popup.dismiss()
            self._open_import_picker()

        box.add_widget(flat_button("Export data", bg=GREEN,
                                   on_release=do_export))
        box.add_widget(flat_button("Import data", bg=BLUE,
                                   on_release=do_import))
        box.add_widget(flat_button("Cancel", bg=NEUTRAL,
                                   on_release=lambda *_: popup.dismiss()))
        popup.open()

    def _export_now(self):
        fname = f"subscriptions_export_{date.today().isoformat()}.json"
        content = logic.export_to_json_string()
        try:
            if android_downloads.is_supported():
                used = android_downloads.save_text(fname, content)
                msg = f"Saved to Downloads:\n{used}"
            else:
                downloads = self._desktop_downloads_dir()
                path = os.path.join(downloads, fname)
                i = 1
                while os.path.exists(path):
                    path = os.path.join(
                        downloads,
                        f"subscriptions_export_{date.today().isoformat()}"
                        f"_{i}.json")
                    i += 1
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                msg = f"Saved to:\n{path}"
        except Exception as e:
            Popup(title="Export failed",
                  content=make_label(str(e), halign="center"),
                  size_hint=(0.85, 0.3)).open()
            return
        Popup(title="Exported", content=make_label(msg, halign="center"),
              size_hint=(0.85, 0.35)).open()

    def _open_import_picker(self):
        """Launch the system file picker so the user can import any file,
        not just ones this app exported itself."""
        if android_downloads.is_supported():
            android_downloads.pick_file(self._on_file_picked)
            return

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                initialdir=self._desktop_downloads_dir(),
                title="Select a file to import",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
            root.destroy()
        except Exception as e:
            Popup(title="Import failed",
                  content=make_label(f"File picker unavailable: {e}",
                                     halign="center"),
                  size_hint=(0.85, 0.3)).open()
            return

        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            Popup(title="Import failed",
                  content=make_label(str(e), halign="center"),
                  size_hint=(0.85, 0.3)).open()
            return
        self._on_file_picked(text, os.path.basename(path))

    def _on_file_picked(self, text, fname, error=None):
        if text is None:
            if error:
                Popup(title="Import failed",
                      content=make_label(str(error), halign="center"),
                      size_hint=(0.85, 0.3)).open()
            return
        self._confirm_import_text(text, fname or "selected file")

    def _confirm_import_text(self, text, fname):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        box.add_widget(make_label(f"Import {fname}", bold=True,
                                  halign="center", size_hint_y=None,
                                  height=dp(30)))
        box.add_widget(make_label(
            "Merge adds these on top of what you have.\n"
            "Replace wipes your current data first.",
            halign="center"))
        popup = Popup(title="", title_size=0, separator_height=0,
                      content=box, size_hint=(0.88, 0.36),
                      background_color=POPUP_BG)

        def run_import(replace):
            try:
                logic.import_from_json_string(text, replace=replace)
            except Exception as e:
                popup.dismiss()
                Popup(title="Import failed",
                      content=make_label(str(e), halign="center"),
                      size_hint=(0.85, 0.3)).open()
                return
            popup.dismiss()
            self.refresh_all()

        btns = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        btns.add_widget(flat_button("Merge", bg=BLUE,
                                    on_release=lambda *_: run_import(False)))
        btns.add_widget(flat_button("Replace", bg=RED,
                                    on_release=lambda *_: run_import(True)))
        box.add_widget(btns)
        box.add_widget(flat_button("Cancel", bg=NEUTRAL,
                                   on_release=lambda *_: popup.dismiss()))
        popup.open()

    # ---- Overview tab (Monthly / Yearly toggle) ----------------------------
    def _build_overview_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=PADX)

        toggle = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(6))
        self.ov_btn_month = flat_button(
            "Monthly", bg=TAB_ACTIVE,
            on_release=lambda *_: self._set_overview_mode("month"))
        self.ov_btn_year = flat_button(
            "Yearly", bg=TAB_INACTIVE,
            on_release=lambda *_: self._set_overview_mode("year"))
        toggle.add_widget(self.ov_btn_month)
        toggle.add_widget(self.ov_btn_year)
        root.add_widget(toggle)

        self.overview_container = BoxLayout(orientation="vertical")
        root.add_widget(self.overview_container)

        self._month_view = self._build_month_view()
        self._year_view = self._build_year_view()
        self.overview_mode = "month"
        self.overview_container.add_widget(self._month_view)
        return root

    def _set_overview_mode(self, mode):
        if mode == self.overview_mode:
            return
        self.overview_mode = mode
        self.overview_container.clear_widgets()
        if mode == "month":
            self.overview_container.add_widget(self._month_view)
            self.ov_btn_month.set_bg(TAB_ACTIVE)
            self.ov_btn_year.set_bg(TAB_INACTIVE)
            self.refresh_month()
        else:
            self.overview_container.add_widget(self._year_view)
            self.ov_btn_month.set_bg(TAB_INACTIVE)
            self.ov_btn_year.set_bg(TAB_ACTIVE)
            self.refresh_year()

    def _build_month_view(self):
        root = BoxLayout(orientation="vertical", spacing=dp(10))

        # big title + "today" subtitle + a month-picker pill, instead of
        # the old plain "< Month Year >" nav bar
        title_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        title_col = BoxLayout(orientation="vertical")
        title_col.add_widget(make_label("Subs", bold=True, font_size=sp(24),
                                        size_hint_y=None, height=dp(30)))
        title_col.add_widget(make_label("Schedule", bold=True,
                                        font_size=sp(24), size_hint_y=None,
                                        height=dp(30)))
        title_row.add_widget(title_col)
        title_row.add_widget(Widget())
        self.month_pill = PillButton("", bg=CARD_BG, radius=dp(18),
                                     width=dp(108), height=dp(36),
                                     on_release=lambda *_: self._month_pick())
        pill_anchor = AnchorLayout(size_hint=(None, None),
                                   size=(dp(108), dp(64)))
        pill_anchor.add_widget(self.month_pill)
        title_row.add_widget(pill_anchor)
        root.add_widget(title_row)

        self.today_label = make_label("", font_size=sp(13),
                                      color=(0.6, 0.6, 0.66, 1),
                                      size_hint_y=None, height=dp(20))
        root.add_widget(self.today_label)

        self.day_strip = BoxLayout(size_hint=(None, None), height=dp(74),
                                   spacing=dp(8))
        self.day_strip.bind(minimum_width=self.day_strip.setter("width"))
        strip_scroll = ScrollView(size_hint_y=None, height=dp(74),
                                  do_scroll_y=False, bar_width=0)
        strip_scroll.add_widget(self.day_strip)
        root.add_widget(strip_scroll)

        # month + total header, then the occurrence grid + total, all in
        # one scroll so the total sits right after the cards
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(8))
        inner.bind(minimum_height=inner.setter("height"))

        totals_header = BoxLayout(size_hint_y=None, height=dp(30),
                                  spacing=dp(8))
        self.month_label = make_label("", bold=True, font_size=sp(19),
                                      size_hint_x=0.5)
        totals_header.add_widget(self.month_label)
        self.m_total_big = make_label("", bold=True, font_size=sp(19),
                                      halign="right", size_hint_x=0.5)
        totals_header.add_widget(self.m_total_big)
        inner.add_widget(totals_header)

        captions_row = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(8))
        self.month_date_caption = make_label("", font_size=sp(12),
                                             color=(0.55, 0.55, 0.6, 1),
                                             size_hint_x=0.5)
        captions_row.add_widget(self.month_date_caption)
        self.upcoming_caption = make_label(
            "in upcoming bills", font_size=sp(12), halign="right",
            color=(0.55, 0.55, 0.6, 1), size_hint_x=0.5)
        captions_row.add_widget(self.upcoming_caption)
        inner.add_widget(captions_row)

        self.m_list = GridLayout(cols=2, size_hint_y=None, spacing=dp(10),
                                 padding=[0, dp(4), 0, 0])
        self.m_list.bind(minimum_height=self.m_list.setter("height"))
        inner.add_widget(self.m_list)

        total_card = RowCard(bg=TOTAL_BG, radius=16, size_hint_y=None,
                             height=dp(54), padding=[dp(16), 0])
        self.m_total = make_label("", font_size=sp(19), halign="right",
                                  bold=True, color=WHITE, markup=True)
        total_card.add_widget(self.m_total)
        inner.add_widget(total_card)

        scroll.add_widget(inner)
        root.add_widget(scroll)
        return root

    def _select_day(self, day_num, *_):
        self.selected_day = None if day_num == self.selected_day else day_num
        self.refresh_month()

    def _month_pick(self):
        pick_year = [self.view_year]
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=dp(10))
        yr_row = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(6))
        yr_label = make_label(str(pick_year[0]), font_size=sp(20),
                              halign="center", bold=True)

        def yr_change(delta, *_):
            pick_year[0] += delta
            yr_label.text = str(pick_year[0])

        yr_row.add_widget(arrow_button("<",
                                       on_release=lambda *_: yr_change(-1)))
        yr_row.add_widget(yr_label)
        yr_row.add_widget(arrow_button(">",
                                       on_release=lambda *_: yr_change(1)))
        content.add_widget(yr_row)

        grid = GridLayout(cols=4, spacing=dp(6), size_hint_y=None,
                          row_default_height=BTN_H, row_force_default=True)
        grid.bind(minimum_height=grid.setter("height"))

        # height that fits content: year row + 3 month rows + spacing/padding
        # + title bar, so there's no empty gap inside the popup
        popup_h = BTN_H * 4 + dp(6) * 4 + dp(20) + dp(56)
        popup = Popup(title="Pick a month", content=content,
                      size_hint=(0.85, None), height=popup_h,
                      title_size=sp(18), title_color=WHITE,
                      separator_color=ACCENT, separator_height=dp(2),
                      background_color=POPUP_BG)

        def select(m, *_):
            self.view_month = m
            self.view_year = pick_year[0]
            self.selected_day = None
            popup.dismiss()
            self.refresh_month()

        for i, name in enumerate(calendar.month_abbr[1:], 1):
            grid.add_widget(flat_button(name, bg=NEUTRAL,
                                        on_release=partial(select, i)))
        content.add_widget(grid)
        popup.open()

    # ---- Yearly view --------------------------------------------------------
    def _build_year_view(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6))

        nav = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(6))
        nav.add_widget(arrow_button("<",
                                    on_release=lambda *_: self._year_prev()))
        self.year_label = make_label("", font_size=sp(20), halign="center",
                                    bold=True)
        nav.add_widget(self.year_label)
        nav.add_widget(arrow_button(">",
                                    on_release=lambda *_: self._year_next()))
        root.add_widget(nav)

        # no scroll: the rows share the available height so the table
        # always fits the page exactly
        self.y_list = GridLayout(cols=1, spacing=dp(5))
        root.add_widget(self.y_list)

        y_total_card = RowCard(bg=TOTAL_BG, radius=16, size_hint_y=None,
                               height=dp(50), padding=[dp(16), 0])
        self.y_total = make_label("", font_size=sp(18), halign="right",
                                  bold=True, color=WHITE)
        y_total_card.add_widget(self.y_total)
        root.add_widget(y_total_card)
        return root

    def _year_prev(self):
        self.y_year -= 1
        self.refresh_year()

    def _year_next(self):
        self.y_year += 1
        self.refresh_year()

    # ---- Analytics tab (Card / Category toggle) ----------------------------
    def _build_analytics_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=PADX)

        toggle = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(6))
        self.an_btn_card = flat_button(
            "By Card", bg=TAB_ACTIVE,
            on_release=lambda *_: self._set_analytics_mode("card"))
        self.an_btn_cat = flat_button(
            "By Category", bg=TAB_INACTIVE,
            on_release=lambda *_: self._set_analytics_mode("category"))
        toggle.add_widget(self.an_btn_card)
        toggle.add_widget(self.an_btn_cat)
        root.add_widget(toggle)

        self.analytics_container = BoxLayout(orientation="vertical")
        root.add_widget(self.analytics_container)

        self._card_panel = self._build_card_panel()
        self._category_panel = self._build_category_panel()
        self.analytics_mode = "card"
        self.analytics_container.add_widget(self._card_panel)
        return root

    def _set_analytics_mode(self, mode):
        if mode == self.analytics_mode:
            return
        self.analytics_mode = mode
        self.analytics_container.clear_widgets()
        if mode == "card":
            self.analytics_container.add_widget(self._card_panel)
            self.an_btn_card.set_bg(TAB_ACTIVE)
            self.an_btn_cat.set_bg(TAB_INACTIVE)
        else:
            self.analytics_container.add_widget(self._category_panel)
            self.an_btn_card.set_bg(TAB_INACTIVE)
            self.an_btn_cat.set_bg(TAB_ACTIVE)

    def _build_card_panel(self):
        self.cards_carousel = Carousel(direction="right", loop=False)
        return self.cards_carousel

    def _build_category_panel(self):
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(14), padding=[0, dp(8), 0, dp(20)])
        inner.bind(minimum_height=inner.setter("height"))

        self.arc_gauge = ArcGauge(size_hint_y=None, height=dp(150))
        inner.add_widget(self.arc_gauge)

        self.arc_total_label = make_label(
            "", bold=True, font_size=sp(26), halign="center",
            color=WHITE, size_hint_y=None, height=dp(34))
        inner.add_widget(self.arc_total_label)
        self.arc_caption_label = make_label(
            "yearly spend", font_size=sp(13), halign="center",
            color=(0.6, 0.6, 0.65, 1), size_hint_y=None, height=dp(20))
        inner.add_widget(self.arc_caption_label)

        self.cat_legend = GridLayout(cols=1, size_hint_y=None, spacing=dp(10),
                                     padding=[0, dp(6), 0, 0])
        self.cat_legend.bind(minimum_height=self.cat_legend.setter("height"))
        inner.add_widget(self.cat_legend)

        scroll.add_widget(inner)
        return scroll

    def _build_card_slide(self, label, subs, cur):
        """One carousel page: the physical card (with faint peeked cards
        behind it for a wallet-stack feel), then a 'Subscriptions' row of
        icons for whatever's billed to it — mirrors the reference layout
        of card-on-top, icon-strip-below instead of a card with a list."""
        total = sum(logic.annual_cost(s) for s in subs)

        stack_pad = dp(10)
        card_w, card_h = CardGroupCard.CARD_W, CardGroupCard.CARD_H
        base = metallic_color(label)[:3]
        stack = RelativeLayout(
            size_hint=(None, None),
            size=(card_w + stack_pad, card_h + stack_pad))
        # two faint, same-size cards offset up-right behind the front one,
        # so their top/right edges peek out — a real-wallet stack look
        peek2 = CardPeek(base + (0.30,), size_hint=(None, None),
                        size=(card_w, card_h), pos=(stack_pad, stack_pad))
        peek1 = CardPeek(base + (0.55,), size_hint=(None, None),
                        size=(card_w, card_h),
                        pos=(stack_pad * 0.5, stack_pad * 0.5))
        card = CardGroupCard(label, f"{total:.2f} {cur}", subs, cur,
                             alias=logic.get_card_alias(label),
                             on_rename=self._rename_card, pos=(0, 0))
        stack.add_widget(peek2)
        stack.add_widget(peek1)
        stack.add_widget(card)

        page = BoxLayout(orientation="vertical", spacing=dp(10),
                         padding=[dp(4), dp(10), dp(4), dp(4)])
        top_anchor = AnchorLayout(size_hint_y=None,
                                  height=card_h + stack_pad)
        top_anchor.add_widget(stack)
        page.add_widget(top_anchor)

        sub_header = AnchorLayout(size_hint_y=None, height=dp(24),
                                  anchor_x="center")
        sub_header_inner = BoxLayout(size_hint=(None, None),
                                     size=(dp(122), dp(24)), spacing=dp(6))
        sub_header_inner.add_widget(make_label(
            "Subscriptions", bold=True, font_size=sp(15),
            size_hint_x=None, width=dp(110)))
        dot = Widget(size_hint=(None, None), size=(dp(6), dp(6)))
        with dot.canvas:
            Color(*RED)
            dot_ellipse = Ellipse(pos=dot.pos, size=dot.size)

        def _sync_dot(*_):
            dot_ellipse.pos = (dot.x, dot.center_y - dp(3))
            dot_ellipse.size = dot.size

        dot.bind(pos=_sync_dot, size=_sync_dot)
        sub_header_inner.add_widget(dot)
        sub_header.add_widget(sub_header_inner)
        page.add_widget(sub_header)

        icons_scroll = ScrollView(size_hint_y=None, height=dp(56),
                                  do_scroll_y=False, bar_width=0)
        icons_row = BoxLayout(size_hint=(None, 1), spacing=dp(10))
        icons_row.bind(minimum_width=icons_row.setter("width"))
        if subs:
            for s in subs:
                icons_row.add_widget(ServiceIcon(
                    s["name"], category_color(s["category"] or "Other"),
                    size=(dp(48), dp(48)), size_hint=(None, None)))
        else:
            icons_row.add_widget(make_label(
                "No subscriptions on this card", font_size=sp(13),
                color=(0.55, 0.55, 0.6, 1), size_hint_x=None, width=dp(220)))
        # centered when the icons fit the viewport; once they overflow it,
        # icons_center grows to match icons_row so scrolling still works
        icons_center = AnchorLayout(size_hint=(None, 1), anchor_x="center")
        icons_center.add_widget(icons_row)

        def _sync_center_width(*_):
            icons_center.width = max(icons_scroll.width, icons_row.width)

        icons_row.bind(width=_sync_center_width)
        icons_scroll.bind(width=_sync_center_width)
        icons_scroll.add_widget(icons_center)
        page.add_widget(icons_scroll)

        page.add_widget(Widget())
        return page

    def refresh_analytics(self):
        cur = logic.get_primary_currency()

        keep_index = self.cards_carousel.index
        self.cards_carousel.clear_widgets()
        card_groups = logic.get_card_groups()
        if not card_groups:
            slide = AnchorLayout()
            slide.add_widget(make_label(
                "Nothing here yet", color=(0.5, 0.5, 0.5, 1),
                size_hint=(None, None), height=dp(30)))
            self.cards_carousel.add_widget(slide)
        for label, subs in card_groups:
            self.cards_carousel.add_widget(
                self._build_card_slide(label, subs, cur))

        if card_groups and keep_index is not None and keep_index < len(card_groups):
            self.cards_carousel.index = keep_index

        cat_totals = logic.get_category_totals()
        grand_total = sum(total for _lbl, total in cat_totals)
        self.arc_gauge.set_data(
            [(lbl, total, category_color(lbl)) for lbl, total in cat_totals])
        self.arc_total_label.text = f"{grand_total:.2f} {cur}"
        self.arc_caption_label.text = (
            "yearly spend" if cat_totals else "nothing tracked yet")

        self.cat_legend.clear_widgets()
        if not cat_totals:
            self.cat_legend.add_widget(make_label(
                "Nothing here yet", color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None, height=dp(30)))
        for label, total in cat_totals:
            share = (total / grand_total * 100) if grand_total else 0
            self.cat_legend.add_widget(CategoryBar(
                label, f"{total:.2f} {cur}", share, category_color(label)))

    def _on_tab_switch(self, _panel, tab):
        if tab is self.tab_overview:
            if self.overview_mode == "month":
                self.refresh_month()
            else:
                self.refresh_year()
        elif tab is self.tab_analytics:
            self.refresh_analytics()

    # ---- Refresh ----------------------------------------------------------
    def refresh_all(self):
        self.refresh_subs_list()
        self.refresh_month()
        self.refresh_year()
        self.refresh_analytics()

    def refresh_subs_list(self):
        self.refresh_hero()
        self.subs_list.clear_widgets()
        self.subs_area.clear_widgets()
        subs = logic.get_all_subscriptions()

        if not subs:
            self.subs_area.add_widget(self.empty_label)
            return
        self.subs_area.add_widget(self.subs_scroll)

        cur = logic.get_primary_currency()
        for s in subs:
            secondary = ""
            if s["secondary_amount"] is not None:
                sc = s["secondary_currency"] or ""
                secondary = f"{s['secondary_amount']:.2f} {sc}".strip()

            card = SubRow(
                s["name"],
                f"{s['price_usd']:.2f} {cur}",
                s["frequency"],
                s["card"],
                secondary,
                s["category"],
            )
            card.bind(on_release=partial(self._edit_clicked, s["id"]))
            self.subs_list.add_widget(card)

    def _edit_clicked(self, sub_id, *_):
        sub = logic.get_subscription(sub_id)
        if sub:
            self._open_popup(sub)

    def _rename_card(self, card_label):
        content = BoxLayout(orientation="vertical", spacing=dp(10),
                            padding=dp(14))
        in_alias = make_input(
            text=logic.get_card_alias(card_label) or "",
            hint_text="e.g. Revolut, Chase Visa")
        content.add_widget(in_alias)
        btn_row = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        popup = Popup(title=f"Rename card {card_label}", content=content,
                      size_hint=(0.85, None), height=dp(160),
                      title_size=sp(16), title_color=WHITE,
                      separator_color=ACCENT, separator_height=dp(2),
                      background_color=POPUP_BG)

        def save(*_):
            logic.set_card_alias(card_label, in_alias.text.strip() or None)
            popup.dismiss()
            self.refresh_analytics()

        btn_row.add_widget(flat_button("Cancel", bg=NEUTRAL,
                                       on_release=lambda *_: popup.dismiss()))
        btn_row.add_widget(flat_button("Save", bg=BRAND,
                                       on_release=save))
        content.add_widget(btn_row)
        popup.open()

    def refresh_month(self):
        y, m = self.view_year, self.view_month
        today = date.today()
        self.month_label.text = calendar.month_name[m]
        self.month_pill.label.text = calendar.month_abbr[m]
        self.m_list.clear_widgets()

        cur = logic.get_primary_currency()
        total = 0.0
        sec_totals = {}
        rows = []
        due_days = set()
        for s in logic.get_all_subscriptions():
            for d in logic.occurrences_in_month(s, y, m):
                total += s["price_usd"]
                due_days.add(d.day)
                sec = ""
                if s["secondary_amount"] is not None:
                    sc = s["secondary_currency"] or ""
                    sec = f"{s['secondary_amount']:.2f} {sc}".strip()
                    sec_totals[sc] = sec_totals.get(sc, 0) + \
                        s["secondary_amount"]
                rows.append((d, s["name"], s["price_usd"], sec,
                            s["category"]))

        rows.sort(key=lambda r: r[0])

        today_count = sum(1 for d, *_ in rows
                          if y == today.year and m == today.month
                          and d.day == today.day)
        self.today_label.text = (
            f"{today_count} subscription{'s' if today_count != 1 else ''} "
            f"for today" if today_count else "Nothing due today")
        self.month_date_caption.text = today.strftime("%d.%m.%Y")

        # horizontal day strip: every day in the viewed month, dot marks a
        # day with something due, tap selects it to filter the list below
        self.day_strip.clear_widgets()
        days_in_month = calendar.monthrange(y, m)[1]
        if self.selected_day is not None and self.selected_day > days_in_month:
            self.selected_day = None
        for day_num in range(1, days_in_month + 1):
            wd = calendar.day_abbr[date(y, m, day_num).weekday()][:2]
            is_today = (y == today.year and m == today.month
                       and day_num == today.day)
            self.day_strip.add_widget(DayCell(
                day_num, wd, is_today=is_today,
                is_selected=(day_num == self.selected_day),
                has_due=day_num in due_days,
                on_release=partial(self._select_day, day_num)))

        # list of occurrences: the full month, unless a day is selected,
        # in which case only that day's rows show. The grey total card
        # below always keeps showing the whole month's total.
        if self.selected_day is not None:
            shown = [r for r in rows if r[0].day == self.selected_day]
            self.upcoming_caption.text = (
                f"on {calendar.month_abbr[m]} {self.selected_day}")
        else:
            shown = rows
            self.upcoming_caption.text = "in upcoming bills"

        for d, name, amt, sec, category in shown:
            card = MonthSubCard(name, f"{amt:.2f} {cur}", category,
                                size_hint_y=None, height=dp(140))
            self.m_list.add_widget(card)

        label = f"Total:  {total:.2f} {cur}"
        extra = _fmt_group(sec_totals)
        if extra:
            label += f"   [size={sp(13):.0f}](+ {extra})[/size]"
        self.m_total.text = label

        # the big number right under the day strip is a per-day summary
        # (0 if nothing's due that day) — defaults to today's day when no
        # day is tapped, unlike the month total in the grey card below
        if self.selected_day is not None:
            day_num = self.selected_day
        elif y == today.year and m == today.month:
            day_num = today.day
        else:
            day_num = None
        day_total = (sum(r[2] for r in rows if r[0].day == day_num)
                    if day_num is not None else 0.0)
        self.m_total_big.text = f"{day_total:.2f} {cur}"

    def refresh_year(self):
        y = self.y_year
        self.year_label.text = str(y)
        self.y_list.clear_widgets()
        subs = logic.get_all_subscriptions()
        cur = logic.get_primary_currency()
        grand = 0.0

        hdr = RowCard(bg=BRAND, radius=8, spacing=dp(4), padding=[dp(10), 0])
        for txt, hint in (("Month", 0.42), ("Payments", 0.22),
                          ("Amount", 0.36)):
            hdr.add_widget(make_label(f"[b]{txt}[/b]", markup=True,
                                      color=WHITE, size_hint_x=hint))
        self.y_list.add_widget(hdr)

        today = date.today()
        for mo in range(1, 13):
            m_total = 0.0
            count = 0
            for s in subs:
                for _ in logic.occurrences_in_month(s, y, mo):
                    m_total += s["price_usd"]
                    count += 1
            grand += m_total

            current = (y == today.year and mo == today.month)
            row_bg = BRAND_DARK if current else CARD_BG
            row = RowCard(bg=row_bg, radius=8, spacing=dp(4),
                         padding=[dp(10), 0])
            row.add_widget(make_label(calendar.month_name[mo], bold=current,
                                      size_hint_x=0.42))
            row.add_widget(make_label(str(count), size_hint_x=0.22))
            row.add_widget(make_label(f"{m_total:.2f} {cur}", bold=current,
                                      size_hint_x=0.36))
            self.y_list.add_widget(row)

        self.y_total.text = f"Year total:  {grand:.2f} {cur}"


if __name__ == "__main__":
    SubscriptionApp().run()
