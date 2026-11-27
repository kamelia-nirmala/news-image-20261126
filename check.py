"""Checks for the 26 November 2026 news poster.

Standard library only, no network.  Every check prints PASS or FAIL and the
script ends with a single overall verdict.  Run with --selftest to prove the
pixel checks actually bite: it tampers with two rendered copies and requires
the checks to reject them.
"""

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
NEWS = os.path.join(HERE, "news.json")

REGIONS = [
    "North America", "Latin America", "Europe", "Middle East",
    "Africa", "Asia", "Oceania", "Global",
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
FORBIDDEN = {"socket", "requests", "urllib", "urllib2", "PIL", "http", "ftplib"}

BG = (0x0B, 0x12, 0x20)
LAND = (0x3A, 0x55, 0x78)
COAST = (0x7C, 0x9C, 0xC4)

HERO = (12, 64)
TILE_XS = (12, 263, 514, 765)
TILE_YS = (276, 410, 544)
CITIES = [
    ("Washington", -77.0, 38.9), ("Sao Paulo", -46.6, -23.5),
    ("London", -0.1, 51.5), ("Cairo", 31.2, 30.0),
    ("Delhi", 77.2, 28.6), ("Beijing", 116.4, 39.9),
    ("Sydney", 151.2, -33.9), ("Nairobi", 36.8, -1.3),
    ("Los Angeles", -118.2, 34.0), ("Miami", -80.2, 25.8),
    ("Kyiv", 30.5, 50.5), ("Goma", 29.2, -1.7),
    ("Jakarta", 106.8, -6.2), ("Tokyo", 139.7, 35.7),
    ("Helsinki", 24.9, 60.2), ("Singapore", 103.8, 1.35),
]

# A featured stat must carry a number, or be one of these verbs.
STAT_WORDS = {"ACCUSES", "JAILS", "HALTED", "REJECTS"}

# The 25 November stories are gone for good, and so is the Macy's parade
# entry that never had a verified date.  Brazil's tariff story, the DART
# image release and the Hasina story were first reported on 25 November or
# earlier, so they are out too.  None of these names may appear again.
FORBIDDEN_WORDS = ("BRAZIL", "TARIFF", "DART", "DIMORPHOS", "HASINA",
                   "NIGER", "MEASLES", "FCC", "SPACEX", "FLINDERS",
                   "TRUMP", "MACY")

# v2's geometry, which this pass must not disturb: 13 numbered tiles,
# three list columns at the same pitch, 13 pins.  Three stories left and
# one Mumbai story came back, so the list is 19 rows in columns of 7/6/6.
TILES = 13
LIST_ROWS = 19
LIST_COL_LEN = (7, 6, 6)
PIN_COUNT = 13

# A match score is written "1.5-1.5"; the headline may name the result in
# words instead, so these two lists let the stat rule accept a draw.
SCORE_RE = re.compile(r"^\d+(\.\d+)?-\d+(\.\d+)?$")
OUTCOME_WORDS = ("draw", "drew", "level", "share", "split", "win", "beaten")

# Headlines sometimes spell a number out; the stat may still show the digit.
NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 12: "twelve",
    20: "twenty", 30: "thirty",
}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        ("  " + detail) if detail and not ok else ""))
    return ok


def read_png(path):
    """Minimal PNG reader: 8-bit RGB, filter 0 only, as main.py writes it."""
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("bad signature")
    pos = 8
    width = height = None
    idat = bytearray()
    while pos < len(blob):
        (length,) = struct.unpack(">I", blob[pos:pos + 4])
        tag = blob[pos + 4:pos + 8]
        payload = blob[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", payload[:10])
            if depth != 8 or ctype != 2:
                raise ValueError("not 8-bit RGB")
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * 3
    pixels = bytearray(width * height * 3)
    for y in range(height):
        off = y * (stride + 1)
        if raw[off] != 0:
            raise ValueError("unexpected filter %d on row %d" % (raw[off], y))
        pixels[y * stride:(y + 1) * stride] = raw[off + 1:off + 1 + stride]
    return width, height, pixels


def pixel(pixels, x, y):
    i = (y * 1024 + x) * 3
    return (pixels[i], pixels[i + 1], pixels[i + 2])


def count_white(pixels, x, y, w, h):
    total = 0
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if pixel(pixels, xx, yy) == (255, 255, 255):
                total += 1
    return total


def run_main(out_dir):
    env = dict(os.environ)
    env["MAKEFUN_OUTPUT_DIR"] = out_dir
    proc = subprocess.run([sys.executable, MAIN], cwd=HERE, env=env,
                          capture_output=True, text=True)
    return proc


def load_main_module():
    """Import main.py so the checks can read its text log and constants."""
    spec = importlib.util.spec_from_file_location("news26_main", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def imported_modules(path):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def check_png(path):
    try:
        width, height, pixels = read_png(path)
    except Exception as exc:
        return check("png is valid 1024x1024", False, str(exc)), None
    ok = width == 1024 and height == 1024
    check("png is valid 1024x1024", ok, "%dx%d" % (width, height))
    return ok, pixels


def check_size(path):
    size = os.path.getsize(path)
    check("file is at most 1000000 bytes", size <= 1000000, "%d bytes" % size)


def check_deterministic(tmp):
    a = os.path.join(tmp, "run_a")
    b = os.path.join(tmp, "run_b")
    for out in (a, b):
        proc = run_main(out)
        if proc.returncode != 0:
            return check("two runs are byte-identical", False,
                         proc.stderr.strip()[:120])
    ha = hashlib.sha256(open(os.path.join(a, "entry.png"), "rb").read()).hexdigest()
    hb = hashlib.sha256(open(os.path.join(b, "entry.png"), "rb").read()).hexdigest()
    check("two runs are byte-identical", ha == hb, ha[:16] + " vs " + hb[:16])
    return os.path.join(a, "entry.png")


def check_imports():
    stdlib = set(sys.stdlib_module_names)
    bad = []
    for path in (MAIN, os.path.join(HERE, "check.py")):
        for name in imported_modules(path):
            if name in FORBIDDEN or name not in stdlib:
                bad.append("%s: %s" % (os.path.basename(path), name))
    check("imports are stdlib only", not bad, ", ".join(sorted(bad)))


def check_news():
    items = json.load(open(NEWS, encoding="utf-8"))
    problems = []
    if len(items) != 32:
        problems.append("count=%d" % len(items))
    ids = [i["id"] for i in items]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    # The wrongly-dated stories are gone: five 25 November stories, the
    # undated Flinders fire, Brazil's tariffs, the DART images, Hasina.
    for gone in (5, 21, 24, 27, 29, 32, 34, 35):
        if gone in ids:
            problems.append("dropped id %d still present" % gone)
    for it in items:
        if len(it["headline"]) > 44:
            problems.append("id %d headline %d chars" % (it["id"], len(it["headline"])))
        if it["region"] not in REGIONS:
            problems.append("id %d region %s" % (it["id"], it["region"]))
        if it.get("date") != "2026-11-26":
            problems.append("id %d date" % it["id"])
        if not it.get("source_url"):
            problems.append("id %d url" % it["id"])
        if "lat" not in it or "lon" not in it:
            problems.append("id %d geo" % it["id"])
        elif not (-58 <= it["lat"] <= 75):
            problems.append("id %d lat %s" % (it["id"], it["lat"]))
        if not -180 <= it.get("lon", 0) <= 180:
            problems.append("id %d lon" % it["id"])
    used = {i["region"] for i in items}
    if len(used) < 6:
        problems.append("only %d regions" % len(used))
    feat = [i for i in items if i.get("featured")]
    if len(feat) != 13:
        problems.append("featured=%d" % len(feat))
    ranks = sorted(i.get("rank") for i in feat)
    if ranks != list(range(1, 14)):
        problems.append("ranks=%s" % ranks)
    for it in feat:
        stat = it.get("big_stat", "")
        if not stat or len(stat) > 11:
            problems.append("id %d stat %r" % (it["id"], stat))
            continue
        # The number in the stat must come from that story's own headline,
        # counting spelled-out numbers ("nine") and "1M" for "1 million".
        # A hyphenated match score is the one exception: the headline may
        # state the result in words ("draw Game 3") instead of digits.
        head = it["headline"].lower().replace(",", "")
        for n in stat.replace(",", "").split():
            core = n.strip("+%$").lower()
            if not any(c.isdigit() for c in core):
                continue
            if core.endswith("m") and core[:-1].isdigit():
                core = core[:-1]
            if core.isdigit() and NUMBER_WORDS.get(int(core)) in head.split():
                continue
            if (SCORE_RE.match(core)
                    and any(w in head for w in OUTCOME_WORDS)):
                continue
            if core and core not in head:
                problems.append("id %d stat %r not in headline" % (it["id"], stat))
                break
    check("news.json is well formed", not problems, "; ".join(problems[:4]))


def check_stats():
    """Every featured tile needs a number or one of the four allowed verbs."""
    items = json.load(open(NEWS, encoding="utf-8"))
    bad = []
    for it in items:
        if not it.get("featured"):
            continue
        stat = it.get("big_stat", "").upper()
        has_digit = any(ch.isdigit() for ch in stat)
        if not has_digit and stat not in STAT_WORDS:
            bad.append("id %d %r" % (it["id"], stat))
    check("featured stats are numbers or verbs", not bad, ", ".join(bad))


def color_mismatches(pixels, items):
    feat = {i["rank"]: i for i in items if i.get("featured")}
    bad = []
    hx, hy = HERO
    if pixel(pixels, hx + 3, hy + 3) != REGION_COLOR[feat[1]["region"]]:
        bad.append("hero")
    for idx in range(2, 14):
        x = TILE_XS[(idx - 2) % 4]
        y = TILE_YS[(idx - 2) // 4]
        if pixel(pixels, x + 3, y + 3) != REGION_COLOR[feat[idx]["region"]]:
            bad.append("tile %d" % idx)
    return bad


def white_shortfalls(pixels):
    bad = []
    if count_white(pixels, HERO[0], HERO[1], 500, 204) < 300:
        bad.append("hero")
    for idx in range(12):
        x = TILE_XS[idx % 4]
        y = TILE_YS[idx // 4]
        if count_white(pixels, x, y, 246, 128) < 300:
            bad.append("tile %d" % (idx + 2))
    return bad


def check_colors(pixels, items):
    bad = color_mismatches(pixels, items)
    check("region colour at hero and tiles", not bad, ", ".join(bad))


def check_white(pixels):
    bad = white_shortfalls(pixels)
    check("hero and tiles carry white ink", not bad, ", ".join(bad))



def load_landmasses():
    """Read LANDMASSES out of main.py so there is a single source of truth."""
    with open(MAIN, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=MAIN)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "LANDMASSES":
                    return ast.literal_eval(node.value)
    raise ValueError("LANDMASSES not found in main.py")


def inside_any(polys, lon, lat):
    for points in polys.values():
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


def check_map(pixels):
    """Each reference city must fall inside a land polygon and be drawn there."""
    polys = load_landmasses()
    bad = []
    for name, lon, lat in CITIES:
        if not inside_any(polys, lon, lat):
            bad.append("%s outside polygons" % name)
            continue
        x = 532 + int((lon + 180.0) * 472 // 360)
        y = 88 + int((75.0 - lat) * 174 // 133)
        if not (532 <= x <= 1004 and 88 <= y <= 262):
            bad.append("%s off the map area" % name)
    check("reference cities fall on land", not bad, ", ".join(bad))

    land_px = 0
    for yy in range(88, 263):
        for xx in range(532, 1005):
            if pixel(pixels, xx, yy) in (LAND, COAST):
                land_px += 1
    check("map area is actually drawn", land_px > 5000, "%d land px" % land_px)



def check_no_failure_markers():
    proc = run_main(os.path.join(tempfile.gettempdir(), "news26_marker"))
    text = (proc.stdout + proc.stderr).upper()
    bad = "OVERFLOW" in text or "NOGLYPH" in text
    check("no OVERFLOW or NOGLYPH", proc.returncode == 0 and not bad,
          (proc.stderr.strip() or "exit %d" % proc.returncode)[:120])


def text_boxes(log):
    """(text, x, y, w, h) for every drawn string, from main's own log."""
    return [(text, x, y, 6 * scale * len(text) - scale, 7 * scale)
            for text, x, y, scale, _colour in log]


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def panel_boxes(main):
    """Every panel a string may live in: hero, twelve tiles, map, list."""
    out = [(main.HERO_X, main.HERO_Y, main.HERO_W, main.HERO_H)]
    for idx in range(12):
        out.append((main.TILE_XS[idx % 4], main.TILE_YS[idx // 4],
                    main.TILE_W, main.TILE_H))
    out.append((main.PANEL_X, main.PANEL_Y, main.PANEL_W, main.PANEL_H))
    out.append((12, 676, 1000, 1024 - 676))
    return out


def text_fit_problems(main, log):
    """No string may leave its panel, leave the canvas, or overlap another."""
    problems = []
    panels = panel_boxes(main)
    boxes = text_boxes(log)
    for text, x, y, w, h in boxes:
        if x < 0 or y < 0 or x + w > 1024 or y + h > 1024:
            problems.append("%s off canvas" % text[:14])
            continue
        for px, py, pw, ph in panels:
            if px <= x < px + pw and py <= y < py + ph:
                if x + w > px + pw or y + h > py + ph:
                    problems.append("%s overruns its panel" % text[:14])
                break
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if overlaps(a[1:], b[1:]):
                problems.append("%r/%r overlap" % (a[0][:10], b[0][:10]))
    return problems


def check_text_fits(main, log):
    bad = text_fit_problems(main, log)
    check("no text leaves its panel or overlaps another string", not bad,
          ", ".join(bad[:4]))


def forbidden_problems(log, items):
    """The dropped stories must not survive anywhere on the poster."""
    bad = []
    shown = [t for t, _x, _y, _s, _c in log]
    for it in items:
        shown.append(it["headline"])
        shown.append(it.get("big_stat", ""))
        shown.append(it.get("region", ""))
    for word in FORBIDDEN_WORDS:
        for text in shown:
            if word in text.upper():
                bad.append("%s in %r" % (word, text[:24]))
                break
    return bad


def check_forbidden(log, items):
    bad = forbidden_problems(log, items)
    check("no 25 November story left in a tile, list or pin", not bad,
          ", ".join(bad[:4]))


def chess_problems(items):
    """The chess tile reports the drawn third game, and never 1-1."""
    bad = []
    feat = {i["rank"]: i for i in items if i.get("featured")}
    it = feat.get(8, {})
    if it.get("big_stat") != "1.5-1.5":
        bad.append("stat %r" % it.get("big_stat"))
    for other in items:
        hay = " ".join(str(other.get(k, "")) for k in
                       ("big_stat", "headline", "date_evidence"))
        if "1-1" in hay and "1.5-1.5" not in hay:
            bad.append("id %d says 1-1" % other["id"])
    return bad


def check_chess(items):
    bad = chess_problems(items)
    check("chess tile reads 1.5-1.5 and no 1-1 anywhere", not bad,
          ", ".join(bad[:4]))


def evidence_problems(items):
    """Each date_evidence line must carry a dateline, and the two items the
    brief names must credit the outlet its URL actually belongs to.

    Kharkiv comes from en.h.ua and the Riyadh round-up from Khaleej Times;
    calling either "Reuters" misattributes it.  Reuters copy carried by a
    syndication host (Yahoo, ThePrint) is left alone.
    """
    bad = []
    want = {37: "en.h.ua", 40: "Khaleej Times"}
    for it in items:
        ev = it.get("date_evidence", "")
        if not ev:
            continue
        if "(" not in ev and "/" not in ev:
            bad.append("id %d evidence has no dateline" % it["id"])
    for idx, outlet in want.items():
        hit = [i for i in items if i["id"] == idx]
        if hit and outlet not in hit[0].get("date_evidence", ""):
            bad.append("id %d evidence lacks %s" % (idx, outlet))
    return bad


def check_evidence(items):
    bad = evidence_problems(items)
    check("date_evidence names the outlet the URL belongs to", not bad,
          ", ".join(bad[:4]))


def nepal_problems(items):
    """Nepal's 213 are missing, presumed dead: the stat must not say DEAD."""
    bad = []
    hits = [i for i in items if i.get("featured")
            and "NEPAL" in i["headline"].upper()]
    if len(hits) != 1:
        return ["%d Nepal tiles" % len(hits)]
    stat = hits[0]["big_stat"].upper()
    if stat == "213 DEAD":
        bad.append("stat still %r" % stat)
    if "213" not in stat or "MISSING" not in stat:
        bad.append("stat %r" % stat)
    if "DEAD" in stat:
        bad.append("stat says DEAD")
    return bad


def check_nepal(items):
    bad = nepal_problems(items)
    check("Nepal stat reads 213 MISSING, never 213 DEAD", not bad,
          ", ".join(bad[:4]))


def structure_problems(items, main):
    """13 tiles, 19 list rows in 7/6/6, 13 pins numbered 1..13."""
    bad = []
    featured, rest = main.split_items(items)
    if len(featured) != TILES:
        bad.append("%d tiles" % len(featured))
    ranks = sorted(i.get("rank") for i in featured)
    if ranks != list(range(1, TILES + 1)):
        bad.append("ranks %s" % ranks)
    if len(rest) != LIST_ROWS:
        bad.append("%d list rows" % len(rest))
    if tuple(main.LIST_COL_LEN) != LIST_COL_LEN:
        bad.append("columns %s" % (main.LIST_COL_LEN,))
    if len(featured) != PIN_COUNT:
        bad.append("%d pins" % len(featured))
    numbers = [it["number"] for it in featured] + [it["number"] for it in rest]
    if numbers != list(range(1, len(items) + 1)):
        bad.append("numbering %s" % numbers[:6])
    return bad


def check_structure(items, main):
    bad = structure_problems(items, main)
    check("13 tiles, 19 list rows in 7/6/6 and 13 pins", not bad,
          ", ".join(bad[:4]))


def mumbai_problems(items):
    """Tile 10 is Mumbai with an 18 YEARS stat, and Brazil is gone."""
    bad = []
    feat = {i["rank"]: i for i in items if i.get("featured")}
    it = feat.get(10, {})
    if "MUMBAI" not in it.get("headline", "").upper():
        bad.append("tile 10 headline %r" % it.get("headline"))
    if it.get("big_stat", "").upper() != "18 YEARS":
        bad.append("tile 10 stat %r" % it.get("big_stat"))
    if it.get("region") != "Asia":
        bad.append("tile 10 region %r" % it.get("region"))
    if not (18.5 <= it.get("lat", 0) <= 19.4
            and 72.4 <= it.get("lon", 0) <= 73.3):
        bad.append("tile 10 at %s,%s" % (it.get("lat"), it.get("lon")))
    for other in items:
        if other.get("featured") and "BRAZIL" in other["headline"].upper():
            bad.append("Brazil still featured")
    return bad


def check_mumbai(items):
    bad = mumbai_problems(items)
    check("tile 10 is Mumbai with 18 YEARS", not bad, ", ".join(bad[:4]))


def header_problems(log, items):
    n = len(items)
    regions = len({i["region"] for i in items})
    want = "%d STORIES, %d REGIONS" % (n, regions)
    texts = [t for t, _x, _y, _s, _c in log]
    bad = []
    if want not in texts:
        bad.append("no %r" % want)
    for text in texts:
        if "STORIES" in text and text != want:
            bad.append("stray %r" % text)
    if n <= 20:
        bad.append("only %d stories" % n)
    more = "ALSO TODAY, %d MORE" % (n - TILES)
    if more not in texts:
        bad.append("no %r" % more)
    return bad


def check_header(log, items):
    bad = header_problems(log, items)
    check("header count matches news.json", not bad, ", ".join(bad[:4]))


def selftest(pixels):
    """Tamper with rendered copies and require the real checks to reject them."""
    items = json.load(open(NEWS, encoding="utf-8"))

    blanked = bytearray(pixels)
    for yy in range(TILE_YS[0], TILE_YS[0] + 128):
        for xx in range(TILE_XS[0], TILE_XS[0] + 246):
            i = (yy * 1024 + xx) * 3
            blanked[i:i + 3] = bytes(BG)

    recoloured = bytearray(pixels)
    i = ((HERO[1] + 3) * 1024 + HERO[0] + 3) * 3
    recoloured[i:i + 3] = bytes((1, 2, 3))

    caught_white = bool(white_shortfalls(blanked))
    caught_color = bool(color_mismatches(recoloured, items))
    check("selftest: blanked tile and wrong hero colour are caught",
          caught_white and caught_color,
          "white=%s colour=%s" % (caught_white, caught_color))

    main_mod = load_main_module()
    _buf, log = main_mod.render(items)

    stale = list(items) + [{
        "id": 999, "featured": True, "rank": 2, "region": "Africa",
        "headline": "Gunmen kill 30 in Niger state", "big_stat": "30+ DEAD",
        "lat": 9.0, "lon": 6.0, "date": "2026-11-26",
    }]
    caught_forbidden = bool(forbidden_problems(log, stale))

    # A resurrected Brazil tile must trip the forbidden list too.
    revived = list(items) + [{
        "id": 998, "featured": True, "rank": 10, "region": "Latin America",
        "headline": "Brazil blasts new US tariff proposals",
        "big_stat": "TARIFFS", "lat": -15.79, "lon": -47.88,
        "date": "2026-11-26",
    }]
    caught_brazil = bool(forbidden_problems(log, revived))

    no_more = [row for row in log if row[0] != "ALSO TODAY, 19 MORE"]
    caught_more = bool(header_problems(no_more, items))

    bad_chess = [dict(i) for i in items]
    for it in bad_chess:
        if it.get("rank") == 8:
            it["big_stat"] = "1-1"
            it["headline"] = "Gukesh and Sindarov level at 1-1"
    caught_chess = bool(chess_problems(bad_chess))

    bad_nepal = [dict(i) for i in items]
    for it in bad_nepal:
        if "NEPAL" in it["headline"].upper():
            it["big_stat"] = "213 DEAD"
    caught_nepal = bool(nepal_problems(bad_nepal))

    short = list(items) + [{"id": 997, "featured": False, "rank": 0,
                            "region": "Asia", "headline": "Extra row",
                            "big_stat": "", "lat": 0.0, "lon": 0.0,
                            "date": "2026-11-26"}]
    caught_structure = bool(structure_problems(short, main_mod))

    # Tile 10 back to Brazil, or to Mumbai with the wrong stat, must fail.
    bad_tile = [dict(i) for i in items]
    for it in bad_tile:
        if it.get("rank") == 10:
            it["headline"] = "Brazil blasts new US tariff proposals"
            it["big_stat"] = "TARIFFS"
    caught_mumbai = bool(mumbai_problems(bad_tile))
    bad_stat = [dict(i) for i in items]
    for it in bad_stat:
        if it.get("rank") == 10:
            it["big_stat"] = "18 DEAD"
    caught_mumbai = caught_mumbai and bool(mumbai_problems(bad_stat))

    # A string pushed past its tile edge must be rejected.
    pushed = [(t, x + 200 if t == "13 DEAD" else x, y, s, c)
              for t, x, y, s, c in log]
    caught_fit = bool(text_fit_problems(main_mod, pushed))

    # Reuters dateline over a non-Reuters URL must be rejected.
    bad_ev = [dict(i) for i in items]
    for it in bad_ev:
        if it["id"] == 37:
            it["date_evidence"] = "KHARKIV, November 26 (Reuters) - drone hit"
    caught_evidence = bool(evidence_problems(bad_ev))

    check("selftest: the content checks bite",
          caught_forbidden and caught_brazil and caught_more and caught_chess
          and caught_nepal and caught_structure and caught_mumbai
          and caught_fit and caught_evidence,
          "forbidden=%s brazil=%s more=%s chess=%s nepal=%s structure=%s "
          "mumbai=%s fit=%s evidence=%s"
          % (caught_forbidden, caught_brazil, caught_more, caught_chess,
             caught_nepal, caught_structure, caught_mumbai, caught_fit,
             caught_evidence))



def main():
    tmp = tempfile.mkdtemp(prefix="news26_check_")
    try:
        png = check_deterministic(tmp)
        ok, pixels = check_png(png)
        check_size(png)
        check_imports()
        check_news()
        check_stats()
        check_no_failure_markers()
        if pixels is not None:
            items = json.load(open(NEWS, encoding="utf-8"))
            main_mod = load_main_module()
            _buf, log = main_mod.render(items)
            check_colors(pixels, items)
            check_white(pixels)
            check_map(pixels)
            check_header(log, items)
            check_structure(items, main_mod)
            check_mumbai(items)
            check_forbidden(log, items)
            check_chess(items)
            check_nepal(items)
            check_evidence(items)
            check_text_fits(main_mod, log)
        if "--selftest" in sys.argv and pixels is not None:
            selftest(pixels)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [name for name, ok, _ in results if not ok]
    print()
    if failed:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
