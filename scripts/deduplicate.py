"""Deduplicate books across multiple sources.

When the same book exists in multiple sources (e.g., Sahih Bukhari in
hadith-json AND Shamela AND OpenITI), we keep the best version and remove duplicates.

Priority order:
1. hadith-json (best structured, Arabic + English, already normalized)
2. tafsir-api (well-structured, per-ayah)
3. openiti (good quality text, academic markup)
4. shamela (largest collection, variable quality)
5. islamhouse (mostly short articles, not classical books)

Matching strategy:
- Normalize Arabic titles (strip diacritics, normalize hamza/alef/ya/ta)
- Fuzzy match titles with rapidfuzz (threshold: 85%)
- Also check author similarity when available
- Log all decisions to dedup_report.json

Usage:
    python deduplicate.py
    python deduplicate.py --dry-run
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import normalize_arabic

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOOKS_DIR = DATA_DIR / "books"
REPORT_PATH = DATA_DIR / "dedup_report.json"

# Source priority (lower = higher priority = keep)
SOURCE_PRIORITY = {
    "hadith-json": 1,
    "tafsir-api": 2,
    "openiti": 3,
    "shamela": 4,
    "islamhouse": 5,
}

TITLE_MATCH_THRESHOLD = 85
AUTHOR_MATCH_THRESHOLD = 80


def load_all_books() -> list[dict]:
    """Load metadata for all books."""
    books = []

    if not BOOKS_DIR.exists():
        return books

    for category_dir in BOOKS_DIR.iterdir():
        if not category_dir.is_dir():
            continue

        for book_dir in category_dir.iterdir():
            if not book_dir.is_dir():
                continue

            meta_path = book_dir / "metadata.json"
            if not meta_path.exists():
                continue

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["_path"] = str(book_dir)
                meta["_category_dir"] = category_dir.name
                books.append(meta)
            except (json.JSONDecodeError, OSError):
                continue

    return books


def find_duplicates(books: list[dict]) -> list[tuple[dict, dict, float]]:
    """Find potential duplicate pairs.

    Returns list of (book_a, book_b, similarity_score) tuples
    where book_a has LOWER priority (should be removed).
    """
    duplicates = []

    # Precompute normalized titles
    normalized = []
    for book in books:
        norm_title = normalize_arabic(book.get("title_ar", ""))
        norm_author = normalize_arabic(book.get("author_ar", ""))
        normalized.append((norm_title, norm_author))

    # Compare all pairs
    for i in range(len(books)):
        for j in range(i + 1, len(books)):
            title_i, author_i = normalized[i]
            title_j, author_j = normalized[j]

            # Skip if either title is empty
            if not title_i or not title_j:
                continue

            # Skip if same source and same ID (not a duplicate)
            if (books[i].get("source") == books[j].get("source") and
                    books[i].get("id") == books[j].get("id")):
                continue

            # Compare titles
            title_score = fuzz.ratio(title_i, title_j)
            if title_score < TITLE_MATCH_THRESHOLD:
                continue

            # If authors available, also check author similarity
            author_score = 100  # Default: assume match if no author info
            if author_i and author_j:
                author_score = fuzz.ratio(author_i, author_j)
                if author_score < AUTHOR_MATCH_THRESHOLD:
                    continue

            combined_score = (title_score * 0.7 + author_score * 0.3)

            # Determine which to keep (lower priority number = keep)
            pri_i = SOURCE_PRIORITY.get(books[i].get("source", ""), 99)
            pri_j = SOURCE_PRIORITY.get(books[j].get("source", ""), 99)

            if pri_i <= pri_j:
                # Keep i, remove j
                duplicates.append((books[j], books[i], combined_score))
            else:
                # Keep j, remove i
                duplicates.append((books[i], books[j], combined_score))

    return duplicates


def main():
    parser = argparse.ArgumentParser(description="Deduplicate books across sources")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report duplicates, don't delete anything",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=TITLE_MATCH_THRESHOLD,
        help=f"Title similarity threshold (default: {TITLE_MATCH_THRESHOLD})",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Deduplicating Islamic Library books")
    print("=" * 60)

    # Load all books
    print("\nLoading book metadata...")
    books = load_all_books()
    print(f"  Found {len(books)} total books")

    if len(books) < 2:
        print("Not enough books to deduplicate")
        return

    # Source breakdown
    sources: dict[str, int] = {}
    for b in books:
        src = b.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    print("\nBy source:")
    for src, count in sorted(sources.items()):
        print(f"  {src}: {count} books")

    # Find duplicates
    print(f"\nFinding duplicates (threshold: {args.threshold}%)...")
    duplicates = find_duplicates(books)
    print(f"  Found {len(duplicates)} duplicate pairs")

    if not duplicates:
        print("No duplicates found!")
        return

    # Report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_books": len(books),
        "duplicates_found": len(duplicates),
        "dry_run": args.dry_run,
        "pairs": [],
    }

    removed_paths = set()

    for to_remove, to_keep, score in duplicates:
        pair_info = {
            "remove": {
                "id": to_remove.get("id"),
                "title_ar": to_remove.get("title_ar"),
                "source": to_remove.get("source"),
                "path": to_remove.get("_path"),
            },
            "keep": {
                "id": to_keep.get("id"),
                "title_ar": to_keep.get("title_ar"),
                "source": to_keep.get("source"),
                "path": to_keep.get("_path"),
            },
            "similarity": round(score, 1),
        }
        report["pairs"].append(pair_info)

        remove_path = to_remove.get("_path")
        if remove_path and remove_path not in removed_paths:
            print(f"\n  DUPLICATE (score: {score:.0f}%):")
            print(f"    Remove: [{to_remove.get('source')}] {to_remove.get('title_ar')}")
            print(f"    Keep:   [{to_keep.get('source')}] {to_keep.get('title_ar')}")

            if not args.dry_run:
                try:
                    shutil.rmtree(remove_path)
                    print(f"    DELETED: {remove_path}")
                    removed_paths.add(remove_path)
                except OSError as e:
                    print(f"    ERROR deleting: {e}")
            else:
                removed_paths.add(remove_path)

    # Save report
    report["total_removed"] = len(removed_paths)
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    REPORT_PATH.write_text(report_json, encoding="utf-8")

    # Summary
    print(f"\n{'=' * 60}")
    action = "Would remove" if args.dry_run else "Removed"
    print(f"{action} {len(removed_paths)} duplicate books")
    print(f"Report saved to: {REPORT_PATH}")

    if args.dry_run:
        print("\nThis was a dry run. Use without --dry-run to actually delete duplicates.")


if __name__ == "__main__":
    main()
