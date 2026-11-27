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

CREAM = (0xF2, 0xEA, 0xD8)
GOLD = (0xFF, 0xD2, 0x3F)
INK = (0x10, 0x16, 0x22)
SMOKE = (0xB9, 0xC2, 0xCE)
WATER = (0x35, 0x6E, 0xA8)
SAND = (0xD8, 0xB4, 0x6E)
RED = (0xE8, 0x3B, 0x3B)
BRICK = (0x9C, 0x36, 0x2E)
ROOF = (0x2F, 0x7A, 0x4F)

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

STATUS_COLOR = {
    "OFFICIAL": (0x7C, 0xC4, 0xFF),
    "CONFIRMED": (0x59, 0xD6, 0x8F),
    "REPORTED": (0xC9, 0xD6, 0xE6),
    "CLAIM": (0xFF, 0xB4, 0x4D),
    "ONGOING": (0x5F, 0xE0, 0xE8),
}

STATUSES = ("OFFICIAL", "CONFIRMED", "REPORTED", "CLAIM", "ONGOING")

# Every draw_text call is appended here when --text-log is passed, so
# check.py can assert on the exact strings and their boxes without
# guessing glyph shapes from pixels.
TEXT_LOG = None

# Set False by render(text=False) so a check can compare a poster with no
# lettering against the real one, pixel for pixel.
DRAW_TEXT = True

MARGIN = 12
HERO_X, HERO_Y, HERO_W, HERO_H = 12, 64, 500, 150
MAP_X, MAP_Y, MAP_W, MAP_H = 524, 64, 488, 150

# Four 245 px columns at a 251 px pitch: 12 + 4*245 + 3*6 = 1010, which
# keeps the 6 px gutter and the 12 px right margin.  The brief's 250 px
# columns at 12/268/524/780 would end at 1030, off the 1024 canvas, so
# the tile is 5 px narrower and the 238 px illustration box still fits
# at +6 with a 1 px right pad.
TILE_XS = (12, 263, 514, 765)
TILE_YS = (220, 382, 544)
TILE_W, TILE_H = 245, 156

SCENE_X, SCENE_Y, SCENE_W, SCENE_H = 6, 22, 238, 50
HERO_SCENE_X, HERO_SCENE_Y = 316, 24
HERO_SCENE_W, HERO_SCENE_H = 178, 88
GROUND_H = 12

MAP_X0, MAP_Y0, MAP_X1, MAP_Y1 = 532, 86, 1004, 208
MAP_LAT_TOP, MAP_LAT_BOT = 75.0, -58.0

LIST_XS = (12, 346, 680)
LIST_Y0 = 726
LIST_PITCH = 20
LIST_ROWS = 6
LIST_COL_W = 324

DATE_X, DATE_Y, DATE_W, DATE_H = 12, 872, 1000, 146
DATE_ITEMS = (
    "NIGER ATTACK: 24-25 NOV",
    "US MEASLES CDC TOTAL: 25 NOV",
    "FCC SPACEX 1M SATS: 25 NOV",
    "TRUMP NATO STATEMENT: 25 NOV",
    "HORMUZ TANKER HITS MINE: 24-25 NOV",
    "HOUTHI CLAIM ON RAS TANURA: 25 NOV",
)
DATE_TITLE = "DATE CHECK: EVERY STORY IS FROM 26 NOV. LEFT OUT (NOT 26 NOV):"
# The four status meanings share one 14 px row above the box.  The full
# wording does not fit the 982 px interior, so each meaning is shortened
# but still names its status.  The 34 px gap is exactly three blank
# columns of the 14 px face, as the brief asks: the row ends at x 982.
STATUS_LEGEND = (
    "OFFICIAL GOV SOURCE",
    "REPORTED 1 OUTLET",
    "CLAIM ONE SIDE SAYS",
    "ONGOING DEVELOPING",
)
STATUS_LEGEND_Y = 846
STATUS_LEGEND_X = 12
STATUS_LEGEND_GAP = 34
# The two old legend lines sat at DATE_Y+100 and DATE_Y+120; the UTC
# timeline takes exactly that space, two rows of 14 px type at 20 px pitch.
TIMELINE_Y = DATE_Y + 100
TIMELINE_PITCH = 20

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


def stroke_rect(buf, x, y, w, h, color, thick=1):
    fill_rect(buf, x, y, w, thick, color)
    fill_rect(buf, x, y + h - thick, w, thick, color)
    fill_rect(buf, x, y, thick, h, color)
    fill_rect(buf, x + w - thick, y, thick, h, color)


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
    ytop = max(0, int(min(ys)))
    ybot = min(H - 1, int(max(ys)))
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
    if TEXT_LOG is not None:
        TEXT_LOG.append((s, x, y, scale, color))
    if not DRAW_TEXT:
        return text_width(s, scale)
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


# Twelve unit vectors 30 degrees apart, enough for radial shapes without
# importing math.
RING12 = (
    (1.0, 0.0), (0.866, 0.5), (0.5, 0.866), (0.0, 1.0),
    (-0.5, 0.866), (-0.866, 0.5), (-1.0, 0.0), (-0.866, -0.5),
    (-0.5, -0.866), (0.0, -1.0), (0.5, -0.866), (0.866, -0.5),
)

RING8 = (
    (1.0, 0.0), (0.707, 0.707), (0.0, 1.0), (-0.707, 0.707),
    (-1.0, 0.0), (-0.707, -0.707), (0.0, -1.0), (0.707, -0.707),
)

class Scene(object):
    """A small illustrated box: sky bands, ground strip and shapes.

    Positions are fractions of the box (0..1 on each axis) and radii and
    stroke widths are in pixels, so circles stay round and the same scene
    reads at 238x50 and at 178x88.
    """

    def __init__(self, buf, x, y, w, h, region_color):
        self.buf = buf
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.clip = (x, y, x + w - 1, y + h - 1)
        self.top = shade(region_color, 0.50)
        self.low = shade(region_color, 0.62)
        self.ground = shade(region_color, 0.88)
        self.cream = CREAM
        self.gold = GOLD
        self.ink = INK
        fill_rect(buf, x, y, w, h, self.top)
        split = y + int(h * 0.45)
        fill_rect(buf, x, split, w, y + h - split, self.low)
        self.repaint_ground(self.ground)
        # Everything in a scene stands on the ground strip, so scenes use
        # this instead of 1.0 for their bottom edge.
        self.base = 1.0 - float(GROUND_H) / h

    def repaint_ground(self, color):
        fill_rect(self.buf, self.x, self.y + self.h - GROUND_H,
                  self.w, GROUND_H, color)

    def X(self, u):
        return self.x + int(u * self.w + 0.5)

    def Y(self, v):
        return self.y + int(v * self.h + 0.5)

    def box(self, x, y, w, h, color):
        x0 = max(self.x, x)
        y0 = max(self.y, y)
        x1 = min(self.x + self.w, x + w)
        y1 = min(self.y + self.h, y + h)
        if x1 > x0 and y1 > y0:
            fill_rect(self.buf, x0, y0, x1 - x0, y1 - y0, color)

    def rect(self, u0, v0, u1, v1, color):
        x0, x1 = self.X(u0), self.X(u1)
        y0, y1 = self.Y(v0), self.Y(v1)
        self.box(x0, y0, x1 - x0, y1 - y0, color)

    def disc(self, u, v, rpx, color):
        cx, cy = self.X(u), self.Y(v)
        r = max(1, int(rpx + 0.5))
        for dy in range(-r, r + 1):
            yy = cy + dy
            if yy < self.y or yy >= self.y + self.h:
                continue
            span = int((r * r - dy * dy) ** 0.5)
            x0 = max(self.x, cx - span)
            x1 = min(self.x + self.w - 1, cx + span)
            if x1 >= x0:
                fill_rect(self.buf, x0, yy, x1 - x0 + 1, 1, color)

    def poly(self, pts, color):
        fill_poly(self.buf, [(self.X(a), self.Y(b)) for a, b in pts],
                  color, self.clip)

    def seg(self, x0, y0, x1, y1, wpx, color):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        w = max(1, int(wpx + 0.5))
        half = w // 2
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i // n
            y = y0 + (y1 - y0) * i // n
            self.box(x - half, y - half, w, w, color)

    def line(self, u0, v0, u1, v1, wpx, color):
        self.seg(self.X(u0), self.Y(v0), self.X(u1), self.Y(v1), wpx, color)

    def ray(self, u, v, dx, dy, r0, r1, wpx, color):
        cx, cy = self.X(u), self.Y(v)
        self.seg(int(cx + dx * r0), int(cy + dy * r0),
                 int(cx + dx * r1), int(cy + dy * r1), wpx, color)

    def ring(self, u, v, rpx, color, dot=1.0):
        for dx, dy in RING12:
            self.disc(u + dx * rpx / self.w, v + dy * rpx / self.h,
                      dot, color)

    # The three scenes added in v6 are written in literal pixel
    # coordinates inside the box, so they get pixel-space primitives
    # that take 0..w / 0..h offsets from the box's top-left corner.
    def box_px(self, x, y, w, h, color):
        self.box(self.x + x, self.y + y, w, h, color)

    def disc_px(self, cx, cy, r, color):
        r = max(1, int(r + 0.5))
        cx, cy = self.x + cx, self.y + cy
        for dy in range(-r, r + 1):
            yy = cy + dy
            if yy < self.y or yy >= self.y + self.h:
                continue
            span = int((r * r - dy * dy) ** 0.5)
            x0 = max(self.x, cx - span)
            x1 = min(self.x + self.w - 1, cx + span)
            if x1 >= x0:
                fill_rect(self.buf, x0, yy, x1 - x0 + 1, 1, color)

    def oval_px(self, cx, cy, rx, ry, color):
        cx, cy = self.x + cx, self.y + cy
        for dy in range(-ry, ry + 1):
            yy = cy + dy
            if yy < self.y or yy >= self.y + self.h:
                continue
            span = int(rx * (1.0 - dy * dy / float(ry * ry)) ** 0.5)
            x0 = max(self.x, cx - span)
            x1 = min(self.x + self.w - 1, cx + span)
            if x1 >= x0:
                fill_rect(self.buf, x0, yy, x1 - x0 + 1, 1, color)

    def poly_px(self, pts, color):
        fill_poly(self.buf, [(self.x + a, self.y + b) for a, b in pts],
                  color, self.clip)

    def star_px(self, cx, cy, r, color):
        cx, cy = self.x + cx, self.y + cy
        pts = [(cx + dx * (r if i % 2 == 0 else r * 0.42),
                cy + dy * (r if i % 2 == 0 else r * 0.42))
               for i, (dx, dy) in enumerate(RING8)]
        fill_poly(self.buf, pts, color, self.clip)

    def star(self, u, v, rpx, color):
        cx, cy = self.X(u), self.Y(v)
        pts = []
        for i, (dx, dy) in enumerate(RING8):
            r = rpx if i % 2 == 0 else rpx * 0.42
            pts.append((cx + dx * r, cy + dy * r))
        fill_poly(self.buf, pts, color, self.clip)


def scene_ebola(sc):
    """Virus with twelve spikes, three inner dots, floating circles, cross."""
    r = min(sc.h * 0.30, sc.w * 0.13)
    cx, cy = 0.20, 0.44
    for dx, dy in RING12:
        sc.ray(cx, cy, dx, dy, r * 0.80, r * 1.44,
               max(2, int(sc.h * 0.055)), CREAM)
    sc.disc(cx, cy, r, CREAM)
    sc.disc(cx, cy, r * 0.62, shade(CREAM, 0.90))
    for ox, oy in ((-0.34, -0.30), (0.30, -0.14), (-0.04, 0.38)):
        sc.disc(cx + ox * r / sc.w, cy + oy * r / sc.h,
                max(1, r * 0.17), INK)
    for u, v in ((0.44, 0.16), (0.49, 0.74), (0.56, 0.44)):
        sc.disc(u, v, max(1, sc.h * 0.07), CREAM)
    arm = sc.h * 0.32
    thick = max(3, int(sc.h * 0.10))
    sc.box(sc.X(0.80) - thick // 2, int(sc.Y(0.44) - arm),
           thick, int(arm * 2), GOLD)
    sc.box(int(sc.X(0.80) - arm), sc.Y(0.44) - thick // 2,
           int(arm * 2), thick, GOLD)


def scene_niger(sc):
    """Sand dunes, three huts with smoke, a low sun."""
    sc.disc(0.87, 0.18, sc.h * 0.15, GOLD)
    sc.poly([(0.0, sc.base), (0.24, 0.70), (0.52, sc.base)], SAND)
    sc.poly([(0.42, sc.base), (0.68, 0.62), (0.98, sc.base)],
            shade(SAND, 0.86))
    for u in (0.06, 0.24, 0.42):
        sc.rect(u, 0.48, u + 0.11, sc.base, CREAM)
        sc.poly([(u - 0.02, 0.50), (u + 0.055, 0.32), (u + 0.13, 0.50)],
                CREAM)
        sc.rect(u + 0.04, 0.66, u + 0.07, sc.base, INK)
    for u, v, r in ((0.60, 0.34, 0.08), (0.64, 0.22, 0.06),
                    (0.68, 0.11, 0.04)):
        sc.disc(u, v, sc.h * r, SMOKE)


def scene_mine(sc):
    """Mountain, dark mine adit, blue water with zigzag waves, helmet."""
    sc.poly([(0.0, 0.92), (0.28, 0.10), (0.56, 0.92)], CREAM)
    sc.poly([(0.42, 0.92), (0.60, 0.42), (0.78, 0.92)], shade(CREAM, 0.82))
    sc.rect(0.20, 0.56, 0.33, 0.84, INK)
    sc.disc(0.265, 0.56, sc.w * 0.065, INK)
    sc.rect(0.0, 0.80, 1.0, 0.88, WATER)
    for u in (0.02, 0.30, 0.58):
        sc.line(u, 0.855, u + 0.08, 0.815, 2, CREAM)
        sc.line(u + 0.08, 0.815, u + 0.16, 0.855, 2, CREAM)
    sc.disc(0.80, 0.66, sc.h * 0.15, GOLD)
    sc.rect(0.745, 0.66, 0.855, 0.86, GOLD)
    sc.rect(0.79, 0.68, 0.81, 0.84, INK)


def scene_gaza(sc):
    """Five windowed buildings, rising smoke, an explosion star."""
    for u, wd, ht in ((0.02, 0.13, 0.50), (0.17, 0.11, 0.66),
                      (0.30, 0.14, 0.40), (0.46, 0.12, 0.56),
                      (0.60, 0.13, 0.34)):
        sc.rect(u, sc.base - ht, u + wd, sc.base, CREAM)
        for i in range(3):
            for j in range(2):
                sc.rect(u + 0.018 + i * 0.036,
                        sc.base - ht + 0.06 + j * 0.14,
                        u + 0.046 + i * 0.036,
                        sc.base - ht + 0.11 + j * 0.14, INK)
    sc.star(0.80, 0.22, sc.h * 0.22, GOLD)
    for u, v, r in ((0.40, 0.28, 0.10), (0.46, 0.16, 0.075),
                    (0.52, 0.06, 0.05)):
        sc.disc(u, v, sc.h * r, SMOKE)


def scene_nepal(sc):
    """Three snow-capped peaks, a brown river, a landslide scar."""
    for u, top in ((0.0, 0.20), (0.28, 0.08), (0.56, 0.26)):
        sc.poly([(u, sc.base), (u + 0.17, top), (u + 0.36, sc.base)],
                CREAM)
        sc.poly([(u + 0.10, top + 0.11), (u + 0.17, top),
                 (u + 0.24, top + 0.11)], WHITE)
    sc.poly([(0.0, 0.94), (0.35, 0.82), (0.70, 0.90), (1.0, 0.84),
             (1.0, sc.base), (0.0, sc.base)], shade(WATER, 0.80))
    sc.poly([(0.60, sc.base), (0.76, 0.40), (0.90, sc.base)], GOLD)
    sc.line(0.68, 0.78, 0.85, 0.88, 2, CREAM)


def scene_jets(sc):
    """A grey runway, three jets seen from above, one trailing smoke."""
    sc.repaint_ground(shade(SMOKE, 0.55))
    for i in range(4):
        sc.rect(0.0, 0.86 + i * 0.022, 1.0, 0.868 + i * 0.022, CREAM)
    for u, v, smoke in ((0.18, 0.32, False), (0.50, 0.62, True),
                        (0.80, 0.28, False)):
        sc.poly([(u, v - 0.20), (u + 0.025, v - 0.04),
                 (u + 0.13, v + 0.03), (u + 0.025, v + 0.06),
                 (u + 0.018, v + 0.18), (u - 0.018, v + 0.18),
                 (u - 0.025, v + 0.06), (u - 0.13, v + 0.03),
                 (u - 0.025, v - 0.04)], CREAM)
        sc.rect(u - 0.008, v - 0.15, u + 0.008, v - 0.02, GOLD)
        if smoke:
            for j in range(3):
                sc.disc(u + 0.11 + j * 0.06, v - 0.14 - j * 0.07,
                        sc.h * (0.07 - j * 0.014), SMOKE)


def scene_measles(sc):
    """A horizontal syringe and nine small virus circles above it."""
    sc.rect(0.02, 0.58, 0.40, 0.70, CREAM)
    sc.rect(0.0, 0.54, 0.04, 0.74, CREAM)
    sc.rect(0.40, 0.61, 0.54, 0.67, CREAM)
    sc.rect(0.54, 0.63, 0.68, 0.65, SMOKE)
    sc.rect(0.06, 0.42, 0.11, 0.86, GOLD)
    sc.rect(0.21, 0.50, 0.26, 0.78, GOLD)
    for i in range(9):
        u = 0.72 + (i % 3) * 0.095
        v = 0.10 + (i // 3) * 0.20
        sc.disc(u, v, max(1, sc.h * 0.07), GOLD)


def scene_satellites(sc):
    """Stars, the blue arc of Earth, five paneled satellites."""
    for u, v in ((0.06, 0.10), (0.20, 0.28), (0.38, 0.08), (0.56, 0.24),
                 (0.72, 0.10), (0.90, 0.28), (0.66, 0.42), (0.14, 0.42)):
        sc.disc(u, v, 1.4, WHITE)
    sc.disc(0.92, 1.06, sc.h * 0.50, WATER)
    sc.disc(0.92, 1.06, sc.h * 0.42, tint(WATER, 0.26))
    for u, v in ((0.24, 0.62), (0.48, 0.72), (0.70, 0.60), (0.40, 0.36),
                 (0.60, 0.20)):
        sc.rect(u - 0.055, v - 0.025, u - 0.012, v + 0.025, GOLD)
        sc.rect(u + 0.012, v - 0.025, u + 0.055, v + 0.025, GOLD)
        sc.rect(u - 0.010, v - 0.035, u + 0.010, v + 0.035, CREAM)


def scene_parade(sc):
    """Three tethered balloons, a building silhouette, slanting rain."""
    sc.rect(0.02, 0.10, 0.22, 0.24, CREAM)
    sc.disc(0.12, 0.17, sc.h * 0.10, CREAM)
    sc.disc(0.19, 0.17, sc.h * 0.07, shade(CREAM, 0.94))
    for u, wd, ht in ((0.0, 0.12, 0.42), (0.11, 0.10, 0.58),
                      (0.21, 0.13, 0.34), (0.34, 0.09, 0.50),
                      (0.43, 0.12, 0.28)):
        sc.rect(u, 0.92 - ht, u + wd, 0.92, shade(sc.top, 0.45))
    for i in range(7):
        sc.line(0.02 + i * 0.09, 0.0, -0.02 + i * 0.09, 0.20, 1, CREAM)
    for u, v, r, col in ((0.62, 0.30, 0.20, GOLD), (0.79, 0.20, 0.17, CREAM),
                         (0.92, 0.34, 0.14, GOLD)):
        sc.disc(u, v, sc.h * r, col)
        sc.line(u, v + r, u, 0.90, 1, CREAM)


def scene_chess(sc):
    """A six-by-four board and a king."""
    for j in range(4):
        for i in range(6):
            col = CREAM if (i + j) % 2 == 0 else shade(CREAM, 0.34)
            sc.rect(0.03 + i * 0.095, 0.20 + j * 0.175,
                    0.125 + i * 0.095, 0.375 + j * 0.175, col)
    sc.rect(0.66, 0.78, 0.84, sc.base, CREAM)
    sc.rect(0.69, 0.64, 0.81, 0.80, CREAM)
    sc.disc(0.75, 0.58, sc.h * 0.09, CREAM)
    sc.rect(0.73, 0.40, 0.77, 0.52, CREAM)
    sc.rect(0.71, 0.32, 0.74, 0.42, CREAM)
    sc.rect(0.76, 0.30, 0.79, 0.42, CREAM)
    sc.rect(0.80, 0.34, 0.83, 0.42, CREAM)


def scene_mumbai(sc):
    """The Gateway of India arch, three candles, a strip of sea."""
    sc.rect(0.02, 0.26, 0.60, sc.base, CREAM)
    sc.poly([(0.0, 0.28), (0.31, 0.06), (0.62, 0.28)], CREAM)
    sc.rect(0.16, 0.48, 0.46, sc.base, INK)
    sc.disc(0.31, 0.48, sc.w * 0.085, INK)
    sc.rect(0.22, 0.40, 0.40, 0.50, CREAM)
    sc.rect(0.0, 0.88, 1.0, 0.94, WATER)
    for u in (0.68, 0.77, 0.86):
        sc.rect(u, 0.56, u + 0.05, sc.base, CREAM)
        sc.poly([(u + 0.012, 0.56), (u + 0.025, 0.40),
                 (u + 0.038, 0.56)], GOLD)


def scene_treaty(sc):
    """A blue field with twelve gold stars in a ring, and a white paper."""
    sc.rect(0.04, 0.08, 0.44, 0.94, tint(WATER, 0.14))
    sc.ring(0.24, 0.50, sc.h * 0.30, GOLD, max(1, sc.h * 0.055))
    sc.rect(0.52, 0.14, 0.88, 0.90, WHITE)
    for v in (0.28, 0.40, 0.52, 0.64):
        sc.rect(0.56, v, 0.84, v + 0.05, shade(WATER, 0.88))
    sc.rect(0.56, 0.76, 0.68, 0.82, GOLD)


def scene_court(sc):
    """A courthouse with a pediment on four columns and a red flag."""
    sc.poly([(0.04, 0.40), (0.48, 0.10), (0.92, 0.40)], CREAM)
    sc.rect(0.04, 0.40, 0.92, 0.48, CREAM)
    for u in (0.08, 0.27, 0.46, 0.65):
        sc.rect(u, 0.48, u + 0.10, 0.90, CREAM)
    sc.rect(0.02, 0.88, 0.94, sc.base, CREAM)
    sc.rect(0.72, 0.04, 0.75, 0.44, SMOKE)
    sc.poly([(0.75, 0.06), (0.93, 0.12), (0.75, 0.20)], RED)


def scene_kremlin(sc):
    """A brick wall, three green-roofed towers, a red star, two ships.

    Drawn in literal pixels for the 238x50 tile box: the wall is the
    bottom 14 px, so it takes the place of the usual 12 px ground strip.
    """
    wall_top = 36
    sc.box_px(0, wall_top, 238, 50 - wall_top, BRICK)
    sc.box_px(0, wall_top, 238, 2, shade(BRICK, 1.18))
    for mx in range(0, 238, 16):
        sc.box_px(mx, wall_top + 4, 1, 10, shade(BRICK, 0.72))

    def tower(cx, width, roof_h, body_h):
        x0 = cx - width // 2
        top = wall_top - body_h
        sc.box_px(x0, top, width, body_h, tint(BRICK, 0.10))
        sc.box_px(x0 + 2, top + 4, 3, 4, INK)
        sc.box_px(x0 + width - 6, top + 4, 3, 4, INK)
        sc.poly_px([(x0 - 3, top), (cx, top - roof_h), (x0 + width + 3, top)],
                   ROOF)
        sc.box_px(cx - 1, top - roof_h + 3, 2, roof_h - 3, shade(ROOF, 0.78))
        return top - roof_h

    # Towers stand 26, 36, 26 px tall (body plus roof) above the wall;
    # the middle one reaches the top edge, since 14 + 36 = 50.
    tower(60, 22, 10, 16)
    apex = tower(119, 24, 12, 24)
    tower(178, 22, 10, 16)
    sc.star_px(119, apex + 5, 4, RED)

    # Harbour at the right of the wall, with two separate 20x6 hulls.
    sc.box_px(192, wall_top - 8, 44, 8, WATER)
    for hx in (194, 217):
        sc.box_px(hx, wall_top - 7, 20, 6, SMOKE)
        sc.box_px(hx + 13, wall_top - 10, 4, 3, shade(SMOKE, 0.82))
        sc.box_px(hx + 4, wall_top - 5, 3, 3, INK)


def scene_summit(sc):
    """A cream oval table, eight chairs, three gold coins, two flags."""
    cx, cy = 119, 27
    sc.oval_px(cx, cy, 55, 12, CREAM)
    for dx, dy in RING8:
        sc.disc_px(int(cx + dx * 66), int(cy + dy * 19), 2.5, WHITE)
    # Three r=6 coins stacked in a pile: the front one is drawn last.
    for i in range(3):
        yy = cy + 4 - i * 5
        sc.disc_px(cx, yy, 6, shade(GOLD, 0.82))
        sc.disc_px(cx, yy, 5, GOLD)
        sc.disc_px(cx, yy - 1, 2, tint(GOLD, 0.45))
    for fx in (22, 202):
        sc.box_px(fx + 6, 8, 2, 24, SMOKE)
        sc.box_px(fx, 10, 14, 10, tint(WATER, 0.14))
        for dx, dy in RING8:
            sc.disc_px(fx + 7 + int(dx * 3.4), 15 + int(dy * 2.4), 1, GOLD)


def scene_servers(sc):
    """Two server cabinets with gold LEDs, and a GPU card in front."""
    for x0 in (12, 70):
        sc.box_px(x0, 8, 54, 38, shade(CREAM, 0.86))
        sc.box_px(x0, 8, 54, 3, CREAM)
        for row in range(4):
            sy = 14 + row * 8
            sc.box_px(x0 + 5, sy, 34, 5, INK)
            sc.box_px(x0 + 42, sy + 1, 3, 3, GOLD)
            sc.box_px(x0 + 47, sy + 1, 3, 3, GOLD if row % 2 == 0 else SMOKE)
    sc.box_px(136, 12, 96, 30, CREAM)
    sc.box_px(148, 18, 40, 18, INK)
    sc.box_px(152, 22, 32, 10, shade(GOLD, 0.55))
    for i in range(10):
        sc.box_px(140 + i * 9, 34, 5, 4, GOLD)
    sc.box_px(136, 12, 4, 30, shade(CREAM, 0.62))


SCENES = {
    "ebola": scene_ebola,
    "niger": scene_niger,
    "mine": scene_mine,
    "gaza": scene_gaza,
    "nepal": scene_nepal,
    "jets": scene_jets,
    "measles": scene_measles,
    "satellites": scene_satellites,
    "parade": scene_parade,
    "chess": scene_chess,
    "mumbai": scene_mumbai,
    "treaty": scene_treaty,
    "court": scene_court,
    "kremlin": scene_kremlin,
    "summit": scene_summit,
    "servers": scene_servers,
}


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
# 472x122 px a continent is a silhouette, not a coastline.  Small, news-
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


PIN_R = 8
PIN_MIN_GAP = 16
PIN_SHIFT = 12

# The v6 map packs five European pins into about 60 px, so pins are
# nudged from their true projection by at most PIN_SHIFT px, always onto
# land and, for Europe, never below 44N (further south the map's Europe
# polygon is the Maghreb).  Measured shifts from the 27 Nov 2026 render:
#   pin  2 Moscow   10.0 -> (807,103)   pin  7 Brussels  6.7 -> (776,102)
#   pin 10 Geneva   11.2 -> (787,114)   pin 12 London    5.8 -> (762,110)
#   pin  5 Nepal     5.7   pin 8 Singapore 8.9   pin 13 Myanmar 5.0
#   pin  3 Jakarta   1.0   pins 1,4,6,9,11 sit on their true coordinates
# Moscow and Kharkiv project 6 px apart, at (817,103) and (823,103), so
# Moscow moves west to (807,103); the chess pin at Geneva slides to
# (787,114) and Brussels to (776,102) to clear London at (762,110).


def _pin_offsets():
    out = []
    for dx in range(-PIN_SHIFT, PIN_SHIFT + 1):
        for dy in range(-PIN_SHIFT, PIN_SHIFT + 1):
            d2 = dx * dx + dy * dy
            if d2 <= PIN_SHIFT * PIN_SHIFT:
                out.append((round(d2 ** 0.5, 3), abs(dx) + abs(dy), dx, dy))
    out.sort()
    return [(dx, dy) for _, _, dx, dy in out]


PIN_OFFSETS = _pin_offsets()


def _pin_candidates(items):
    cand = []
    for it in sorted([i for i in items if i["featured"]],
                     key=lambda i: i["rank"]):
        bx, by = proj(it["lon"], it["lat"])
        opts = []
        for dx, dy in PIN_OFFSETS:
            x, y = bx + dx, by + dy
            if not (MAP_X0 + PIN_R + 1 <= x <= MAP_X1 - PIN_R - 1):
                continue
            if not (MAP_Y0 + PIN_R + 1 <= y <= MAP_Y1 - PIN_R - 1):
                continue
            lon, lat = unproj(x, y)
            if not point_in_land(lon, lat):
                continue
            # A US story must never be nudged into Canada.
            if it["region"] == "North America" and lat > 49.5:
                continue
            # A nudged European pin must stay in Europe, so the chess pin
            # cannot slide south into Algeria to find room.  44N is the
            # floor: below it the map's Europe polygon is the Maghreb.
            if it["region"] == "Europe" and not (
                    -12.0 <= lon <= 45.0 and 44.0 <= lat <= 71.5):
                continue
            opts.append((x, y))
        cand.append((it, bx, by, opts))
    return cand


def pin_layout(items):
    """One (x, y) per featured item: nearest on-land spot, 16 px apart.

    With Moscow (rank 2) and Kharkiv (rank 6) projecting 6 px apart the
    plain rank-order depth-first search blew up, so pins are placed
    most-constrained-first (fewest on-land offsets inside the 12 px
    budget) and every step forward-checks that the pins still to come
    keep a legal slot.  Ties break on rank, so the result stays a pure
    function of the data.
    """
    cand = _pin_candidates(items)
    order = sorted(range(len(cand)),
                   key=lambda i: (len(cand[i][3]), cand[i][0]["rank"]))
    placed = []
    chosen = [None] * len(cand)
    budget = [200000]

    def free(x, y):
        for px, py in placed:
            if (x - px) ** 2 + (y - py) ** 2 < PIN_MIN_GAP ** 2:
                return False
        return True

    def solve(k):
        if k == len(order):
            return True
        i = order[k]
        for x, y in cand[i][3]:
            budget[0] -= 1
            if budget[0] < 0:
                return False
            if not free(x, y):
                continue
            placed.append((x, y))
            chosen[i] = (x, y)
            # Forward check: every pin still to come must keep a slot.
            alive = True
            for j in order[k + 1:]:
                if not any(free(ox, oy) for ox, oy in cand[j][3]):
                    alive = False
                    break
            if alive and solve(k + 1):
                return True
            placed.pop()
            chosen[i] = None
        return False

    if not solve(0):
        fail("PINS do not fit")
    pins = []
    for (it, bx, by, _), (x, y) in zip(cand, chosen):
        pins.append({"id": it["id"], "x": x, "y": y, "rank": it["rank"],
                     "featured": True, "region": it["region"],
                     "lon": it["lon"], "lat": it["lat"]})
    dots = []
    for it in sorted([i for i in items if not i["featured"]],
                     key=lambda i: i["id"]):
        x, y = proj(it["lon"], it["lat"])
        if any((x - p["x"]) ** 2 + (y - p["y"]) ** 2
               < (PIN_R + 4) ** 2 for p in pins):
            continue
        dots.append({"id": it["id"], "x": x, "y": y, "region": it["region"]})
    return pins, dots


def draw_map(buf, items):
    fill_rect(buf, MAP_X, MAP_Y, MAP_W, MAP_H, PANEL)
    stroke_rect(buf, MAP_X, MAP_Y, MAP_W, MAP_H, PANEL_EDGE)
    draw_text(buf, MAP_X0, 68, "WHERE IT HAPPENED", 2, MUTED)

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

    pins, dots = pin_layout(items)
    for dot in dots:
        # A 4x4 px dot, as specified; the numbered pins are 16 px discs.
        fill_rect(buf, dot["x"] - 2, dot["y"] - 2, 4, 4,
                  REGION_COLOR[dot["region"]])

    for pin in sorted(pins, key=lambda p: p["rank"]):
        color = REGION_COLOR[pin["region"]]
        # White disc with a region-coloured ring; the rank digit is 7 px
        # tall (scale 1), so two digits still fit inside a 16 px pin.
        fill_circle(buf, pin["x"], pin["y"], PIN_R, color)
        fill_circle(buf, pin["x"], pin["y"], PIN_R - 2, WHITE)
        label = str(pin["rank"])
        tw = text_width(label, 1)
        draw_text(buf, pin["x"] - tw // 2, pin["y"] - 3, label, 1, INK)


def draw_badge(buf, x, y, label, height=14):
    w = max(20, text_width(label, 2) + 8)
    fill_rect(buf, x, y, w, height, WHITE)
    draw_text(buf, x + (w - text_width(label, 2)) // 2,
              y + (height - 14) // 2, label, 2, BADGE_INK)
    return w


def draw_status_row(buf, it, x, y, limit):
    """Status pill plus short source name; returns the right edge used."""
    status = it["status"]
    source = it["source"]
    w = text_width(status, 2) + 6
    fill_rect(buf, x, y, w, 14, STATUS_COLOR[status])
    draw_text(buf, x + 3, y, status, 2, INK)
    sx = x + w + 6
    draw_text(buf, sx, y, source, 2, WHITE)
    end = sx + text_width(source, 2)
    if end > limit:
        fail("OVERFLOW %d status row" % it["id"])
    return end


def status_boxes(items):
    """(label, x, y, w, h) for every status pill, in draw order."""
    out = []
    hero = [i for i in items if i["featured"] and i["rank"] == 1][0]
    out.append(("hero", HERO_X + 8, HERO_Y + 128,
                text_width(hero["status"], 2) + 6, 14))
    for idx, it in enumerate(sorted([i for i in items
                                     if i["featured"] and i["rank"] != 1],
                                    key=lambda i: i["rank"])):
        x = TILE_XS[idx % 4]
        y = TILE_YS[idx // 4]
        out.append(("tile %d" % it["rank"], x + 6, y + 140,
                    text_width(it["status"], 2) + 6, 14))
    return out


def draw_header(buf, n_stories, n_regions):
    draw_text(buf, 12, 14, "WORLD NEWS 26 NOV 2026", 4, WHITE)
    line1 = "%d STORIES, %d REGIONS" % (n_stories, n_regions)
    draw_text(buf, 1012 - text_width(line1, 2), 12, line1, 2, MUTED)
    line2 = "ALL DATED 26 NOV 2026"
    draw_text(buf, 1012 - text_width(line2, 2), 34, line2, 2, ACCENT)


def scene_box(items):
    """(label, x, y, w, h) for the hero scene and the twelve tile scenes."""
    boxes = [("hero", HERO_X + HERO_SCENE_X, HERO_Y + HERO_SCENE_Y,
              HERO_SCENE_W, HERO_SCENE_H)]
    for idx, it in enumerate(sorted([i for i in items
                                     if i["featured"] and i["rank"] != 1],
                                    key=lambda i: i["rank"])):
        boxes.append(("tile %d" % it["rank"],
                      TILE_XS[idx % 4] + SCENE_X,
                      TILE_YS[idx // 4] + SCENE_Y, SCENE_W, SCENE_H))
    return boxes


def draw_scene(buf, it, x, y, w, h):
    fn = SCENES[it["scene"]]
    fn(Scene(buf, x, y, w, h, REGION_COLOR[it["region"]]))


def draw_hero(buf, it):
    color = REGION_COLOR[it["region"]]
    fill_rect(buf, HERO_X, HERO_Y, HERO_W, HERO_H, color)
    bw = draw_badge(buf, HERO_X + 8, HERO_Y + 4, "1")
    draw_text(buf, HERO_X + 8 + bw + 8, HERO_Y + 4, it["region"], 2, WHITE)

    stat = it["big_stat"]
    # The brief fixes the hero figure at scale 6 (42 px tall, y 24..66);
    # the widest stat in the data, "12,000", is 210 px, inside the 292 px
    # column that stops at x 300.
    scale = 6
    if text_width(stat, scale) > 292:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, HERO_X + 8, HERO_Y + 24, stat, scale, WHITE)

    lines = wrap(it["headline"], 2, 292, 2)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, HERO_X + 8, HERO_Y + 74 + i * 18, line, 2, WHITE)

    draw_scene(buf, it, HERO_X + HERO_SCENE_X, HERO_Y + HERO_SCENE_Y,
               HERO_SCENE_W, HERO_SCENE_H)
    draw_status_row(buf, it, HERO_X + 8, HERO_Y + 128,
                    HERO_X + HERO_W - 8)


def tile_headline_box(it):
    """(x offset, width) of a tile headline.

    A tile's headline sits at +8 in a TILE_W-16 column, which holds 19
    characters.  "KREMLIN ACCUSES KYIV OF WIDENING WAR" splits only as
    15+20 or 20+15, so its longest line is 20 characters, 238 px: the
    only box that holds it starts at +6 and runs to the tile's last
    column.  Any headline that fits the usual column keeps it, so this
    widens one tile and leaves the other eleven untouched.
    """
    if wrap(it["headline"], 2, TILE_W - 16, 2) is not None:
        return 8, TILE_W - 16
    return 6, TILE_W - 7


def draw_tile(buf, it, x, y):
    color = REGION_COLOR[it["region"]]
    fill_rect(buf, x, y, TILE_W, TILE_H, color)
    bw = draw_badge(buf, x + 6, y + 3, str(it["rank"]))
    draw_text(buf, x + 6 + bw + 6, y + 3, SHORT_REGION[it["region"]], 2, WHITE)

    draw_scene(buf, it, x + SCENE_X, y + SCENE_Y, SCENE_W, SCENE_H)

    stat = it["big_stat"]
    # Scale 4 (28 px tall, y 76..104) as specified.  "213 MISSING" is
    # 236 px wide and will not fit the 229 px column, so that one tile
    # falls back to scale 3, which the earlier brief allowed.
    scale = 4 if text_width(stat, 4) <= TILE_W - 16 else 3
    if text_width(stat, scale) > TILE_W - 16:
        fail("OVERFLOW %d" % it["id"])
    draw_text(buf, x + 8, y + 76 + (4 - scale) * 7, stat, scale, WHITE)

    hx, hw = tile_headline_box(it)
    lines = wrap(it["headline"], 2, hw, 2)
    if lines is None:
        fail("OVERFLOW %d" % it["id"])
    for i, line in enumerate(lines):
        draw_text(buf, x + hx, y + 106 + i * 18, line, 2, WHITE)

    draw_status_row(buf, it, x + 6, y + 140, x + TILE_W - 4)


LEGEND_RIGHT = 1012
LEGEND_SWATCH = 10
LEGEND_GAP = 5
LEGEND_ITEM_GAP = 12
LEGEND_Y = 706


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
        fill_rect(buf, x, LEGEND_Y + 2, LEGEND_SWATCH, LEGEND_SWATCH,
                  REGION_COLOR[region])
        stroke_rect(buf, x, LEGEND_Y + 2, LEGEND_SWATCH, LEGEND_SWATCH, BG)
        draw_text(buf, x + LEGEND_SWATCH + LEGEND_GAP, LEGEND_Y,
                  REGION_ABBR[region], 2, MUTED)


def list_rows(items):
    """(item, text, x, y) for the 18 single-line stories, column by column."""
    out = []
    for idx, it in enumerate(items):
        col = idx // LIST_ROWS
        row = idx % LIST_ROWS
        out.append((it, it["short"], LIST_XS[col], LIST_Y0 + row * LIST_PITCH))
    return out


def draw_list(buf, items):
    draw_text(buf, 12, 706, "ALSO TODAY, %d MORE" % len(items), 2, MUTED)
    draw_legend(buf, items)
    for it, text, x, y in list_rows(items):
        fill_rect(buf, x, y + 2, 10, 10, REGION_COLOR[it["region"]])
        draw_text(buf, x + 16, y, text, 2, LIST_INK)
        if x + 16 + text_width(text, 2) > x + LIST_COL_W:
            fail("OVERFLOW %d list" % it["id"])


def date_lines():
    """(text, x, y, role) for the date-check box, title and six items."""
    out = [(DATE_TITLE, DATE_X + 12, DATE_Y + 6, "title")]
    for i, text in enumerate(DATE_ITEMS):
        col = i // 3
        row = i % 3
        out.append((text, DATE_X + 12 + col * 522,
                    DATE_Y + 30 + row * 20, "item"))
    return out


def timeline_rows():
    """The two drawn UTC lines, as news.json states them.

    They are 58 and 54 characters, 350 and 324 px at 6 px per glyph, so
    both fit the 976 px interior without moving a word.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "news.json"), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data["timeline"]["rows"]


def draw_timeline(buf, rows):
    for i, text in enumerate(rows):
        x = DATE_X + 12
        y = TIMELINE_Y + i * TIMELINE_PITCH
        draw_text(buf, x, y, text, 2, MUTED)
        if x + text_width(text, 2) > DATE_X + DATE_W - 6:
            fail("OVERFLOW timeline")
        if y + 14 > DATE_Y + DATE_H - 4:
            fail("OVERFLOW timeline bottom")


def status_legend_lines():
    """(text, x, y) for the one legend row above the date box.

    All four statuses share a single 14 px row in the band between the
    list (ends y 840) and the frame (starts y 872), in the same MUTED
    colour and 14 px size as the old lines inside the box.
    """
    out = []
    x = STATUS_LEGEND_X
    for text in STATUS_LEGEND:
        out.append((text, x, STATUS_LEGEND_Y))
        x += text_width(text, 2) + STATUS_LEGEND_GAP
    return out


def draw_status_legend(buf):
    for text, x, y in status_legend_lines():
        draw_text(buf, x, y, text, 2, MUTED)
        if x + text_width(text, 2) > DATE_X + DATE_W - 6:
            fail("OVERFLOW status legend")


def draw_date_check(buf, timeline):
    stroke_rect(buf, DATE_X, DATE_Y, DATE_W, DATE_H, RED, 2)
    for text, x, y, role in date_lines():
        color = WHITE if role == "title" else LIST_INK
        draw_text(buf, x, y, text, 2, color)
        if x + text_width(text, 2) > DATE_X + DATE_W - 6:
            fail("OVERFLOW date check")
    draw_timeline(buf, timeline)


def fail(message):
    sys.stderr.write(message + "\n")
    raise SystemExit(1)


def load_timeline():
    """The two drawn UTC lines plus the four entries behind them.

    The times are publication times for the first three reports, not the
    exact minute of the event: the brief says so and no other clock is
    invented here.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "news.json"), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    timeline = data["timeline"]
    if len(timeline["entries"]) != 4 or len(timeline["rows"]) != 2:
        fail("TIMELINE shape")
    for text in timeline["rows"]:
        for ch in text:
            if ch.upper() not in FONT:
                fail("NOGLYPH timeline %s" % ch)
    return timeline


def load_news():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "news.json"), "r", encoding="utf-8") as fh:
        items = json.load(fh)["items"]

    for it in items:
        for ch in (it["headline"] + it.get("big_stat", "") + it["region"]
                   + it.get("short", "") + it.get("source", "")
                   + it.get("status", "")):
            if ch.upper() not in FONT:
                fail("NOGLYPH %d %s" % (it["id"], ch))
        if it.get("short") and len(it["short"]) > 24:
            fail("OVERFLOW %d short" % it["id"])
        if it.get("source") and len(it["source"]) > 8:
            fail("OVERFLOW %d source" % it["id"])
        if it.get("status") not in STATUSES:
            fail("STATUS %d %s" % (it["id"], it.get("status")))
        if it["featured"]:
            if it["rank"] == 1:
                width = 292
            else:
                _hx, width = tile_headline_box(it)
            lines = wrap(it["headline"], 2, width, 2)
            if lines is None or sum(len(line) for line in lines) > 36:
                fail("OVERFLOW %d headline" % it["id"])

    featured, rest = split_items(items)
    if len(rest) != LIST_ROWS * len(LIST_XS):
        fail("LIST %d rows for %d columns" % (len(rest), len(LIST_XS)))
    return items, featured, rest


def split_items(items):
    """(featured by rank, list by region then id) — the one true ordering."""
    featured = sorted([i for i in items if i["featured"]],
                      key=lambda i: i["rank"])
    rest = sorted([i for i in items if not i["featured"]],
                  key=lambda i: (REGION_ORDER.index(i["region"]), i["id"]))
    return featured, rest


def render(items, buf=None, text=True):
    """Draw the whole poster onto a canvas and return (buf, text_log).

    check.py calls this directly so it can inspect the text boxes without
    a second render, and main() calls it once to write the PNG.  Passing
    text=False skips every string, which lets the checks prove that no
    glyph lands inside an illustration box.
    """
    global TEXT_LOG, DRAW_TEXT
    saved = TEXT_LOG
    saved_draw = DRAW_TEXT
    TEXT_LOG = [] if text else None
    DRAW_TEXT = text
    try:
        featured, rest = split_items(items)
        regions = {it["region"] for it in items}
        if buf is None:
            buf = new_canvas()
        draw_header(buf, len(items), len(regions))
        draw_hero(buf, featured[0])
        for idx, it in enumerate(featured[1:]):
            draw_tile(buf, it, TILE_XS[idx % 4], TILE_YS[idx // 4])
        draw_map(buf, items)
        draw_list(buf, rest)
        draw_status_legend(buf)
        draw_date_check(buf, timeline_rows())
        return buf, list(TEXT_LOG or ())
    finally:
        TEXT_LOG = saved
        DRAW_TEXT = saved_draw


def main():
    items, featured, rest = load_news()
    buf, _ = render(items)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), buf)


if __name__ == "__main__":
    main()
