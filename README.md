# World News in One Image — 26 November 2026

A single 1024x1024 PNG that sums up the world's news of Thursday 26 November 2026, drawn from scratch by a Python 3 standard-library-only script.

## What is here

| File | Contents |
|---|---|
| `main.py` | The generator. Reads `news.json`, draws the poster, writes `entry.png`. |
| `check.py` | Ten checks over the output and the data, plus a `--selftest` that proves the pixel checks fail when they should. |
| `news.json` | The 36 stories as data: `id`, `headline`, `region`, `category`, `date`, `lat`, `lon`, `featured`, `rank`, `big_stat`, `source_url`. |
| `entry.png` | The rendered poster. |
| `LICENSE` | MIT. |

`news.json` holds the day's facts and `main.py` holds the drawing code, so a factual
correction means editing one JSON field, not redoing the layout. Every story is dated
`2026-11-26` and carries a link to an article that reports it. The 13 `featured` items
carry a `rank` (1 is the hero) and a `big_stat` that is drawn from that item's own
headline — `check.py` enforces that.

## No dependencies

There is no Pillow, no numpy, nothing outside the standard library. The PNG is written
by hand in `main.py` with `struct` and `zlib` (RGB, 8-bit, filter 0, IHDR/IDAT/IEND with
`zlib.crc32`), and the type is a 5x7 bitmap font defined in the same file. There is no
network access, no clock, and no randomness, so the same input always produces the same
bytes.

## Run it

```sh
python3 main.py
```

Output goes to `$MAKEFUN_OUTPUT_DIR/entry.png`, which defaults to `/output/entry.png`.
To write somewhere else:

```sh
MAKEFUN_OUTPUT_DIR=/tmp/out python3 main.py
```

## Check it

```sh
python3 check.py            # ten checks, then PASS or FAIL
python3 check.py --selftest # also tampers with two copies to prove the checks bite
```

`check.py` re-renders the poster twice into temporary folders and compares the SHA-256
of both runs, so it needs no arguments and touches nothing in place.
