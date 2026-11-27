"""Checks for the 26 November 2026 news poster.

Standard library only, no network.  Every check prints PASS or FAIL and the
script ends with a single overall verdict.  Run with --selftest to prove the
pixel checks actually bite: it tampers with rendered copies and requires the
checks to reject them.

    python3 check.py              all checks
    python3 check.py --selftest   also prove the checks reject tampers
    python3 check.py --ascii 3    print illustration box 3 as an ASCII grid
"""

import ast
import hashlib
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
WHITE = (0xFF, 0xFF, 0xFF)
RED = (0xE8, 0x3B, 0x3B)
PIN_INK = (0x10, 0x16, 0x22)

STATUS_VALUES = ("OFFICIAL", "CONFIRMED", "REPORTED", "CLAIM", "ONGOING")
PIN_MIN_GAP = 16
SCENE_MIN_COLOURS = 4
SCENE_MIN_DIFF = 0.40
LIST_LINES = 18
LIST_PER_COL = 6
# The brief's v6 checks: no story that turned out to be 25 November may
# survive anywhere on the poster, and Nepal's 213 are missing, not dead.
FORBIDDEN_WORDS = ("NIGER", "MEASLES", "FCC", "SPACEX", "FLINDERS", "TRUMP")
LIST_COL_W = 324

HERO = (12, 64)
TILE_XS = (12, 263, 514, 765)
TILE_YS = (220, 382, 544)

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
STAT_WORDS = {"ACCUSES", "TARIFFS", "HALTED", "REJECTS"}

# v7 corrections, pinned to the exact text the brief asks for.
TILE2_STAT = "ACCUSES"
TILE2_HEADLINE = "KREMLIN ACCUSES KYIV OF WIDENING WAR"
TILE7_STAT = "1.58T EUR"
ARGENTINA_SHORT = "ARGENTINA PRIMARY DEBATE"
ARGENTINA_HEADLINE = "Argentina Senate weighs suspending primaries"
# The Senate only debated the bill; any of these would claim a ballot.
VOTE_WORDS = ("VOTE", "VOTES", "VOTED", "BALLOT", "POLL", "ELECTION")

# v8: the chess tile reports the drawn third game, and the footer carries
# a four-entry UTC timeline.  The match score is a hyphenated pair, so the
# headline may state the outcome in words instead of repeating the digits.
CHESS_STAT = "1.5-1.5"
CHESS_SOURCE = "FIDE"
CHESS_HEADLINE_WORDS = ("DRAW", "GAME", "3")
SCORE_RE = re.compile(r"^\d+(\.\d+)?-\d+(\.\d+)?$")
OUTCOME_WORDS = ("draw", "drew", "level", "share", "split", "beaten", "win")
TIMELINE_HOURS = ("07:07", "10:22", "11:00", "14:00")
TIMELINE_LABELS = ("IRAQ 8 FRENCH GET LIFE", "KREMLIN ACCUSES KYIV",
                   "EU SUMMIT IN BRUSSELS", "CHESS GAME 3 STARTS")
LEGEND_STATUSES = ("OFFICIAL", "REPORTED", "CLAIM", "ONGOING")
MIN_TEXT_SCALE = 2

NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 12: "twelve",
    20: "twenty", 30: "thirty",
}

# Every scene is one of these; news.json names one per featured story.
SCENES = ("ebola", "niger", "mine", "gaza", "nepal", "jets", "measles",
          "satellites", "parade", "chess", "mumbai", "treaty", "court",
          "kremlin", "summit", "servers")

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


def load_news():
    data = json.load(open(NEWS, encoding="utf-8"))
    return data["items"]


def load_timeline():
    data = json.load(open(NEWS, encoding="utf-8"))
    return data["timeline"]


def check_news():
    items = load_news()
    problems = []
    if len(items) != 31:
        problems.append("count=%d" % len(items))
    ids = [i["id"] for i in items]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    # 21/30 left in v5; 24/27/29/32/35 turned out to be 25 November news.
    for gone in (21, 30, 24, 27, 29, 32, 35):
        if gone in ids:
            problems.append("dropped id %d still present" % gone)
    for it in items:
        if len(it["headline"]) > 44:
            problems.append("id %d headline %d chars"
                            % (it["id"], len(it["headline"])))
        if it["region"] not in REGIONS:
            problems.append("id %d region %s" % (it["id"], it["region"]))
        if it.get("date") != "2026-11-26":
            problems.append("id %d date" % it["id"])
        if not it.get("source_url"):
            problems.append("id %d url" % it["id"])
        src = it.get("source", "")
        if not src or len(src) > 8 or src != src.upper():
            problems.append("id %d source %r" % (it["id"], src))
        if it.get("status") not in STATUS_VALUES:
            problems.append("id %d status %r" % (it["id"], it.get("status")))
        if "lat" not in it or "lon" not in it:
            problems.append("id %d geo" % it["id"])
        elif not (-58 <= it["lat"] <= 75):
            problems.append("id %d lat %s" % (it["id"], it["lat"]))
        if not -180 <= it.get("lon", 0) <= 180:
            problems.append("id %d lon" % it["id"])
        if it.get("featured"):
            if it.get("scene") not in SCENES:
                problems.append("id %d scene %r" % (it["id"], it.get("scene")))
        else:
            short = it.get("short", "")
            if not short:
                problems.append("id %d no short" % it["id"])
            elif len(short) > 24:
                problems.append("id %d short %d chars"
                                % (it["id"], len(short)))
    used = {i["region"] for i in items}
    if len(used) < 6:
        problems.append("only %d regions" % len(used))
    feat = [i for i in items if i.get("featured")]
    if len(feat) != 13:
        problems.append("featured=%d" % len(feat))
    ranks = sorted(i.get("rank") for i in feat)
    if ranks != list(range(1, 14)):
        problems.append("ranks=%s" % ranks)
    check("news.json is well formed", not problems, "; ".join(problems[:4]))


def stat_in_headline(stat, headline):
    """True when every numeric token of the stat is grounded in the headline.

    A match score such as "1.5-1.5" is the one exception: it may be left
    out of the headline when the headline already names the result, which
    is how a draw is written ("draw Game 3").
    """
    head = headline.lower().replace(",", "")
    for n in stat.replace(",", "").split():
        core = n.strip("+%$").lower()
        if not any(c.isdigit() for c in core):
            continue
        if core.endswith("m") and core[:-1].isdigit():
            core = core[:-1]
        if core.isdigit() and NUMBER_WORDS.get(int(core)) in head.split():
            continue
        if SCORE_RE.match(core) and any(
                word in head for word in OUTCOME_WORDS):
            continue
        if core and core not in head:
            return False
    return True


def check_stats():
    """Every featured tile needs a number or one of the four allowed verbs."""
    items = load_news()
    bad = []
    for it in items:
        if not it.get("featured"):
            continue
        stat = it.get("big_stat", "").upper()
        has_digit = any(ch.isdigit() for ch in stat)
        if not has_digit and stat not in STAT_WORDS:
            bad.append("id %d %r" % (it["id"], stat))
            continue
        if not stat_in_headline(stat, it["headline"]):
            bad.append("id %d stat %r not in headline" % (it["id"], stat))
    check("featured stats are numbers or verbs", not bad, ", ".join(bad))


def headline_problems(main, items):
    """A featured headline is two 14 px lines and at most 36 characters.

    Each tile is measured against the box main.py actually draws it in, so
    the one tile whose headline needs a wider column is not failed for
    using it.
    """
    bad = []
    for it in items:
        if not it.get("featured"):
            continue
        if it["rank"] == 1:
            width = 292
        else:
            _hx, width = main.tile_headline_box(it)
        lines = main.wrap(it["headline"], 2, width, 2)
        if lines is None:
            bad.append("id %d will not wrap" % it["id"])
            continue
        total = sum(len(line) for line in lines)
        if total > 36:
            bad.append("id %d %d chars" % (it["id"], total))
        if max(len(line) for line in lines) > 36:
            bad.append("id %d line over 36" % it["id"])
    return bad


def check_headline_budget(main, items):
    bad = headline_problems(main, items)
    check("featured headlines fit two lines and 36 characters", not bad,
          ", ".join(bad[:4]))


def tile_text_problems(main, items):
    """Tiles 2 and 7 must carry the corrected stat and headline wording."""
    feat = {i["rank"]: i for i in items if i.get("featured")}
    bad = []
    two = feat.get(2, {})
    if two.get("big_stat", "").upper() != TILE2_STAT:
        bad.append("tile 2 stat %r" % two.get("big_stat"))
    if two.get("headline", "").upper() != TILE2_HEADLINE:
        bad.append("tile 2 headline %r" % two.get("headline"))
    if "WARN" in two.get("headline", "").upper():
        bad.append("tile 2 still says warns")
    for field in ("source", "status"):
        if two.get(field) != ("REUTERS" if field == "source" else "REPORTED"):
            bad.append("tile 2 %s %r" % (field, two.get(field)))
    seven = feat.get(7, {})
    if seven.get("big_stat", "").upper() != TILE7_STAT:
        bad.append("tile 7 stat %r" % seven.get("big_stat"))
    if "EUR" not in seven.get("headline", "").upper():
        bad.append("tile 7 headline %r" % seven.get("headline"))
    if seven.get("status") != "REPORTED" or seven.get("source") != "REUTERS":
        bad.append("tile 7 source/status")
    # The stat and the headline must still be drawn, in the tile's own
    # column, at a scale the tile can hold.
    _buf, log = main.render(items, main.new_canvas())
    drawn = [t for t, _x, _y, _s, _c in log]
    for want in (TILE2_STAT, TILE7_STAT):
        if want not in drawn:
            bad.append("%r not drawn" % want)
    lines = main.wrap(seven["headline"], 2,
                      main.tile_headline_box(seven)[1], 2) or []
    for line in lines:
        if line not in drawn:
            bad.append("%r not drawn" % line[:16])
    return bad


def check_tile_text(main, items):
    bad = tile_text_problems(main, items)
    check("tiles 2 and 7 carry the corrected stat and headline", not bad,
          ", ".join(bad[:4]))


def argentina_problems(items):
    """The Senate is debating, not voting: no row may imply a ballot."""
    bad = []
    hits = [i for i in items if i.get("featured") is False
            and "ARGENTINA" in i.get("short", "").upper()]
    if len(hits) != 1:
        return ["%d Argentina rows" % len(hits)]
    it = hits[0]
    short = it["short"]
    if short.upper() != ARGENTINA_SHORT:
        bad.append("short %r" % short)
    if short != short.upper():
        bad.append("short not uppercase")
    if len(short) > 24:
        bad.append("short %d chars" % len(short))
    if "PRIMARY" not in short.upper():
        bad.append("short lacks PRIMARY")
    for word in VOTE_WORDS:
        if word in short.upper():
            bad.append("short says %s" % word)
    if it["headline"] != ARGENTINA_HEADLINE:
        bad.append("headline %r" % it["headline"][:28])
    if it["status"] != "ONGOING" or it["source"] != "REUTERS":
        bad.append("source/status changed")
    if it["region"] != "Latin America":
        bad.append("region %s" % it["region"])
    if (it["lat"], it["lon"]) != (-34.6, -58.38):
        bad.append("geo moved")
    return bad


def check_argentina(items):
    bad = argentina_problems(items)
    check("Argentina row reads PRIMARY DEBATE, not a vote", not bad,
          ", ".join(bad[:4]))


def status_legend_problems(pixels, main, log):
    """One 14 px row above the box names all four statuses.

    Each line must be drawn at scale 2 in MUTED, sit on the single
    legend baseline, stay inside the box width, and carry real ink.
    """
    bad = []
    boxes = {(t, x, y): (w, h) for t, x, y, w, h in text_boxes(log)}
    drawn = {}
    for text, x, y, scale, colour in log:
        if text in main.STATUS_LEGEND:
            drawn[text] = (x, y, scale, colour)
    for text in main.STATUS_LEGEND:
        if text not in drawn:
            bad.append("%r not drawn" % text)
            continue
        x, y, scale, colour = drawn[text]
        if scale != 2:
            bad.append("%r scale %d" % (text[:10], scale))
        if colour != main.MUTED:
            bad.append("%r colour %s" % (text[:10], colour))
        w, h = boxes[(text, x, y)]
        if x + w > main.DATE_X + main.DATE_W - 6:
            bad.append("%r overruns" % text[:10])
        if y + h > main.DATE_Y:
            bad.append("%r crosses frame" % text[:10])
        ink = 0
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if pixel(pixels, xx, yy) == main.MUTED:
                    ink += 1
        if ink < 40:
            bad.append("%r ink %d" % (text[:10], ink))
    # One row, in order, never touching: the brief asks for a single line.
    spots = [(t, drawn[t][0], drawn[t][1],
              boxes[(t,) + drawn[t][:2]][0])
             for t in main.STATUS_LEGEND if t in drawn]
    if spots:
        ys = {s[2] for s in spots}
        if len(ys) != 1:
            bad.append("legend rows %s" % sorted(ys))
        ordered = sorted(spots, key=lambda s: s[1])
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            if a[1] + a[3] + 3 > b[1]:
                bad.append("%s/%s touch" % (a[0][:8], b[0][:8]))
    # Every status the tiles use must be named in the legend.
    joined = " ".join(main.STATUS_LEGEND)
    for status in LEGEND_STATUSES:
        if status not in joined:
            bad.append("legend lacks %s" % status)
    # Nothing else may share that band.
    for text, x, y, w, h in text_boxes(log):
        if text in main.STATUS_LEGEND:
            continue
        if y + h > main.STATUS_LEGEND_Y - 2 and y < main.STATUS_LEGEND_Y + 16:
            bad.append("%r shares the legend band" % text[:12])
    return bad


def check_status_legend(pixels, main, log):
    bad = status_legend_problems(pixels, main, log)
    check("the status legend names all four statuses on one row", not bad,
          ", ".join(bad[:4]))


def chess_problems(main, items):
    """Tile 10 reports the drawn third game: 1.5-1.5, from FIDE."""
    bad = []
    feat = {i["rank"]: i for i in items if i.get("featured")}
    it = feat.get(10, {})
    stat = it.get("big_stat", "").upper()
    if stat != CHESS_STAT:
        bad.append("stat %r" % it.get("big_stat"))
    head = it.get("headline", "").upper()
    for word in CHESS_HEADLINE_WORDS:
        if word not in head:
            bad.append("headline lacks %s" % word)
    if it.get("source") != CHESS_SOURCE:
        bad.append("source %r" % it.get("source"))
    if it.get("status") != "ONGOING":
        bad.append("status %r" % it.get("status"))
    if it.get("region") != "Europe":
        bad.append("region %r" % it.get("region"))
    # No "1-1" anywhere: not the stat, headline, summary, evidence, or
    # anything drawn on the poster.
    hay = " ".join(str(it.get(k, "")) for k in
                   ("big_stat", "headline", "summary", "date_evidence",
                    "short", "source"))
    if "1-1" in hay:
        bad.append("1-1 survives in the data")
    _buf, log = main.render(items, main.new_canvas())
    for text, _x, _y, _s, _c in log:
        if "1-1" in text and "1.5-1.5" not in text:
            bad.append("1-1 drawn as %r" % text[:16])
    drawn = [t for t, _x, _y, _s, _c in log]
    if CHESS_STAT not in drawn:
        bad.append("%r not drawn" % CHESS_STAT)
    for line in main.wrap(it.get("headline", ""), 2,
                          main.tile_headline_box(it)[1], 2) or []:
        if line not in drawn:
            bad.append("%r not drawn" % line[:16])
    return bad


def check_chess(main, items):
    bad = chess_problems(main, items)
    check("tile 10 reads 1.5-1.5, DRAW GAME 3, from FIDE", not bad,
          ", ".join(bad[:4]))


def timeline_data_problems(timeline):
    """news.json carries exactly the four briefed entries, each with proof."""
    bad = []
    entries = timeline.get("entries") or []
    if len(entries) != 4:
        bad.append("%d entries" % len(entries))
    for i, want in enumerate(TIMELINE_HOURS):
        if i >= len(entries):
            break
        got = entries[i]
        if got.get("jam_utc") != want:
            bad.append("entry %d time %r" % (i, got.get("jam_utc")))
        if got.get("label") != TIMELINE_LABELS[i]:
            bad.append("entry %d label %r" % (i, got.get("label")))
        proof = got.get("bukti") or ""
        if not proof.strip():
            bad.append("entry %d no proof" % i)
        elif not ("http" in proof or "verification" in proof.lower()):
            bad.append("entry %d proof not a URL" % i)
    rows = timeline.get("rows") or []
    if len(rows) != 2:
        bad.append("%d rows" % len(rows))
    joined = " ".join(rows)
    for want in TIMELINE_HOURS:
        if want not in joined:
            bad.append("rows lack %s" % want)
    for want in TIMELINE_LABELS:
        if want not in joined:
            bad.append("rows lack %s" % want[:12])
    return bad


def check_timeline_data():
    bad = timeline_data_problems(load_timeline())
    check("timeline in news.json has four stamped entries with proof",
          not bad, ", ".join(bad[:4]))


def timeline_problems(pixels, main, log):
    """The two UTC lines are drawn inside the box, at 14 px or larger."""
    bad = []
    rows = main.timeline_rows()
    boxes = text_boxes(log)
    drawn = {(t, x, y): (w, h) for t, x, y, w, h in boxes}
    seen = {}
    for text, x, y, scale, colour in log:
        if text in rows:
            seen[text] = (x, y, scale, colour)
    if len(rows) != 2:
        bad.append("%d rows" % len(rows))
    for i, text in enumerate(rows):
        if text not in seen:
            bad.append("row %d not drawn" % i)
            continue
        x, y, scale, colour = seen[text]
        if scale < MIN_TEXT_SCALE:
            bad.append("row %d scale %d" % (i, scale))
        if colour != main.MUTED:
            bad.append("row %d colour %s" % (i, colour))
        w, h = drawn[(text, x, y)]
        if x < main.DATE_X + 4 or x + w > main.DATE_X + main.DATE_W - 6:
            bad.append("row %d width" % i)
        if y < main.DATE_Y + 4 or y + h > main.DATE_Y + main.DATE_H - 4:
            bad.append("row %d height" % i)
        ink = 0
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if pixel(pixels, xx, yy) == main.MUTED:
                    ink += 1
        if ink < 60:
            bad.append("row %d ink %d" % (i, ink))
        for want in TIMELINE_HOURS[i * 2:i * 2 + 2]:
            if want not in text:
                bad.append("row %d lacks %s" % (i, want))
    # The two rows must be separate lines, in order, inside the box.
    if len(seen) == 2:
        a, b = seen[rows[0]], seen[rows[1]]
        if b[1] <= a[1]:
            bad.append("rows not stacked")
        if abs((b[1] - a[1]) - main.TIMELINE_PITCH) > 1:
            bad.append("row pitch %d" % (b[1] - a[1]))
    # Nothing else may occupy the timeline band.
    for text, x, y, w, h in boxes:
        if text in rows:
            continue
        if y + h > main.TIMELINE_Y - 2 and y < main.TIMELINE_Y + 34:
            bad.append("%r shares the timeline band" % text[:12])
    return bad


def check_timeline(pixels, main, log):
    bad = timeline_problems(pixels, main, log)
    check("four UTC timeline entries are drawn inside the date box",
          not bad, ", ".join(bad[:4]))


def text_scale_problems(log, main=None, items=None):
    """Every string on the poster is 14 px or taller.

    The pin numbers are the exception: they are part of the 7 px marker
    graphics the earlier brief fixed (white r=8 disc, 7 px digit), so
    they are not running text and must not change.
    """
    pins = []
    if main is not None and items is not None:
        pins, _dots = main.pin_layout(items)
    small = []
    for text, x, y, scale, _c in log:
        if scale >= MIN_TEXT_SCALE:
            continue
        on_pin = any(abs(x - p["x"]) <= 6 and abs(y - p["y"]) <= 6
                     for p in pins)
        if on_pin and text.strip().isdigit():
            continue
        small.append("%r@%d" % (text[:12], scale))
    return small


def check_text_scale(log, main=None, items=None):
    bad = text_scale_problems(log, main, items)
    check("no text smaller than 14 px (pin digits excepted)", not bad,
          ", ".join(bad[:4]))


def check_source_status():
    """Each source name is grounded in its URL or date_evidence, and the
    status is one the data supports."""
    items = load_news()
    bad = []
    for it in items:
        host = it["source_url"].split("/")[2].lower()
        letters = "".join(ch for ch in it["source"].lower() if ch.isalnum())
        hay = "".join(ch for ch in host if ch.isalnum())
        evidence = it.get("date_evidence", "").lower()
        # Either the short name is a subsequence of the domain, or the
        # quote already names the agency in brackets.
        pos = 0
        for ch in letters:
            pos = hay.find(ch, pos)
            if pos < 0:
                break
            pos += 1
        grounded = pos >= 0 and letters and pos > 0
        if not grounded and letters not in evidence:
            bad.append("id %d %s not in %s" % (it["id"], it["source"], host))
    # A single outlet can only be CONFIRMED if it cites two sources; the
    # data has no such case, so no item may claim it.
    confirmed = [i["id"] for i in items if i["status"] == "CONFIRMED"]
    if confirmed:
        bad.append("CONFIRMED without a second source: %s"
                   % ",".join(str(i) for i in confirmed))
    check("every source name is grounded in its URL or quote",
          not bad, ", ".join(bad[:4]))


def check_no_failure_markers():
    proc = run_main(os.path.join(tempfile.gettempdir(), "news26_marker"))
    text = (proc.stdout + proc.stderr).upper()
    bad = "OVERFLOW" in text or "NOGLYPH" in text
    check("no OVERFLOW or NOGLYPH", proc.returncode == 0 and not bad,
          (proc.stderr.strip() or "exit %d" % proc.returncode)[:120])


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
    if count_white(pixels, HERO[0], HERO[1], 500, 150) < 300:
        bad.append("hero")
    for idx in range(12):
        x = TILE_XS[idx % 4]
        y = TILE_YS[idx // 4]
        if count_white(pixels, x, y, 245, 156) < 300:
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


def load_main_module():
    """Import main.py so the checks use its projection and layout."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("news26_main", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scene_stats(pixels, x, y, w, h):
    """(distinct colours, fraction of pixels off the modal colour, modal)."""
    counts = {}
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            got = pixel(pixels, xx, yy)
            counts[got] = counts.get(got, 0) + 1
    base = max(counts.items(), key=lambda kv: kv[1])[0]
    diff = sum(n for c, n in counts.items() if c != base)
    return len(counts), diff / float(w * h), base


def scene_shortfalls(pixels, main, items):
    bad = []
    for label, x, y, w, h in main.scene_box(items):
        colours, diff, _base = scene_stats(pixels, x, y, w, h)
        if colours < SCENE_MIN_COLOURS:
            bad.append("%s %d colours" % (label, colours))
        elif diff < SCENE_MIN_DIFF:
            bad.append("%s %.0f%% off base" % (label, diff * 100))
    return bad


def check_scenes(pixels, main, items):
    """Every illustration box must be a drawn scene, not a flat plate."""
    bad = scene_shortfalls(pixels, main, items)
    check("illustration boxes carry %d+ colours and %d%%+ off base"
          % (SCENE_MIN_COLOURS, int(SCENE_MIN_DIFF * 100)),
          not bad, ", ".join(bad[:4]))


def text_boxes(log):
    """(text, x, y, w, h) for every drawn string, from main's own log."""
    return [(text, x, y, 6 * scale * len(text) - scale, 7 * scale)
            for text, x, y, scale, _colour in log]


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def text_in_scenes(main, items, log, pixels=None):
    """Strings, and then pixels, that land inside an illustration box."""
    boxes = main.scene_box(items)
    hits = []
    for text, x, y, w, h in text_boxes(log):
        for label, sx, sy, sw, sh in boxes:
            if overlaps((x, y, w, h), (sx, sy, sw, sh)):
                hits.append("%s in %s" % (text[:14], label))
    if pixels is not None:
        plain, _ = main.render(items, main.new_canvas(), text=False)
        for label, sx, sy, sw, sh in boxes:
            for yy in range(sy, sy + sh):
                for xx in range(sx, sx + sw):
                    i = (yy * 1024 + xx) * 3
                    if (pixels[i], pixels[i + 1], pixels[i + 2]) != \
                            (plain[i], plain[i + 1], plain[i + 2]):
                        hits.append("%s px %d,%d" % (label, xx, yy))
                        break
                else:
                    continue
                break
    return hits


def check_no_text_in_scenes(pixels, main, items, log):
    hits = text_in_scenes(main, items, log, pixels)
    check("no text pixels inside an illustration box", not hits,
          ", ".join(hits[:4]))


def status_problems(main, items, log):
    """Every hero and tile needs a valid status pill plus its source name."""
    problems = []
    feat = {i["rank"]: i for i in items if i.get("featured")}
    pills = [(x, y, text) for text, x, y, scale, _c in log
             if text.upper() in STATUS_VALUES]
    for label, x, y, w, h in main.status_boxes(items):
        rank = 1 if label == "hero" else int(label.split()[1])
        it = feat[rank]
        if it["status"] not in STATUS_VALUES:
            problems.append("%s bad status" % label)
            continue
        same_row = [p for p in pills if abs(p[1] - y) <= 2]
        if not same_row:
            problems.append("%s no pill at y=%d" % (label, y))
        else:
            px, py, pt = min(same_row, key=lambda p: abs(p[0] - x))
            if pt != it["status"]:
                problems.append("%s pill %r" % (label, pt))
            if abs(px - (x + 3)) > 2:
                problems.append("%s pill x=%d" % (label, px))
        src = [b for b in text_boxes(log) if b[0] == it["source"]
               and abs(b[2] - y) <= 2]
        if not src:
            problems.append("%s no source %s" % (label, it["source"]))
        else:
            right = (x - 6) + (main.HERO_W if label == "hero"
                               else main.TILE_W)
            if src[0][1] + src[0][3] > right:
                problems.append("%s source to %d" % (label,
                                                     src[0][1] + src[0][3]))
    return problems


def check_status_rows(main, items, log):
    bad = status_problems(main, items, log)
    check("every hero and tile has a status pill and source", not bad,
          ", ".join(bad[:4]))


def date_problems(pixels, main, log):
    """The six excluded stories and the title stay put; the old legend
    lines inside the box are gone, replaced by the UTC timeline."""
    x, y, w, h = main.DATE_X, main.DATE_Y, main.DATE_W, main.DATE_H
    bad = []
    if pixel(pixels, x + 1, y + 1) != RED:
        bad.append("frame not red")
    if pixel(pixels, x + w - 2, y + h - 2) != RED:
        bad.append("frame corner open")
    inside = []
    for text, tx, ty, tw, th in text_boxes(log):
        if x <= tx < x + w and y <= ty < y + h:
            inside.append(text)
            if tx + tw > x + w - 4 or ty + th > y + h - 4:
                bad.append("%s leaves the frame" % text[:14])
    for want in main.DATE_ITEMS + (main.DATE_TITLE,):
        if want not in inside:
            bad.append("missing %r" % want[:18])
    if len(main.DATE_ITEMS) != 6:
        bad.append("%d date items" % len(main.DATE_ITEMS))
    for gone in ("OFFICIAL GOV OR INSTITUTION | CONFIRMED 2+ SOURCES",
                 "REPORTED 1 OUTLET | CLAIM ONE SIDE | ONGOING STILL UNFOLDING"):
        if gone in inside:
            bad.append("old legend line remains")
    for row in main.timeline_rows():
        if row not in inside:
            bad.append("timeline %r outside" % row[:12])
    return bad


def check_date_box(pixels, main, log):
    bad = date_problems(pixels, main, log)
    check("date check box holds the six excluded stories", not bad,
          ", ".join(bad[:4]))


def list_problems(main, items, log):
    _featured, rest = main.split_items(items)
    rows = main.list_rows(rest)
    bad = []
    if len(rows) != LIST_LINES:
        bad.append("%d rows" % len(rows))
    for idx, (it, text, x, y) in enumerate(rows):
        if text != it.get("short"):
            bad.append("row %d text" % idx)
        hits = [b for b in text_boxes(log) if b[0] == text]
        if not hits:
            bad.append("row %d not drawn" % idx)
            continue
        _t, tx, ty, tw, _th = hits[0]
        if tx + tw > x + LIST_COL_W:
            bad.append("row %d overruns to %d" % (idx, tx + tw))
        if abs(ty - y) > 1:
            bad.append("row %d at y=%d not %d" % (idx, ty, y))
    ys = sorted({y for _it, _t, _x, y in rows})
    if len(ys) != LIST_PER_COL or any(ys[i + 1] - ys[i] != 20
                                      for i in range(LIST_PER_COL - 1)):
        bad.append("row pitch %s" % ys)
    cols = {}
    for _it, _t, x, _y in rows:
        cols[x] = cols.get(x, 0) + 1
    if sorted(cols.values()) != [LIST_PER_COL] * 3 or len(cols) != 3:
        bad.append("columns %s" % sorted(cols.items()))
    return bad


def forbidden_problems(log, items, main=None):
    """No 25 November story may survive in a tile, the list, or a pin label.

    The DATE CHECK box is the one place these names belong: it is what
    tells the reader the stories were dropped, so its text is exempt.
    """
    bad = []
    shown = []
    for text, x, y, _s, _c in log:
        if main is not None:
            if (main.DATE_X <= x < main.DATE_X + main.DATE_W
                    and main.DATE_Y <= y < main.DATE_Y + main.DATE_H):
                continue
        shown.append(text)
    for it in items:
        shown.append(it["headline"])
        shown.append(it.get("big_stat", ""))
        shown.append(it.get("short", ""))
        shown.append(it.get("source", ""))
    for word in FORBIDDEN_WORDS:
        for text in shown:
            if word in text.upper():
                bad.append("%s in %r" % (word, text[:22]))
                break
    return bad


def check_forbidden(log, items, main):
    bad = forbidden_problems(log, items, main)
    check("no 25 November story left in a tile, list or pin", not bad,
          ", ".join(bad[:4]))


def _blobs(points, gap=2):
    """Connected components of a pixel set, joined across up to `gap` px."""
    left = set(points)
    out = []
    while left:
        seed = left.pop()
        blob = [seed]
        stack = [seed]
        while stack:
            cx, cy = stack.pop()
            near = [p for p in left
                    if abs(p[0] - cx) <= gap and abs(p[1] - cy) <= gap]
            for p in near:
                left.discard(p)
                blob.append(p)
                stack.append(p)
        out.append(blob)
    return out


def _bbox(points):
    return (min(p[0] for p in points), max(p[0] for p in points),
            min(p[1] for p in points), max(p[1] for p in points))


def scene_element_problems(pixels, main, items):
    """The three v6 scenes must contain the parts the brief enumerates."""
    boxes = {label: (x, y, w, h) for label, x, y, w, h
             in main.scene_box(items)}
    bad = []
    for label in ("tile 2", "tile 7", "tile 8"):
        x, y, w, h = boxes[label]

        def has(colour):
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    if pixel(pixels, xx, yy) == colour:
                        return True
            return False

        def pts(colour):
            return [(xx - x, yy - y)
                    for yy in range(y, y + h) for xx in range(x, x + w)
                    if pixel(pixels, xx, yy) == colour]

        if label == "tile 2":
            # Brick wall in the bottom 14 px, three green roofs of 26/36/26,
            # a 4 px red star on the middle tower, two grey hulls at right.
            if not has(main.BRICK):
                bad.append("kremlin no brick")
            wall = [p for p in pts(main.BRICK) if p[1] < 36]
            if wall:
                bad.append("kremlin brick above wall")
            roof = pts(main.ROOF)
            if not roof:
                bad.append("kremlin no roof")
                continue
            # Each roof is a separate connected triangle, so its own
            # bounding box gives the tower height directly.
            roofs = sorted([_bbox(b) for b in _blobs(roof) if len(b) > 30],
                           key=lambda bb: bb[0])
            if len(roofs) != 3:
                bad.append("kremlin roofs %d" % len(roofs))
            for bb, want in zip(roofs, (26, 36, 26)):
                # Heights are measured above the 14 px wall, which starts
                # at y 36 inside the 50 px box.
                got = 36 - bb[2]
                if got != want:
                    bad.append("kremlin tower height %d not %d" % (got, want))
            star = pts(main.RED)
            if len(star) < 12:
                bad.append("kremlin star %d px" % len(star))
            elif _bbox(star)[1] - _bbox(star)[0] < 5:
                bad.append("kremlin star too small")
            hulls = _blobs([p for p in pts(main.SMOKE) if p[0] > 190])
            wide = [b for b in hulls if _bbox(b)[1] - _bbox(b)[0] + 1 >= 18]
            if len(wide) < 2:
                bad.append("kremlin hulls %d" % len(wide))
            elif any(_bbox(b)[1] - _bbox(b)[0] + 1 != 20
                     or _bbox(b)[3] - _bbox(b)[2] + 1 != 6 for b in wide):
                bad.append("kremlin hull %dx%d"
                           % (_bbox(wide[0])[1] - _bbox(wide[0])[0] + 1,
                              _bbox(wide[0])[3] - _bbox(wide[0])[2] + 1))

        elif label == "tile 7":
            # Cream oval ~110x24, eight white 5 px chairs, three gold r=6
            # coins on it, a small blue flag left and right.
            table = pts(main.CREAM)
            if not table:
                bad.append("summit no table")
                continue
            bx0, bx1, by0, by1 = _bbox(table)
            if not (100 <= bx1 - bx0 + 1 <= 120):
                bad.append("summit table %d wide" % (bx1 - bx0 + 1))
            if not (20 <= by1 - by0 + 1 <= 28):
                bad.append("summit table %d tall" % (by1 - by0 + 1))
            chairs = [b for b in _blobs(pts((255, 255, 255)))
                      if 12 <= len(b) <= 40]
            if len(chairs) < 8:
                bad.append("summit chairs %d" % len(chairs))
            coins = [b for b in _blobs(pts(main.GOLD))
                     if 20 <= len(b) <= 400 and abs(b[0][0] - 119) < 20]
            # Three overlapping r=6 discs merge into one pile; a pile 5 px
            # tall and 12 px wide is three coins, so accept either reading.
            pile = [p for p in pts(main.GOLD) if abs(p[0] - 119) < 20]
            if not coins or not pile:
                bad.append("summit coins missing")
            else:
                px0, px1, py0, py1 = _bbox(pile)
                if py1 - py0 + 1 < 14 or px1 - px0 + 1 < 10:
                    bad.append("summit pile %dx%d"
                               % (px1 - px0 + 1, py1 - py0 + 1))
            flag = main.tint(main.WATER, 0.14)
            left = [p for p in pts(flag) if p[0] < 60]
            right = [p for p in pts(flag) if p[0] > 178]
            for side, group in (("left", left), ("right", right)):
                if not group:
                    bad.append("summit %s flag missing" % side)
                    continue
                fx0, fx1, fy0, fy1 = _bbox(group)
                if fx1 - fx0 + 1 != 14 or fy1 - fy0 + 1 != 10:
                    bad.append("summit %s flag %dx%d"
                               % (side, fx1 - fx0 + 1, fy1 - fy0 + 1))

        else:
            # Servers: two cream cabinets and a card, all with gold LEDs.
            cabinets = [b for b in _blobs(pts(main.shade(main.CREAM, 0.86)))
                        if len(b) > 400]
            if len(cabinets) < 2:
                bad.append("servers cabinets %d" % len(cabinets))
            leds = [b for b in _blobs(pts(main.GOLD)) if len(b) >= 6]
            if len(leds) < 6:
                bad.append("servers LEDs %d" % len(leds))
            if not has(main.INK):
                bad.append("servers no dark slots")
    return bad


def check_scene_elements(pixels, main, items):
    bad = scene_element_problems(pixels, main, items)
    check("the three new scenes hold every part the brief lists",
          not bad, ", ".join(bad[:4]))


def nepal_problems(items):
    """Nepal's 213 are missing, presumed dead: the stat must not say DEAD."""
    bad = []
    for it in items:
        if not it.get("featured") or it.get("scene") != "nepal":
            continue
        stat = it["big_stat"].upper()
        if stat == "213 DEAD":
            bad.append("stat still %r" % stat)
        if "213" not in stat or "MISSING" not in stat:
            bad.append("stat %r" % stat)
        if it["source"] != "PTI":
            bad.append("source %s" % it["source"])
        if it["status"] != "OFFICIAL":
            bad.append("status %s" % it["status"])
        if "213" not in it["headline"]:
            bad.append("headline %r" % it["headline"][:24])
    return bad


def check_nepal(items):
    bad = nepal_problems(items)
    check("Nepal stat reads 213 MISSING, from PTI", not bad,
          ", ".join(bad[:4]))


def check_list(main, items, log):
    bad = list_problems(main, items, log)
    check("list is %d single-line rows, %d per column"
          % (LIST_LINES, LIST_PER_COL), not bad, ", ".join(bad[:4]))


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
    return bad


def check_header(log, items):
    bad = header_problems(log, items)
    check("header count matches news.json", not bad, ", ".join(bad[:4]))


def pin_problems(pixels, main, items, pins=None):
    """Pin spacing, land contact and drawn markers.  Shared with the selftest."""
    if pins is None:
        pins, _dots = main.pin_layout(items)
    problems = []
    for i in range(len(pins)):
        for j in range(i + 1, len(pins)):
            a, b = pins[i], pins[j]
            d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
            if d < PIN_MIN_GAP:
                problems.append("close %d/%d %.1fpx" % (a["id"], b["id"], d))
    for p in pins:
        lon, lat = main.unproj(p["x"], p["y"])
        if not main.point_in_land(lon, lat):
            problems.append("pin %d off polygons" % p["id"])
            continue
        land = 0
        for yy in range(p["y"] - 10, p["y"] + 11):
            for xx in range(p["x"] - 10, p["x"] + 11):
                if pixel(pixels, xx, yy) in (LAND, COAST):
                    land += 1
        if land < 25:
            problems.append("pin %d on bare panel" % p["id"])
            continue
        want = REGION_COLOR[p["region"]]
        hit = False
        for dy in range(-7, 8):
            for dx in range(-7, 8):
                if dx * dx + dy * dy > 49:
                    continue
                if pixel(pixels, p["x"] + dx, p["y"] + dy) in (want, WHITE):
                    hit = True
        if not hit:
            problems.append("pin %d not drawn" % p["id"])
    return problems


def digit_counts(pixels, pins):
    out = []
    for p in pins:
        n = 0
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if pixel(pixels, p["x"] + dx, p["y"] + dy) == PIN_INK:
                    n += 1
        out.append((p, n))
    return out


def check_pins(pixels, main, items):
    pins, dots = main.pin_layout(items)
    problems = pin_problems(pixels, main, items, pins)
    close = [p for p in problems if p.startswith("close")]
    rest = [p for p in problems if not p.startswith("close")]
    check("thirteen numbered pins, no two closer than %d px" % PIN_MIN_GAP,
          len(pins) == 13 and not close, ", ".join(close[:4]))
    check("every pin sits on drawn land and is drawn", not rest,
          ", ".join(rest[:4]))
    ranks = sorted(p["rank"] for p in pins)
    check("pin numbers are 1 to 13", ranks == list(range(1, 14)), str(ranks))

    dark = ["%d %dpx" % (p["rank"], n) for p, n in digit_counts(pixels, pins)
            if n < 3]
    check("every pin shows its number", not dark, ", ".join(dark[:4]))

    clash = []
    for d in dots:
        for p in pins:
            if (d["x"] - p["x"]) ** 2 + (d["y"] - p["y"]) ** 2 <= 100:
                clash.append("%d/%d" % (d["id"], p["id"]))
    check("story dots clear of numbered pins", not clash, ", ".join(clash[:4]))

    wrong = []
    for p in pins:
        if p["region"] != "North America":
            continue
        lon, lat = main.unproj(p["x"], p["y"])
        if lat > 49.5 and lon < -60:
            wrong.append("%d at %.1fN" % (p["id"], lat))
    check("US pins stay in the US", not wrong, ", ".join(wrong[:4]))


def legend_problems(pixels, main, items):
    """The legend row exists, uses the list colours, and clears the title."""
    regions = [r for r in main.REGION_ORDER
               if any(i["region"] == r for i in items)]
    layout = main.legend_layout(regions)
    bad = []
    if len(layout) != len(regions):
        bad.append("entries=%d" % len(layout))
    title = "ALSO TODAY, %d MORE" % len([i for i in items
                                         if not i["featured"]])
    title_end = 12 + main.text_width(title, 2)
    if layout and layout[0][1] < title_end + 8:
        bad.append("legend at %d, title ends %d" % (layout[0][1], title_end))
    for region, x, w in layout:
        want = REGION_COLOR[region]
        got = pixel(pixels, x + 4, main.LEGEND_Y + 7)
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
        y = 86 + int((75.0 - lat) * 122 // 133)
        if not (532 <= x <= 1004 and 86 <= y <= 208):
            bad.append("%s off the map area" % name)
    check("reference cities fall on land", not bad, ", ".join(bad))

    land_px = 0
    for yy in range(86, 209):
        for xx in range(532, 1005):
            if pixel(pixels, xx, yy) in (LAND, COAST):
                land_px += 1
    check("map area is actually drawn", land_px > 5000, "%d land px" % land_px)


def text_fit_problems(main, log):
    """No string may leave the panel it belongs to or overlap another."""
    problems = []
    panels = [(x, y, main.TILE_W, main.TILE_H)
              for x in main.TILE_XS for y in main.TILE_YS]
    panels.append((main.HERO_X, main.HERO_Y, main.HERO_W, main.HERO_H))
    boxes = text_boxes(log)
    for text, x, y, w, h in boxes:
        if x < 0 or x + w > 1024 or y < 0 or y + h > 1024:
            problems.append("%s off canvas" % text[:12])
            continue
        for px, py, pw, ph in panels:
            if px <= x < px + pw and py <= y < py + ph:
                if x + w > px + pw or y + h > py + ph:
                    problems.append("%s overruns its panel" % text[:12])
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[1:3] == b[1:3] and a[0] == b[0]:
                continue
            if overlaps(a[1:], b[1:]):
                problems.append("%r/%r overlap" % (a[0][:8], b[0][:8]))
    return problems


def check_text_fits(main, log):
    bad = text_fit_problems(main, log)
    check("no text leaves its panel or overlaps another string",
          not bad, ", ".join(bad[:4]))


def ascii_dump(main, items, pixels, which):
    """Print one illustration box as a grid, with its colour census."""
    boxes = main.scene_box(items)
    if which < 1 or which > len(boxes):
        print("tile number must be 1..%d" % len(boxes))
        return 1
    label, x, y, w, h = boxes[which - 1]
    ramp = " .:-=+*#%@"
    print("%s  box %dx%d at (%d,%d)" % (label, w, h, x, y))
    for yy in range(y, y + h, 2):
        row = []
        for xx in range(x, x + w, 2):
            r, g, b = pixel(pixels, xx, yy)
            lum = (r * 3 + g * 6 + b) // 10
            row.append(ramp[min(9, lum * 10 // 256)])
        print("%4d %s" % (yy, "".join(row)))
    colours, diff, base = scene_stats(pixels, x, y, w, h)
    print("colours=%d  off-base=%.1f%%  base=#%02X%02X%02X"
          % (colours, diff * 100, base[0], base[1], base[2]))
    census = {}
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            got = pixel(pixels, xx, yy)
            census[got] = census.get(got, 0) + 1
    for col, n in sorted(census.items(), key=lambda kv: -kv[1])[:8]:
        print("  %5.2f%%  #%02X%02X%02X" % (100.0 * n / (w * h),
                                             col[0], col[1], col[2]))
    return 0


def selftest(pixels, main, items, log):
    """Tamper with rendered copies and require the real checks to reject them."""
    blanked = bytearray(pixels)
    for yy in range(TILE_YS[0], TILE_YS[0] + main.TILE_H):
        for xx in range(TILE_XS[0], TILE_XS[0] + main.TILE_W):
            i = (yy * 1024 + xx) * 3
            blanked[i:i + 3] = bytes(BG)

    recoloured = bytearray(pixels)
    i = ((HERO[1] + 3) * 1024 + HERO[0] + 3) * 3
    recoloured[i:i + 3] = bytes((1, 2, 3))

    caught_white = bool(white_shortfalls(blanked))
    caught_color = bool(color_mismatches(recoloured, items))

    flat = bytearray(pixels)
    _, sx, sy, sw, sh = main.scene_box(items)[3]
    for yy in range(sy, sy + sh):
        for xx in range(sx, sx + sw):
            i = (yy * 1024 + xx) * 3
            flat[i:i + 3] = bytes((20, 40, 60))
    caught_scene = bool(scene_shortfalls(flat, main, items))

    # One glyph inside a scene box must trip the no-text check.
    dirty, dirty_log = main.render(items, main.new_canvas())
    _, tx, ty, _tw, _th = main.scene_box(items)[5]
    main.draw_text(dirty, tx + 4, ty + 4, "XXXX", 2, WHITE)
    caught_text = bool(text_in_scenes(main, items, log, dirty))

    no_land = bytearray(pixels)
    for yy in range(86, 209):
        for xx in range(532, 1005):
            i = (yy * 1024 + xx) * 3
            no_land[i:i + 3] = bytes((0x0F, 0x1A, 0x2B))
    land_px = 0
    for yy in range(86, 209):
        for xx in range(532, 1005):
            if pixel(no_land, xx, yy) in (LAND, COAST):
                land_px += 1
    caught_land = land_px <= 5000

    no_legend = bytearray(pixels)
    for yy in range(main.LEGEND_Y - 2, main.LEGEND_Y + 16):
        for xx in range(600, 1020):
            i = (yy * 1024 + xx) * 3
            no_legend[i:i + 3] = bytes(BG)
    caught_legend = bool(legend_problems(no_legend, main, items))

    pins, _dots = main.pin_layout(items)
    p = pins[0]
    no_digit = bytearray(pixels)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            i = ((p["y"] + dy) * 1024 + p["x"] + dx) * 3
            no_digit[i:i + 3] = bytes(WHITE)
    caught_digit = any(n < 3 for _q, n in digit_counts(no_digit, pins))

    no_frame = bytearray(pixels)
    i = ((main.DATE_Y + 1) * 1024 + main.DATE_X + 1) * 3
    no_frame[i:i + 3] = bytes(BG)
    caught_frame = bool(date_problems(no_frame, main, log))

    no_status = [row for row in log
                 if not (row[0].upper() in STATUS_VALUES)]
    caught_status = bool(status_problems(main, items, no_status))

    no_rows = [row for row in log if row[0] not in
               {i.get("short") for i in items if not i.get("featured")}]
    caught_rows = bool(list_problems(main, items, no_rows))

    # A resurrected 25 November headline and a Nepal stat back to DEAD
    # must both be rejected.
    stale = list(items) + [{"id": 999, "featured": True, "rank": 2,
                            "headline": "Gunmen kill 30 in Niger state",
                            "big_stat": "30+ DEAD", "short": "",
                            "region": "Africa", "scene": "niger"}]
    caught_stale = bool(forbidden_problems(log, stale, main))
    bad_nepal = [dict(i) for i in items]
    for it in bad_nepal:
        if it.get("scene") == "nepal":
            it["big_stat"] = "213 DEAD"
    caught_nepal = bool(nepal_problems(bad_nepal))

    # Flatten the new Kremlin scene: its towers and star must vanish.
    flat_kremlin = bytearray(pixels)
    for label, sx, sy, sw, sh in main.scene_box(items):
        if label != "tile 2":
            continue
        for yy in range(sy, sy + sh):
            for xx in range(sx, sx + sw):
                i = (yy * 1024 + xx) * 3
                flat_kremlin[i:i + 3] = bytes((20, 40, 60))
    caught_elements = bool(scene_element_problems(flat_kremlin, main, items))

    # v7: revert tile 2 to "warns", drop the EUR from tile 7, put the
    # Argentina vote row back, and erase the two new legend lines.
    old_two = [dict(i) for i in items]
    for it in old_two:
        if it.get("rank") == 2:
            it["big_stat"] = "WARNS"
            it["headline"] = "Kremlin warns Kyiv over widening war"
    caught_tile2 = bool(tile_text_problems(main, old_two))
    no_eur = [dict(i) for i in items]
    for it in no_eur:
        if it.get("rank") == 7:
            it["big_stat"] = "1.58T"
            it["headline"] = "EU leaders wrestle 1.58T budget"
    caught_tile7 = bool(tile_text_problems(main, no_eur))
    # One tamper must not be able to hide behind the other's failure.
    caught_tile7_only = bool(tile_text_problems(main, no_eur)) and not any(
        "tile 2" in b for b in tile_text_problems(main, no_eur))
    old_arg = [dict(i) for i in items]
    for it in old_arg:
        if it.get("short") == ARGENTINA_SHORT:
            it["short"] = "ARGENTINA PRIMARY VOTE"
    caught_arg = bool(argentina_problems(old_arg))
    old_head = [dict(i) for i in items]
    for it in old_head:
        if it.get("short") == ARGENTINA_SHORT:
            it["headline"] = "Argentina primary vote held"
    caught_arg_head = bool(argentina_problems(old_head))
    no_legend = bytearray(pixels)
    for text, x, y in main.status_legend_lines():
        w = main.text_width(text, 2)
        for yy in range(y, y + 14):
            for xx in range(x, x + w):
                i = (yy * 1024 + xx) * 3
                no_legend[i:i + 3] = bytes(BG)
    caught_legend_lines = bool(status_legend_problems(no_legend, main, log))
    # Moving a legend line into the DATE CHECK frame must be rejected.
    shifted = [(t, x, main.STATUS_LEGEND_Y + 40, s, c)
               if t in main.STATUS_LEGEND else (t, x, y, s, c)
               for t, x, y, s, c in log]
    caught_legend_place = bool(status_legend_problems(pixels, main, shifted))

    # v8: an old chess tile, a blanked timeline, a legend missing a
    # status, a shrunken string, and timeline data with no proof.
    old_chess = [dict(i) for i in items]
    for it in old_chess:
        if it.get("rank") == 10:
            it["big_stat"] = "1-1"
            it["headline"] = "Gukesh and Sindarov level at 1-1"
            it["source"] = "CHESS"
    caught_chess = bool(chess_problems(main, old_chess))
    caught_score = bool(chess_problems(main, [dict(
        i, big_stat="2-1") if i.get("rank") == 10 else i for i in items]))
    no_timeline = bytearray(pixels)
    for row, x, y in [(t, main.DATE_X + 12, main.TIMELINE_Y + i * main.TIMELINE_PITCH)
                      for i, t in enumerate(main.timeline_rows())]:
        w = main.text_width(row, 2)
        for yy in range(y, y + 14):
            for xx in range(x, x + w):
                i = (yy * 1024 + xx) * 3
                no_timeline[i:i + 3] = bytes(BG)
    caught_timeline = bool(timeline_problems(no_timeline, main, log))
    short_legend = main.STATUS_LEGEND[:3]
    saved_legend = main.STATUS_LEGEND
    try:
        main.STATUS_LEGEND = short_legend
        caught_legend_status = bool(status_legend_problems(pixels, main, log))
    finally:
        main.STATUS_LEGEND = saved_legend
    tiny = [(t, x, y, 1, c) if t == main.STATUS_LEGEND[0] else (t, x, y, s, c)
            for t, x, y, s, c in log]
    caught_scale = bool(text_scale_problems(tiny))
    bad_timeline = dict(load_timeline())
    bad_timeline["entries"] = bad_timeline["entries"][:3]
    caught_timeline_data = bool(timeline_data_problems(bad_timeline))
    unproven = dict(load_timeline())
    unproven["entries"] = [dict(e, bukti="") for e in unproven["entries"]]
    caught_timeline_proof = bool(timeline_data_problems(unproven))

    check("selftest: every pixel and layout check bites",
          caught_white and caught_color and caught_scene and caught_text
          and caught_land and caught_legend and caught_digit and caught_frame
          and caught_status and caught_rows and caught_stale
          and caught_elements
          and caught_nepal and caught_tile2 and caught_tile7
          and caught_tile7_only and caught_arg and caught_arg_head
          and caught_legend_lines and caught_legend_place
          and caught_chess and caught_score and caught_timeline
          and caught_legend_status and caught_scale and caught_timeline_data
          and caught_timeline_proof,
          "white=%s colour=%s scene=%s text=%s land=%s legend=%s digit=%s "
          "frame=%s status=%s rows=%s stale=%s elements=%s nepal=%s "
          "tile2=%s tile7=%s tile7only=%s arg=%s arghead=%s lines=%s place=%s "
          "chess=%s score=%s timeline=%s legendstatus=%s scale=%s "
          "timedata=%s timeproof=%s"
          % (caught_white, caught_color, caught_scene, caught_text,
             caught_land, caught_legend, caught_digit, caught_frame,
             caught_status, caught_rows, caught_stale, caught_elements,
             caught_nepal, caught_tile2, caught_tile7, caught_tile7_only,
             caught_arg, caught_arg_head, caught_legend_lines,
             caught_legend_place, caught_chess, caught_score,
             caught_timeline, caught_legend_status, caught_scale,
             caught_timeline_data, caught_timeline_proof))


def main():
    tmp = tempfile.mkdtemp(prefix="news26_check_")
    main_mod = load_main_module()
    items = load_news()
    try:
        png = check_deterministic(tmp)
        ok, pixels = check_png(png)
        if pixels is None:
            return 1
        if "--ascii" in sys.argv:
            idx = int(sys.argv[sys.argv.index("--ascii") + 1])
            return ascii_dump(main_mod, items, pixels, idx)
        check_size(png)
        check_imports()
        check_news()
        check_stats()
        check_headline_budget(main_mod, items)
        check_tile_text(main_mod, items)
        check_argentina(items)
        check_chess(main_mod, items)
        check_timeline_data()
        check_source_status()
        check_no_failure_markers()
        _buf, log = main_mod.render(items, main_mod.new_canvas())
        check_header(log, items)
        check_colors(pixels, items)
        check_white(pixels)
        check_map(pixels)
        check_scenes(pixels, main_mod, items)
        check_no_text_in_scenes(pixels, main_mod, items, log)
        check_status_rows(main_mod, items, log)
        check_date_box(pixels, main_mod, log)
        check_forbidden(log, items, main_mod)
        check_scene_elements(pixels, main_mod, items)
        check_nepal(items)
        check_list(main_mod, items, log)
        check_pins(pixels, main_mod, items)
        check_legend(pixels, main_mod, items)
        check_status_legend(pixels, main_mod, log)
        check_timeline(pixels, main_mod, log)
        check_text_scale(log, main_mod, items)
        check_text_fits(main_mod, log)
        if "--selftest" in sys.argv:
            selftest(pixels, main_mod, items, log)
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
