"""
Subscription Tracker - Kivy app (Android-ready via Buildozer).

Desktop:  pip install kivy  &&  python main.py
APK:      buildozer -v android debug
"""

import os
import calendar
import math
from datetime import date
from functools import partial

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Line, Ellipse, Rectangle, RoundedRectangle
from kivy.animation import Animation

import logic

# ---- Sizing -----------------------------------------------------------------
FS = sp(17)
CARD_H = dp(116)             # height of a subscription card
BTN_H = dp(54)
INPUT_H = dp(46)
PADX = dp(10)
NAV_BTN_W = dp(56)
ICON_BTN_W = dp(50)

# ---- Colours ----------------------------------------------------------------
GREEN = (0.18, 0.62, 0.34, 1)
BLUE = (0.20, 0.45, 0.70, 1)
RED = (0.74, 0.25, 0.25, 1)
NEUTRAL = (0.24, 0.24, 0.29, 1)
WHITE = (0.95, 0.95, 0.95, 1)
TAB_ACTIVE = (0.22, 0.49, 0.76, 1)
TAB_INACTIVE = (0.16, 0.16, 0.20, 1)
TAB_TEXT_ACTIVE = (1, 1, 1, 1)
TAB_TEXT_INACTIVE = (0.55, 0.55, 0.60, 1)


def _is_android():
    try:
        import android  # noqa: F401
        return True
    except ImportError:
        return False


def _system_insets():
    """(top, bottom) system-bar insets in px. Only needed on Android 15+
    (SDK 35+), where the app is forced to draw edge-to-edge. On older
    versions the OS already reserves the bars, so we add nothing."""
    if not _is_android():
        return (0, 0)
    try:
        from jnius import autoclass
        if autoclass("android.os.Build$VERSION").SDK_INT < 35:
            return (0, 0)
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        decor = activity.getWindow().getDecorView()
        insets = decor.getRootWindowInsets()
        if insets is not None:
            Type = autoclass("android.view.WindowInsets$Type")
            ins = insets.getInsets(Type.systemBars())
            return (ins.top, ins.bottom)
        res = activity.getResources()

        def dim(name):
            rid = res.getIdentifier(name, "dimen", "android")
            return res.getDimensionPixelSize(rid) if rid > 0 else 0

        return (dim("status_bar_height"), dim("navigation_bar_height"))
    except Exception:
        return (0, 0)


# ---- Vector-icon button (no font dependency) --------------------------------
class IconButton(Button):
    """A flat coloured button that draws its icon as vector graphics."""

    def __init__(self, icon="", icon_color=WHITE, bg=NEUTRAL, **kwargs):
        super().__init__(**kwargs)
        self.text = ""
        self.background_normal = ""
        self.background_down = ""
        self.background_color = bg
        self.border = (0, 0, 0, 0)
        self._icon = icon
        self._icon_color = icon_color
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.after.clear()
        if not self._icon:
            return
        x, y = self.pos
        w, h = self.size
        s = min(w, h) * 0.44
        r = s / 2
        cx, cy = x + w / 2, y + h / 2
        lw = max(dp(1.7), s * 0.10)
        with self.canvas.after:
            Color(*self._icon_color)
            self._draw(self._icon, cx, cy, r, lw)

    def _draw(self, icon, cx, cy, r, lw):
        if icon == "left":
            Line(points=[cx + r * 0.4, cy - r * 0.75, cx - r * 0.4, cy,
                         cx + r * 0.4, cy + r * 0.75],
                 width=lw, cap="round", joint="round")
        elif icon == "right":
            Line(points=[cx - r * 0.4, cy - r * 0.75, cx + r * 0.4, cy,
                         cx - r * 0.4, cy + r * 0.75],
                 width=lw, cap="round", joint="round")
        elif icon == "plus":
            Line(points=[cx - r * 0.8, cy, cx + r * 0.8, cy],
                 width=lw, cap="round")
            Line(points=[cx, cy - r * 0.8, cx, cy + r * 0.8],
                 width=lw, cap="round")
        elif icon == "calendar":
            Line(rectangle=(cx - r * 0.85, cy - r * 0.85,
                            r * 1.7, r * 1.55), width=lw)
            Line(points=[cx - r * 0.85, cy + r * 0.35,
                         cx + r * 0.85, cy + r * 0.35], width=lw)
            Line(points=[cx - r * 0.45, cy + r * 0.5,
                         cx - r * 0.45, cy + r * 0.95],
                 width=lw, cap="round")
            Line(points=[cx + r * 0.45, cy + r * 0.5,
                         cx + r * 0.45, cy + r * 0.95],
                 width=lw, cap="round")
        elif icon == "pencil":
            inv = 1 / math.sqrt(2)
            dx, dy = inv, inv          # axis toward the eraser (up-right)
            px, py = -inv, inv         # perpendicular (pencil width)
            hw = r * 0.30
            tip = (cx - dx * r * 0.95, cy - dy * r * 0.95)
            nb = (cx - dx * r * 0.45, cy - dy * r * 0.45)   # nib base
            er = (cx + dx * r * 0.90, cy + dy * r * 0.90)   # eraser end
            nb_l = (nb[0] + px * hw, nb[1] + py * hw)
            nb_r = (nb[0] - px * hw, nb[1] - py * hw)
            er_l = (er[0] + px * hw, er[1] + py * hw)
            er_r = (er[0] - px * hw, er[1] - py * hw)
            # body outline (closed)
            Line(points=[tip[0], tip[1], nb_l[0], nb_l[1],
                         er_l[0], er_l[1], er_r[0], er_r[1],
                         nb_r[0], nb_r[1], tip[0], tip[1]],
                 width=lw, joint="round", cap="round")
            # line where the wood meets the painted body
            Line(points=[nb_l[0], nb_l[1], nb_r[0], nb_r[1]],
                 width=lw, cap="round")
            # eraser band
            eb = (cx + dx * r * 0.55, cy + dy * r * 0.55)
            Line(points=[eb[0] + px * hw, eb[1] + py * hw,
                         eb[0] - px * hw, eb[1] - py * hw],
                 width=lw, cap="round")
        elif icon == "trash":
            Line(points=[cx - r * 0.7, cy + r * 0.55,
                         cx + r * 0.7, cy + r * 0.55],
                 width=lw, cap="round")
            Line(points=[cx - r * 0.28, cy + r * 0.55,
                         cx - r * 0.28, cy + r * 0.8,
                         cx + r * 0.28, cy + r * 0.8,
                         cx + r * 0.28, cy + r * 0.55],
                 width=lw, cap="round", joint="round")
            Line(points=[cx - r * 0.55, cy + r * 0.55,
                         cx - r * 0.42, cy - r * 0.8,
                         cx + r * 0.42, cy - r * 0.8,
                         cx + r * 0.55, cy + r * 0.55],
                 width=lw, cap="round", joint="round")
            Line(points=[cx, cy + r * 0.35, cx, cy - r * 0.55],
                 width=lw * 0.8, cap="round")


class FloatingActionButton(Button):
    """Circular elevated button (Material-style FAB)."""

    def __init__(self, bg=GREEN, icon_color=WHITE, **kwargs):
        super().__init__(**kwargs)
        self.text = ""
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (None, None)
        self.size = (dp(64), dp(64))
        self._bg = bg
        self._icon_color = icon_color
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        self.canvas.after.clear()
        x, y = self.pos
        w, h = self.size
        with self.canvas.before:
            Color(0, 0, 0, 0.28)            # soft shadow
            Ellipse(pos=(x + dp(2), y - dp(2)), size=(w, h))
            Color(*self._bg)                # button face
            Ellipse(pos=(x, y), size=(w, h))
        cx, cy = x + w / 2, y + h / 2
        r = min(w, h) * 0.22
        lw = max(dp(2.5), r * 0.32)
        with self.canvas.after:
            Color(*self._icon_color)
            Line(points=[cx - r, cy, cx + r, cy], width=lw, cap="round")
            Line(points=[cx, cy - r, cx, cy + r], width=lw, cap="round")


class SubCard(ButtonBehavior, BoxLayout):
    """A tappable card showing one subscription; tap opens the edit window."""

    def __init__(self, name, amount, freq, card, secondary, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(12), dp(10)]
        self.spacing = dp(1)
        self.size_hint_y = None
        self.height = CARD_H

        with self.canvas.before:
            Color(0.18, 0.18, 0.22, 1)
            self._bg = RoundedRectangle(radius=[dp(12)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.add_widget(make_label(name, bold=True, font_size=sp(16),
                                   shorten=True, shorten_from="right",
                                   size_hint_y=None, height=dp(24)))
        self.add_widget(make_label(amount, font_size=sp(18),
                                   size_hint_y=None, height=dp(28)))
        meta = f"{freq}  ·  {secondary}" if secondary else freq
        self.add_widget(make_label(meta, font_size=sp(12), shorten=True,
                                   color=(0.62, 0.62, 0.68, 1),
                                   size_hint_y=None, height=dp(20)))
        self.add_widget(make_label(f"Card {card}" if card else "",
                                   font_size=sp(12),
                                   color=(0.62, 0.62, 0.68, 1),
                                   size_hint_y=None, height=dp(18)))

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


FIELD = (0.18, 0.18, 0.22, 1)
ACCENT = (0.22, 0.49, 0.76, 1)


class FlatOption(Button):
    """Flat dropdown option for Spinners (replaces the holo look)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0.20, 0.20, 0.24, 1)
        self.color = WHITE
        self.font_size = FS
        self.size_hint_y = None
        self.height = INPUT_H


def modern_spinner(values, text="", **kwargs):
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", INPUT_H)
    kwargs.setdefault("font_size", FS)
    sp_ = Spinner(text=text, values=values, **kwargs)
    sp_.background_normal = ""
    sp_.background_down = ""
    sp_.background_color = FIELD
    sp_.color = WHITE
    sp_.option_cls = FlatOption
    return sp_


def make_input(**kwargs):
    kwargs.setdefault("multiline", False)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", INPUT_H)
    kwargs.setdefault("font_size", FS)
    kwargs.setdefault("padding", [dp(10), dp(12)])
    ti = TextInput(**kwargs)
    ti.background_normal = ""
    ti.background_active = ""
    ti.background_color = FIELD
    ti.foreground_color = WHITE
    ti.cursor_color = ACCENT
    ti.hint_text_color = (0.5, 0.5, 0.55, 1)
    return ti


def make_label(text, **kwargs):
    kwargs.setdefault("font_size", FS)
    kwargs.setdefault("halign", "left")
    kwargs.setdefault("valign", "middle")
    lbl = Label(text=text, **kwargs)
    lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
    return lbl


def flat_button(text, bg=NEUTRAL, **kwargs):
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", BTN_H)
    kwargs.setdefault("font_size", FS)
    b = Button(text=text, **kwargs)
    b.background_normal = ""
    b.background_down = ""
    b.background_color = bg
    b.border = (0, 0, 0, 0)
    return b


def _fmt_group(d):
    """Format {currency: total} as 'X.XX CUR   Y.YY CUR2' (skips blanks)."""
    return "   ".join(f"{v:.2f} {k}".strip() for k, v in d.items() if k)


def arrow_button(symbol, **kwargs):
    """Nav arrow using the plain keyboard glyph (renders everywhere)."""
    kwargs.setdefault("size_hint_x", None)
    kwargs.setdefault("width", NAV_BTN_W)
    b = flat_button(symbol, bg=NEUTRAL, **kwargs)
    b.font_size = sp(24)
    b.bold = True
    return b


class SubscriptionApp(App):

    def build(self):
        self.title = "Subscription Tracker"
        Window.clearcolor = (0.12, 0.12, 0.14, 1)
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

        # tabs at the BOTTOM
        panel = TabbedPanel(do_default_tab=False, tab_pos="bottom_mid",
                            tab_height=dp(56))
        panel.background_color = (0.12, 0.12, 0.14, 1)

        self.tab_subs = TabbedPanelItem(text="Subscriptions", font_size=sp(15))
        self.tab_subs.add_widget(self._build_subs_tab())
        panel.add_widget(self.tab_subs)

        self.tab_month = TabbedPanelItem(text="Monthly", font_size=sp(15))
        self.tab_month.add_widget(self._build_month_tab())
        panel.add_widget(self.tab_month)

        self.tab_year = TabbedPanelItem(text="Yearly", font_size=sp(15))
        self.tab_year.add_widget(self._build_year_tab())
        panel.add_widget(self.tab_year)

        for tab in (self.tab_subs, self.tab_month, self.tab_year):
            tab.background_normal = ""
            tab.background_down = ""
            tab.border = (0, 0, 0, 0)
            tab.bind(state=lambda inst, _v: self._style_tab(inst))
            self._style_tab(tab)

        # size each tab to exactly one third of the screen so all three
        # fit snug with no scrolling (and re-fit on rotation)
        def _fit_tabs(*_):
            panel.tab_width = int(Window.width / 3)

        Window.bind(width=lambda *_: _fit_tabs())
        Clock.schedule_once(lambda *_: _fit_tabs(), 0)

        panel.bind(current_tab=self._on_tab_switch)
        self.refresh_all()
        self._start_notification_service()

        # edge-to-edge: pad around the status bar and navigation pill so
        # nothing is drawn underneath them (Android 15+ / API 35+)
        self.root_box = BoxLayout(orientation="vertical")
        self.root_box.add_widget(panel)
        Window.bind(size=lambda *_: self._apply_insets())
        Clock.schedule_once(self._apply_insets, 0)
        Clock.schedule_once(self._apply_insets, 0.5)
        return self.root_box

    def _apply_insets(self, *_):
        top, bottom = _system_insets()
        self.root_box.padding = [0, top, 0, bottom]

    @staticmethod
    def _style_tab(tab):
        if tab.state == "down":
            tab.background_color = TAB_ACTIVE
            tab.color = TAB_TEXT_ACTIVE
        else:
            tab.background_color = TAB_INACTIVE
            tab.color = TAB_TEXT_INACTIVE

    # ---- Android notification service -------------------------------------
    def _start_notification_service(self):
        if not _is_android():
            return
        try:
            from android import mActivity
            from jnius import autoclass
            service = autoclass(
                "org.example.subscriptiontracker.ServiceNotify")
            service.start(mActivity, "Subscription Tracker notifications")
        except Exception as e:
            print(f"[SubTracker] Could not start service: {e}")

    # ---- Subscriptions tab ------------------------------------------------
    def _build_subs_tab(self):
        # FloatLayout lets the FAB float over the list
        root = FloatLayout()

        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=PADX, size_hint=(1, 1),
                            pos_hint={"x": 0, "y": 0})

        # slim header: title + global currency selector
        header = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        header.add_widget(make_label("Subscriptions", font_size=sp(20),
                                     bold=True))
        self.cur_spinner = modern_spinner(
            logic.PRIMARY_CURRENCIES, text=logic.get_primary_currency(),
            size_hint_x=None, width=dp(110))
        self.cur_spinner.bind(text=self._on_currency_change)
        header.add_widget(self.cur_spinner)
        content.add_widget(header)

        self.subs_area = BoxLayout(orientation="vertical")
        content.add_widget(self.subs_area)
        root.add_widget(content)

        self.empty_label = make_label(
            "Nothing here yet", font_size=sp(22),
            halign="center", valign="middle", color=(0.5, 0.5, 0.5, 1))

        self.subs_list = GridLayout(cols=2, size_hint_y=None, spacing=dp(8),
                                    padding=[0, dp(2), 0, dp(84)])
        self.subs_list.bind(minimum_height=self.subs_list.setter("height"))
        self.subs_scroll = ScrollView()
        self.subs_scroll.add_widget(self.subs_list)

        # floating Add button, bottom-right, above the tab bar
        self.fab = FloatingActionButton(bg=GREEN)
        self.fab.bind(on_release=lambda *_: self._open_popup())
        root.add_widget(self.fab)

        def place_fab(*_):
            # FloatLayout uses absolute window coords, so anchor to the
            # content area's own right/bottom edges (which sit above the
            # tab strip) rather than the window's bottom
            self.fab.right = root.right - dp(18)
            self.fab.y = root.y + dp(18)

        root.bind(size=place_fab, pos=place_fab)
        Clock.schedule_once(lambda *_: place_fab(), 0)
        return root

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
        content.add_widget(make_label(
            "Edit subscription" if existing is not None
            else "Add subscription",
            font_size=sp(19), bold=True,
            size_hint_y=None, height=dp(40)))
        form = GridLayout(cols=2, size_hint_y=None, spacing=dp(6),
                          row_default_height=INPUT_H, row_force_default=True)
        form.bind(minimum_height=form.setter("height"))

        def add_row(label, widget):
            form.add_widget(make_label(label))
            form.add_widget(widget)

        in_name = make_input(hint_text="e.g. Netflix")
        add_row("Service name", in_name)
        in_price = make_input(input_filter="float", hint_text="0.00")
        add_row(f"Price ({logic.get_primary_currency()})", in_price)
        in_sec_amt = make_input(input_filter="float", hint_text="optional")
        add_row("Secondary amt", in_sec_amt)
        in_sec_cur = modern_spinner(logic.CURRENCIES, text="")
        add_row("Currency", in_sec_cur)
        in_freq = modern_spinner(logic.FREQUENCIES, text="monthly")
        add_row("Frequency", in_freq)
        in_interval = make_input(input_filter="int", hint_text="days",
                                 disabled=True)
        add_row("Custom days", in_interval)
        in_freq.bind(text=lambda _s, v:
                     setattr(in_interval, "disabled", v != "custom"))

        in_day = make_input(text=str(today.day), input_filter="int")
        in_month = make_input(text=str(today.month), input_filter="int")
        in_year = make_input(text=str(today.year), input_filter="int")
        date_box = BoxLayout(spacing=dp(4), size_hint_y=None, height=INPUT_H)
        for w in (in_day, in_month, in_year):
            date_box.add_widget(w)
        add_row("Date  D / M / Y", date_box)

        in_card_text = make_input(hint_text="last 4 digits",
                                  input_filter="int")
        in_card_text.bind(text=lambda w, v:
                          setattr(w, "text", v[:4]) if len(v) > 4 else None)
        add_row("Card charged", in_card_text)

        if editing:
            in_name.text = existing["name"]
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

        form_scroll = ScrollView()
        form_scroll.add_widget(form)
        content.add_widget(form_scroll)

        popup = Popup(title="", separator_height=0,
                      content=content, size_hint=(1, 1),
                      background_color=(0.13, 0.13, 0.16, 1))

        def submit(*_):
            try:
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
            except (ValueError, TypeError) as e:
                Popup(title="Error",
                      content=make_label(str(e), halign="center"),
                      size_hint=(0.8, 0.3)).open()
                return

            if editing:
                logic.update_subscription(existing["id"], name, price,
                                          sec_amt, sec_cur, freq, start,
                                          interval, card)
            else:
                logic.add_subscription(name, price, sec_amt, sec_cur, freq,
                                       start, interval, card)
            popup.dismiss()
            self.refresh_all()

        actions = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(8))
        actions.add_widget(flat_button("Cancel", bg=NEUTRAL, size_hint_x=0.4,
                                       on_release=lambda *_: popup.dismiss()))
        actions.add_widget(flat_button("Save", bg=GREEN, on_release=submit))
        content.add_widget(actions)

        if editing:
            def do_delete(*_):
                popup.dismiss()
                self._confirm_delete(existing["id"])

            content.add_widget(flat_button("Delete", bg=RED,
                                           on_release=do_delete))

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
                      background_color=(0.13, 0.13, 0.16, 1))

        def do_delete(*_):
            logic.delete_subscription(sub_id)
            popup.dismiss()
            self.refresh_all()

        btns.add_widget(flat_button("Yes", bg=RED, on_release=do_delete))
        btns.add_widget(flat_button("No", bg=NEUTRAL,
                                    on_release=lambda *_: popup.dismiss()))
        box.add_widget(btns)
        popup.open()

    # ---- Monthly tab ------------------------------------------------------
    def _build_month_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=PADX)

        nav = BoxLayout(size_hint_y=None, height=BTN_H, spacing=dp(6))
        nav.add_widget(arrow_button("<",
                                    on_release=lambda *_: self._month_prev()))
        self.month_label = make_label("", font_size=sp(20), halign="center")
        nav.add_widget(self.month_label)
        nav.add_widget(arrow_button(">",
                                    on_release=lambda *_: self._month_next()))
        nav.add_widget(IconButton(icon="calendar", bg=BLUE, size_hint_x=None,
                                  width=NAV_BTN_W,
                                  on_release=lambda *_: self._month_pick()))
        root.add_widget(nav)

        # list + total together inside one scroll, so total sits right
        # below the list rather than pinned to the screen bottom
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(4))
        inner.bind(minimum_height=inner.setter("height"))

        self.m_list = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        self.m_list.bind(minimum_height=self.m_list.setter("height"))
        inner.add_widget(self.m_list)

        self.m_total = make_label("", font_size=sp(19), halign="right",
                                  bold=True, size_hint_y=None, height=dp(52))
        inner.add_widget(self.m_total)

        scroll.add_widget(inner)
        root.add_widget(scroll)
        return root

    def _month_prev(self):
        if self.view_month == 1:
            self.view_month, self.view_year = 12, self.view_year - 1
        else:
            self.view_month -= 1
        self.refresh_month()

    def _month_next(self):
        if self.view_month == 12:
            self.view_month, self.view_year = 1, self.view_year + 1
        else:
            self.view_month += 1
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
                      background_color=(0.13, 0.13, 0.16, 1))

        def select(m, *_):
            self.view_month = m
            self.view_year = pick_year[0]
            popup.dismiss()
            self.refresh_month()

        for i, name in enumerate(calendar.month_abbr[1:], 1):
            grid.add_widget(flat_button(name, bg=NEUTRAL,
                                        on_release=partial(select, i)))
        content.add_widget(grid)
        popup.open()

    # ---- Yearly tab -------------------------------------------------------
    def _build_year_tab(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=PADX)

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
        self.y_list = GridLayout(cols=1, spacing=dp(2))
        root.add_widget(self.y_list)

        self.y_total = make_label("", font_size=sp(18), halign="right",
                                  bold=True, size_hint_y=None, height=dp(46))
        root.add_widget(self.y_total)
        return root

    def _year_prev(self):
        self.y_year -= 1
        self.refresh_year()

    def _year_next(self):
        self.y_year += 1
        self.refresh_year()

    def _on_tab_switch(self, _panel, tab):
        if tab is self.tab_month:
            self.refresh_month()
        elif tab is self.tab_year:
            self.refresh_year()

    # ---- Refresh ----------------------------------------------------------
    def refresh_all(self):
        self.refresh_subs_list()
        self.refresh_month()
        self.refresh_year()

    def refresh_subs_list(self):
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

            card = SubCard(
                s["name"],
                f"{s['price_usd']:.2f} {cur}",
                s["frequency"],
                s["card"],
                secondary,
            )
            card.bind(on_release=partial(self._edit_clicked, s["id"]))
            self.subs_list.add_widget(card)

    def _edit_clicked(self, sub_id, *_):
        sub = logic.get_subscription(sub_id)
        if sub:
            self._open_popup(sub)

    def refresh_month(self):
        y, m = self.view_year, self.view_month
        self.month_label.text = f"{calendar.month_name[m]}  {y}"
        self.m_list.clear_widgets()

        cur = logic.get_primary_currency()
        total = 0.0
        sec_totals = {}
        rows = []
        for s in logic.get_all_subscriptions():
            for d in logic.occurrences_in_month(s, y, m):
                total += s["price_usd"]
                sec = ""
                if s["secondary_amount"] is not None:
                    sc = s["secondary_currency"] or ""
                    sec = f"{s['secondary_amount']:.2f} {sc}".strip()
                    sec_totals[sc] = sec_totals.get(sc, 0) + \
                        s["secondary_amount"]
                rows.append((d, s["name"], s["price_usd"], sec))

        for d, name, amt, sec in sorted(rows, key=lambda r: r[0]):
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4),
                            padding=[dp(6), 0])
            row.add_widget(make_label(d.strftime("%b %d"), size_hint_x=0.22))
            row.add_widget(make_label(name, size_hint_x=0.38))
            row.add_widget(make_label(f"{amt:.2f} {cur}", size_hint_x=0.22))
            row.add_widget(make_label(sec, size_hint_x=0.18))
            self.m_list.add_widget(row)

        label = f"Total:  {total:.2f} {cur}"
        extra = _fmt_group(sec_totals)
        if extra:
            label += f"   (+ {extra})"
        self.m_total.text = label

    def refresh_year(self):
        y = self.y_year
        self.year_label.text = str(y)
        self.y_list.clear_widgets()
        subs = logic.get_all_subscriptions()
        cur = logic.get_primary_currency()
        grand = 0.0

        hdr = BoxLayout(spacing=dp(4), padding=[dp(6), 0])
        for txt, hint in (("Month", 0.42), ("Payments", 0.22),
                          ("Amount", 0.36)):
            hdr.add_widget(make_label(f"[b]{txt}[/b]", markup=True,
                                      size_hint_x=hint))
        self.y_list.add_widget(hdr)

        for mo in range(1, 13):
            m_total = 0.0
            count = 0
            for s in subs:
                for _ in logic.occurrences_in_month(s, y, mo):
                    m_total += s["price_usd"]
                    count += 1
            grand += m_total

            row = BoxLayout(spacing=dp(4), padding=[dp(6), 0])
            row.add_widget(make_label(calendar.month_name[mo],
                                      size_hint_x=0.42))
            row.add_widget(make_label(str(count), size_hint_x=0.22))
            row.add_widget(make_label(f"{m_total:.2f} {cur}",
                                      size_hint_x=0.36))
            self.y_list.add_widget(row)

        self.y_total.text = f"Year total:  {grand:.2f} {cur}"


if __name__ == "__main__":
    SubscriptionApp().run()
