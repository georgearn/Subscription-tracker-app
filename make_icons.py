"""
Generate Android adaptive-icon assets for the Subscription Tracker.

Foreground: icon_source.svg (white wallet-with-alert), kept inside the
adaptive safe zone. Background: solid #101c31.

Outputs (in ./data):
  icon_background.png  - full-bleed #101c31 (adaptive background layer)
  icon_foreground.png  - transparent, white icon within the safe zone
  icon_monochrome.png  - white silhouette on transparent (themed icon)
  icon.png             - 512px legacy composite for pre-API-26 launchers
"""

import io
import os
import math
import cairosvg
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

SVG = os.path.join(HERE, "icon_source.svg")

SIZE = 432                      # adaptive layer size (108dp @ xxxhdpi)
# Adaptive icon geometry: the 108dp layer is cropped to a 72dp visible
# area, and only the central 66dp circle is guaranteed unclipped.
VISIBLE_D = SIZE * 72 / 108     # 288 px
SAFE_D = SIZE * 66 / 108        # 264 px
BG = (16, 28, 49)               # #101c31


def render_foreground():
    """White icon centered, sized so it can never be clipped by a mask.

    The content's *diagonal* is fitted to the safe-zone circle, so the
    corners stay inside the circle rather than poking out of it.
    """
    png = cairosvg.svg2png(url=SVG, output_width=1024, output_height=1024)
    icon = Image.open(io.BytesIO(png)).convert("RGBA")
    icon = icon.crop(icon.getbbox())            # trim transparent margins

    w, h = icon.size
    diagonal = math.hypot(w, h)
    scale = SAFE_D / diagonal
    icon = icon.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                       Image.LANCZOS)

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(icon, ((SIZE - icon.width) // 2,
                                  (SIZE - icon.height) // 2))
    return canvas


def make_background():
    return Image.new("RGB", (SIZE, SIZE), BG)


def make_legacy(background, foreground):
    """Composite + rounded corners for old launchers."""
    base = background.convert("RGBA")
    base.alpha_composite(foreground)
    base = base.resize((512, 512), Image.LANCZOS)
    mask = Image.new("L", (512, 512), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 511, 511], radius=96,
                                           fill=255)
    out = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def main():
    fg = render_foreground()
    bg = make_background()

    fg.save(os.path.join(OUT, "icon_foreground.png"))
    fg.save(os.path.join(OUT, "icon_monochrome.png"))   # white silhouette
    bg.save(os.path.join(OUT, "icon_background.png"))
    make_legacy(bg, fg).save(os.path.join(OUT, "icon.png"))
    print("Generated:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
