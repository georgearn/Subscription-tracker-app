"""
Generic, reusable UI building blocks — a rounded flat button, a styled
text input, a rounded-corner row background, and the like. Nothing in
here knows about subscriptions, cards, or categories; they're just the
app's visual vocabulary, used everywhere from the tab bar to the popups.
"""

from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle

from theme import (WHITE, NEUTRAL, GREEN, CARD_BG, FIELD, ACCENT, FS, BTN_H,
                   INPUT_H, NAV_BTN_W)


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


class ColorSwatch(Widget):
    """Small rounded square used as a legend marker. Superseded by icons
    everywhere it used to appear, but kept around unused rather than
    deleted during a pure reorganisation."""

    def __init__(self, color=(1, 1, 1, 1), **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(16), dp(16)))
        super().__init__(**kwargs)
        with self.canvas:
            Color(*color)
            self._rect = RoundedRectangle(radius=[dp(3)])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class RowCard(BoxLayout):
    """Rounded-corner row background, the same visual language as the
    subscription cards, reused for list rows on the Overview/Analytics
    tabs instead of plain unstyled BoxLayout rows."""

    def __init__(self, bg=CARD_BG, radius=10, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg)
            self._bg = RoundedRectangle(radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


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
    sp_.background_color = (0, 0, 0, 0)
    sp_.color = WHITE
    sp_.option_cls = FlatOption
    with sp_.canvas.before:
        Color(*FIELD)
        bg_rect = RoundedRectangle()

    def sync(*_):
        bg_rect.pos = sp_.pos
        bg_rect.size = sp_.size
        bg_rect.radius = [min(sp_.width, sp_.height) / 2]

    sp_.bind(pos=sync, size=sync)
    sync()
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


def flat_button(text, bg=NEUTRAL, radius=dp(14), **kwargs):
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", BTN_H)
    kwargs.setdefault("font_size", FS)
    b = Button(text=text, **kwargs)
    b.background_normal = ""
    b.background_down = ""
    b.background_color = (0, 0, 0, 0)
    b.border = (0, 0, 0, 0)
    b.color = WHITE
    with b.canvas.before:
        bg_color = Color(*bg)
        bg_rect = RoundedRectangle(radius=[radius])

    def sync(*_):
        bg_rect.pos = b.pos
        bg_rect.size = b.size

    b.bind(pos=sync, size=sync)

    def set_bg(color):
        # Button.background_color is left permanently transparent; changing
        # it (instead of this) revives Kivy's own square backdrop under our
        # rounded overlay and its corners peek out, squaring the button off.
        bg_color.rgba = color

    b.set_bg = set_bg
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


class Chevron(Widget):
    """Small down-pointing chevron, drawn on canvas instead of a unicode
    glyph — some devices lack the glyph in their font and render it as a
    missing-character box (this bit us with U+2304 in the month pill)."""

    def __init__(self, color=WHITE, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(10), dp(6)))
        super().__init__(**kwargs)
        self._color = color
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        with self.canvas:
            Color(*self._color)
            Line(points=[x, y + h, x + w / 2, y, x + w, y + h],
                width=dp(1.6), cap="round", joint="round")


class PillButton(ButtonBehavior, BoxLayout):
    """Rounded pill button that can hold a label plus a trailing chevron —
    flat_button can only show plain text, and Kivy Buttons can't take
    child widgets, so the month-picker pill needs its own composite."""

    def __init__(self, text, bg=NEUTRAL, radius=dp(18), **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        super().__init__(**kwargs)
        with self.canvas.before:
            bg_color = Color(*bg)
            bg_rect = RoundedRectangle(radius=[radius])

        def sync(*_):
            bg_rect.pos = self.pos
            bg_rect.size = self.size

        self.bind(pos=sync, size=sync)

        def set_bg(color):
            bg_color.rgba = color

        self.set_bg = set_bg

        # label + chevron as one fixed-size unit, anchored to the pill's
        # centre, instead of packed directly in self as flexible BoxLayout
        # children — that left the chevron bottom-aligned (its own fixed
        # height, no size_hint_y, so the BoxLayout never centred it on the
        # cross axis) and the label's centred text floating away from it.
        anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        unit = BoxLayout(orientation="horizontal", size_hint=(None, None),
                         height=dp(20), spacing=dp(6))
        self.label = make_label(text, font_size=FS, halign="center",
                                bold=True, size_hint=(None, None),
                                size=(dp(46), dp(20)))
        chevron = Chevron()
        unit.add_widget(self.label)
        unit.add_widget(chevron)
        unit.width = self.label.width + dp(6) + chevron.width
        anchor.add_widget(unit)
        self.add_widget(anchor)
