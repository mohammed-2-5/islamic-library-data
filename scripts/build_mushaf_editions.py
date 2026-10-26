"""Build the page layouts of the 1421 and 1441 Madinah mushaf prints from QUL.

The app draws a mushaf page from a font set: V1 (1405, bundled), V2 (the
King Fahd Complex print of 1421) and V4 (the print of 1441, with the tajweed
colours). Each set breaks the 6236 ayahs into its own lines, so a page cannot
be drawn from the 1405 files. Tarteel QUL publishes, per font set, the same
thing as sqlite: `pages` (what every line of every page is) and `words` (the
glyph code or codes of every word). This script joins them into one
`layout.json` per set, which the app downloads and parses:

    {"format": 1, "set": "v4", "edition": "1441",
     "pages": {"1": {"lines": ["<glyphs>", ...],
                     "runs":  [[[surah, ayah, firstWord, glyphs], ...], ...],
                     "starts": [{"l": 0, "s": 1, "h": 1, "b": 0}]}},
     "table": [{"p": 1, "s": 1, "a": 1, "j": 1, "h": 1}, ...]}

`lines` and `runs` hold the text lines only, one entry per `ayah` row. The
surah headings and the bismillahs are not text lines; `starts` says where they
go. `l` is the index of the text line a slot sits ABOVE, and it may equal the
page's line count: in 1421, 18 pages end on a surah heading, with the first
ayah of the surah, and its bismillah, at the top of the next page. `h` means
"draw the surah heading", `b` "draw the bismillah". `table` has the shape of
`assets/quran/mushaf_pages.json` in the app: the first ayah of every page, its
juz and its hizb.

`runs` follow the rule of the app's `scripts/build_word_index.py`: inside a run
the Nth glyph is the Nth word. A word can be two glyphs (the font splits a long
word to justify the line); the second glyph starts a new run rather than being
folded into the one before.

THE CHECKS: when any fails the script names the page and exits 1, writing
nothing. A layout that looks right and is a page off is worse than none.

Usage:
    python scripts/build_mushaf_editions.py \\
        --qul raw/qul \\
        --hizb ../azkar/assets/quran/hizb_quarters.json \\
        --v1405 ../azkar/assets/quran/mushaf_pages.json \\
        --out data/mushaf
"""

from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

TOTAL_PAGES = 604
TOTAL_WORDS = 83668
LINES_PER_PAGE = 15
SHORT_PAGES = {1: 8, 2: 8}

# The pages of the 1405 print whose first ayah is not the first ayah of the same
# page in 1421 and 1441. Both prints agree with each other on all 604 pages.
SHIFTED_FROM_1405 = [
    121, 122, 123, 145, 532, 533, 534, 565, 568, 570, 576, 584, 586, 588, 589,
    590, 592, 593, 594, 595, 596, 597, 598, 599, 600,
]

# 1421 (V2): the pages whose last row is a surah heading. The bismillah, and
# the surah's first line, are at the top of the next page.
V2_HEADING_LAST = [
    76, 207, 331, 341, 349, 366, 376, 414, 417, 445, 452, 498, 506, 525, 548,
    555, 557, 584,
]

# set id -> (edition shown to readers, layout archive, words archive)
SETS = {
    'v2': ('1421', 'qpc-v2-15-lines.db.zip', 'qpc-v2.db.zip'),
    'v4': ('1441', 'qpc-v4-tajweed-15-lines.db.zip', 'qpc-v4.db.zip'),
}


@dataclass
class Word:
    surah: int
    ayah: int
    position: int
    glyphs: str  # the word's glyph code(s), whitespace removed


@dataclass
class Row:
    line_number: int
    line_type: str
    first_word: int  # 0 for rows that are not text
    last_word: int
    surah_number: int  # 0 for rows that carry none


@dataclass
class Layout:
    key: str
    edition: str
    rows: dict[int, list[Row]]
    words: dict[int, Word]
    pages: dict[str, dict] = field(default_factory=dict)
    table: list[dict] = field(default_factory=list)
    row_count: int = 0
    words_used: int = 0
    # pages whose last row is a surah heading
    heading_last: list[int] = field(default_factory=list)


class Failures:
    """Every check that failed, named by page, so one run says everything."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, message: str) -> None:
        self.items.append(message)

    def __bool__(self) -> bool:
        return bool(self.items)


def read_db(archive: Path, workdir: Path) -> sqlite3.Connection:
    """Open the one `.db` inside a QUL zip.

    The member is located by its file name, not its path: the archives keep
    it at the root today and in a folder of the same name otherwise. It is
    written under the archive's own name inside `workdir` (qpc-v2.db.zip ->
    qpc-v2.db) rather than extracted with the member's own path.
    """
    with zipfile.ZipFile(archive) as bundle:
        members = [m for m in bundle.namelist()
                   if m.lower().endswith('.db') and not m.endswith('/')]
        if len(members) != 1:
            raise SystemExit('%s: expected one .db, found %s'
                             % (archive.name, members))
        target = workdir / archive.stem
        target.write_bytes(bundle.read(members[0]))
    return sqlite3.connect(str(target))


def to_int(value: object) -> int:
    """QUL stores a missing id as '' and a present one as a number."""
    if value is None or value == '':
        return 0
    return int(value)


def load_rows(connection: sqlite3.Connection) -> dict[int, list[Row]]:
    rows: dict[int, list[Row]] = {}
    cursor = connection.execute(
        'SELECT page_number, line_number, line_type, first_word_id, '
        'last_word_id, surah_number FROM pages '
        'ORDER BY page_number, line_number')
    for page, line, kind, first, last, surah in cursor:
        rows.setdefault(int(page), []).append(
            Row(int(line), str(kind), to_int(first), to_int(last),
                to_int(surah)))
    return rows


def load_words(connection: sqlite3.Connection,
               failures: Failures, label: str) -> dict[int, Word]:
    words: dict[int, Word] = {}
    cursor = connection.execute(
        'SELECT id, location, surah, ayah, word, text FROM words ORDER BY id')
    for word_id, location, surah, ayah, position, text in cursor:
        word_id = int(word_id)
        if word_id in words:
            failures.add('%s: word id %d appears twice' % (label, word_id))
            continue
        if location != '%d:%d:%d' % (surah, ayah, position):
            failures.add('%s: word %d: location %r is not %d:%d:%d'
                         % (label, word_id, location, surah, ayah, position))
        glyphs = ''.join(str(text or '').split())
        if not glyphs:
            failures.add('%s: word %d (%s) has no glyphs'
                         % (label, word_id, location))
        words[word_id] = Word(int(surah), int(ayah), int(position), glyphs)
    return words


def runs_of(line_words: list[Word]) -> list[list[int]]:
    """The runs of one line: [surah, ayah, firstWord, glyphs]."""
    runs: list[list[int]] = []
    for word in line_words:
        for _ in word.glyphs:
            if (runs and runs[-1][0] == word.surah
                    and runs[-1][1] == word.ayah
                    and runs[-1][2] + runs[-1][3] == word.position):
                runs[-1][3] += 1
            else:
                # The second glyph of a split word lands here: it carries the
                # same position as the first, so it opens a run of its own.
                runs.append([word.surah, word.ayah, word.position, 1])
    return runs


def hizb_of(surah: int, ayah: int, quarters: list[dict],
            keys: list[tuple[int, int]]) -> int:
    """The hizb of an ayah: that of the last quarter start at or before it."""
    at = bisect.bisect_right(keys, (surah, ayah)) - 1
    return int(quarters[at]['h'])


def build_layout(key: str, qul: Path, workdir: Path, quarters: list[dict],
                 failures: Failures) -> Layout:
    edition, layout_zip, words_zip = SETS[key]
    label = '%s (%s)' % (key, edition)

    layout_db = read_db(qul / layout_zip, workdir)
    words_db = read_db(qul / words_zip, workdir)
    try:
        rows = load_rows(layout_db)
        words = load_words(words_db, failures, label)
    finally:
        layout_db.close()
        words_db.close()

    layout = Layout(key, edition, rows, words)
    keys = [(int(q['s']), int(q['a'])) for q in quarters]

    if sorted(rows) != list(range(1, TOTAL_PAGES + 1)):
        failures.add('%s: the layout has %d pages, expected pages 1..%d'
                     % (label, len(rows), TOTAL_PAGES))
    if sorted(words) != list(range(1, TOTAL_WORDS + 1)):
        failures.add('%s: word ids are not exactly 1..%d (%d found)'
                     % (label, TOTAL_WORDS, len(words)))

    expected_next = 1  # the word id the next ayah row must start with
    previous_position: tuple[int, int, int] | None = None

    for page in sorted(rows):
        page_rows = rows[page]
        layout.row_count += len(page_rows)
        want = SHORT_PAGES.get(page, LINES_PER_PAGE)
        if len(page_rows) != want:
            failures.add('%s page %d: %d rows, expected %d'
                         % (label, page, len(page_rows), want))
        if [r.line_number for r in page_rows] != list(
                range(1, len(page_rows) + 1)):
            failures.add('%s page %d: line numbers are not 1..%d in order'
                         % (label, page, len(page_rows)))

        lines: list[str] = []
        runs: list[list[list[int]]] = []
        starts: list[dict] = []
        orphans: list[dict] = []  # bismillah starts that follow no heading
        first_ayah: Word | None = None

        for at, row in enumerate(page_rows):
            if row.line_type == 'ayah':
                if row.first_word != expected_next or (
                        row.last_word < row.first_word):
                    failures.add(
                        '%s page %d line %d: words %d..%d, expected the '
                        'range to start at %d'
                        % (label, page, row.line_number, row.first_word,
                           row.last_word, expected_next))
                    # Keep going from where the data says, so the later
                    # pages are still checked.
                expected_next = row.last_word + 1
                line_words = [words[i]
                              for i in range(row.first_word, row.last_word + 1)
                              if i in words]
                for word in line_words:
                    here = (word.surah, word.ayah, word.position)
                    if previous_position and here <= previous_position:
                        failures.add(
                            '%s page %d line %d: word %d:%d:%d does not '
                            'follow %d:%d:%d'
                            % (label, page, row.line_number, *here,
                               *previous_position))
                    previous_position = here
                if first_ayah is None and line_words:
                    first_ayah = line_words[0]
                text = ' '.join(w.glyphs for w in line_words)
                line_runs = runs_of(line_words)
                glyph_count = sum(1 for ch in text if not ch.isspace())
                if glyph_count != sum(run[3] for run in line_runs):
                    failures.add(
                        '%s page %d line %d: %d glyphs, the runs claim %d'
                        % (label, page, row.line_number, glyph_count,
                           sum(run[3] for run in line_runs)))
                lines.append(text)
                runs.append(line_runs)
                layout.words_used += len(line_words)
            elif row.line_type == 'surah_name':
                after = page_rows[at + 1] if at + 1 < len(page_rows) else None
                starts.append({
                    'l': len(lines),
                    's': row.surah_number,
                    'h': 1,
                    'b': 1 if after is not None
                    and after.line_type == 'basmallah' else 0,
                })
            elif row.line_type == 'basmallah':
                before = page_rows[at - 1] if at > 0 else None
                if before is not None and before.line_type == 'surah_name':
                    continue  # already carried by that heading's `b`
                if at != 0:
                    failures.add(
                        '%s page %d line %d: a bismillah with no heading '
                        'before it, and not at the top of the page'
                        % (label, page, row.line_number))
                    continue
                # Its surah is the one of the page's first ayah row, which
                # is not read yet: filled in below.
                starts.append({'l': 0, 's': 0, 'h': 0, 'b': 1})
                orphans.append(starts[-1])
            else:
                failures.add('%s page %d line %d: unknown line type %r'
                             % (label, page, row.line_number, row.line_type))

        if first_ayah is None:
            failures.add('%s page %d: no text line' % (label, page))
            continue

        # A bismillah at the top of a page belongs to the surah of the page's
        # first ayah row (the heading closed the page before).
        for start in orphans:
            start['s'] = first_ayah.surah

        if page_rows and page_rows[-1].line_type == 'surah_name':
            layout.heading_last.append(page)

        layout.pages[str(page)] = {
            'lines': lines, 'runs': runs, 'starts': starts,
        }
        hizb = hizb_of(first_ayah.surah, first_ayah.ayah, quarters, keys)
        layout.table.append({
            'p': page, 's': first_ayah.surah, 'a': first_ayah.ayah,
            'j': (hizb + 1) // 2, 'h': hizb,
        })

    if expected_next != TOTAL_WORDS + 1:
        failures.add('%s: the lines end at word id %d, expected %d'
                     % (label, expected_next - 1, TOTAL_WORDS))
    if layout.words_used != TOTAL_WORDS:
        failures.add('%s: the lines use %d words, expected %d'
                     % (label, layout.words_used, TOTAL_WORDS))
    return layout


def check_pair(v2: Layout, v4: Layout, v1405: list[dict],
               failures: Failures) -> list[int]:
    """Checks that compare layouts. Returns the pages that differ from 1405."""
    first = {t['p']: (t['s'], t['a']) for t in v2.table}
    second = {t['p']: (t['s'], t['a']) for t in v4.table}
    for page in range(1, TOTAL_PAGES + 1):
        if first.get(page) != second.get(page):
            failures.add('page %d: v2 starts at %s, v4 at %s'
                         % (page, first.get(page), second.get(page)))

    old = {t['p']: (t['s'], t['a']) for t in v1405}
    differ = [p for p in range(1, TOTAL_PAGES + 1)
              if second.get(p) != old.get(p)]
    if differ != SHIFTED_FROM_1405:
        extra = sorted(set(differ) - set(SHIFTED_FROM_1405))
        missing = sorted(set(SHIFTED_FROM_1405) - set(differ))
        failures.add('pages that differ from 1405 are not the expected 25: '
                     'unexpected %s, missing %s' % (extra, missing))
    return differ


def check_headings(v2: Layout, v4: Layout, failures: Failures) -> None:
    # 1441 never ends a page on a heading.
    for page, body in v4.pages.items():
        count = len(body['lines'])
        for start in body['starts']:
            if start['l'] >= count and start['h']:
                failures.add('v4 (1441) page %s: a heading after the last '
                             'line' % page)

    if v2.heading_last != V2_HEADING_LAST:
        failures.add('v2 (1421): pages ending on a heading are %s, expected '
                     '%s' % (v2.heading_last, V2_HEADING_LAST))
    for page in v2.heading_last:
        body = v2.pages[str(page)]
        closing = [s for s in body['starts']
                   if s['h'] and s['l'] == len(body['lines'])]
        if len(closing) != 1:
            failures.add('v2 (1421) page %d: %d headings after the last line, '
                         'expected 1' % (page, len(closing)))
            continue
        if closing[0]['b']:
            failures.add('v2 (1421) page %d: the closing heading carries its '
                         'bismillah on the same page' % page)
        following = v2.pages.get(str(page + 1))
        top = following['starts'][0] if following and following['starts'] \
            else None
        if (top is None or top['l'] != 0 or top['h'] != 0 or top['b'] != 1
                or top['s'] != closing[0]['s']):
            failures.add('v2 (1421) page %d: its heading (surah %d) is not '
                         'followed by a bismillah start on page %d (got %s)'
                         % (page, closing[0]['s'], page + 1, top))


def write_layout(layout: Layout, out: Path) -> Path:
    target = out / layout.key / 'layout.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {
        'format': 1,
        'set': layout.key,
        'edition': layout.edition,
        'pages': layout.pages,
        'table': layout.table,
    }
    with open(target, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(document, handle, ensure_ascii=False,
                  separators=(',', ':'))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--qul', type=Path, required=True,
                        help='folder holding the four QUL .db.zip files')
    parser.add_argument('--hizb', type=Path, required=True,
                        help='hizb_quarters.json of the app')
    parser.add_argument('--v1405', type=Path, required=True,
                        help='mushaf_pages.json of the app (the 1405 table)')
    parser.add_argument('--out', type=Path, required=True,
                        help='folder that gets v2/layout.json and v4/layout.json')
    args = parser.parse_args()

    with open(args.hizb, encoding='utf-8') as handle:
        quarters = sorted(json.load(handle),
                          key=lambda q: (int(q['s']), int(q['a'])))
    with open(args.v1405, encoding='utf-8') as handle:
        v1405 = json.load(handle)

    failures = Failures()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
        built = {key: build_layout(key, args.qul, Path(scratch), quarters,
                                   failures)
                 for key in SETS}

    v2, v4 = built['v2'], built['v4']
    differ = check_pair(v2, v4, v1405, failures)
    check_headings(v2, v4, failures)

    if failures:
        print('REFUSING TO WRITE - %d check(s) failed:' % len(failures.items))
        for message in failures.items[:40]:
            print('   ' + message)
        if len(failures.items) > 40:
            print('   ... and %d more' % (len(failures.items) - 40))
        return 1

    for layout in (v2, v4):
        target = write_layout(layout, args.out)
        print('wrote %s (%.1f KB)' % (target, target.stat().st_size / 1024))

    for layout in (v2, v4):
        print('%s (%s): %d pages, %d rows, %d words'
              % (layout.key, layout.edition, len(layout.pages),
                 layout.row_count, layout.words_used))
    print('%d pages differ from 1405: %s'
          % (len(differ), ', '.join(str(p) for p in differ)))
    print('%d v2 headings close their page' % len(v2.heading_last))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
