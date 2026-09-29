"""
Everything to do with drawing or loading an icon: the hand-drawn vector
glyph vocabulary (no font/image dependency, so it always renders), the
bottom-tab icon loader, and the per-service brand-logo system (real PNG
logos when bundled in res/icons, hand-drawn fallback otherwise).
"""

import os
import math

from kivy.metrics import dp, sp
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Line, Ellipse, Rectangle, RoundedRectangle, \
    Triangle
from kivy.clock import Clock

from theme import WHITE, NEUTRAL, TAB_TEXT_ACTIVE, TAB_TEXT_INACTIVE


# ---- Vector-icon button (no font dependency) --------------------------------
class IconButton(Button):
    """A flat coloured button that draws its icon as vector graphics."""

    def __init__(self, icon="", icon_color=WHITE, bg=NEUTRAL, **kwargs):
        super().__init__(**kwargs)
        self.text = ""
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.border = (0, 0, 0, 0)
        self._icon = icon
        self._icon_color = icon_color
        with self.canvas.before:
            Color(*bg)
            self._bg_rect = RoundedRectangle()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.after.clear()
        x, y = self.pos
        w, h = self.size
        self._bg_rect.pos = (x, y)
        self._bg_rect.size = (w, h)
        self._bg_rect.radius = [min(w, h) / 2]
        if not self._icon:
            return
        s = min(w, h) * 0.44
        r = s / 2
        cx, cy = x + w / 2, y + h / 2
        lw = max(dp(1.7), s * 0.10)
        with self.canvas.after:
            Color(*self._icon_color)
            draw_icon_shape(self._icon, cx, cy, r, lw)


def draw_icon_shape(icon, cx, cy, r, lw):
    """Draw one of the vector icon glyphs, centred at (cx, cy) with
    radius r and line width lw. Must be called inside a canvas context
    that already has its Color set. Shared by IconButton and the tab bar
    icons so there's one vocabulary of glyphs across the app."""
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
    elif icon == "swap":
        # two opposing arrows: import/export at a glance. Drawn thinner
        # and more compact than the other icons, which read fine bolder
        # but two adjacent thick arrowheads here just looked cluttered.
        thin = lw * 0.6
        rr = r * 0.8
        off = rr * 0.45
        Line(points=[cx - off, cy - rr * 0.55, cx - off, cy + rr * 0.5],
             width=thin, cap="round")
        Line(points=[cx - off - rr * 0.28, cy + rr * 0.1,
                     cx - off, cy + rr * 0.5,
                     cx - off + rr * 0.28, cy + rr * 0.1],
             width=thin, cap="round", joint="round")
        Line(points=[cx + off, cy + rr * 0.55, cx + off, cy - rr * 0.5],
             width=thin, cap="round")
        Line(points=[cx + off - rr * 0.28, cy - rr * 0.1,
                     cx + off, cy - rr * 0.5,
                     cx + off + rr * 0.28, cy - rr * 0.1],
             width=thin, cap="round", joint="round")
    elif icon == "list":
        # bulleted rows read more like a proper list glyph than bare
        # lines, and echo the app's own row-avatar dots
        dot_r = lw * 0.55
        for dy in (0.62, 0.0, -0.62):
            Ellipse(pos=(cx - r * 0.85 - dot_r, cy + dy * r - dot_r),
                    size=(dot_r * 2, dot_r * 2))
            Line(points=[cx - r * 0.5, cy + dy * r,
                         cx + r * 0.85, cy + dy * r],
                 width=lw, cap="round")
    elif icon == "chart":
        base = cy - r * 0.8
        for dx, hh in ((-r * 0.5, r * 0.9), (0, r * 1.55),
                      (r * 0.5, r * 1.2)):
            Line(points=[cx + dx, base, cx + dx, base + hh],
                 width=lw * 1.5, cap="round")
        # baseline ties the bars together into one glyph instead of
        # three floating strokes
        Line(points=[cx - r * 0.9, base, cx + r * 0.9, base],
             width=lw * 0.7, cap="round")
    elif icon == "down":
        Line(points=[cx - r * 0.75, cy + r * 0.3,
                     cx, cy - r * 0.3,
                     cx + r * 0.75, cy + r * 0.3],
             width=lw, cap="round", joint="round")


NAV_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "res", "nav_icons")
_nav_texture_cache = {}


def _get_nav_texture(icon):
    """Thin Lucide-style stroke icon for a bottom tab, lazily loaded from
    res/nav_icons/<icon>.png. Falls back to the hand-drawn glyph in
    draw_icon_shape if the file is missing."""
    if icon not in _nav_texture_cache:
        path = os.path.join(NAV_ICONS_DIR, f"{icon}.png")
        tex = None
        if os.path.exists(path):
            try:
                tex = CoreImage(path).texture
            except Exception:
                tex = None
        _nav_texture_cache[icon] = tex
    return _nav_texture_cache[icon]


def _add_tab_icon(tab, icon, small=False):
    """Draw a centred glyph in a bottom tab; icon only, no label text.
    Uses a real thin-stroke icon (nicer, more elegant than the old
    hand-drawn shapes) when its PNG is bundled, else the vector glyph.
    `small` shrinks the middle tab's icon, which sits right under the
    FAB overlapping the strip, so it stays visible instead of covered."""
    tab.text = ""

    def redraw(*_):
        tab.canvas.after.clear()
        color = TAB_TEXT_ACTIVE if tab.state == "down" else TAB_TEXT_INACTIVE
        cx = tab.center_x
        cy = tab.center_y
        tex = _get_nav_texture(icon)
        with tab.canvas.after:
            Color(*color)
            if tex is not None:
                s = dp(17) if small else dp(24)
                Rectangle(texture=tex, pos=(cx - s / 2, cy - s / 2),
                         size=(s, s))
            else:
                r = dp(9) if small else dp(13)
                draw_icon_shape(icon, cx, cy, r, max(dp(1.6), r * 0.22))

    tab.bind(pos=redraw, size=redraw, state=redraw)
    Clock.schedule_once(redraw, 0)


# ---- Per-service icon (no font/image dependency) -----------------------
# Recognised brands get a small vector glyph on their real brand colour;
# anything else falls back to Avatar's tinted-initial look, drawn the same
# way so both sit at identical sizes in lists.
SERVICE_BRAND_COLORS = {
    "spotify": (0.11, 0.73, 0.33, 1),
    "netflix": (0.70, 0.09, 0.13, 1),
    "youtube": (0.80, 0.12, 0.12, 1),
    "adobe": (0.78, 0.10, 0.10, 1),
    "amazon": (0.10, 0.10, 0.11, 1),
    "microsoft": (0.14, 0.14, 0.17, 1),
    "google": (0.14, 0.14, 0.17, 1),
    "telegram": (0.15, 0.62, 0.87, 1),
    "nordvpn": (0.14, 0.14, 0.22, 1),
    "claude": (0.82, 0.44, 0.30, 1),
    "hulu": (0.11, 0.83, 0.35, 1),
    "twitch": (0.40, 0.22, 0.75, 1),
    "dropbox": (0.0, 0.35, 0.87, 1),
    "expressvpn": (0.86, 0.20, 0.20, 1),
    "paypal": (0.0, 0.44, 0.73, 1),
    "playstation": (0.0, 0.32, 0.65, 1),
    "xbox": (0.06, 0.49, 0.06, 1),
    "steam": (0.09, 0.10, 0.13, 1),
    "notion": (0.12, 0.12, 0.13, 1),
    "zoom": (0.16, 0.49, 0.94, 1),
    "slack": (0.29, 0.08, 0.29, 1),
    "figma": (0.95, 0.31, 0.12, 1),
    "1password": (0.02, 0.45, 0.93, 1),
    "hbomax": (0.42, 0.12, 0.78, 1),
    "discord": (0.35, 0.40, 0.95, 1),
    "openai": (0.06, 0.64, 0.50, 1),
    "chatgpt": (0.06, 0.64, 0.50, 1),
    "grammarly": (0.08, 0.77, 0.60, 1),
    "canva": (0.0, 0.77, 0.80, 1),
    "github": (0.09, 0.09, 0.09, 1),
    "linkedin": (0.04, 0.40, 0.76, 1),
    "bitwarden": (0.09, 0.36, 0.86, 1),
    "lastpass": (0.83, 0.18, 0.18, 1),
    "protonvpn": (0.43, 0.29, 1.0, 1),
    "surfshark": (0.12, 0.75, 0.75, 1),
    "icloud": (0.21, 0.58, 0.95, 1),
    "applemusic": (0.98, 0.14, 0.24, 1),
    "wordpress": (0.13, 0.46, 0.61, 1),
    "soundcloud": (1.0, 0.33, 0.0, 1),
}


ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "res", "icons")
_icon_texture_cache = {}


def _get_icon_texture(brand):
    """Real logo PNG for a recognised brand, lazily loaded from
    res/icons/<brand>.png and cached (misses cached as None too, so a
    missing file is only checked once). Falls back to the hand-drawn
    glyph in _draw_service_glyph when there's no file — e.g. if this is
    running somewhere the res/icons folder wasn't copied."""
    if brand not in _icon_texture_cache:
        path = os.path.join(ICONS_DIR, f"{brand}.png")
        tex = None
        if os.path.exists(path):
            try:
                tex = CoreImage(path).texture
            except Exception:
                tex = None
        _icon_texture_cache[brand] = tex
    return _icon_texture_cache[brand]


def _service_key(name):
    """Match loosely: 'Nord VPN', 'YouTube Premium', 'Google One' all
    resolve to their brand even with extra words/spacing."""
    flat = "".join(ch for ch in (name or "").lower() if ch.isalnum())
    for key in SERVICE_BRAND_COLORS:
        if key in flat:
            return key
    return None


def _draw_service_glyph(brand, cx, cy, r, lw):
    if brand == "spotify":
        for dy, span in ((0.32, 0.75), (0.0, 0.9), (-0.32, 0.75)):
            Line(points=[cx - r * span, cy + dy * r, cx + r * span,
                        cy + dy * r], width=lw, cap="round")
    elif brand == "netflix":
        Line(points=[cx - r * 0.5, cy - r * 0.85, cx - r * 0.5, cy + r * 0.85],
             width=lw, cap="round")
        Line(points=[cx + r * 0.5, cy - r * 0.85, cx + r * 0.5, cy + r * 0.85],
             width=lw, cap="round")
        Line(points=[cx - r * 0.5, cy - r * 0.85, cx + r * 0.5, cy + r * 0.85],
             width=lw * 1.15, cap="round")
    elif brand == "youtube":
        Triangle(points=[cx - r * 0.42, cy + r * 0.62,
                         cx - r * 0.42, cy - r * 0.62,
                         cx + r * 0.68, cy])
    elif brand == "adobe":
        Line(points=[cx, cy + r * 0.9, cx - r * 0.8, cy - r * 0.75,
                     cx + r * 0.8, cy - r * 0.75, cx, cy + r * 0.9],
             width=lw, cap="round", joint="round")
    elif brand == "amazon":
        Line(points=[cx - r * 0.75, cy - r * 0.1, cx, cy - r * 0.5,
                     cx + r * 0.75, cy - r * 0.1],
             width=lw, cap="round", joint="round")
        Line(points=[cx + r * 0.55, cy - r * 0.28, cx + r * 0.78, cy - r * 0.1,
                     cx + r * 0.6, cy + r * 0.15],
             width=lw * 0.85, cap="round", joint="round")
    elif brand == "microsoft":
        s = r * 0.42
        gap = r * 0.12
        for (ox, oy), col in zip(
            [(-s - gap / 2, gap / 2), (gap / 2, gap / 2),
             (-s - gap / 2, -s - gap / 2), (gap / 2, -s - gap / 2)],
            [(0.96, 0.29, 0.16, 1), (0.32, 0.62, 0.14, 1),
             (0.0, 0.63, 0.9, 1), (1, 0.72, 0.0, 1)],
        ):
            Color(*col)
            Rectangle(pos=(cx + ox, cy + oy), size=(s, s))
    elif brand == "google":
        Line(circle=(cx, cy, r * 0.8), width=lw)
        Line(points=[cx, cy, cx + r * 0.85, cy], width=lw, cap="round")
    elif brand == "telegram":
        Triangle(points=[cx - r * 0.8, cy + r * 0.15,
                         cx + r * 0.8, cy + r * 0.65,
                         cx - r * 0.05, cy - r * 0.75])
        Line(points=[cx - r * 0.05, cy - r * 0.75, cx + r * 0.25, cy - r * 0.05],
             width=lw * 0.8, cap="round")


class ServiceIcon(Widget):
    """Circle avatar for a subscription: known brands get a small vector
    glyph on their real colour; everything else falls back to a
    category-tinted initial."""

    def __init__(self, name, fallback_color, shape="circle", **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(34), dp(34)))
        super().__init__(**kwargs)
        self._fallback_color = fallback_color
        self._shape = shape
        self._label = Label(bold=True, font_size=sp(15), color=WHITE)
        self.add_widget(self._label)
        self.bind(pos=self._redraw, size=self._redraw)
        self.set_name(name)

    def set_color(self, color):
        self._fallback_color = color
        self._redraw()

    def set_name(self, name):
        self._name = name or ""
        self._brand = _service_key(self._name)
        self._label.text = "" if self._brand else (self._name[:1] or "?").upper()
        self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        self.canvas.after.clear()
        x, y = self.pos
        w, h = self.size
        cx, cy = x + w / 2, y + h / 2
        self._label.font_size = max(sp(11), min(w, h) * 0.44)
        bg = SERVICE_BRAND_COLORS.get(self._brand, self._fallback_color)
        with self.canvas.before:
            Color(*bg)
            if self._shape == "square":
                RoundedRectangle(pos=(x, y), size=(w, h),
                                 radius=[min(w, h) * 0.28])
            else:
                Ellipse(pos=(x, y), size=(w, h))
        if self._brand:
            tex = _get_icon_texture(self._brand)
            with self.canvas.after:
                Color(1, 1, 1, 1)
                if tex is not None:
                    s = min(w, h) * 0.58
                    Rectangle(texture=tex, pos=(cx - s / 2, cy - s / 2),
                             size=(s, s))
                else:
                    r = min(w, h) * 0.30
                    lw = max(dp(1.4), r * 0.22)
                    _draw_service_glyph(self._brand, cx, cy, r, lw)
        self._label.pos = (x, y)
        self._label.size = (w, h)
