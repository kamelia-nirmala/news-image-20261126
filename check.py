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
LAND = (0x22, 0x34, 0x4F)
COAST = (0x3B, 0x52, 0x73)

HERO = (12, 64)
TILE_XS = (12, 263, 514, 765)
TILE_YS = (276, 410, 544)
CITIES = [
    ("Washington", -77.0, 38.9), ("Sao Paulo", -46.6, -23.5),
    ("London", -0.1, 51.5), ("Cairo", 31.2, 30.0),
    ("Delhi", 77.2, 28.6), ("Beijing", 116.4, 39.9),
    ("Sydney", 151.2, -33.9), ("Nairobi", 36.8, -1.3),
]

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
        if not stat or len(stat) > 7:
            problems.append("id %d stat %r" % (it["id"], stat))
            continue
        head = it["headline"].upper()
        words = {w.strip(".,:;!?'-") for w in head.split()}
        digits = stat.replace(",", "").replace(".", "")
        if stat.upper() in words:
            pass
        elif digits.isdigit() and digits in head.replace(",", ""):
            pass
        else:
            problems.append("id %d stat %r not in headline" % (it["id"], stat))
    check("news.json is well formed", not problems, "; ".join(problems[:4]))


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


def selftest(pixels):
    """Tamper with two rendered copies and require the real checks to reject them."""
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



def main():
    tmp = tempfile.mkdtemp(prefix="news26_check_")
    try:
        png = check_deterministic(tmp)
        ok, pixels = check_png(png)
        check_size(png)
        check_imports()
        check_news()
        check_no_failure_markers()
        if pixels is not None:
            items = json.load(open(NEWS, encoding="utf-8"))
            check_colors(pixels, items)
            check_white(pixels)
            check_map(pixels)
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
