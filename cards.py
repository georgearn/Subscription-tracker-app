"""
The subscription-domain composite widgets: a single subscription row, the
bank-card visuals for the 'By Card' carousel, the schedule strip and its
day/occurrence cards, and the category spend gauge/bars. Everything here
is specific to this app (unlike widgets.py, which is generic chrome).
"""

from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle

from theme import BRAND, CARD_BG, RED, WHITE, category_color, metallic_color
from icons import ServiceIcon
from widgets import make_label


class TapArea(ButtonBehavior, AnchorLayout):
    """Invisible tappable wrapper around a single child widget — used
    where a plain Label needs to become tappable (e.g. the card alias)
    without turning it into a full flat_button."""


class SubRow(ButtonBehavior, BoxLayout):
    """One subscription per line: icon, name/meta, price — tap to edit."""

    def __init__(self, name, amount, freq, card, secondary, category=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.padding = [dp(14), dp(8)]
        self.spacing = dp(12)
        self.size_hint_y = None
        self.height = dp(68)

        with self.canvas.before:
            Color(*CARD_BG)
            self._bg = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.add_widget(ServiceIcon(
            name, category_color(category or "Other"),
            size=(dp(42), dp(42))))

        mid = BoxLayout(orientation="vertical", spacing=dp(2))
        mid.add_widget(make_label(name, bold=True, font_size=sp(15),
                                  shorten=True, shorten_from="right",
                                  size_hint_y=None, height=dp(20)))
        meta = f"{freq}  ·  Card {card}" if card else freq
        if secondary:
            meta = f"{meta}  ·  {secondary}"
        mid.add_widget(make_label(meta, font_size=sp(12), shorten=True,
                                  color=(0.62, 0.62, 0.68, 1),
                                  size_hint_y=None, height=dp(16)))
        self.add_widget(mid)

        self.add_widget(make_label(amount, font_size=sp(15), bold=True,
                                   halign="right", size_hint_x=None,
                                   width=dp(92)))

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class CardNetworkMark(Widget):
    """Two overlapping circles, Mastercard-style — a generic 'this is a
    payment card' glyph. Purely decorative, not tied to a real network
    since the app doesn't know which one was used."""

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(52), dp(32)))
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        d = h
        with self.canvas:
            Color(0.89, 0.24, 0.22, 0.92)
            Ellipse(pos=(x, y), size=(d, d))
            Color(0.96, 0.62, 0.13, 0.92)
            Ellipse(pos=(x + w - d, y), size=(d, d))


class CardGroupCard(BoxLayout):
    """One physical card as a vertical, metallic bank-card — network mark,
    'Virtual Card' label, masked digits and chip — swiped through in the
    'By Card' analytics carousel. The subscriptions billed to it are shown
    underneath as an icon row rather than on the card face."""

    CARD_W = dp(300)
    CARD_H = dp(400)

    def __init__(self, last4, total_text, subs, cur, alias=None,
                 on_rename=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.size = (self.CARD_W, self.CARD_H)
        self.padding = [dp(26), dp(24)]
        self.spacing = dp(6)

        base = metallic_color(last4)
        highlight = tuple(min(1.0, c * 1.6 + 0.15) for c in base[:3]) + (0.9,)
        shadow = tuple(c * 0.45 for c in base[:3]) + (1,)
        with self.canvas.before:
            Color(*base)
            self._bg = RoundedRectangle(radius=[dp(32)])
            # faint diagonal sheen, redrawn on resize, gives the flat
            # rounded rect a brushed-metal highlight instead of a block
            # of flat colour
            Color(1, 1, 1, 0.09)
            self._sheen = Line(width=dp(44), cap="round")
            # metallic accent frame: a bright inset line plus a darker
            # outer line give the edge a beveled, brushed-metal look
            # instead of the old single thin outline
            Color(*shadow)
            self._edge = Line(width=dp(1.6))
            Color(*highlight)
            self._edge_hi = Line(width=dp(1.2))
        self.bind(pos=self._sync_bg, size=self._sync_bg)
        # this card sits at a fixed pos in an unmanaged RelativeLayout, so
        # unlike widgets a BoxLayout/GridLayout re-positions later, nothing
        # will ever re-trigger the bind above — sync once now, or the edge
        # Lines (which have no geometry until rounded_rectangle is set)
        # never draw at all and the bg stays at its instruction default.
        self._sync_bg()

        mark_row = AnchorLayout(size_hint_y=None, height=dp(32))
        mark_row.add_widget(CardNetworkMark())
        self.add_widget(mark_row)

        alias_btn = TapArea(size_hint_y=None, height=dp(20))
        alias_btn.add_widget(make_label(
            alias or "Virtual Card  ·  tap to rename", font_size=sp(13),
            halign="center", color=(1, 1, 1, 0.7)))
        if on_rename:
            alias_btn.bind(on_release=lambda *_: on_rename(last4))
        self.add_widget(alias_btn)

        self.add_widget(Widget())  # flexible spacer, pushes number to mid

        number = ("••••  ••••  ••••  " + last4) if last4 and last4 != "No card" \
            else "No card linked"
        self.add_widget(make_label(number, font_size=sp(20), bold=True,
                                   halign="center", color=WHITE,
                                   size_hint_y=None, height=dp(28)))

        self.add_widget(Widget())  # flexible spacer, pushes chip down

        totals_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        totals_row.add_widget(make_label("Yearly", font_size=sp(12),
                                         color=(1, 1, 1, 0.6)))
        totals_row.add_widget(make_label(total_text, font_size=sp(15),
                                         bold=True, halign="right",
                                         color=WHITE))
        self.add_widget(totals_row)

        chip_row = BoxLayout(size_hint_y=None, height=dp(22))
        chip = Widget(size_hint=(None, None), size=(dp(32), dp(22)))
        with chip.canvas:
            Color(0.86, 0.72, 0.36, 1)
            chip_rect = RoundedRectangle(radius=[dp(4)])

        def sync_chip(*_):
            chip_rect.pos = chip.pos
            chip_rect.size = chip.size

        chip.bind(pos=sync_chip, size=sync_chip)
        sync_chip()
        chip_row.add_widget(chip)
        chip_row.add_widget(Widget())
        self.add_widget(chip_row)

    def _sync_bg(self, *_):
        x, y = self.pos
        w, h = self.size
        self._bg.pos = (x, y)
        self._bg.size = (w, h)
        self._edge.rounded_rectangle = (x, y, w, h, dp(32))
        self._edge_hi.rounded_rectangle = (x + dp(2), y + dp(2),
                                           w - dp(4), h - dp(4), dp(29))
        self._sheen.points = [x + w * 0.12, y + h * 1.05,
                              x + w * 0.5, y - h * 0.05]


class CardPeek(Widget):
    """A faint, slightly offset rounded rect behind the front card, so the
    stack reads as 'more cards behind this one' like a real wallet."""

    def __init__(self, color, **kwargs):
        super().__init__(**kwargs)
        self._color = color
        self.bind(pos=self._redraw, size=self._redraw)
        # same fixed-pos-in-RelativeLayout issue as CardGroupCard: nothing
        # re-triggers this bind later, so draw once now or it stays blank.
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self._color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(32)])


class DayCell(ButtonBehavior, BoxLayout):
    """One day in the horizontal schedule strip: day number, weekday
    abbreviation, and a dot if a subscription is due that day. A selected
    day gets the brand fill; today (when not selected) gets a thin brand
    ring instead so both states stay visible at once. Tappable — filters
    the schedule list below to that day's occurrences only."""

    def __init__(self, day_num, weekday_abbr, is_today=False,
                 is_selected=False, has_due=False, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(50), dp(74)))
        super().__init__(orientation="vertical", **kwargs)
        bg = BRAND if is_selected else CARD_BG
        with self.canvas.before:
            Color(*bg)
            self._bg = RoundedRectangle(radius=[dp(16)])
            if is_today and not is_selected:
                Color(*BRAND)
                self._ring = Line(rounded_rectangle=(0, 0, 1, 1, dp(16)),
                                  width=dp(1.4))
            else:
                self._ring = None
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        num_color = WHITE
        wd_color = (1, 1, 1, 0.75) if is_selected else (0.6, 0.6, 0.66, 1)
        self.add_widget(Widget(size_hint_y=None, height=dp(8)))
        self.add_widget(make_label(str(day_num), bold=True, font_size=sp(16),
                                   halign="center", color=num_color,
                                   size_hint_y=None, height=dp(22)))
        self.add_widget(make_label(weekday_abbr, font_size=sp(11),
                                   halign="center", color=wd_color,
                                   size_hint_y=None, height=dp(16)))
        if has_due:
            dot = Widget(size_hint=(None, None), size=(dp(5), dp(5)),
                        pos_hint={"center_x": 0.5})
            with dot.canvas:
                Color(1, 1, 1, 0.9) if is_selected else Color(*RED)
                dot_ellipse = Ellipse(pos=dot.pos, size=dot.size)

            def _sync_dot(*_):
                dot_ellipse.pos = dot.pos
                dot_ellipse.size = dot.size

            dot.bind(pos=_sync_dot, size=_sync_dot)
            self.add_widget(dot)
        else:
            self.add_widget(Widget(size_hint_y=None, height=dp(5)))
        self.add_widget(Widget(size_hint_y=None, height=dp(6)))

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        if self._ring is not None:
            x, y = self.pos
            w, h = self.size
            self._ring.rounded_rectangle = (x + 1, y + 1, w - 2, h - 2,
                                            dp(16))


class MonthSubCard(BoxLayout):
    """One occurrence in the month's schedule grid: icon, name, price —
    the 2-column card grid from the reference instead of a flat row."""

    def __init__(self, name, amount, category, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8),
                         padding=[dp(14), dp(14)], **kwargs)
        with self.canvas.before:
            Color(*CARD_BG)
            self._bg = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.add_widget(ServiceIcon(name, category_color(category or "Other"),
                                    shape="square", size=(dp(44), dp(44)),
                                    size_hint=(None, None)))
        self.add_widget(Widget())
        self.add_widget(make_label(name, bold=True, font_size=sp(14),
                                   shorten=True, size_hint_y=None,
                                   height=dp(18)))
        self.add_widget(make_label(amount, bold=True, font_size=sp(15),
                                   size_hint_y=None, height=dp(20)))

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class PieChart(Widget):
    """Simple pie chart drawn with Ellipse angle slices, no dependencies.
    Superseded by ArcGauge in the category panel, but kept around unused
    rather than deleted during a pure reorganisation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = []  # [(label, value, color), ...]
        self.bind(pos=self._redraw, size=self._redraw)

    def set_data(self, data):
        self.data = data
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        total = sum(v for _, v, _ in self.data)
        if total <= 0:
            return
        x, y = self.pos
        w, h = self.size
        d = min(w, h) * 0.86
        cx, cy = x + w / 2, y + h / 2
        with self.canvas:
            start = 0.0
            for _label, value, color in self.data:
                end = start + (value / total) * 360.0
                Color(*color)
                Ellipse(pos=(cx - d / 2, cy - d / 2), size=(d, d),
                       angle_start=start, angle_end=end)
                start = end


class ArcGauge(Widget):
    """Half-circle ring split into coloured arcs, one per category, sized
    by that category's share of total spend — the reference's budget gauge
    without the budget: no target value, the ring always reads 100% of
    what you actually spend, split proportionally by category."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = []  # [(label, value, color), ...]
        self.bind(pos=self._redraw, size=self._redraw)

    def set_data(self, data):
        self.data = data
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        # the round line cap sticks out lw/2 past the arc's radius on every
        # side (both flat ends plus the very top) — sized for a provisional
        # radius first, then the radius is shrunk to leave room for that
        # stroke so the whole gauge stays inside the widget's own bounds.
        r0 = min(w / 2 - dp(6), h - dp(18))
        if r0 <= 0:
            return
        lw = max(dp(8), r0 * 0.16)
        # cy sits lw/2 + a small gap above the bottom edge, so the arc's
        # top (cy + r + lw/2) must stay <= h, and half-width must stay
        # inside the widget on both left and right of centre.
        r = min(w / 2 - lw / 2, h - lw - dp(4))
        if r <= 0:
            return
        lw = max(dp(8), r * 0.16)
        r = min(r, w / 2 - lw / 2, h - lw - dp(4))
        if r <= 0:
            return
        cx, cy = x + w / 2, y + lw / 2 + dp(4)

        total = sum(v for _, v, _ in self.data)
        with self.canvas:
            Color(0.22, 0.22, 0.27, 1)
            # Kivy's Line(circle=...) angles are clock-style — 0=12 o'clock,
            # 90=3 o'clock, clockwise — not the standard math convention.
            # -90..90 sweeps left -> top -> right: a proper upper semicircle,
            # not the 0..180 top->right quarter (a lopsided "rising moon")
            # this used to draw.
            Line(circle=(cx, cy, r, -90, 90), width=lw, cap="round")
            if total > 0:
                # left-to-right across the top: first category starts at
                # the 9-o'clock end (-90°) and each slice eats into the
                # remaining sweep toward the 3-o'clock end (90°)
                angle = -90.0
                for _label, value, color in self.data:
                    sweep = (value / total) * 180.0
                    Color(*color)
                    Line(circle=(cx, cy, r, angle, angle + sweep),
                        width=lw, cap="round")
                    angle += sweep


class CategoryBar(BoxLayout):
    """One category row: icon, name and its share of total spend, amount,
    and a proportional progress bar — the reference's per-category row
    without a budget: the bar is that category's share of what you
    actually spend, not progress toward a limit you haven't set."""

    def __init__(self, name, amount_text, share, color, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(78))
        super().__init__(orientation="vertical", spacing=dp(8),
                         padding=[dp(14), dp(12)], **kwargs)
        with self.canvas.before:
            Color(*CARD_BG)
            self._bg = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        top = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        top.add_widget(ServiceIcon(name, color, size=(dp(36), dp(36)),
                                   size_hint=(None, None)))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(make_label(name, bold=True, font_size=sp(14),
                                  shorten=True, size_hint_y=None,
                                  height=dp(18)))
        mid.add_widget(make_label(f"{share:.0f}% of total spend",
                                  font_size=sp(11),
                                  color=(0.6, 0.6, 0.65, 1),
                                  size_hint_y=None, height=dp(16)))
        top.add_widget(mid)
        top.add_widget(make_label(amount_text, bold=True, font_size=sp(15),
                                  halign="right", size_hint_x=None,
                                  width=dp(84)))
        self.add_widget(top)

        track = Widget(size_hint_y=None, height=dp(6))
        with track.canvas:
            Color(0.24, 0.24, 0.29, 1)
            track_rect = RoundedRectangle(radius=[dp(3)])
            Color(*color)
            fill_rect = RoundedRectangle(radius=[dp(3)])

        def _sync_track(*_):
            track_rect.pos = track.pos
            track_rect.size = track.size
            fill_w = track.width * max(0.0, min(1.0, share / 100))
            fill_rect.pos = track.pos
            fill_rect.size = (fill_w, track.height)

        track.bind(pos=_sync_track, size=_sync_track)
        self.add_widget(track)

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
