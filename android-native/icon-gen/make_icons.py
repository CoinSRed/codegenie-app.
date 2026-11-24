"""
Generates the PORTX Game Launcher app icon:
 - a transparent foreground glyph (the "P" mark, same as the in-app brand
   mark) for the adaptive icon
 - legacy + round launcher PNGs at the five standard mipmap densities
 - a 512x512 store listing icon

Run once with `python3 make_icons.py`; output lands in ./out/.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)

BG_TOP = (79, 141, 255)      # --blue-glow
BG_BOTTOM = (27, 63, 196)    # darker blue, matches .brand-mark gradient
BG_SOLID = (16, 24, 43)      # adaptive icon background color (navy)
FG_WHITE = (233, 237, 246)   # --text

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

MIPMAP_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

FOREGROUND_SIZE = 432  # adaptive icon canvas (108dp @ xxxhdpi)
SAFE_ZONE_RATIO = 0.66  # keep glyph inside the ~66dp safe circle


def vertical_gradient(size, top, bottom):
    img = Image.new("RGB", (1, size), color=0)
    for y in range(size):
        t = y / max(1, size - 1)
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        img.putpixel((0, y), (r, g, b))
    return img.resize((size, size))


def rounded_mask(size, radius_ratio=0.22):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255)
    return mask


def circle_mask(size):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([0, 0, size - 1, size - 1], fill=255)
    return mask


def draw_p_glyph(size, color, scale=0.56):
    """Draws a bold 'P' centered on a transparent canvas of `size`x`size`."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font_size = int(size * scale)
    font = ImageFont.truetype(FONT_PATH, font_size)
    text = "P"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1])
    draw.text(pos, text, font=font, fill=color)
    return layer


def make_square_icon(size):
    bg = vertical_gradient(size, BG_TOP, BG_BOTTOM).convert("RGBA")
    glyph = draw_p_glyph(size, FG_WHITE + (255,), scale=0.56)
    bg.alpha_composite(glyph)
    return bg


def main():
    # 1. Adaptive icon foreground (transparent, glyph only, kept inside safe zone)
    fg = Image.new("RGBA", (FOREGROUND_SIZE, FOREGROUND_SIZE), (0, 0, 0, 0))
    glyph_size = int(FOREGROUND_SIZE * SAFE_ZONE_RATIO)
    glyph = draw_p_glyph(glyph_size, FG_WHITE + (255,), scale=0.62)
    offset = (FOREGROUND_SIZE - glyph_size) // 2
    fg.alpha_composite(glyph, (offset, offset))
    fg.save(os.path.join(OUT, "ic_launcher_foreground.png"))

    # 2. Legacy + round icons per density
    for density, px in MIPMAP_SIZES.items():
        square = make_square_icon(px)

        legacy = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        legacy.paste(square, (0, 0), rounded_mask(px, 0.18))
        legacy.save(os.path.join(OUT, f"ic_launcher_{density}.png"))

        round_icon = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        round_icon.paste(square, (0, 0), circle_mask(px))
        round_icon.save(os.path.join(OUT, f"ic_launcher_round_{density}.png"))

    # 3. Play Store / promo icon (512x512, flat square, no transparency)
    store = make_square_icon(512).convert("RGB")
    store.save(os.path.join(OUT, "play_store_icon_512.png"))

    print("Done. Files written to", OUT)


if __name__ == "__main__":
    main()
