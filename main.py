"""World news in one image: 26 November 2026.

Draws a 1024x1024 poster from news.json with nothing but the Python
standard library: the PNG is written by hand with struct and zlib, and
the type is a 5x7 bitmap font defined below.  No network, no clock, no
randomness, so the same input always produces the same bytes.

Usage:
    python3 main.py

Output goes to $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""

import json
import os
import struct
import sys
import zlib

W = 1024
H = 1024

BG = (0x0B, 0x12, 0x20)
WHITE = (0xFF, 0xFF, 0xFF)
MUTED = (0x9F, 0xB3, 0xC8)
ACCENT = (0x7C, 0xC4, 0xFF)
LIST_INK = (0xE8, 0xEE, 0xF5)
PANEL = (0x0F, 0x1A, 0x2B)
PANEL_EDGE = (0x2A, 0x3B, 0x55)
GRID_INK = (0x1F, 0x31, 0x50)
LAND = (0x3A, 0x55, 0x78)
COAST = (0x7C, 0x9C, 0xC4)
BADGE_INK = (0x0B, 0x12, 0x20)

REGION_ORDER = [
    "North America",
    "Latin America",
    "Europe",
    "Middle East",
    "Africa",
    "Asia",
    "Oceania",
    "Global",
]

REGION_COLOR = {
    "North America": (0x6B, 0x4F, 0xBB),
    "Latin America": (0x9A, 0x6B, 0x00),
    "Europe": (0x2F, 0x5F, 0xB3),
    "Middle East": (0xC2, 0x6A, 0x1B),
    "Africa": (0x2E, 0x8B, 0x57),
    "Asia": (0xB8, 0x3A, 0x3A),
    "Oceania": (0x1E, 0x8A, 0x9C),
    "Global": (0x5A, 0x6B, 0x7B),
}

HERO_X, HERO_Y, HERO_W, HERO_H = 12, 64, 500, 204
TILE_XS = (12, 263, 514, 765)
TILE_YS = (276, 410, 544)
TILE_W, TILE_H = 246, 128

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 524, 64, 488, 204
MAP_X0, MAP_Y0, MAP_X1, MAP_Y1 = 532, 88, 1004, 262
MAP_LAT_TOP, MAP_LAT_BOT = 75.0, -58.0

LIST_XS = (12, 348, 684)
LIST_Y0 = 704
LIST_PITCH = 40
LIST_COL_LEN = (8, 8, 7)

# Region names are too wide for a 246 px tile at the 14 px minimum type
# size, so tiles use these short forms; the hero has room for the full name.
SHORT_REGION = {
    "North America": "N AMERICA",
    "Latin America": "L AMERICA",
    "Europe": "EUROPE",
    "Middle East": "MID EAST",
    "Africa": "AFRICA",
    "Asia": "ASIA",
    "Oceania": "OCEANIA",
    "Global": "GLOBAL",
}

REGION_ABBR = {
    "North America": "NA",
    "Latin America": "LA",
    "Europe": "EU",
    "Middle East": "ME",
    "Africa": "AF",
    "Asia": "AS",
    "Oceania": "OC",
    "Global": "GL",
}

# Icon plates sit inside the hero and every tile.  The stat and region
# label stop short of the plate, so no text can land on the pictogram.
ICON_INSET = 8
ICON_HERO = 120
ICON_TILE = 56
HERO_ICON_X = HERO_X + HERO_W - ICON_INSET - ICON_HERO
HERO_ICON_Y = HERO_Y + ICON_INSET
HERO_STAT_W = HERO_ICON_X - 24 - 8
# A tile stat sits in the column left of the icon plate and may not run
# under it, so its width stops 8 px short of the plate.
TILE_STAT_W = TILE_W - ICON_INSET - ICON_TILE - 8 - 8

DEFAULT_ICON = {
    "climate": "waves",
    "conflict": "burst",
    "economy": "chart",
    "health": "cross",
    "politics": "flag",
    "science": "satellite",
    "sport": "chess",
    "tech": "satellite",
}

# 5x7 bitmap font.  Each glyph is seven rows; each row is five bits, the
# most significant bit being the leftmost column.  Text is drawn in upper
# case only, so there are no lower-case glyphs.
FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 14),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 17, 17, 17, 17),
    "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 17, 21, 27, 17),
    "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 12, 8),
    ":": (0, 12, 12, 0, 12, 12, 0),
    ";": (0, 12, 12, 0, 12, 12, 8),
    "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 2, 4, 0, 4),
    "'": (4, 4, 0, 0, 0, 0, 0),
    "-": (0, 0, 0, 31, 0, 0, 0),
    "+": (0, 4, 4, 31, 4, 4, 0),
    "%": (25, 26, 2, 4, 8, 19, 19),
    "$": (4, 15, 20, 14, 5, 30, 4),
    "&": (12, 18, 20, 8, 21, 18, 13),
    "/": (1, 1, 2, 4, 8, 16, 16),
    "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8),
    "#": (10, 10, 31, 10, 31, 10, 10),
}

def new_canvas():
    buf = bytearray(W * H * 3)
    r, g, b = BG
    for i in range(0, len(buf), 3):
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b
    return buf


def put(buf, x, y, color):
    if x < 0 or y < 0 or x >= W or y >= H:
        return
    i = (y * W + x) * 3
    buf[i] = color[0]
    buf[i + 1] = color[1]
    buf[i + 2] = color[2]


def fill_rect(buf, x, y, w, h, color):
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    r, g, b = color
    run = bytes((r, g, b)) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * W + x0) * 3
        buf[i:i + len(run)] = run


def stroke_rect(buf, x, y, w, h, color):
    fill_rect(buf, x, y, w, 1, color)
    fill_rect(buf, x, y + h - 1, w, 1, color)
    fill_rect(buf, x, y, 1, h, color)
    fill_rect(buf, x + w - 1, y, 1, h, color)


def fill_circle(buf, cx, cy, radius, color):
    rr = radius * radius
    for dy in range(-radius, radius + 1):
        span = int((rr - dy * dy) ** 0.5)
        fill_rect(buf, cx - span, cy + dy, span * 2 + 1, 1, color)


def fill_poly(buf, points, color, clip=None):
    """Scanline fill with the even-odd rule, optionally clipped."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    ytop = max(0, min(ys))
    ybot = min(H - 1, max(ys))
    if clip is not None:
        cx0, cy0, cx1, cy1 = clip
        ytop = max(ytop, cy0)
        ybot = min(ybot, cy1)
    n = len(points)
    for y in range(ytop, ybot + 1):
        sy = y + 0.5
        xs = []
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if y0 == y1:
                continue
            lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
            if lo <= sy < hi:
                xs.append(x0 + (sy - y0) * (x1 - x0) / (y1 - y0))
        if not xs:
            continue
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = int(xs[i] + 0.5)
            xb = int(xs[i + 1] + 0.5)
            if clip is not None:
                xa = max(xa, clip[0])
                xb = min(xb, clip[2])
            if xb > xa:
                fill_rect(buf, xa, y, xb - xa, 1, color)


def poly_outline(buf, points, color, clip=None):
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for s in range(steps + 1):
            x = int(x0 + (x1 - x0) * s / steps + 0.5)
            y = int(y0 + (y1 - y0) * s / steps + 0.5)
            if clip is not None:
                if x < clip[0] or x > clip[2] or y < clip[1] or y > clip[3]:
                    continue
            put(buf, x, y, color)


def text_width(s, scale):
    if not s:
        return 0
    return 6 * scale * len(s) - scale


def draw_text(buf, x, y, s, scale, color):
    """Draw upper-cased bitmap text; returns the advance width."""
    cx = x
    for ch in s.upper():
        glyph = FONT.get(ch)
        if glyph is None:
            return -1
        for row in range(7):
            bits = glyph[row]
            if not bits:
                continue
            for col in range(5):
                if bits & (1 << (4 - col)):
                    fill_rect(buf, cx + col * scale, y + row * scale,
                              scale, scale, color)
        cx += 6 * scale
    return cx - x


def wrap(text, scale, max_w, max_lines):
    """Greedy word wrap.  Returns a list of lines or None if it will not fit."""
    per_line = (max_w + scale) // (6 * scale)
    if per_line < 1:
        return None
    words = text.upper().split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for word in words[1:]:
        if len(cur) + 1 + len(word) <= per_line:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
            if len(lines) > max_lines:
                return None
    lines.append(cur)
    if len(lines) > max_lines:
        return None
    for line in lines:
        if len(line) > per_line:
            return None
    return lines


def fit_scale(text, max_w, start, floor):
    scale = start
    while scale > floor and text_width(text, scale) > max_w:
        scale -= 1
    return scale


def shade(color, f):
    return tuple(int(v * f) for v in color)


def tint(color, f):
    return tuple(int(v + (255 - v) * f) for v in color)


def stroke_circle(buf, cx, cy, r, thick, color, bg):
    fill_circle(buf, cx, cy, r, color)
    if r - thick >= 1:
        fill_circle(buf, cx, cy, r - thick, bg)


# Eight unit vectors, enough for radial shapes without importing math.
DIRS8 = ((1.0, 0.0), (0.707, 0.707), (0.0, 1.0), (-0.707, 0.707),
         (-1.0, 0.0), (-0.707, -0.707), (0.0, -1.0), (0.707, -0.707))

ICON_KINDS = ("virus", "burst", "waves", "mountain", "jet", "cross",
              "satellite", "balloon", "chess", "candle", "document", "flag")


def draw_icon(buf, x, y, size, kind, ink, accent, plate):
    """Pictogram on a 16x16 grid, drawn from rectangles, polygons and discs."""
    s = size / 16.0

    def gx(v):
        return int(x + v * s + 0.5)

    def gy(v):
        return int(y + v * s + 0.5)

    def rect(a, b, w, h, col):
        fill_rect(buf, gx(a), gy(b), max(1, int(w * s + 0.5)),
                  max(1, int(h * s + 0.5)), col)

    def disc(a, b, r, col):
        fill_circle(buf, gx(a), gy(b), max(1, int(r * s + 0.5)), col)

    def poly(pts, col):
        fill_poly(buf, [(gx(a), gy(b)) for a, b in pts], col)

    def line(a, b, c, d, w, col):
        x0, y0, x1, y1 = gx(a), gy(b), gx(c), gy(d)
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        w = max(2, int(w * s + 0.5))
        for i in range(n + 1):
            fill_rect(buf, x0 + (x1 - x0) * i // n - w // 2,
                      y0 + (y1 - y0) * i // n - w // 2, w, w, col)

    if kind == "virus":
        for dx, dy in DIRS8:
            line(8 + dx * 3.6, 8 + dy * 3.6, 8 + dx * 6.4,
                 8 + dy * 6.4, 1.1, ink)
        stroke_circle(buf, gx(8), gy(8), max(2, int(4.4 * s + 0.5)),
                      max(2, int(1.5 * s + 0.5)), ink, plate)
        for a, b in ((6.4, 6.8), (9.6, 7.2), (8.0, 9.6)):
            disc(a, b, 0.85, accent)
    elif kind == "burst":
        pts = []
        for i, (dx, dy) in enumerate(DIRS8):
            r = 7.0 if i % 2 == 0 else 2.9
            pts.append((8 + dx * r, 8 + dy * r))
        poly(pts, accent)
        poly([(8, 3.2), (9.6, 8), (8, 12.8), (6.4, 8)], ink)
    elif kind == "waves":
        # Three filled sine bands: a polygon between the crest line and a
        # parallel line below it, so the water reads as continuous.
        cycle = (0.0, -0.7, -1.4, -0.7, 0.0, 0.7, 1.4, 0.7)
        for base, col in ((2.6, ink), (7.4, accent), (12.2, ink)):
            top = [(float(i), base + cycle[i % 8]) for i in range(16)]
            bottom = [(float(i), base + 1.8 + cycle[i % 8])
                      for i in range(15, -1, -1)]
            poly(top + bottom, col)
    elif kind == "mountain":
        poly([(0.8, 14.2), (6.2, 3.6), (9.4, 10.0), (11.4, 6.4),
              (15.2, 14.2)], ink)
        poly([(4.6, 6.8), (6.2, 3.6), (7.8, 6.8)], accent)
        poly([(10.6, 8.4), (11.4, 6.4), (12.3, 8.4)], accent)
    elif kind == "jet":
        poly([(8.0, 0.8), (9.4, 5.6), (14.2, 8.8), (14.2, 10.8),
              (9.4, 9.4), (9.0, 12.6), (10.8, 14.2), (10.8, 15.2),
              (8.0, 14.6), (5.2, 15.2), (5.2, 14.2), (7.0, 12.6),
              (6.6, 9.4), (1.8, 10.8), (1.8, 8.8), (6.6, 5.6)], ink)
        rect(7.4, 4.0, 1.2, 3.0, accent)
    elif kind == "cross":
        rect(6.0, 1.6, 4.0, 12.8, ink)
        rect(1.6, 6.0, 12.8, 4.0, ink)
        rect(6.9, 2.6, 2.2, 4.4, accent)
    elif kind == "satellite":
        rect(1.0, 6.6, 4.2, 2.8, accent)
        rect(10.8, 6.6, 4.2, 2.8, accent)
        rect(6.2, 6.2, 3.6, 3.6, ink)
        line(5.2, 8.0, 6.2, 8.0, 0.8, ink)
        line(9.8, 8.0, 10.8, 8.0, 0.8, ink)
        disc(11.6, 3.6, 1.7, ink)
        line(11.6, 3.6, 8.6, 6.2, 0.8, ink)
        rect(7.2, 12.6, 1.6, 2.2, ink)
    elif kind == "balloon":
        for a, b in ((4.6, 4.4), (8.4, 3.2), (11.8, 5.2)):
            disc(a, b, 2.1, accent)
        line(4.6, 6.5, 7.6, 10.4, 0.7, ink)
        line(8.4, 5.3, 8.0, 10.4, 0.7, ink)
        line(11.8, 7.3, 8.8, 10.4, 0.7, ink)
        rect(7.0, 10.6, 3.2, 2.6, ink)
        rect(7.9, 9.8, 1.4, 1.0, ink)
    elif kind == "chess":
        cell = 1.45
        for j in range(8):
            for i in range(8):
                if (i + j) % 2:
                    rect(0.8 + i * cell, 0.8 + j * cell, cell, cell, accent)
        # A white queen on the right half of the board, foot on the last rank.
        poly([(9.8, 14.6), (13.2, 14.6), (12.6, 11.9), (10.4, 11.9)], ink)
        rect(10.6, 10.6, 2.8, 1.5, ink)
        disc(12.0, 9.6, 1.3, ink)
        rect(11.4, 7.6, 1.2, 1.4, ink)
        rect(10.5, 6.9, 0.9, 0.9, ink)
        rect(11.6, 6.6, 0.9, 1.0, ink)
        rect(12.6, 6.9, 0.9, 0.9, ink)
    elif kind == "candle":
        rect(6.4, 6.4, 3.2, 8.0, ink)
        rect(7.6, 4.8, 0.9, 1.8, ink)
        poly([(8.0, 0.8), (9.3, 3.0), (8.0, 4.6), (6.7, 3.0)], accent)
        rect(4.2, 14.2, 7.6, 1.4, ink)
        rect(6.9, 7.4, 1.0, 1.2, accent)
    elif kind == "document":
        rect(4.2, 1.4, 7.6, 13.2, ink)
        poly([(9.6, 1.4), (11.8, 3.6), (9.6, 3.6)], plate)
        for b in (5.6, 7.6, 9.6):
            rect(5.6, b, 4.8, 1.0, accent)
        rect(5.6, 11.8, 2.8, 1.0, accent)
    elif kind == "flag":
        rect(3.6, 1.2, 1.3, 12.6, ink)
        poly([(4.9, 1.6), (13.4, 3.0), (11.2, 5.2), (13.4, 7.4),
              (4.9, 8.6)], accent)
        rect(2.2, 13.8, 5.4, 1.2, ink)
    else:
        rect(4.0, 4.0, 8.0, 8.0, ink)


def icon_for(it):
    return it.get("icon") or DEFAULT_ICON.get(it["category"], "flag")


def icon_box(it, x, y):
    """Plate rectangle (x, y, w, h) for a hero or tile item."""
    if it["featured"] and it["rank"] == 1:
        return (HERO_ICON_X, HERO_ICON_Y, ICON_HERO, ICON_HERO)
    return (x + TILE_W - ICON_INSET - ICON_TILE, y + ICON_INSET,
            ICON_TILE, ICON_TILE)


def draw_icon_plate(buf, it, x, y):
    color = REGION_COLOR[it["region"]]
    plate = shade(color, 0.42)
    accent = tint(color, 0.74)
    bx, by, bw, bh = icon_box(it, x, y)
    fill_rect(buf, bx, by, bw, bh, plate)
    stroke_rect(buf, bx, by, bw, bh, accent)
    draw_icon(buf, bx, by, bw, icon_for(it), WHITE, accent, plate)


def png_chunk(tag, payload):
    head = struct.pack(">I", len(payload)) + tag + payload
    return head + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def write_png(path, buf):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", ihdr)
    data += png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += png_chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(data)


# Coarse land outlines in (lon, lat).  These are deliberately blocky: at
# 472x174 px a continent is a silhouette, not a coastline.  Small, news-
# bearing landmasses get their own polygons so their cities land on land.
LANDMASSES = {
    "North America": [
        (-168, 65), (-166, 68), (-160, 71), (-152, 71), (-145, 70),
        (-140, 70), (-132, 69), (-125, 70), (-118, 70), (-110, 68),
        (-100, 69), (-92, 70), (-85, 70), (-80, 73), (-74, 73),
        (-68, 70), (-62, 68), (-58, 62), (-55, 52), (-60, 47),
        (-66, 45), (-70, 43), (-74, 40), (-76, 37), (-78, 34),
        (-81, 31), (-80.4, 29.5), (-79.8, 27.5), (-79.9, 25.6),
        (-80.6, 24.9), (-81.6, 25.4), (-82.4, 27.2), (-83, 29),
        (-85, 30), (-89, 29),
        (-94, 29), (-97, 26), (-97, 22), (-105, 22), (-110, 24),
        (-114, 28), (-117, 32), (-122, 37), (-124, 40), (-124, 48),
        (-130, 54), (-135, 58), (-142, 60), (-150, 60), (-158, 57),
        (-165, 55), (-168, 60),
    ],
    "Greenland": [
        (-45, 60), (-50, 64), (-55, 68), (-60, 72), (-58, 76),
        (-52, 78), (-50, 80), (-40, 83), (-30, 83), (-25, 82),
        (-20, 76), (-25, 70), (-32, 66), (-40, 62), (-43, 60),
    ],
    "South America": [
        (-81, 8), (-77, 8), (-75, 11), (-71, 12), (-68, 11),
        (-64, 10), (-60, 8), (-56, 6), (-53, 5), (-50, 2),
        (-50, -2), (-44, -2),
        (-38, -5), (-35, -6), (-37, -13), (-39, -18), (-40, -22),
        (-44, -23), (-48, -26), (-53, -34), (-58, -38), (-62, -41),
        (-65, -47), (-68, -53), (-73, -54), (-75, -46), (-73, -36),
        (-71, -25), (-70, -18), (-72.5, -17.5), (-73.5, -11),
        (-75.5, -5), (-77.5, 0.5), (-79, 6), (-80.5, 7.5),
    ],
    "Europe": [
        (-9, 36), (-9, 39), (-9, 44), (-2, 44), (-2, 48),
        (-5, 48), (-4, 52), (-8, 54), (-8, 58), (-5, 59),
        (-4, 60), (2, 62), (5, 58), (8, 58), (10, 54),
        (10, 64), (14, 68), (20, 70), (28, 71), (30, 66),
        (28, 58), (32, 58), (36, 58), (42, 58), (48, 58),
        (48, 52), (44, 48), (40, 46), (36, 45), (32, 46),
        (30, 45), (26, 41), (20, 40), (16, 38), (13, 38),
        (9, 40), (6, 40), (3, 42), (0, 39), (-2, 36.5), (-6, 36),
    ],
    "Africa": [
        (-17, 15), (-16, 21), (-10, 27), (-10, 35), (-6, 36),
        (0, 37), (10, 37), (20, 32), (25, 32), (32, 31),
        (34, 28), (38, 22), (43, 12), (48, 12), (51, 12),
        (48, 5), (43, 2), (41, -2), (40, -10), (35, -20),
        (33, -26), (27, -34), (20, -35), (18, -30), (14, -22),
        (12, -15), (9, -1), (9, 4), (3, 6), (-8, 4), (-13, 8),
    ],
    "Asia": [
        (26, 40), (30, 41), (35, 42), (40, 40), (45, 42),
        (50, 45), (55, 45), (60, 44), (65, 45), (70, 45),
        (75, 47), (80, 50), (85, 50), (90, 52), (95, 52),
        (100, 52), (105, 53), (110, 52), (115, 52), (120, 50),
        (125, 50), (130, 48), (135, 48), (140, 50), (142, 52),
        (145, 58), (150, 62), (155, 62), (160, 65), (170, 68),
        (178, 70), (178, 62), (172, 60), (165, 58), (160, 55),
        (155, 50), (150, 48), (145, 44), (140, 40), (135, 35),
        (130, 34), (125, 30), (122, 26), (120, 25), (115, 22),
        (110, 20), (108, 15), (105, 10), (100, 5), (98, 8),
        (95, 10), (92, 18), (90, 22), (88, 21), (85, 20),
        (82, 16), (80, 10), (77, 8), (74, 14), (72, 20),
        (68, 24), (62, 25), (60, 25), (55, 28), (50, 30),
        (45, 32), (40, 35), (35, 36), (30, 36),
    ],
    "Australia": [
        (113, -22), (114, -26), (115, -32), (118, -35), (123, -34),
        (129, -32), (135, -35), (138, -35), (141, -38), (147, -38),
        (151, -37), (154, -30), (153, -25), (146, -19), (142, -11),
        (136, -12), (130, -11), (125, -14), (122, -18),
    ],
    "Britain": [
        (-5, 50), (-3, 51), (0, 51), (1, 52), (-1, 54),
        (-2, 56), (-3, 58), (-5, 58), (-6, 57), (-5, 55),
        (-4, 53), (-5, 51),
    ],
    "Japan": [
        (130, 31), (131, 33), (133, 34), (135, 34), (137, 35),
        (139, 35), (141, 36), (141, 39), (142, 42), (145, 44),
        (145, 42), (142, 39), (140, 36), (138, 34), (135, 33),
        (132, 31),
    ],
    "Malaya": [
        (100, 7), (101, 6), (102, 6), (103, 4), (104, 3),
        (104, 1), (103, 1), (102, 2), (101, 3), (100, 5),
    ],
    "Sumatra": [
        (95, 5), (97, 4), (99, 2), (101, 0), (103, -2),
        (105, -4), (106, -6), (104, -6), (102, -4), (100, -2),
        (98, 0), (96, 3),
    ],
    "Java": [
        (105, -6), (107, -6), (109, -6), (111, -7), (114, -7),
        (114, -8.5), (111, -8.5), (108, -8), (106, -7.5), (105, -7),
    ],
    "Kalimantan": [
        (109, 2), (110, 1), (113, -1), (116, -2), (117, -4),
        (116, -4.5), (113, -3), (110, -2), (109, 0),
    ],
    "Sulawesi": [
        (119, 1), (120, 0), (121, -2), (123, -3), (123, -5),
        (121, -5), (120, -3), (119, -1),
    ],
    "India": [
        (68, 23), (70, 21), (72, 20), (74, 16), (76, 10),
        (78, 8), (80, 12), (82, 17), (85, 20), (88, 22),
        (90, 24), (92, 25), (94, 27), (92, 28), (88, 27),
        (85, 26), (80, 28), (76, 30), (72, 26), (70, 24),
    ],
    "Arabia": [
        (35, 29), (38, 30), (41, 30), (44, 29), (48, 29),
        (51, 26), (54, 24), (56, 26), (57, 23), (55, 20),
        (52, 16), (48, 14), (44, 13), (42, 16), (40, 20),
        (37, 24), (35, 27),
    ],
    "Madagascar": [
        (43, -12), (46, -13), (48, -15), (50, -16), (49, -20),
        (47, -25), (45, -25), (44, -22), (43, -18), (43, -14),
    ],
    "New Zealand": [
        (172, -34), (174, -35), (176, -37), (178, -38), (177, -40),
        (175, -41), (173, -41), (171, -44), (168, -46), (166, -46),
        (167, -44), (170, -42), (172, -40), (173, -37),
    ],
    "Levant": [
        (34, 33), (35, 33), (36, 34), (36, 36), (37, 37),
        (38, 37), (38, 35), (37, 32), (35, 31), (34, 31),
    ],
    "Tasmania": [
        (144, -40.5), (146, -40.5), (148, -41), (148.5, -42),
        (148, -43), (146, -43.5), (145, -42.5), (144, -41.5),
    ],
    "Puerto Rico": [
        (-67.9, 18.6), (-66.4, 18.6), (-65.1, 18.4), (-65.3, 17.8),
        (-66.7, 17.6), (-67.8, 17.9),
    ],
    "Ibiza": [
        (0.9, 39.2), (1.4, 39.2), (1.7, 38.9), (1.7, 38.7),
        (1.1, 38.7), (0.8, 38.9),
    ],
    "Flinders Island": [
        (147.0, -39.7), (148.4, -39.9), (148.9, -40.3),
        (148.2, -40.9), (147.4, -40.9), (146.9, -40.3),
    ],
}


def proj(lon, lat):
    x = MAP_X0 + int((lon + 180.0) * (MAP_X1 - MAP_X0) // 360)
    y = MAP_Y0 + int((MAP_LAT_TOP - lat) * (MAP_Y1 - MAP_Y0)
                     // (MAP_LAT_TOP - MAP_LAT_BOT))
    return x, y


def point_in_land(lon, lat):
    """Even-odd test in lon/lat space, used by check.py's map sanity pass."""
    for points in LANDMASSES.values():
        inside = False
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 > lat) != (y1 > lat):
                cut = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
                if lon < cut:
                    inside = not inside
        if inside:
            return True
    return False


def unproj(x, y):
    lon = (x - MAP_X0) * 360.0 / (MAP_X1 - MAP_X0) - 180.0
    lat = MAP_LAT_TOP - (y - MAP_Y0) * (MAP_LAT_TOP - MAP_LAT_BOT) \
        / (MAP_Y1 - MAP_Y0)
    return lon, lat


# Fixed search order for nudging a crowded pin.  The first offset that is
# on land, inside the map and clear of every pin already placed wins, so
# the layout is a pure function of the data.
def _pin_offsets():
    out = []
    for dx in range(-14, 15):
        for dy in range(-14, 15):
            d2 = dx * dx + dy * dy
            if d2 <= 14 * 14:
                out.append((round(d2 ** 0.5, 3), abs(dx) + abs(dy), dx, dy))
    out.sort()
    return [(dx, dy) for _, _, dx, dy in out]


PIN_OFFSETS = _pin_offsets()

PIN_MIN_GAP = 12
PIN_SHIFT = 14


def pin_layout(items):
    """One (x, y) per item, de-clustered and kept on land.

    On a 472 px world a degree of longitude is 1.3 px, so two stories from
    the same city are one dot.  Those cannot be separated within the 14 px
    allowance without leaving land, so the later one is merged into the
    nearest placed pin and that pin is drawn with a ring to show a cluster.
    """
    featured = sorted([i for i in items if i["featured"]],
                      key=lambda i: (-proj(i["lon"], i["lat"])[0], i["rank"]))
    order = featured + sorted([i for i in items if not i["featured"]],
                              key=lambda i: i["id"])
    placed = []
    out = []
    for it in order:
        bx, by = proj(it["lon"], it["lat"])
        best = None
        for dx, dy in PIN_OFFSETS:
            x, y = bx + dx, by + dy
            if not (MAP_X0 + 6 <= x <= MAP_X1 - 6):
                continue
            if not (MAP_Y0 + 6 <= y <= MAP_Y1 - 6):
                continue
            lon, lat = unproj(x, y)
            if not point_in_land(lon, lat):
                continue
            if any((x - p[0]) ** 2 + (y - p[1]) ** 2 < PIN_MIN_GAP ** 2
                   for p in placed):
                continue
            best = (x, y)
            break
        merged_into = None
        if best is None:
            near = min(placed, key=lambda p: (p[0] - bx) ** 2 + (p[1] - by) ** 2)
            best = (near[0], near[1])
            merged_into = near[2]
            near[4] += 1
        placed.append([best[0], best[1], it["id"], it["featured"], 0])
        if merged_into is None:
            placed[-1][4] = 1
        out.append({"id": it["id"], "x": best[0], "y": best[1],
                    "rank": it.get("rank"), "featured": bool(it["featured"]),
                    "region": it["region"], "merged_into": merged_into,
                    "cluster": 0})
    counts = {p[2]: p[4] for p in placed}
    for pin in out:
        pin["cluster"] = counts.get(pin["merged_into"] or pin["id"], 1)
    return out


def draw_map(buf, items):
    fill_rect(buf, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, PANEL)
    stroke_rect(buf, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, PANEL_EDGE)
    draw_text(buf, 532, 70, "WHERE IT HAPPENED", 2, MUTED)

    clip = (MAP_X0, MAP_Y0, MAP_X1, MAP_Y1)

    for lon in range(-180, 181, 30):
        x, _ = proj(lon, 0)
        fill_rect(buf, x, MAP_Y0, 1, MAP_Y1 - MAP_Y0 + 1, GRID_INK)
    for lat in range(-60, 76, 30):
        _, y = proj(0, lat)
        fill_rect(buf, MAP_X0, y, MAP_X1 - MAP_X0 + 1, 1, GRID_INK)

    for pts in LANDMASSES.values():
        poly = [proj(lon, lat) for lon, lat in pts]
        fill_poly(buf, poly, LAND, clip)
        poly_outline(buf, poly, COAST, clip)

    by_id = {it["id"]: it for it in items}
    pins = [p for p in pin_layout(items) if p["merged_into"] is None]
    for pin in pins:
        if pin["featured"]:
            continue
        if pin["cluster"] > 1:
            stroke_circle(buf, pin["x"], pin["y"], 4, 1, WHITE, LAND)
        fill_circle(buf, pin["x"], pin["y"], 3, WHITE)
        fill_circle(buf, pin["x"], pin["y"], 2,
                    REGION_COLOR[by_id[pin["id"]]["region"]])

    # Featured markers are slightly larger discs.  Two pins may sit 12 px
    # apart, so the outer radius stays at 5 and no digit is drawn inside:
    # a 14 px digit would need a 7 px radius and the markers would collide.
    for pin in sorted([p for p in pins if p["featured"]],
                      key=lambda p: p["rank"]):
        color = REGION_COLOR[pin["region"]]
        if pin["cluster"] > 1:
            stroke_circle(buf, pin["x"], pin["y"], 5, 1, WHITE, LAND)
        fill_circle(buf, pin["x"], pin["y"], 4, WHITE)
        fill_circle(buf, pin["x"], pin["y"], 3, color)


def draw_badge(buf, x, y, label, scale=2):
    fill_rect(buf, x, y, 30, 24, WHITE)
    draw_text(buf, x + (30 - text_width(label, scale)) // 2,
              y + (24 - 7 * scale) // 2, label, scale, BADGE_INK)


def draw_header(buf, n_regions):
    draw_text(buf, 12, 14, "WORLD NEWS 26 NOV 2026", 4, WHITE)
    line1 = "36 STORIES, %d REGIONS" % n_regions
    draw_text(buf, 1012 - text_width(line1, 2), 12, line1, 2, MUTED)
    line2 = "ALL DATED 26 NOV 2026"
    draw_text(buf, 1012 - text_width(line2, 2), 34, line2, 2, ACCENT)


def draw_hero(buf, it):
    color = REGION_COLOR[it["region"]]
    fill_rect(buf, HERO_X, HERO_Y, HERO_W, HERO_H, color)
    draw_badge(buf, 24, 76, str(it["rank"]))
    draw_text(buf, 60, 80, it["region"], 2, WHITE)

    stat = it["big_stat"]
    scale = fit_scale(stat, HERO_STAT_W, 10, 6)
    if text_width(stat, scale) > HERO_STAT_W:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, 24, 108, stat, scale, WHITE)

    lines = wrap(it["headline"], 3, 476, 2)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, 24, 192 + i * 26, line, 3, WHITE)

    draw_icon_plate(buf, it, HERO_X, HERO_Y)


def draw_tile(buf, it, x, y):
    color = REGION_COLOR[it["region"]]
    fill_rect(buf, x, y, TILE_W, TILE_H, color)
    draw_badge(buf, x + 8, y + 8, str(it["rank"]))
    draw_text(buf, x + 46, y + 12, SHORT_REGION[it["region"]], 2, WHITE)

    # The stat shares the top row with the plate, so its width stops short
    # of the plate; the headline starts below the plate and may use the
    # whole tile width.
    stat = it["big_stat"]
    scale = fit_scale(stat, TILE_STAT_W, 5, 3)
    if text_width(stat, scale) > TILE_STAT_W:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, x + 8, y + 34, stat, scale, WHITE)

    lines = wrap(it["headline"], 2, TILE_W - 16, 2)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, x + 8, y + 78 + i * 16, line, 2, WHITE)

    draw_icon_plate(buf, it, x, y)


LEGEND_RIGHT = 1012
LEGEND_SWATCH = 10
LEGEND_GAP = 5
LEGEND_ITEM_GAP = 12
LEGEND_Y = 682


def legend_layout(regions):
    """Swatch/label columns, right-aligned, widest-first reading order."""
    widths = []
    for region in regions:
        w = LEGEND_SWATCH + LEGEND_GAP + text_width(REGION_ABBR[region], 2)
        widths.append((region, w))
    total = sum(w for _, w in widths) + LEGEND_ITEM_GAP * (len(widths) - 1)
    x = LEGEND_RIGHT - total
    out = []
    for region, w in widths:
        out.append((region, x, w))
        x += w + LEGEND_ITEM_GAP
    return out


def draw_legend(buf, items):
    regions = [r for r in REGION_ORDER
               if any(i["region"] == r for i in items)]
    for region, x, w in legend_layout(regions):
        fill_rect(buf, x, LEGEND_Y + 3, LEGEND_SWATCH, LEGEND_SWATCH,
                  REGION_COLOR[region])
        stroke_rect(buf, x, LEGEND_Y + 3, LEGEND_SWATCH, LEGEND_SWATCH, BG)
        draw_text(buf, x + LEGEND_SWATCH + LEGEND_GAP, LEGEND_Y,
                  REGION_ABBR[region], 2, MUTED)


def draw_list(buf, items):
    fill_rect(buf, 12, 676, 1000, 1, PANEL_EDGE)
    draw_text(buf, 12, 682, "ALSO TODAY, 23 MORE", 2, MUTED)
    draw_legend(buf, items)
    for idx, it in enumerate(items):
        col = 0
        row = idx
        while row >= LIST_COL_LEN[col]:
            row -= LIST_COL_LEN[col]
            col += 1
        x = LIST_XS[col]
        y = LIST_Y0 + row * LIST_PITCH
        fill_rect(buf, x, y, 28, 20, REGION_COLOR[it["region"]])
        num = str(it["number"])
        draw_text(buf, x + (28 - text_width(num, 2)) // 2, y + 3, num, 2, WHITE)
        lines = wrap(it["headline"], 2, 292, 2)
        if lines is None:
            fail("OVERFLOW %d" % it["id"])
        for i, line in enumerate(lines):
            draw_text(buf, x + 36, y + 2 + i * 16, line, 2, LIST_INK)


def fail(message):
    sys.stderr.write(message + "\n")
    raise SystemExit(1)


def load_news():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "news.json"), "r", encoding="utf-8") as fh:
        items = json.load(fh)

    for it in items:
        for ch in (it["headline"] + it.get("big_stat", "") + it["region"]):
            if ch.upper() not in FONT:
                fail("NOGLYPH %d %s" % (it["id"], ch))
        if len(it["headline"]) > 44:
            fail("OVERFLOW %d" % it["id"])
        if len(it.get("big_stat", "")) > 11:
            fail("OVERFLOW %d" % it["id"])

    featured = sorted([i for i in items if i["featured"]], key=lambda i: i["rank"])
    rest = sorted([i for i in items if not i["featured"]],
                  key=lambda i: (REGION_ORDER.index(i["region"]), i["id"]))
    for n, it in enumerate(featured, 1):
        it["number"] = it["rank"]
    for n, it in enumerate(rest, len(featured) + 1):
        it["number"] = n
    return items, featured, rest


def main():
    items, featured, rest = load_news()
    regions = {it["region"] for it in items}

    buf = new_canvas()
    draw_header(buf, len(regions))
    draw_hero(buf, featured[0])
    for idx, it in enumerate(featured[1:]):
        draw_tile(buf, it, TILE_XS[idx % 4], TILE_YS[idx // 4])
    draw_map(buf, items)
    draw_list(buf, rest)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), buf)


if __name__ == "__main__":
    main()

