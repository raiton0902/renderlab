#!/usr/bin/env python
"""Render the Renderlab logo: a gradient R on a dark tile.

    python tools/make_logo.py

Writes 512x512 and 1024x1024 JPEGs into dist/ (gitignored) and a PNG for the
repo README (assets/logo.png).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
# Plus Jakarta Sans ExtraBold ships with the demo projects; fall back to any
# heavy sans that PIL can find.
CANDIDATES = [
    ROOT / "tools" / "fonts" / "R-heavy.ttf",
    Path(r"D:\akuvideo\lauraferry\_stylecopy\fonts\f1.ttf"),
]

ORANGE = (255, 106, 0)
YELLOW = (255, 209, 51)
BG_TOP = (24, 24, 26)
BG_BOTTOM = (12, 12, 13)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def load_font(size):
    for path in CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise SystemExit("no bold font found; put one at tools/fonts/R-heavy.ttf")


def make(size):
    # background: soft vertical gradient
    bg = Image.new("RGB", (size, size))
    px = bg.load()
    for y in range(size):
        row = lerp(BG_TOP, BG_BOTTOM, y / max(1, size - 1))
        for x in range(size):
            px[x, y] = row

    # glyph mask, sized to the tile
    target_h = int(size * 0.62)
    probe = 400
    font = load_font(probe)
    box = font.getbbox("R")
    ratio = target_h / (box[3] - box[1])
    font = load_font(max(10, int(probe * ratio)))

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    box = font.getbbox("R")
    w, h = box[2] - box[0], box[3] - box[1]
    x0 = (size - w) / 2 - box[0]
    y0 = (size - h) / 2 - box[1]
    md.text((x0, y0), "R", font=font, fill=255)

    # slight optical centring: the R sits a touch left of the box centre
    shift = int(size * 0.012)
    mask = mask.transform(mask.size, Image.AFFINE, (1, 0, shift, 0, 1, 0))

    # orange -> yellow swept across the glyph itself, so the whole ramp shows
    grad = Image.new("RGB", (size, size))
    gpx = grad.load()
    left, top = x0 + box[0], y0 + box[1]
    gw, gh = max(1.0, w), max(1.0, h)
    for y in range(size):
        ty = (y - top) / gh
        for x in range(size):
            tx = (x - left) / gw
            t = min(1.0, max(0.0, tx * 0.5 + ty * 0.5))
            gpx[x, y] = lerp(ORANGE, YELLOW, t)

    logo = Image.composite(grad, bg, mask)

    # quiet inner border so the tile reads as a tile on light backgrounds
    d = ImageDraw.Draw(logo)
    inset = int(size * 0.035)
    radius = int(size * 0.16)
    d.rounded_rectangle(
        [inset, inset, size - inset, size - inset],
        radius=radius,
        outline=(58, 58, 62),
        width=max(1, int(size * 0.004)),
    )
    return logo


def main():
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    for size in (1024, 512):
        img = make(size)
        out = dist / ("renderlab-logo-%d.jpg" % size)
        img.save(out, "JPEG", quality=93, optimize=True, subsampling=0, progressive=True)
        print("wrote %s" % out)
    png = make(512)
    png.save(ROOT / "assets" / "logo.png", "PNG", optimize=True)
    print("wrote %s" % (ROOT / "assets" / "logo.png"))


if __name__ == "__main__":
    main()


