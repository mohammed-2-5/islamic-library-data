"""Build master catalog.json from all processed books.

Scans data/books/{category}/{book_id}/metadata.json and aggregates
into a single catalog.json file.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOOKS_DIR = DATA_DIR / "books"
CATALOG_PATH = DATA_DIR / "catalog.json"

CATEGORIES = [
    {"id": "hadith", "name_ar": "الحديث", "name_en": "Hadith", "icon": "menu_book"},
    {"id": "tafseer", "name_ar": "التفسير", "name_en": "Exegesis", "icon": "auto_stories"},
    {"id": "fiqh", "name_ar": "الفقه", "name_en": "Jurisprudence", "icon": "gavel"},
    {"id": "aqeedah", "name_ar": "العقيدة", "name_en": "Creed", "icon": "star"},
    {"id": "seerah", "name_ar": "السيرة", "name_en": "Prophetic Biography", "icon": "history_edu"},
    {"id": "tazkiyah", "name_ar": "التزكية", "name_en": "Purification", "icon": "favorite"},
    {"id": "arabic_language", "name_ar": "اللغة العربية", "name_en": "Arabic Language", "icon": "translate"},
    {"id": "general", "name_ar": "عام", "name_en": "General", "icon": "library_books"},
]

# Books to mark as featured (well-known, important books)
FEATURED_BOOKS = {
    "bukhari", "muslim", "riyad_assalihin", "nawawi40",
    "tafsir_ibn_kathir", "tafsir_al_qurtubi", "tafsir_muyassar",
    "tafsir_al_tabari", "tafsir_al_saadi", "tafsir_al_baghawi",
    "mishkat_almasabih", "bulugh_almaram",
}


def scan_books() -> list[dict]:
    """Scan all book directories and collect metadata."""
    books = []

    if not BOOKS_DIR.exists():
        print(f"No books directory found at {BOOKS_DIR}")
        return books

    for category_dir in sorted(BOOKS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue

        category = category_dir.name

        for book_dir in sorted(category_dir.iterdir()):
            if not book_dir.is_dir():
                continue

            meta_path = book_dir / "metadata.json"
            if not meta_path.exists():
                print(f"  WARNING: No metadata.json in {book_dir}")
                continue

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                print(f"  ERROR reading {meta_path}: {e}")
                continue

            # Build catalog entry (subset of metadata)
            book_entry = {
                "id": meta.get("id", book_dir.name),
                "title_ar": meta.get("title_ar", ""),
                "title_en": meta.get("title_en", ""),
                "author_ar": meta.get("author_ar", ""),
                "author_en": meta.get("author_en", ""),
                "category": meta.get("category", category),
                "chapter_count": meta.get("chapter_count", 0),
                "total_size_bytes": meta.get("total_size_bytes", 0),
                "source": meta.get("source", "unknown"),
                "featured": meta.get("id", book_dir.name) in FEATURED_BOOKS,
            }
            books.append(book_entry)

    return books


def build_catalog(books: list[dict]) -> dict:
    """Build the full catalog structure."""
    # Filter categories to only include those with books
    used_categories = {b["category"] for b in books}
    active_categories = [c for c in CATEGORIES if c["id"] in used_categories]

    return {
        "version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "categories": active_categories,
        "books": sorted(books, key=lambda b: (b["category"], b["title_ar"])),
    }


def main():
    print("=" * 60)
    print("Building catalog.json")
    print("=" * 60)

    books = scan_books()
    if not books:
        print("No books found!")
        return

    catalog = build_catalog(books)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)
    CATALOG_PATH.write_text(catalog_json, encoding="utf-8")

    # Stats
    print(f"\nCatalog built:")
    print(f"  Books: {len(books)}")
    print(f"  Categories: {len(catalog['categories'])}")
    for cat in catalog["categories"]:
        count = sum(1 for b in books if b["category"] == cat["id"])
        print(f"    {cat['name_ar']} ({cat['name_en']}): {count} books")
    featured = sum(1 for b in books if b.get("featured"))
    print(f"  Featured: {featured}")
    total_size = sum(b["total_size_bytes"] for b in books)
    print(f"  Total size: {total_size / (1024 * 1024):.2f} MB")
    print(f"  Output: {CATALOG_PATH}")


if __name__ == "__main__":
    main()
