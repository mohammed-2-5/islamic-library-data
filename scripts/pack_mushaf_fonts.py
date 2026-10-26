"""Fetch, check and pack the per-page fonts of the 1421 and 1441 mushaf prints.

The two prints the app offers beside the bundled 1405 one (QPC V1) are drawn
from a King Fahd Complex font set each: V2 (1421) and V4 (1441, with the
tajweed colours as COLR/CPAL). A set is 604 TTFs, one per page, about 300 KB
each. They are never bundled and never committed: this script downloads them
into raw/ (gitignored), proves they match the page layouts that
build_mushaf_editions.py wrote, and packs them into 8 zips per set which the
app downloads from R2 on the reader's request.

THE CHECKS: when any fails the script names the page and exits 1, packing and
uploading nothing.

  - the font loads;
  - every glyph character of page N's `lines` in layout.json is in font N's
    cmap (glyph codes are page-local: the same code is another word on
    another page, so a font from the wrong page fails here);
  - V4 only: the font has COLR and CPAL, CPAL version 0 and 6 palettes.

OUTPUT, per set <s>, under --out:

    <s>/v1/part-1.zip ... part-8.zip     members p001.ttf ... p604.ttf, deflate
    <s>/manifest.json                    {"set", "version", "bytes", "parts"}

The parts cover pages 1-76, 77-152, ... 533-604. The zips are written with
fixed timestamps, so the same fonts always give the same bytes and sha256: a
rerun that uploads again changes nothing for a reader.

--upload sends the parts to R2 first and the manifest last, under
mushaf-editions/<s>/, then asks the PUBLIC address for every object (as the
app does, with its Dart user agent: r2.dev refuses Python's) and compares what
it serves with what was packed. Credentials come from .r2.env, as in
sync_r2.py.

Usage:
    python scripts/pack_mushaf_fonts.py --set v4 \\
        --layout data/mushaf/v4/layout.json \\
        --raw raw/qpc_fonts --out raw/qpc_packs [--upload]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import sync_r2  # scripts/ is sys.path[0] when this file is run

sys.stdout.reconfigure(encoding='utf-8')

TOTAL_PAGES = 604
PARTS = 8
PAGES_PER_PART = 76  # 7 parts of 76, the last one holds the remaining 72
VERSION = 1
USER_AGENT = 'Dart/3.9 (dart:io)'
TIMEOUT = 60
ATTEMPTS = 5

FONT_URLS = {
    'v2': 'https://verses.quran.foundation/fonts/quran/hafs/v2/ttf/p{n}.ttf',
    'v4': 'https://verses.quran.foundation/fonts/quran/hafs/v4/colrv1/ttf/p{n}.ttf',
}
# sfnt version tags a font file starts with: TrueType, 'true', CFF. An error
# page saved as p12.ttf must not pass for a font.
FONT_MAGIC = (b'\x00\x01\x00\x00', b'true', b'OTTO')
V4_PALETTES = 6

# Fixed so that packing is reproducible (the zip format cannot go before 1980).
ZIP_STAMP = (1980, 1, 1, 0, 0, 0)

KEY_PREFIX = 'mushaf-editions'


def font_name(page: int) -> str:
    return f'p{page:03d}.ttf'


def part_range(part: int) -> tuple[int, int]:
    first = (part - 1) * PAGES_PER_PART + 1
    return first, min(part * PAGES_PER_PART, TOTAL_PAGES)


def request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={'User-Agent': USER_AGENT})


# --- fetch ---------------------------------------------------------------


def download(url: str, target: Path) -> None:
    """Fetch one font; write it only when it is whole and looks like a font."""
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request(url), timeout=TIMEOUT) as response:
                body = response.read()
                expected = response.headers.get('Content-Length')
            if expected is not None and int(expected) != len(body):
                raise OSError(f'short body: {len(body)} of {expected} bytes')
            if body[:4] not in FONT_MAGIC:
                raise ValueError(f'not a font (starts {body[:4]!r})')
            partial = target.with_name(target.name + '.part')
            partial.write_bytes(body)
            partial.replace(target)
            return
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (408, 425, 429) and e.code < 500:
                break  # 404 and friends will not change on a retry
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
        time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f'{url}: {last}')


def fetch_all(set_name: str, raw: Path, workers: int) -> None:
    folder = raw / set_name
    folder.mkdir(parents=True, exist_ok=True)
    todo = [
        n for n in range(1, TOTAL_PAGES + 1)
        if not (folder / font_name(n)).is_file() or (folder / font_name(n)).stat().st_size == 0
    ]
    print(f'{set_name}: {TOTAL_PAGES - len(todo)} fonts on disk, {len(todo)} to fetch')
    if not todo:
        return
    failed: list[str] = []
    template = FONT_URLS[set_name]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download, template.format(n=n), folder / font_name(n)): n
            for n in todo
        }
        for done, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as e:  # noqa: BLE001 - reported and counted, the rest carry on
                failed.append(f'page {futures[future]}: {e}')
            if done % 100 == 0 or done == len(todo):
                print(f'  {done}/{len(todo)}')
    if failed:
        for line in sorted(failed):
            print(f'  FAILED {line}')
        sys.exit(f'{set_name}: {len(failed)} fonts could not be fetched; rerun to resume')


# --- validate ------------------------------------------------------------


def load_layout(path: Path, set_name: str) -> dict[int, list[str]]:
    layout = json.loads(path.read_text(encoding='utf-8'))
    if layout.get('set') != set_name:
        sys.exit(f'{path}: layout is for set {layout.get("set")!r}, not {set_name!r}')
    pages = {int(k): v['lines'] for k, v in layout['pages'].items()}
    if sorted(pages) != list(range(1, TOTAL_PAGES + 1)):
        sys.exit(f'{path}: pages are not exactly 1..{TOTAL_PAGES}')
    return pages


def glyphs_of(lines: list[str]) -> set[str]:
    return {ch for line in lines for ch in line if not ch.isspace()}


def page_problems(path: Path, wanted: set[str], coloured: bool) -> list[str]:
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(str(path), lazy=True)
    except Exception as e:  # noqa: BLE001 - any parse failure is the finding
        return [f'does not load: {e}']
    try:
        problems: list[str] = []
        cmap = font.getBestCmap() or {}
        missing = sorted(ord(ch) for ch in wanted if ord(ch) not in cmap)
        if missing:
            shown = ' '.join(f'U+{cp:04X}' for cp in missing[:12])
            more = f' (+{len(missing) - 12} more)' if len(missing) > 12 else ''
            problems.append(f'{len(missing)} of {len(wanted)} glyphs not in the cmap: {shown}{more}')
        if coloured:
            if 'COLR' not in font:
                problems.append('no COLR table')
            if 'CPAL' not in font:
                problems.append('no CPAL table')
            else:
                cpal = font['CPAL']
                if cpal.version != 0:
                    problems.append(f'CPAL version {cpal.version}, expected 0')
                if len(cpal.palettes) != V4_PALETTES:
                    problems.append(f'CPAL has {len(cpal.palettes)} palettes, expected {V4_PALETTES}')
        return problems
    finally:
        font.close()


def validate_all(set_name: str, raw: Path, pages: dict[int, list[str]]) -> None:
    folder = raw / set_name
    coloured = set_name == 'v4'
    bad: list[str] = []
    for n in range(1, TOTAL_PAGES + 1):
        for problem in page_problems(folder / font_name(n), glyphs_of(pages[n]), coloured):
            bad.append(f'page {n}: {problem}')
    if bad:
        for line in bad:
            print(f'  INVALID {line}')
        failing = len({line.split(':')[0] for line in bad})
        sys.exit(f'{set_name}: {failing} pages failed validation; nothing packed')


# --- pack ----------------------------------------------------------------


def pack(set_name: str, raw: Path, out: Path) -> dict:
    folder = raw / set_name
    parts_dir = out / set_name / f'v{VERSION}'
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for part in range(1, PARTS + 1):
        first, last = part_range(part)
        target = parts_dir / f'part-{part}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for n in range(first, last + 1):
                info = zipfile.ZipInfo(font_name(n), date_time=ZIP_STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, (folder / font_name(n)).read_bytes(), compresslevel=9)
        data = target.read_bytes()
        parts.append({
            'name': f'v{VERSION}/part-{part}.zip',
            'first': first,
            'last': last,
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        'set': set_name,
        'version': VERSION,
        'bytes': sum(p['bytes'] for p in parts),
        'parts': parts,
    }
    (out / set_name / 'manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8'
    )
    return manifest


# --- upload --------------------------------------------------------------


def s3_client(env: dict[str, str]):
    # Built exactly as sync_r2.main builds it.
    import boto3
    from botocore.config import Config

    return boto3.client(
        's3',
        endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=env['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        config=Config(retries={'max_attempts': 5, 'mode': 'standard'}),
    )


def upload(set_name: str, out: Path, manifest: dict) -> None:
    env = sync_r2.load_env()
    public = env.get('R2_PUBLIC_URL', '').rstrip('/')
    if not public:
        sys.exit('R2_PUBLIC_URL is not set in .r2.env: uploads cannot be verified, nothing sent')
    s3 = s3_client(env)
    bucket = env['R2_BUCKET']

    # (key, file, content type, cache control, bytes, sha256): parts first,
    # the manifest last, so a reader who finds a manifest finds every part.
    objects = []
    for part in manifest['parts']:
        objects.append((
            f"{KEY_PREFIX}/{set_name}/{part['name']}",
            out / set_name / part['name'],
            sync_r2.CONTENT_TYPES['.zip'],
            sync_r2.CACHE_OTHER,
            part['bytes'],
            part['sha256'],
        ))
    manifest_file = out / set_name / 'manifest.json'
    manifest_data = manifest_file.read_bytes()
    objects.append((
        f'{KEY_PREFIX}/{set_name}/manifest.json',
        manifest_file,
        sync_r2.CONTENT_TYPES['.json'],
        sync_r2.CACHE_JSON,
        len(manifest_data),
        hashlib.sha256(manifest_data).hexdigest(),
    ))

    for key, path, content_type, cache, _, _ in objects:
        s3.upload_file(
            str(path), bucket, key,
            ExtraArgs={'ContentType': content_type, 'CacheControl': cache},
        )
        print(f'  uploaded {key}')

    verified = 0
    for key, _, _, _, size, digest in objects:
        with urllib.request.urlopen(request(f'{public}/{key}'), timeout=TIMEOUT * 3) as response:
            status = response.status
            length = response.headers.get('Content-Length')
            body = response.read()
        if status != 200:
            sys.exit(f'{key}: public address answered {status}')
        if length is not None and int(length) != size:
            sys.exit(f'{key}: Content-Length {length}, packed {size}')
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            sys.exit(f'{key}: public body differs from the packed file ({len(body)} of {size} bytes)')
        verified += 1
    print(f'{set_name}: verified {verified} objects')


# --- main ----------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--set', dest='set_name', choices=sorted(FONT_URLS), required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()

    pages = load_layout(args.layout, args.set_name)
    fetch_all(args.set_name, args.raw, args.workers)
    validate_all(args.set_name, args.raw, pages)
    manifest = pack(args.set_name, args.raw, args.out)
    print(
        f"{args.set_name}: {TOTAL_PAGES} fonts valid, {len(manifest['parts'])} parts, "
        f"{manifest['bytes']} bytes"
    )
    if args.upload:
        upload(args.set_name, args.out, manifest)


if __name__ == '__main__':
    main()
