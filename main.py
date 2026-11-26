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
PANEL = (0x11, 0x1C, 0x2E)
PANEL_EDGE = (0x2A, 0x3B, 0x55)
GRID_INK = (0x1A, 0x2A, 0x42)
LAND = (0x22, 0x34, 0x4F)
COAST = (0x3B, 0x52, 0x73)
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
# 472x174 px a continent is a silhouette, not a coastline.
LANDMASSES = {
    "North America": [
        (-168, 65), (-160, 70), (-140, 70), (-125, 70), (-110, 68),
        (-95, 70), (-80, 73), (-62, 68), (-55, 52), (-66, 45),
        (-70, 41), (-75, 35), (-81, 25), (-90, 29), (-97, 26),
        (-105, 22), (-115, 30), (-124, 40), (-124, 48), (-135, 58),
        (-150, 60), (-165, 55),
    ],
    "Greenland": [
        (-45, 60), (-50, 64), (-55, 68), (-60, 72), (-58, 76),
        (-50, 80), (-40, 83), (-25, 82), (-20, 76), (-25, 70),
        (-32, 66), (-40, 62),
    ],
    "South America": [
        (-81, 8), (-77, 1), (-70, -5), (-60, -8), (-50, -2),
        (-44, -2), (-35, -6), (-37, -13), (-39, -18), (-40, -22),
        (-48, -26), (-53, -34), (-58, -38), (-62, -41), (-65, -47),
        (-68, -53), (-73, -54), (-75, -46), (-73, -36), (-71, -25),
        (-70, -18), (-76, -14), (-80, -5), (-81, 2),
    ],
    "Europe": [
        (-9, 36), (-9, 44), (-8, 50), (-8, 58), (-4, 60),
        (2, 62), (10, 64), (14, 68), (20, 70), (28, 71),
        (30, 66), (28, 58), (30, 50), (28, 45), (20, 40),
        (12, 38), (3, 42), (-2, 36.5),
    ],
    "Africa": [
        (-17, 15), (-10, 35), (0, 37), (10, 37), (20, 32),
        (25, 32), (32, 31), (34, 28), (38, 22), (43, 12),
        (51, 12), (48, 5), (41, -2), (40, -10), (35, -20),
        (33, -26), (27, -34), (20, -35), (18, -30), (14, -22),
        (12, -15), (9, -1), (9, 4), (3, 6), (-8, 4), (-13, 8),
    ],
    "Asia": [
        (26, 40), (35, 42), (45, 42), (55, 45), (65, 45),
        (75, 47), (85, 50), (95, 52), (105, 53), (115, 52),
        (125, 50), (135, 48), (142, 52), (145, 58), (150, 62),
        (160, 65), (170, 68), (178, 70), (178, 60), (170, 58),
        (160, 55), (150, 48), (145, 44), (140, 40), (135, 35),
        (130, 34), (125, 30), (120, 25), (115, 22), (110, 20),
        (105, 10), (100, 5), (95, 10), (90, 22), (85, 20),
        (80, 10), (77, 8), (72, 20), (68, 24), (60, 25),
        (55, 28), (50, 30), (45, 32), (40, 35), (30, 36),
    ],
    "Australia": [
        (113, -22), (114, -26), (115, -32), (118, -35), (123, -34),
        (129, -32), (135, -35), (138, -35), (141, -38), (147, -38),
        (151, -37), (154, -30), (153, -25), (146, -19), (142, -11),
        (136, -12), (130, -11), (125, -14), (122, -18),
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

    for name in ("North America", "Greenland", "South America", "Europe",
                 "Africa", "Asia", "Australia"):
        pts = [proj(lon, lat) for lon, lat in LANDMASSES[name]]
        fill_poly(buf, pts, LAND, clip)
        poly_outline(buf, pts, COAST, clip)

    featured = [it for it in items if it["featured"]]
    rest = [it for it in items if not it["featured"]]

    for it in rest:
        x, y = proj(it["lon"], it["lat"])
        fill_circle(buf, x, y, 4, WHITE)
        fill_circle(buf, x, y, 3, REGION_COLOR[it["region"]])

    placed = []
    for it in sorted(featured, key=lambda i: i["rank"]):
        x, y = proj(it["lon"], it["lat"])
        for _ in range(5):
            clash = False
            for px, py in placed:
                if abs(px - x) < 20 and abs(py - y) < 20:
                    clash = True
                    break
            if not clash:
                break
            x += 12
            y -= 12
        placed.append((x, y))
        fill_circle(buf, x, y, 10, REGION_COLOR[it["region"]])
        fill_circle(buf, x, y, 8, WHITE)
        label = str(it["rank"])
        draw_text(buf, x - text_width(label, 1) // 2, y - 3, label, 1,
                  BADGE_INK)


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
    scale = fit_scale(stat, 476, 10, 6)
    if text_width(stat, scale) > 476:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, 24, 108, stat, scale, WHITE)

    lines = wrap(it["headline"], 3, 476, 2)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, 24, 192 + i * 26, line, 3, WHITE)


def draw_tile(buf, it, x, y):
    color = REGION_COLOR[it["region"]]
    fill_rect(buf, x, y, TILE_W, TILE_H, color)
    draw_badge(buf, x + 8, y + 8, str(it["rank"]))
    draw_text(buf, x + 46, y + 12, it["region"], 2, WHITE)

    stat = it["big_stat"]
    scale = fit_scale(stat, 230, 5, 3)
    if text_width(stat, scale) > 230:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, x + 8, y + 34, stat, scale, WHITE)

    lines = wrap(it["headline"], 2, 230, 3)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, x + 8, y + 74 + i * 16, line, 2, WHITE)


def draw_list(buf, items):
    fill_rect(buf, 12, 676, 1000, 1, PANEL_EDGE)
    draw_text(buf, 12, 682, "ALSO TODAY, 23 MORE", 2, MUTED)
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

