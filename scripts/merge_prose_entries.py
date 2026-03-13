#!/usr/bin/env python3
"""Merge fragmented paragraph entries into proper prose blocks.

The original pipeline splits prose books into one-entry-per-paragraph,
which works for hadith collections but makes fiqh/aqeedah/tazkiyah/seerah
books read like numbered verse collections instead of flowing text.

This script:
1. Scans data/books/ for prose categories
2. Merges consecutive entries within each chapter into ~3000-char blocks
3. Rewrites chapter JSON files and updates metadata

Categories merged: aqeedah, fiqh, tazkiyah, seerah
Categories skipped: hadith (numbered hadiths), tafseer (ayah-level structure)

Usage:
    python merge_prose_entries.py              # apply changes
    python merge_prose_entries.py --dry-run    # preview only
"""

import json
import sys
from pathlib import Path

# Fix Windows console encoding for Arabic text
sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "books"

# Categories where entries should be merged into prose blocks.
# hadith: each hadith is a distinct numbered unit — keep as-is.
# tafseer: ayah-level commentary structure is meaningful — keep as-is.
PROSE_CATEGORIES = {"aqeedah", "fiqh", "tazkiyah", "seerah"}

# Target size for merged entries (Arabic characters).
# ~3000 chars ≈ one printed book page.
MAX_CHARS = 3000


def merge_entries(entries: list[dict]) -> list[dict]:
    """Merge small consecutive entries into larger prose blocks.

    Joins Arabic text with paragraph breaks (\\n\\n).
    English translations are joined similarly if present.
    """
    if not entries:
        return entries

    merged = []
    arabic_parts: list[str] = []
    english_parts: list[str] = []
    char_count = 0

    def flush():
        nonlocal char_count
        if not arabic_parts:
            return
        en_joined = "\n\n".join(p for p in english_parts if p)
        merged.append({
            "id": len(merged) + 1,
            "text_ar": "\n\n".join(arabic_parts),
            "text_en": en_joined,
            "reference": "",
        })
        arabic_parts.clear()
        english_parts.clear()
        char_count = 0

    for entry in entries:
        ar = entry.get("text_ar", "").strip()
        en = entry.get("text_en", "").strip()

        if not ar:
            continue

        arabic_parts.append(ar)
        if en:
            english_parts.append(en)
        char_count += len(ar)

        if char_count >= MAX_CHARS:
            flush()

    flush()
    return merged


def process_book(book_dir: Path, dry_run: bool = False) -> tuple[int, int]:
    """Process a single book, merging entries in all chapters.

    Returns (old_entry_count, new_entry_count).
    """
    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        return 0, 0

    old_total = 0
    new_total = 0
    total_bytes = 0

    chapter_files = sorted(
        chapters_dir.glob("*.json"),
        key=lambda f: int(f.stem) if f.stem.isdigit() else 0,
    )

    for ch_file in chapter_files:
        try:
            data = json.loads(ch_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"    WARN: skipping {ch_file.name}: {e}")
            continue

        entries = data.get("entries", [])
        old_total += len(entries)

        merged = merge_entries(entries)
        new_total += len(merged)

        data["entries"] = merged

        if not dry_run:
            ch_json = json.dumps(data, ensure_ascii=False, indent=2)
            ch_file.write_text(ch_json, encoding="utf-8")
            total_bytes += len(ch_json.encode("utf-8"))

    # Update metadata
    if not dry_run:
        meta_file = book_dir / "metadata.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["entry_count"] = new_total
                meta["total_size_bytes"] = total_bytes
                meta_json = json.dumps(meta, ensure_ascii=False, indent=2)
                meta_file.write_text(meta_json, encoding="utf-8")
                # Rewrite with corrected total (includes metadata file itself)
                meta["total_size_bytes"] = total_bytes + len(
                    meta_json.encode("utf-8")
                )
                meta_json = json.dumps(meta, ensure_ascii=False, indent=2)
                meta_file.write_text(meta_json, encoding="utf-8")
            except (json.JSONDecodeError, OSError) as e:
                print(f"    WARN: metadata update failed: {e}")

    return old_total, new_total


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("DRY RUN - no files will be modified\n")

    print("=" * 60)
    print("Merging prose book entries")
    print("=" * 60)

    grand_old = 0
    grand_new = 0
    books_processed = 0

    for category in sorted(PROSE_CATEGORIES):
        cat_dir = DATA_DIR / category
        if not cat_dir.exists():
            continue

        print(f"\n--- {category} ---")

        for book_dir in sorted(cat_dir.iterdir()):
            if not book_dir.is_dir():
                continue

            old_count, new_count = process_book(book_dir, dry_run)
            if old_count > 0:
                pct = new_count / old_count * 100
                print(
                    f"  {book_dir.name}: "
                    f"{old_count} -> {new_count} entries ({pct:.0f}%)"
                )
                grand_old += old_count
                grand_new += new_count
                books_processed += 1

    print(f"\n{'=' * 60}")
    print(f"Processed {books_processed} books")
    if grand_old > 0:
        pct = grand_new / grand_old * 100
        print(f"Total entries: {grand_old:,} -> {grand_new:,} ({pct:.0f}%)")

    if dry_run:
        print("\nRun without --dry-run to apply changes.")
    else:
        print("\nDone! Run build_catalog.py to update catalog.json.")


if __name__ == "__main__":
    main()
