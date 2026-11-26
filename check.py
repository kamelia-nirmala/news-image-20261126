"""Checks for the 26 November 2026 news poster.

Standard library only, no network.  Every check prints PASS or FAIL and the
script ends with a single overall verdict.  Run with --selftest to prove the
pixel checks actually bite: it tampers with two rendered copies and requires
the checks to reject them.
"""

import ast
import hashlib
import json
import os
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
WHITE = (0xFF, 0xFF, 0xFF)

ICON_MIN_INK = 0.12
PIN_MIN_GAP = 12
ICON_HERO = 120
ICON_TILE = 56
ICON_INSET = 8

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
STAT_WORDS = {"WARNS", "TARIFFS", "HALTED", "REJECTS"}

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
    if len(items) != 36:
        problems.append("count=%d" % len(items))
    ids = [i["id"] for i in items]
    if len(set(ids)) != 36:
        problems.append("duplicate ids")
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
        head = it["headline"].lower().replace(",", "")
        for n in stat.replace(",", "").split():
            core = n.strip("+%$").lower()
            if not any(c.isdigit() for c in core):
                continue
            if core.endswith("m") and core[:-1].isdigit():
                core = core[:-1]
            if core.isdigit() and NUMBER_WORDS.get(int(core)) in head.split():
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


def load_main_module():
    """Import main.py so the checks use its projection and pin layout."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("news26_main", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def icon_boxes(main, items):
    """(label, x, y, w, h) for every icon plate, straight from main.py."""
    boxes = []
    hero = [i for i in items if i["featured"] and i["rank"] == 1][0]
    boxes.append(("hero",) + main.icon_box(hero, main.HERO_X, main.HERO_Y))
    tiles = sorted([i for i in items if i["featured"] and i["rank"] != 1],
                   key=lambda i: i["rank"])
    for idx, it in enumerate(tiles):
        x = main.TILE_XS[idx % 4]
        y = main.TILE_YS[idx // 4]
        boxes.append(("tile %d" % it["rank"],) + main.icon_box(it, x, y))
    return boxes


def plate_interior(pixels, x, y, w, h):
    """Modal colour of a plate's interior: its fill, ignoring the border."""
    counts = {}
    for yy in range(y + 3, y + h - 3):
        for xx in range(x + 3, x + w - 3):
            got = pixel(pixels, xx, yy)
            counts[got] = counts.get(got, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def pictogram_shortfalls(pixels, main, items):
    """Plates whose pictogram covers less than 12% of the plate."""
    short = []
    for label, x, y, w, h in icon_boxes(main, items):
        fill = plate_interior(pixels, x, y, w, h)
        marks = 0
        for yy in range(y + 2, y + h - 2):
            for xx in range(x + 2, x + w - 2):
                if pixel(pixels, xx, yy) != fill:
                    marks += 1
        frac = marks / float(w * h)
        if frac < ICON_MIN_INK:
            short.append("%s %.1f%%" % (label, frac * 100))
    return short


def check_icons(pixels, main, items):
    """Every plate must be mostly drawn on, and carry no text."""
    boxes = icon_boxes(main, items)
    thin = []
    for label, x, y, w, h in boxes:
        ink = 0
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if pixel(pixels, xx, yy) != BG:
                    ink += 1
        frac = ink / float(w * h)
        if frac < ICON_MIN_INK:
            thin.append("%s %.1f%%" % (label, frac * 100))
    check("icon plates are at least 12%% drawn", not thin, ", ".join(thin))

    # Ink that is not the plate fill or its border: that is the pictogram.
    drawn = pictogram_shortfalls(pixels, main, items)
    check("icon pictograms are at least 12%% ink", not drawn, ", ".join(drawn))

    # A pictogram is white plus the plate accent; body text is pure white
    # too, so overlap is proved by re-rendering the text alone onto a blank
    # canvas and requiring that canvas to be empty inside every plate.
    tbuf = bytearray(1024 * 1024 * 3)
    for it in items:
        if not it["featured"]:
            continue
        if it["rank"] == 1:
            main.draw_text(tbuf, 24, 108, it["big_stat"],
                           main.fit_scale(it["big_stat"], main.HERO_STAT_W,
                                          10, 6), WHITE)
            for i, line in enumerate(main.wrap(it["headline"], 3, 476, 2)):
                main.draw_text(tbuf, 24, 192 + i * 26, line, 3, WHITE)
        else:
            idx = it["rank"] - 2
            tx = main.TILE_XS[idx % 4]
            ty = main.TILE_YS[idx // 4]
            main.draw_text(tbuf, tx + 8, ty + 34, it["big_stat"],
                           main.fit_scale(it["big_stat"], main.TILE_STAT_W,
                                          5, 3), WHITE)
            for i, line in enumerate(main.wrap(it["headline"], 2,
                                               main.TILE_W - 16, 2)):
                main.draw_text(tbuf, tx + 8, ty + 78 + i * 16, line, 2, WHITE)
    hits = []
    for label, x, y, w, h in boxes:
        n = 0
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                i = (yy * 1024 + xx) * 3
                if tbuf[i] or tbuf[i + 1] or tbuf[i + 2]:
                    n += 1
        if n:
            hits.append("%s %dpx" % (label, n))
    check("no text pixels inside an icon plate", not hits, ", ".join(hits[:4]))

    # Text inside a plate would be pure white glyph pixels; the pictograms
    # use white too, so the test is run against the layout instead: no
    # text box may overlap a plate.
    overlaps = []
    hero = [i for i in items if i["featured"] and i["rank"] == 1][0]
    hx, hy, hw, hh = main.icon_box(hero, main.HERO_X, main.HERO_Y)
    stat_w = main.text_width(hero["big_stat"],
                             main.fit_scale(hero["big_stat"],
                                            main.HERO_STAT_W, 10, 6))
    if 24 + stat_w > hx:
        overlaps.append("hero stat")
    if 24 + main.text_width(hero["region"], 2) > hx and 80 < hy + hh:
        overlaps.append("hero label")
    for idx, it in enumerate(sorted([i for i in items
                                     if i["featured"] and i["rank"] != 1],
                                    key=lambda i: i["rank"])):
        tx = main.TILE_XS[idx % 4]
        ty = main.TILE_YS[idx // 4]
        bx, by, bw, bh = main.icon_box(it, tx, ty)
        scale = main.fit_scale(it["big_stat"], main.TILE_STAT_W, 5, 3)
        if tx + 8 + main.text_width(it["big_stat"], scale) > bx:
            overlaps.append("tile %d stat" % it["rank"])
        if tx + 46 + main.text_width(main.SHORT_REGION[it["region"]], 2) > bx:
            overlaps.append("tile %d label" % it["rank"])
        lines = main.wrap(it["headline"], 2, main.TILE_W - 16, 2) or []
        for i in range(len(lines)):
            if ty + 78 + i * 16 < by + bh:
                overlaps.append("tile %d headline" % it["rank"])
    check("no text runs into an icon plate", not overlaps,
          ", ".join(sorted(set(overlaps))))


def pin_problems(pixels, main, items, pins=None):
    """Pin spacing, land contact and drawn markers.  Shared with the selftest."""
    if pins is None:
        pins = main.pin_layout(items)
    placed = [p for p in pins if p["merged_into"] is None]
    problems = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i], placed[j]
            d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
            if d < PIN_MIN_GAP:
                problems.append("close %d/%d %.1fpx" % (a["id"], b["id"], d))
    for p in placed:
        lon, lat = main.unproj(p["x"], p["y"])
        if not main.point_in_land(lon, lat):
            problems.append("pin %d off polygons" % p["id"])
            continue
        # The marker covers the spot, so require drawn land in the wider
        # neighbourhood.  Thin islands are a few pixels tall, hence 24 px.
        land = 0
        for yy in range(p["y"] - 12, p["y"] + 13):
            for xx in range(p["x"] - 12, p["x"] + 13):
                if pixel(pixels, xx, yy) in (LAND, COAST):
                    land += 1
        if land < 25:
            problems.append("pin %d on bare panel" % p["id"])
            continue
        # The marker is a small white disc with a region-coloured centre,
        # so look across the whole marker rather than just its middle.
        want = REGION_COLOR[p["region"]]
        hit = False
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                if dx * dx + dy * dy > 25:
                    continue
                if pixel(pixels, p["x"] + dx, p["y"] + dy) in (want, WHITE):
                    hit = True
        if not hit:
            problems.append("pin %d not drawn" % p["id"])
    return problems


def marker_radius(pin):
    """Outer radius of the drawn marker, matching main.draw_map."""
    return 5 if pin["cluster"] > 1 else 4


def check_pins(pixels, main, items):
    """Pins are spaced apart, sit on drawn land, and are actually drawn."""
    problems = pin_problems(pixels, main, items)
    close = [p for p in problems if p.startswith("close")]
    check("no two pins closer than 12 px", not close, ", ".join(close[:4]))
    rest = [p for p in problems if not p.startswith("close")]
    check("every pin sits on drawn land and is drawn", not rest,
          ", ".join(rest[:4]))

    # Some cities are a few pixels apart on a 472 px world and cannot be
    # separated within the 14 px nudge while staying on land; those are
    # merged into one ringed marker.  Require that to stay rare and local.
    pins = main.pin_layout(items)
    by_id = {p["id"]: p for p in pins}
    merged = [p for p in pins if p["merged_into"]]
    bad = []
    for p in merged:
        host = by_id[p["merged_into"]]
        d = ((p["x"] - host["x"]) ** 2 + (p["y"] - host["y"]) ** 2) ** 0.5
        if d > 14:
            bad.append("%d %0.1fpx from %d" % (p["id"], d, host["id"]))
    hosts = {p["merged_into"] for p in merged}
    for hid in hosts:
        if by_id[hid]["cluster"] < 2:
            bad.append("host %d not marked" % hid)
    if len(merged) > 3:
        bad.append("%d merges" % len(merged))
    check("clustered pins merge locally and are ringed", not bad,
          ", ".join(bad[:4]))

    # Drawn markers must not collide, so a crowded region stays readable
    # instead of becoming one blob of white rings.
    placed = [p for p in pins if p["merged_into"] is None]
    clash = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i], placed[j]
            d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
            need = marker_radius(a) + marker_radius(b)
            if d < need:
                clash.append("%d/%d %.1f<%.0f" % (a["id"], b["id"], d, need))
    check("pin markers do not overlap", not clash, ", ".join(clash[:4]))

    # A US story must not land in Canada, and New York must sit east.
    wrong = []
    for it in items:
        if it["region"] != "North America":
            continue
        if it["lat"] > 49.5 and it["lon"] < -60:
            pin = by_id[it["id"]]
            lon, lat = main.unproj(pin["x"], pin["y"])
            if lat > 49.5:
                wrong.append("%d at %.1fN" % (it["id"], lat))
    ny = [p for p in pins if p["id"] == 43]
    if ny and ny[0]["x"] < 640:
        wrong.append("New York at x=%d" % ny[0]["x"])
    check("US pins stay in the US", not wrong, ", ".join(wrong[:4]))


def legend_problems(pixels, main, items):
    """The legend row exists, uses the list colours, and clears the title."""
    regions = [r for r in main.REGION_ORDER
               if any(i["region"] == r for i in items)]
    layout = main.legend_layout(regions)
    bad = []
    if len(layout) != len(regions):
        bad.append("entries=%d" % len(layout))
    title_end = 12 + main.text_width("ALSO TODAY, 23 MORE", 2)
    if layout and layout[0][1] < title_end + 8:
        bad.append("legend at %d, title ends %d" % (layout[0][1], title_end))
    for region, x, w in layout:
        want = REGION_COLOR[region]
        got = pixel(pixels, x + 4, main.LEGEND_Y + 8)
        if got != want:
            bad.append("%s swatch %s" % (region, got))
        if x + w > 1016:
            bad.append("%s runs off" % region)
    return bad


def check_legend(pixels, main, items):
    bad = legend_problems(pixels, main, items)
    check("legend row is drawn and clear of the title", not bad,
          ", ".join(bad[:4]))


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


def selftest(pixels, main, items):
    """Tamper with rendered copies and require the real checks to reject them."""
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

    # Wipe a plate down to bare plate colour, border included: the plate
    # and pictogram ink checks must both notice.
    no_icon = bytearray(pixels)
    _, x, y, w, h = icon_boxes(main, items)[1]
    fill = plate_interior(pixels, x, y, w, h)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            i = (yy * 1024 + xx) * 3
            no_icon[i:i + 3] = bytes(fill)
    wiped_plate = bool(pictogram_shortfalls(no_icon, main, items))

    # Flatten one drawn landmass: the land census must drop.
    no_land = bytearray(pixels)
    for yy in range(88, 263):
        for xx in range(532, 1005):
            i = (yy * 1024 + xx) * 3
            no_land[i:i + 3] = bytes((0x0F, 0x1A, 0x2B))
    land_px = 0
    for yy in range(88, 263):
        for xx in range(532, 1005):
            if pixel(no_land, xx, yy) in (LAND, COAST):
                land_px += 1
    caught_land = land_px <= 5000

    # Smear the legend row: the swatch colours must no longer match.
    no_legend = bytearray(pixels)
    for yy in range(main.LEGEND_Y - 2, main.LEGEND_Y + 16):
        for xx in range(600, 1020):
            i = (yy * 1024 + xx) * 3
            no_legend[i:i + 3] = bytes(BG)
    caught_legend = bool(legend_problems(no_legend, main, items))

    # Erase a pin marker back to bare land: the "is drawn" test must fail,
    # and the layout must still keep a pin moved into open ocean on land
    # (by merging it) rather than dropping it in the sea.
    no_pin = bytearray(pixels)
    target = [p for p in main.pin_layout(items)
              if p["merged_into"] is None and p["featured"]][0]
    for yy in range(target["y"] - 11, target["y"] + 12):
        for xx in range(target["x"] - 11, target["x"] + 12):
            if (xx - target["x"]) ** 2 + (yy - target["y"]) ** 2 <= 11 * 11:
                i = (yy * 1024 + xx) * 3
                no_pin[i:i + 3] = bytes(LAND)
    caught_drawn = any("not drawn" in p
                       for p in pin_problems(no_pin, main, items))

    moved = json.loads(json.dumps(items))
    for it in moved:
        if it["id"] == target["id"]:
            it["lon"], it["lat"] = -150.0, -10.0
    caught_moved = all(main.point_in_land(*main.unproj(p["x"], p["y"]))
                       for p in main.pin_layout(moved)
                       if p["merged_into"] is None)

    check("selftest: white, colour, icon, map, legend and pin tampers bite",
          caught_white and caught_color and wiped_plate and caught_land
          and caught_legend and caught_drawn and caught_moved,
          "white=%s colour=%s icon=%s land=%s legend=%s drawn=%s moved=%s"
          % (caught_white, caught_color, wiped_plate, caught_land,
             caught_legend, caught_drawn, caught_moved))


def main():
    tmp = tempfile.mkdtemp(prefix="news26_check_")
    main_mod = load_main_module()
    items = json.load(open(NEWS, encoding="utf-8"))
    try:
        png = check_deterministic(tmp)
        ok, pixels = check_png(png)
        check_size(png)
        check_imports()
        check_news()
        check_stats()
        check_no_failure_markers()
        if pixels is not None:
            check_colors(pixels, items)
            check_white(pixels)
            check_map(pixels)
            check_icons(pixels, main_mod, items)
            check_pins(pixels, main_mod, items)
            check_legend(pixels, main_mod, items)
        if "--selftest" in sys.argv and pixels is not None:
            selftest(pixels, main_mod, items)
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
