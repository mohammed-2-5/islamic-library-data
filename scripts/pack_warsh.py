"""Check and pack the Warsh mushaf's layout and font for the app.

The app draws its Warsh print from two files that the app's own build step
(Task 1 of the Warsh mushaf plan) wrote into build/warsh_pack/:

  * warsh_pack.json: format 1, the 6214 Warsh ayahs laid out on the 604 pages of
    the Madinah print, line by line; every word is [text, surah, ayah];
  * warsh.10.ttf: the King Fahd Complex Warsh font those words are written in.

They are never committed: this script checks them against each other and packs
them into ONE zip which the app downloads from R2, in the same shape as the
font editions of pack_mushaf_fonts.py, so the app's edition-manifest parser
reads it unchanged.

THE CHECKS: when any fails the script says which and exits 1, packing nothing.

  - warsh_pack.json parses, `format` is 1, it has 6214 ayahs and 604 pages;
  - the font loads with fontTools;
  - every character the pack's words use (whitespace aside, which any font
    falls back for) is in the font's cmap. A character that is not would draw
    as a missing-glyph box in the reader: the uncovered ones are listed.

OUTPUT under --out:

    warsh/v1/part-1.zip      members warsh_pack.json, warsh.10.ttf, deflate
    warsh/manifest.json      {"set", "version", "bytes", "parts"}

The one part holds pages 1-604. The zip is written with fixed timestamps, so
the same inputs always give the same bytes and sha256. Uploading to R2 (under
mushaf-editions/warsh/) is not done here.

Usage:
    python scripts/pack_warsh.py --pack ../azkar/build/warsh_pack --out raw/warsh_packs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SET_NAME = 'warsh'
VERSION = 1
FORMAT = 1
TOTAL_PAGES = 604
TOTAL_AYAHS = 6214
PACK_NAME = 'warsh_pack.json'
FONT_NAME = 'warsh.10.ttf'
# sfnt version tags a font file starts with: TrueType, 'true', CFF.
FONT_MAGIC = (b'\x00\x01\x00\x00', b'true', b'OTTO')

# Fixed so that packing is reproducible (the zip format cannot go before 1980).
ZIP_STAMP = (1980, 1, 1, 0, 0, 0)


def load_pack(path: Path) -> dict:
    try:
        pack = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        sys.exit(f'{path}: does not parse ({e})')
    problems = []
    if pack.get('format') != FORMAT:
        problems.append(f'format is {pack.get("format")!r}, expected {FORMAT}')
    if pack.get('ayahs') != TOTAL_AYAHS:
        problems.append(f'{pack.get("ayahs")!r} ayahs, expected {TOTAL_AYAHS}')
    pages = pack.get('pages')
    if not isinstance(pages, list) or len(pages) != TOTAL_PAGES:
        count = len(pages) if isinstance(pages, list) else pages
        problems.append(f'{count!r} pages, expected {TOTAL_PAGES}')
    elif [p.get('p') for p in pages] != list(range(1, TOTAL_PAGES + 1)):
        problems.append(f'pages are not numbered 1..{TOTAL_PAGES} in order')
    if problems:
        sys.exit(f'{path}: ' + '; '.join(problems))
    return pack


def characters_of(pack: dict) -> set[str]:
    """Every non-whitespace character the pack's words are drawn with."""
    return {
        ch
        for page in pack['pages']
        for line in page['lines']
        for word in line['words']
        for ch in word[0]
        if not ch.isspace()
    }


def check_font(path: Path, wanted: set[str]) -> None:
    from fontTools.ttLib import TTFont

    head = path.read_bytes()[:4]
    if head not in FONT_MAGIC:
        sys.exit(f'{path}: not a font (starts {head!r})')
    try:
        font = TTFont(str(path), lazy=True)
    except Exception as e:  # noqa: BLE001 - any parse failure is the finding
        sys.exit(f'{path}: does not load ({e})')
    try:
        cmap = font.getBestCmap() or {}
        missing = sorted(ord(ch) for ch in wanted if ord(ch) not in cmap)
    finally:
        font.close()
    if missing:
        for cp in missing:
            print(f'  MISSING U+{cp:04X} {chr(cp)!r}')
        sys.exit(
            f'{path.name}: {len(missing)} of {len(wanted)} characters of the pack '
            f'are not in the font\'s cmap; nothing packed'
        )


def pack(pack_dir: Path, out: Path) -> dict:
    parts_dir = out / SET_NAME / f'v{VERSION}'
    parts_dir.mkdir(parents=True, exist_ok=True)
    target = parts_dir / 'part-1.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in (PACK_NAME, FONT_NAME):
            info = zipfile.ZipInfo(name, date_time=ZIP_STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (pack_dir / name).read_bytes(), compresslevel=9)
    data = target.read_bytes()
    part = {
        'name': f'v{VERSION}/part-1.zip',
        'first': 1,
        'last': TOTAL_PAGES,
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    }
    manifest = {
        'set': SET_NAME,
        'version': VERSION,
        'bytes': part['bytes'],
        'parts': [part],
    }
    (out / SET_NAME / 'manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8'
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--pack', type=Path, required=True,
                        help='folder holding warsh_pack.json and warsh.10.ttf')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    pack_data = load_pack(args.pack / PACK_NAME)
    wanted = characters_of(pack_data)
    check_font(args.pack / FONT_NAME, wanted)
    manifest = pack(args.pack, args.out)
    part = manifest['parts'][0]
    print(
        f"OK {SET_NAME}: {TOTAL_AYAHS} ayahs, {TOTAL_PAGES} pages, {len(wanted)} characters "
        f"all in the font; 1 part, {part['bytes']} bytes, sha256 {part['sha256']}"
    )


if __name__ == '__main__':
    main()
