"""Convert Shamela library books from SQLite databases to our JSON schema.

Shamela books use SQLite databases with this schema:
- Main DB: books(id, title), categories(id, title, parentid),
           authors(id, name, information, deathhigriyear),
           bookscategories(bookid, categoryid), booksauthors(bookid, authorid)
- Per-book DB: pages(id, partnumber, pagenumber, page),
              titles(id, title, pageid, parentid)

This script can work with:
1. fekracomputers format: main.db + individual {bookid}.db files
2. Shamela .bok files (which are SQLite databases)

Usage:
    python convert_shamela.py --input-dir /path/to/shamela/books
    python convert_shamela.py --main-db /path/to/main.db --books-dir /path/to/books/

The input directory should contain:
- A main database (main.db or similar) with book/author/category metadata
- Individual book databases (named by book ID, e.g., 1234.db or 1234.bok)
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text, strip_html, normalize_arabic

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books"

# Category mapping from Shamela categories to our categories
CATEGORY_MAP = {
    # Arabic Shamela category keywords -> our category IDs
    "تفسير": "tafseer",
    "حديث": "hadith",
    "مصطلح": "hadith",
    "فقه": "fiqh",
    "أصول الفقه": "fiqh",
    "عقيدة": "aqeedah",
    "توحيد": "aqeedah",
    "سيرة": "seerah",
    "تاريخ": "seerah",
    "تراجم": "seerah",
    "رقائق": "raqaiq",
    "زهد": "raqaiq",
    "تصوف": "raqaiq",
    "أخلاق": "raqaiq",
    "آداب": "raqaiq",
    "لغة": "arabic_language",
    "نحو": "arabic_language",
    "صرف": "arabic_language",
    "بلاغة": "arabic_language",
    "أدب": "arabic_language",
}

DEFAULT_CATEGORY = "general"

# Target size for merged prose entries (Arabic characters).
MAX_MERGE_CHARS = 3000


def _merge_prose_entries(texts: list[str]) -> list[dict]:
    """Merge short text fragments into ~3000-char prose blocks.

    Joins consecutive paragraphs with \\n\\n so books read as flowing
    text rather than numbered verse collections.
    """
    merged = []
    parts: list[str] = []
    char_count = 0

    def flush():
        nonlocal char_count
        if not parts:
            return
        merged.append({
            "id": len(merged) + 1,
            "text_ar": "\n\n".join(parts),
            "text_en": "",
            "reference": "",
        })
        parts.clear()
        char_count = 0

    for text in texts:
        text = text.strip()
        if not text:
            continue
        parts.append(text)
        char_count += len(text)
        if char_count >= MAX_MERGE_CHARS:
            flush()

    flush()
    return merged


def map_category(category_name: str) -> str:
    """Map Shamela category name to our category ID."""
    normalized = normalize_arabic(category_name)
    for keyword, cat_id in CATEGORY_MAP.items():
        if keyword in category_name or keyword in normalized:
            return cat_id
    return DEFAULT_CATEGORY


def load_main_db(db_path: str) -> dict:
    """Load metadata from the main Shamela database.

    Returns dict of book_id -> {title, author, category, ...}
    """
    books = {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Load categories
        categories = {}
        try:
            for row in conn.execute("SELECT id, title FROM categories"):
                categories[row["id"]] = clean_text(row["title"])
        except sqlite3.OperationalError:
            print("  Warning: no categories table found")

        # Load authors
        authors = {}
        try:
            for row in conn.execute("SELECT id, name, deathhigriyear FROM authors"):
                authors[row["id"]] = {
                    "name": clean_text(row["name"]),
                    "death_hijri": row["deathhigriyear"],
                }
        except sqlite3.OperationalError:
            print("  Warning: no authors table found")

        # Load book-category mappings
        book_categories = {}
        try:
            for row in conn.execute("SELECT bookid, categoryid FROM bookscategories"):
                book_categories[row["bookid"]] = row["categoryid"]
        except sqlite3.OperationalError:
            pass

        # Load book-author mappings
        book_authors = {}
        try:
            for row in conn.execute("SELECT bookid, authorid FROM booksauthors"):
                book_authors[row["bookid"]] = row["authorid"]
        except sqlite3.OperationalError:
            pass

        # Load books
        try:
            for row in conn.execute("SELECT id, title FROM books"):
                book_id = row["id"]
                cat_id = book_categories.get(book_id)
                cat_name = categories.get(cat_id, "") if cat_id else ""
                author_id = book_authors.get(book_id)
                author_info = authors.get(author_id, {}) if author_id else {}

                books[book_id] = {
                    "title_ar": clean_text(row["title"]),
                    "author_ar": author_info.get("name", ""),
                    "death_hijri": author_info.get("death_hijri"),
                    "category_name": cat_name,
                    "category": map_category(cat_name),
                }
        except sqlite3.OperationalError as e:
            print(f"  Error loading books: {e}")

    finally:
        conn.close()

    return books


def convert_book_db(book_db_path: str, book_id: int, meta: dict) -> dict | None:
    """Convert a single book SQLite database to our JSON schema.

    Returns metadata dict or None on failure.
    """
    conn = sqlite3.connect(book_db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Load titles (table of contents / chapters)
        titles = []
        try:
            for row in conn.execute(
                "SELECT id, title, pageid, parentid FROM titles ORDER BY id"
            ):
                titles.append({
                    "id": row["id"],
                    "title": clean_text(row["title"]),
                    "pageid": row["pageid"],
                    "parentid": row["parentid"],
                })
        except sqlite3.OperationalError:
            pass

        # Load pages
        pages = []
        try:
            for row in conn.execute(
                "SELECT id, partnumber, pagenumber, page FROM pages "
                "ORDER BY partnumber, pagenumber"
            ):
                text = strip_html(row["page"]) if row["page"] else ""
                if text.strip():
                    pages.append({
                        "id": row["id"],
                        "part": row["partnumber"],
                        "page_num": row["pagenumber"],
                        "text": text,
                    })
        except sqlite3.OperationalError as e:
            print(f"  Error reading pages for book {book_id}: {e}")
            return None

        if not pages:
            return None

        # Group pages into chapters based on titles
        chapters = _build_chapters(titles, pages, book_id, meta)

        if not chapters:
            # If no titles, treat the whole book as one chapter
            chapters = [{
                "book_id": str(book_id),
                "chapter_id": 1,
                "title_ar": meta.get("title_ar", ""),
                "title_en": "",
                "entries": _merge_prose_entries([
                    p["text"] for p in pages
                ]),
            }]

        # Write to disk
        category = meta.get("category", DEFAULT_CATEGORY)
        safe_id = f"shamela_{book_id}"
        book_dir = OUTPUT_DIR / category / safe_id
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
            "id": safe_id,
            "title_ar": meta.get("title_ar", ""),
            "title_en": "",
            "author_ar": meta.get("author_ar", ""),
            "author_en": "",
            "category": category,
            "chapter_count": len(chapters),
            "entry_count": total_entries,
            "total_size_bytes": total_bytes,
            "source": "shamela",
            "shamela_id": book_id,
        }

        meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")
        metadata["total_size_bytes"] = total_bytes + len(meta_json.encode("utf-8"))

        # Rewrite with final size
        meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")

        return metadata

    finally:
        conn.close()


def _build_chapters(
    titles: list[dict], pages: list[dict], book_id: int, meta: dict
) -> list[dict]:
    """Group pages into chapters based on title page references."""
    if not titles:
        return []

    # Build page_id -> page lookup
    page_by_id = {p["id"]: p for p in pages}

    # Sort titles by pageid to get chapter order
    sorted_titles = sorted(
        [t for t in titles if t.get("parentid", 0) == 0 or t.get("parentid") is None],
        key=lambda t: t.get("pageid", 0),
    )

    # If no top-level titles, use all titles
    if not sorted_titles:
        sorted_titles = sorted(titles, key=lambda t: t.get("pageid", 0))

    # Assign page ranges to chapters
    chapters = []
    for idx, title in enumerate(sorted_titles):
        start_page_id = title.get("pageid", 0)

        # End page is the start of next chapter (or end of book)
        if idx + 1 < len(sorted_titles):
            end_page_id = sorted_titles[idx + 1].get("pageid", float("inf"))
        else:
            end_page_id = float("inf")

        # Collect pages in this range
        chapter_pages = [
            p for p in pages
            if start_page_id <= p["id"] < end_page_id
        ]

        if not chapter_pages:
            continue

        entries = _merge_prose_entries([
            p["text"] for p in chapter_pages
        ])

        chapters.append({
            "book_id": str(book_id),
            "chapter_id": idx + 1,
            "title_ar": title.get("title", ""),
            "title_en": "",
            "entries": entries,
        })

    return chapters


def find_book_databases(books_dir: str) -> dict[int, str]:
    """Find all book database files in a directory.

    Returns dict of book_id -> file_path.
    Supports .db, .sqlite, and .bok extensions.
    """
    book_files = {}
    books_path = Path(books_dir)

    for ext in ("*.db", "*.sqlite", "*.bok"):
        for f in books_path.glob(ext):
            # Extract book ID from filename (expect numeric name)
            stem = f.stem
            if stem.isdigit():
                book_files[int(stem)] = str(f)

    return book_files


def main():
    parser = argparse.ArgumentParser(description="Convert Shamela books to JSON")
    parser.add_argument(
        "--main-db",
        help="Path to main Shamela database (main.db) with book/author/category metadata",
    )
    parser.add_argument(
        "--books-dir",
        required=True,
        help="Directory containing individual book databases (e.g., 1234.db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of books to process (0 = all)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Converting Shamela books to JSON")
    print("=" * 60)

    # Load main database metadata
    book_meta = {}
    if args.main_db and Path(args.main_db).exists():
        print(f"\nLoading main database: {args.main_db}")
        book_meta = load_main_db(args.main_db)
        print(f"  Found {len(book_meta)} books in main database")
    else:
        print("\nNo main database provided, will use minimal metadata")

    # Find book databases
    print(f"\nScanning for book databases in: {args.books_dir}")
    book_files = find_book_databases(args.books_dir)
    print(f"  Found {len(book_files)} book databases")

    if not book_files:
        print("No book databases found!")
        return

    # Limit if requested
    book_ids = sorted(book_files.keys())
    if args.limit > 0:
        book_ids = book_ids[: args.limit]
        print(f"  Processing first {args.limit} books")

    # Convert books
    all_metadata = []
    failed = 0

    for bid in tqdm(book_ids, desc="Converting"):
        meta = book_meta.get(bid, {
            "title_ar": f"كتاب {bid}",
            "author_ar": "",
            "category": DEFAULT_CATEGORY,
        })

        result = convert_book_db(book_files[bid], bid, meta)
        if result:
            all_metadata.append(result)
        else:
            failed += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Converted {len(all_metadata)}/{len(book_ids)} books ({failed} failed)")

    if all_metadata:
        total_entries = sum(m.get("entry_count", 0) for m in all_metadata)
        total_size = sum(m["total_size_bytes"] for m in all_metadata)
        print(f"Total entries: {total_entries:,}")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")

        # Category breakdown
        categories = {}
        for m in all_metadata:
            cat = m["category"]
            categories[cat] = categories.get(cat, 0) + 1
        print("\nBy category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count} books")


if __name__ == "__main__":
    main()
