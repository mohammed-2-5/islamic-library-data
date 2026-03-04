"""Convert OpenITI texts from mARkdown format to our JSON schema.

Source: https://github.com/OpenITI/RELEASE
Format: Custom mARkdown (see utils/markdown_parser.py)

OpenITI organizes texts by author death date:
  data/{century}AH/{AuthorID}/{AuthorID.BookID}/
    {AuthorID.BookID}.{version}-{lang}{edition}

This script:
1. Scans the OpenITI release directory for .mARkdown files
2. Parses each file using the mARkdown parser
3. Extracts metadata and chapters
4. Writes normalized JSON to data/books/{category}/{book_id}/

Usage:
    python convert_openiti.py --input-dir /path/to/OpenITI/RELEASE/data
    python convert_openiti.py --input-dir /path/to/OpenITI --limit 100
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text, normalize_arabic
from utils.markdown_parser import (
    parse_openiti,
    get_book_title,
    get_author_name,
    get_genre,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books"

# Map OpenITI genre tags to our categories
GENRE_MAP = {
    "TAFSIR": "tafseer",
    "tafsir": "tafseer",
    "HADITH": "hadith",
    "hadith": "hadith",
    "FIQH": "fiqh",
    "fiqh": "fiqh",
    "SIRA": "seerah",
    "sira": "seerah",
    "TARIKH": "seerah",
    "tarikh": "seerah",
    "TABAQAT": "seerah",
    "TARAJIM": "seerah",
    "AQIDA": "aqeedah",
    "aqida": "aqeedah",
    "KALAM": "aqeedah",
    "TASAWWUF": "raqaiq",
    "ZUHD": "raqaiq",
    "AKHLAQ": "raqaiq",
    "ADAB": "arabic_language",
    "LUGHA": "arabic_language",
    "NAHW": "arabic_language",
    "SARF": "arabic_language",
    "BALAGHA": "arabic_language",
}

DEFAULT_CATEGORY = "general"

# Minimum content threshold (skip very small files)
MIN_PARAGRAPHS = 5
MIN_CHARS = 500

# Files to skip (non-text files, duplicates, etc.)
SKIP_EXTENSIONS = {".yml", ".md", ".py", ".txt", ".csv", ".json", ".xml"}


def find_markdown_files(input_dir: str) -> list[Path]:
    """Find all mARkdown text files in the OpenITI directory structure."""
    input_path = Path(input_dir)
    markdown_files = []

    # OpenITI uses various extensions: .mARkdown, .completed, .inProgress
    # and sometimes no extension. Look for files with the magic value.
    for pattern in ("**/*.mARkdown", "**/*.completed", "**/*.inProgress"):
        markdown_files.extend(input_path.glob(pattern))

    # Also check for files without standard extensions
    # but with the OpenITI naming pattern: AuthorID.BookID.Version
    for f in input_path.rglob("*"):
        if f.is_file() and f.suffix not in SKIP_EXTENSIONS and f not in markdown_files:
            # Check if it looks like an OpenITI file (has dots in name)
            if f.name.count('.') >= 2 and f.stat().st_size > MIN_CHARS:
                # Quick check for magic value
                try:
                    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                        first_line = fh.readline().strip()
                        if first_line.startswith('######OpenITI#'):
                            markdown_files.append(f)
                except (OSError, UnicodeDecodeError):
                    pass

    return sorted(set(markdown_files))


def extract_id_from_path(file_path: Path) -> str:
    """Extract a book ID from the OpenITI file path.

    OpenITI paths look like:
    data/0850AH/0256Bukhari/0256Bukhari.SahihBukhari/
        0256Bukhari.SahihBukhari.Shamela0001-ara1

    We extract: 0256Bukhari_SahihBukhari
    """
    name = file_path.stem  # e.g., 0256Bukhari.SahihBukhari.Shamela0001-ara1
    parts = name.split('.')

    if len(parts) >= 2:
        # Use author.book as the ID
        author_part = parts[0]
        book_part = parts[1]
        return f"openiti_{author_part}_{book_part}"

    return f"openiti_{name.replace('.', '_')}"


def map_genre(genre_str: str) -> str:
    """Map OpenITI genre string to our category."""
    if not genre_str:
        return DEFAULT_CATEGORY

    # Genre might be comma-separated or have multiple tags
    for tag, category in GENRE_MAP.items():
        if tag.lower() in genre_str.lower():
            return category

    return DEFAULT_CATEGORY


def convert_file(file_path: Path) -> dict | None:
    """Convert a single OpenITI file to our JSON schema.

    Returns metadata dict or None on failure/skip.
    """
    try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
    except OSError as e:
        print(f"  Cannot read {file_path}: {e}")
        return None

    # Skip very small files
    if len(text) < MIN_CHARS:
        return None

    # Parse mARkdown
    parsed = parse_openiti(text)

    # Skip if too little content
    total_paras = sum(len(s.content) for s in parsed.sections) + len(parsed.raw_paragraphs)
    if total_paras < MIN_PARAGRAPHS:
        return None

    # Extract metadata
    book_id = extract_id_from_path(file_path)
    title_ar = clean_text(get_book_title(parsed.metadata))
    author_ar = clean_text(get_author_name(parsed.metadata))
    genre = get_genre(parsed.metadata)
    category = map_genre(genre)

    # If no title from metadata, try to get from first header
    if not title_ar and parsed.sections:
        title_ar = clean_text(parsed.sections[0].title)

    # If still no title, use the book part of the file name
    if not title_ar:
        parts = file_path.stem.split('.')
        title_ar = parts[1] if len(parts) >= 2 else parts[0]

    # Build chapters from sections
    chapters = []

    if parsed.sections:
        # Use level-1 sections as chapters
        chapter_id = 0
        for section in parsed.sections:
            if section.level <= 2 and section.content:
                chapter_id += 1
                entries = [
                    {
                        "id": i + 1,
                        "text_ar": para,
                        "text_en": "",
                        "reference": "",
                    }
                    for i, para in enumerate(section.content)
                    if para.strip()
                ]

                if entries:
                    chapters.append({
                        "book_id": book_id,
                        "chapter_id": chapter_id,
                        "title_ar": clean_text(section.title) or f"الفصل {chapter_id}",
                        "title_en": "",
                        "entries": entries,
                    })
            elif section.level > 2 and chapters and section.content:
                # Append subsection content to the last chapter
                last_ch = chapters[-1]
                start_id = len(last_ch["entries"]) + 1
                for i, para in enumerate(section.content):
                    if para.strip():
                        last_ch["entries"].append({
                            "id": start_id + i,
                            "text_ar": para,
                            "text_en": "",
                            "reference": "",
                        })

    # Fallback: if no chapters from sections, create from raw paragraphs
    if not chapters and parsed.raw_paragraphs:
        # Split into chunks of ~50 paragraphs per chapter
        chunk_size = 50
        for i in range(0, len(parsed.raw_paragraphs), chunk_size):
            chunk = parsed.raw_paragraphs[i:i + chunk_size]
            chapter_id = (i // chunk_size) + 1
            entries = [
                {"id": j + 1, "text_ar": p, "text_en": "", "reference": ""}
                for j, p in enumerate(chunk)
                if p.strip()
            ]
            if entries:
                chapters.append({
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "title_ar": f"الجزء {chapter_id}",
                    "title_en": f"Part {chapter_id}",
                    "entries": entries,
                })

    if not chapters:
        return None

    # Write to disk
    book_dir = OUTPUT_DIR / category / book_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_entries = 0

    for ch in chapters:
        ch_json = json.dumps(ch, ensure_ascii=False, indent=2)
        (chapters_dir / f"{ch['chapter_id']}.json").write_text(ch_json, encoding="utf-8")
        total_bytes += len(ch_json.encode("utf-8"))
        total_entries += len(ch.get("entries", []))

    metadata = {
        "id": book_id,
        "title_ar": title_ar,
        "title_en": "",
        "author_ar": author_ar,
        "author_en": "",
        "category": category,
        "chapter_count": len(chapters),
        "entry_count": total_entries,
        "total_size_bytes": total_bytes,
        "source": "openiti",
    }

    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")
    metadata["total_size_bytes"] = total_bytes + len(meta_json.encode("utf-8"))

    # Rewrite with final size
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")

    return metadata


def main():
    parser = argparse.ArgumentParser(description="Convert OpenITI texts to JSON")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Path to OpenITI RELEASE data directory",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of files to process (0 = all)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Converting OpenITI texts to JSON")
    print("=" * 60)

    # Find mARkdown files
    print(f"\nScanning for mARkdown files in: {args.input_dir}")
    files = find_markdown_files(args.input_dir)
    print(f"  Found {len(files)} text files")

    if not files:
        print("No OpenITI text files found!")
        return

    if args.limit > 0:
        files = files[:args.limit]
        print(f"  Processing first {args.limit} files")

    # Convert files
    all_metadata = []
    skipped = 0
    failed = 0

    for f in tqdm(files, desc="Converting"):
        result = convert_file(f)
        if result:
            all_metadata.append(result)
        elif result is None:
            skipped += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Converted {len(all_metadata)} texts "
          f"({skipped} skipped, {failed} failed)")

    if all_metadata:
        total_entries = sum(m.get("entry_count", 0) for m in all_metadata)
        total_size = sum(m["total_size_bytes"] for m in all_metadata)
        print(f"Total entries: {total_entries:,}")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")

        # Category breakdown
        categories: dict[str, int] = {}
        for m in all_metadata:
            cat = m["category"]
            categories[cat] = categories.get(cat, 0) + 1
        print("\nBy category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count} texts")


if __name__ == "__main__":
    main()
