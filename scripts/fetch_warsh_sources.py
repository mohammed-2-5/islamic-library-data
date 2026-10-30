"""Fetch the two Warsh sources and cross-check them into one warsh_source.json.

The app has no Warsh mushaf yet. Two public sources describe one:

  * KFGQPC (King Fahd Complex) `warshData_v10.json` + `warsh.10.ttf`: every
    Warsh ayah with its page, its first and last line, and its text in the
    Warsh font's own code points. Ayahs are counted the Madani way: 6214.
  * open-mushaf-native: the 604 page images of the Madinah Warsh print and,
    per page, the point where every ayah ends (`aya.json`), plus the frame
    those points live in (`specs.json`), the surah table (`surah.json`) and
    the hizb table (`hizb.json`).
    The images are a Warsh text, but their ayahs are numbered by the Kufi
    count (Hafs): 6236 end points, and `surah.json` has the Kufi counts.

THE TWO SOURCES CANNOT BE JOINED BY (surah, ayah): in 50 surahs the counts
differ, so 2:5 of one is 2:6 of the other. The reference end points are
therefore kept per page, unjoined, as `refEnds`. What ties the sources to one
print is the checks below (the last ayah of every surah ends on the same page
in both) and a diagnostic that is printed and never fails.

    {"format": 1, "pages": 604, "spec": {<specs.json verbatim>},
     "ayahs": [{"s": 1, "a": 1, "p": [1], "ls": 3, "le": 3,
                "words": ["...", "... \\u00a0<marker>"]}, ...],
     "refEnds": {"1": [{"x": 181, "y": 301}, ...], "2": [...], ...}}

`p` is the page or the two consecutive pages the ayah touches, `ls`/`le` the
KFGQPC `line_start`/`line_end`, `words` the `aya_text` split on ASCII spaces
(the trailing `\\xa0<marker>` stays on the last word). A two-page ayah has
`"p": [n, n+1]` and `"split": k`: words[0..k) are on page n, the rest on n+1
(KFGQPC marks the page break with a double space; it is not a word). The one
leading space 1639 rows start with is dropped. `refEnds[page]` lists the
reference ayah-end points of that page in reading order (top line first, right
to left within a line), in the `specs.json` frame. `aya.json` entries are
[surah, ayah, V1, V2] and `AYA_JSON_ORDER` says V1 is y and V2 is x.

THE HARD CHECKS: when any fails the script names the ayah or page, prints every
failing check (first 10 each) and exits 1, writing no warsh_source.json:

  * 6214 KFGQPC rows with unique (surah, ayah) keys;
  * pages 1..604 each have a PNG Pillow opens, all one size (pages 1-2 may
    differ; the sizes are reported);
  * for every surah, its last ayah ends on the same page in both sources;
  * 1 <= ls <= 15 and 1 <= le <= 15, and ls <= le except for two-page ayahs
    (they can start on line 14 and end on line 1);
  * the words round-trip to `aya_text`, and only two-page ayahs have a page
    break.

THE DIAGNOSTIC (printed, never fails): on the pages where both sources have the
same number of ayah ends, the ends are paired in reading order and the share of
pairs whose KFGQPC `le` equals the reference marker's line is reported. The
line comes from y: `line = round((y / s - marginY) / lineHeight)` with the
`specs.json` marginY 20 and lineHeight 32.5 and s = 39.4 / 32.5, the factor
that maps the spec frame onto the end-point frame (the end points of pages
3..604 form 15 tight bands 39.4 apart, line 1 at y = 63.6). Pages 1-2 do not
follow that grid; their end points sit 26.3 apart from slot 2 at y = 301
(checked on the images: the basmala line is slot 2, the first text line 3), so
`line = 2 + round((y - 301) / 26.3)`. Both are fitted to the data, not read
from the specs, which only give the first-pages margins.

Everything downloaded lands under --out and is git-ignored: the font and the
page images are never committed and never uploaded.

Usage:
    python scripts/fetch_warsh_sources.py --out raw/warsh
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

TOTAL_PAGES = 604
TOTAL_AYAHS = 6214
LINES_PER_PAGE = 15
MAX_SHOWN = 10

KFGQPC = 'https://cdn.jsdelivr.net/gh/thetruetruth/quran-data-kfgqpc@master/warsh'
# `develop` is the default branch of adelpro/open-mushaf-native.
MUSHAF = 'https://raw.githubusercontent.com/adelpro/open-mushaf-native/develop/assets'
PRINT = 'mushaf-elmadina-warsh-azrak'

# open-mushaf `aya.json` entries are [surah, ayah, V1, V2]. Proved on page 3 /
# 2:6 = [2, 6, 106, 335]: V1 grows down the page with the ayah order (106, 146,
# 185, ...) and the dots (x=V2, y=V1) land on the ayah-end markers, while
# (x=V1, y=V2) lands in the middle of the text. So V1 is y and V2 is x.
AYA_JSON_ORDER = ('y', 'x')

# Frame constants for the diagnostic's line numbers (see the module docstring).
SPEC_LINE_HEIGHT = 32.5
SPEC_MARGIN_Y = 20
FRAME_SCALE = 39.4 / SPEC_LINE_HEIGHT
FIRST_PAGES_SLOT2_Y = 301
FIRST_PAGES_PITCH = 26.3


def fetch(url: str, dest: Path) -> Path:
    """Download `url` to `dest`, unless `dest` already exists and is not empty."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'azkar-data'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f'empty response: {url}')
    part = dest.with_name(dest.name + '.part')
    part.write_bytes(data)
    part.replace(dest)
    return dest


def split_words(aya_text: str) -> tuple[list[str], int | None]:
    """The words of an ayah, and where its page break is (or None).

    The `\\xa0<marker>` stays on the last word. One leading ASCII space (a quirk
    of 1639 rows, not a word) is dropped. A double space is KFGQPC's page break
    inside a two-page ayah: it is not a word, and `split` is the number of
    words before it.
    """
    text = aya_text.lstrip(' ')
    if '  ' not in text:
        return text.split(' '), None
    before, after = text.split('  ', 1)
    head, tail = before.split(' '), after.split(' ')
    return head + tail, len(head)


def rejoin_words(words: list[str], split: int | None, aya_text: str) -> str:
    """The inverse of `split_words`, restoring the leading space and the break."""
    lead = ' ' if aya_text.startswith(' ') else ''
    if split is None:
        return lead + ' '.join(words)
    return lead + ' '.join(words[:split]) + '  ' + ' '.join(words[split:])


def pages_of(page_field: str) -> list[int]:
    """`"5"` gives [5]; `"5-6"` (hyphen or en dash) gives [5, 6]."""
    return [int(part) for part in re.split(r'[-–]', page_field.strip())]


def ref_line(page: int, y: float) -> int:
    """The line (slot) a reference end point is on, from its y."""
    if page <= 2:
        return 2 + round((y - FIRST_PAGES_SLOT2_Y) / FIRST_PAGES_PITCH)
    return round((y / FRAME_SCALE - SPEC_MARGIN_Y) / SPEC_LINE_HEIGHT)


def ref_ends(aya_json: dict) -> dict[int, list[dict]]:
    """page -> reference end points in reading order: {x, y, surah, ayah}."""
    iy, ix = AYA_JSON_ORDER.index('y'), AYA_JSON_ORDER.index('x')
    pages: dict[int, list[dict]] = {}
    for page, entries in enumerate(aya_json['coordinates']):
        if page == 0:
            continue
        points = []
        for entry in entries:
            values = (entry[2], entry[3])
            points.append({
                'x': values[ix], 'y': values[iy], 'surah': entry[0], 'ayah': entry[1],
            })
        points.sort(key=lambda p: (ref_line(page, p['y']), -p['x']))
        pages[page] = points
    return pages


def build_source(kfgqpc: list[dict], aya_json: dict, spec: dict) -> dict:
    """Join the sources into one file. Assumes the checks passed."""
    ayahs = []
    for row in kfgqpc:
        words, split = split_words(row['aya_text'])
        ayah = {
            's': row['sura_no'],
            'a': row['aya_no'],
            'p': pages_of(row['page']),
            'ls': row['line_start'],
            'le': row['line_end'],
            'words': words,
        }
        if split is not None:
            ayah['split'] = split
        ayahs.append(ayah)
    refs = {
        str(page): [{'x': p['x'], 'y': p['y']} for p in points]
        for page, points in ref_ends(aya_json).items()
    }
    return {
        'format': 1, 'pages': TOTAL_PAGES, 'spec': spec, 'ayahs': ayahs, 'refEnds': refs,
    }


def label(row: dict) -> str:
    return f"{row['sura_no']}:{row['aya_no']}"


def check_kfgqpc(kfgqpc: list[dict]) -> list[str]:
    problems = []
    if len(kfgqpc) != TOTAL_AYAHS:
        problems.append(f'KFGQPC has {len(kfgqpc)} rows, expected {TOTAL_AYAHS}')
    seen: set[tuple[int, int]] = set()
    for row in kfgqpc:
        key = (row['sura_no'], row['aya_no'])
        if key in seen:
            problems.append(f'ayah {label(row)} appears twice in KFGQPC')
        seen.add(key)
    for row in kfgqpc:
        pages = pages_of(row['page'])
        two_pages = len(pages) == 2
        if len(pages) not in (1, 2) or (two_pages and pages[1] != pages[0] + 1):
            problems.append(
                f"ayah {label(row)}: page field {row['page']!r} is not one page or two consecutive"
            )
            continue
        ls, le = row['line_start'], row['line_end']
        in_range = 1 <= ls <= LINES_PER_PAGE and 1 <= le <= LINES_PER_PAGE
        if not in_range or (not two_pages and ls > le):
            problems.append(f'ayah {label(row)}: lines {ls}..{le} outside 1..{LINES_PER_PAGE}')
        words, split = split_words(row['aya_text'])
        if (split is not None) != two_pages:
            problems.append(
                f"ayah {label(row)}: page break in the text does not match page {row['page']}"
            )
        round_trips = rejoin_words(words, split, row['aya_text']) == row['aya_text']
        if not round_trips or any(not w for w in words):
            problems.append(f'ayah {label(row)}: words do not round-trip to aya_text')
    return problems


def check_pages(pages_dir: Path) -> tuple[list[str], dict[int, tuple[int, int]]]:
    problems = []
    sizes: dict[int, tuple[int, int]] = {}
    for page in range(1, TOTAL_PAGES + 1):
        path = pages_dir / f'{page:03d}.png'
        try:
            with Image.open(path) as image:
                image.load()
                sizes[page] = image.size
        except Exception as error:  # noqa: BLE001 - name the page, whatever it was
            problems.append(f'page {page}: {path.name} does not open ({error})')
    body = collections.Counter(size for page, size in sizes.items() if page > 2)
    if len(body) > 1:
        common = body.most_common(1)[0][0]
        for page, size in sizes.items():
            if page > 2 and size != common:
                problems.append(f'page {page}: image is {size}, pages 3.. are {common}')
    return problems, sizes


def check_surah_ends(kfgqpc: list[dict], aya_json: dict) -> list[str]:
    """The last ayah of every surah ends on the same page in both sources."""
    ours: dict[int, int] = {}
    for row in kfgqpc:
        ours[row['sura_no']] = max(ours.get(row['sura_no'], 0), pages_of(row['page'])[-1])
    theirs: dict[int, int] = {}
    for page, entries in enumerate(aya_json['coordinates']):
        for entry in entries:
            theirs[entry[0]] = max(theirs.get(entry[0], 0), page)
    problems = []
    for surah in range(1, 115):
        if ours.get(surah) != theirs.get(surah):
            problems.append(
                f'surah {surah}: its last ayah ends on page {ours.get(surah)} in KFGQPC, '
                f'on page {theirs.get(surah)} in open-mushaf'
            )
    return problems


def diagnostic(kfgqpc: list[dict], aya_json: dict) -> list[str]:
    """Lines to print: how well the two sources agree, per page. Never fails."""
    refs = ref_ends(aya_json)
    ours: dict[int, list[dict]] = collections.defaultdict(list)
    for row in kfgqpc:
        ours[pages_of(row['page'])[-1]].append(row)
    equal_pages = pairs = same_line = 0
    pairs_first = same_first = 0
    offsets: collections.Counter[int] = collections.Counter()
    unsorted = 0
    original = aya_json['coordinates']
    for page in range(1, TOTAL_PAGES + 1):
        order = [(p['surah'], p['ayah']) for p in refs[page]]
        if order != [(e[0], e[1]) for e in original[page]]:
            unsorted += 1
        if len(ours[page]) != len(refs[page]):
            continue
        equal_pages += 1
        for row, point in zip(ours[page], refs[page]):
            line = ref_line(page, point['y'])
            hit = row['line_end'] == line
            pairs += 1
            same_line += hit
            offsets[row['line_end'] - line] += 1
            if page <= 2:
                pairs_first += 1
                same_first += hit
    percent = 100.0 * same_line / pairs if pairs else 0.0
    common = sorted(offsets.items(), key=lambda kv: -kv[1])[:6]
    return [
        f'diagnostic: {equal_pages} of {TOTAL_PAGES} pages have the same number of ayah ends',
        f'diagnostic: {pairs} pairs in reading order, KFGQPC le == reference line in '
        f'{same_line} ({percent:.1f}%)',
        f'diagnostic: pages 1-2 only: {same_first} of {pairs_first} pairs',
        'diagnostic: le minus reference line: ' + ', '.join(f'{k:+d}: {v}' for k, v in common),
        f'diagnostic: {unsorted} pages where reading order differs from aya.json order',
    ]


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def download_all(out: Path) -> None:
    fetch(f'{KFGQPC}/data/warshData_v10.json', out / 'kfgqpc' / 'warshData_v10.json')
    fetch(f'{KFGQPC}/font/warsh.10.ttf', out / 'kfgqpc' / 'warsh.10.ttf')
    for name in ('aya', 'specs', 'surah', 'hizb'):
        fetch(
            f'{MUSHAF}/quran-metadata/{PRINT}/{name}.json',
            out / 'meta' / f'{name}.json',
        )

    def page(n: int) -> None:
        fetch(f'{MUSHAF}/mushaf-data/{PRINT}/{n}.png', out / 'pages' / f'{n:03d}.png')

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(page, range(1, TOTAL_PAGES + 1)))


def report(title: str, problems: list[str]) -> None:
    print(f'FAIL {title}: {len(problems)} problem(s)')
    for problem in problems[:MAX_SHOWN]:
        print(f'  {problem}')
    if len(problems) > MAX_SHOWN:
        print(f'  ... and {len(problems) - MAX_SHOWN} more')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', type=Path, default=Path('raw/warsh'))
    args = parser.parse_args()
    out: Path = args.out

    download_all(out)
    kfgqpc = read_json(out / 'kfgqpc' / 'warshData_v10.json')
    aya_json = read_json(out / 'meta' / 'aya.json')
    spec = read_json(out / 'meta' / 'specs.json')

    page_problems, sizes = check_pages(out / 'pages')
    checks = [
        ('KFGQPC rows, lines, words', check_kfgqpc(kfgqpc)),
        ('page images', page_problems),
        ('last ayah of every surah on the same page', check_surah_ends(kfgqpc, aya_json)),
    ]
    failed = False
    for title, problems in checks:
        if problems:
            failed = True
            report(title, problems)
    if failed:
        print('no warsh_source.json written')
        return 1

    source = build_source(kfgqpc, aya_json, spec)
    (out / 'warsh_source.json').write_text(
        json.dumps(source, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    for line in diagnostic(kfgqpc, aya_json):
        print(line)
    body = collections.Counter(size for page, size in sizes.items() if page > 2)
    width, height = body.most_common(1)[0][0]
    print(f'page 1: {sizes[1][0]}x{sizes[1][1]} px, page 2: {sizes[2][0]}x{sizes[2][1]} px')
    print(f'OK: {len(source["ayahs"])} ayahs, {TOTAL_PAGES} pages, {width}x{height} px')
    return 0


if __name__ == '__main__':
    sys.exit(main())
