"""
Sizing constants, colours, and tiny pure-data helpers shared across the
whole app. No widget classes here — just numbers and lookups — so any
other module can import this without dragging in Kivy graphics code.
"""

from kivy.metrics import dp, sp

# ---- Sizing -----------------------------------------------------------------
FS = sp(17)
CARD_H = dp(124)             # height of a subscription card
BTN_H = dp(54)
INPUT_H = dp(46)
PADX = dp(10)
NAV_BTN_W = dp(56)
ICON_BTN_W = dp(50)

# ---- Colours ------------------------------------------------------------
# Brand accent — a vivid purple/indigo, Trackizer-style, used for the tab
# bar, hero card and interactive highlights instead of the old flat blue.
BRAND = (0.45, 0.35, 0.88, 1)
BRAND_DARK = (0.30, 0.22, 0.62, 1)
TOTAL_BG = (0.30, 0.30, 0.34, 1)     # light-neutral card for totals
GREEN = (0.18, 0.62, 0.34, 1)
BLUE = (0.20, 0.45, 0.70, 1)
RED = (0.74, 0.25, 0.25, 1)
NEUTRAL = (0.24, 0.24, 0.29, 1)
WHITE = (0.95, 0.95, 0.95, 1)
TAB_ACTIVE = BRAND
TAB_INACTIVE = (0.09, 0.09, 0.12, 1)
TAB_TEXT_ACTIVE = (1, 1, 1, 1)
TAB_TEXT_INACTIVE = (0.55, 0.55, 0.60, 1)

# Near-black app background (was a lighter charcoal) — Trackizer-style,
# with cards/sheets a couple shades up from it (CARD_BG/POPUP_BG) so they
# still read as distinct surfaces.
WINDOW_BG = (0.045, 0.045, 0.06, 1)
CARD_BG = (0.15, 0.15, 0.19, 1)
POPUP_BG = (0.10, 0.10, 0.13, 1)

# form-field colours, used by widgets.make_input/modern_spinner
FIELD = CARD_BG
ACCENT = BRAND

# One fixed colour per category, used for tags, cards, and the pie chart.
CATEGORY_COLORS = {
    "Entertainment": (0.85, 0.45, 0.20, 1),
    "Essentials": (0.20, 0.55, 0.75, 1),
    "Productivity": (0.30, 0.65, 0.45, 1),
    "Quality of Life": (0.60, 0.45, 0.80, 1),
    "Streaming": (0.80, 0.25, 0.45, 1),
    "Random": (0.75, 0.70, 0.20, 1),
    "Other": (0.55, 0.55, 0.58, 1),
}


def category_color(name):
    return CATEGORY_COLORS.get(name, CATEGORY_COLORS["Other"])


# Muted, desaturated tones instead of the bright per-category accents —
# every bank-card reads as brushed metal, cycled by name/category so
# neighbouring cards in the carousel still look distinct.
METALLIC_PALETTE = [
    (0.58, 0.59, 0.63, 1),   # silver
    (0.33, 0.34, 0.38, 1),   # gunmetal
    (0.64, 0.58, 0.42, 1),   # champagne gold
    (0.44, 0.46, 0.50, 1),   # steel
    (0.40, 0.35, 0.38, 1),   # rose gunmetal
    (0.30, 0.36, 0.40, 1),   # slate
]


def metallic_color(seed):
    return METALLIC_PALETTE[hash(seed or "") % len(METALLIC_PALETTE)]
