"""Fetch Islamic content from IslamHouse.com API v3.

Source: https://islamhouse.com
API docs: https://documenter.getpostman.com/view/7929737/TzkyMfPc

IslamHouse provides curated Islamic content (books, articles, fatwas)
in 90+ languages, licensed for free distribution.

Usage:
    python fetch_islamhouse.py
    python fetch_islamhouse.py --lang ar --limit 100
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text, strip_html

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books"

# IslamHouse API v3
API_BASE = "https://api3.islamhouse.com/v3/pa498zhj"

# Category mapping from IslamHouse categories to ours
# IslamHouse uses numeric category IDs - we map the main ones
ISLAMHOUSE_CATEGORIES = {
    # These will be populated dynamically from the API
}

MAX_RETRIES = 3
RETRY_DELAY = 2


def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    """Make an API request to IslamHouse."""
    url = f"{API_BASE}/{endpoint}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  FAILED {url}: {e}")
                return None


def fetch_categories(lang: str = "ar") -> list[dict]:
    """Fetch available categories from IslamHouse."""
    data = api_get(f"categories/tree/{lang}")
    if not data or "data" not in data:
        return []
    return data["data"]


def fetch_books_list(lang: str = "ar", category_id: int | None = None,
                     page: int = 1, per_page: int = 50) -> dict | None:
    """Fetch list of books from IslamHouse."""
    params = {"page": page, "per_page": per_page}
    if category_id:
        endpoint = f"books/category/{category_id}/{lang}"
    else:
        endpoint = f"books/list/{lang}"
    return api_get(endpoint, params)


def fetch_book_detail(book_id: int, lang: str = "ar") -> dict | None:
    """Fetch detailed book info including attachments."""
    return api_get(f"books/item/{book_id}/{lang}")


def map_category(cat_title: str) -> str:
    """Map IslamHouse category title to our category ID."""
    title_lower = cat_title.lower()
    mapping = {
        "تفسير": "tafseer",
        "حديث": "hadith",
        "فقه": "fiqh",
        "عقيدة": "aqeedah",
        "توحيد": "aqeedah",
        "سيرة": "seerah",
        "رقائق": "raqaiq",
        "أخلاق": "raqaiq",
        "دعوة": "general",
        "quran": "tafseer",
        "hadith": "hadith",
        "fiqh": "fiqh",
        "creed": "aqeedah",
        "biography": "seerah",
    }
    for keyword, cat_id in mapping.items():
        if keyword in cat_title or keyword in title_lower:
            return cat_id
    return "general"


def process_book(book_data: dict, lang: str) -> dict | None:
    """Process a single book from IslamHouse and save as JSON.

    IslamHouse books are typically articles/short texts, not full classical books.
    We treat each book as a single-chapter entry.
    """
    book_id = book_data.get("id")
    if not book_id:
        return None

    title = clean_text(book_data.get("title", ""))
    description = clean_text(strip_html(book_data.get("description", "")))
    add_date = book_data.get("add_date", "")

    # Get author info
    prepared_by = book_data.get("prepared_by", [])
    author_names = [clean_text(a.get("title", "")) for a in prepared_by if a.get("title")]
    author_ar = " ، ".join(author_names) if author_names else ""

    # Get category
    categories = book_data.get("categories", [])
    cat_title = categories[0].get("title", "") if categories else ""
    category = map_category(cat_title)

    # Get content - IslamHouse provides content as read_content or attachments
    content_text = ""
    read_content = book_data.get("read_content")
    if read_content:
        content_text = strip_html(read_content)

    if not content_text and not description:
        return None

    # Build as single chapter
    safe_id = f"islamhouse_{book_id}"
    entries = []

    if content_text:
        # Split long content into paragraphs
        paragraphs = [p.strip() for p in content_text.split('\n') if p.strip()]
        for i, para in enumerate(paragraphs):
            entries.append({
                "id": i + 1,
                "text_ar": clean_text(para),
                "text_en": "",
                "reference": "",
            })
    elif description:
        entries.append({
            "id": 1,
            "text_ar": description,
            "text_en": "",
            "reference": "",
        })

    if not entries:
        return None

    # Write to disk
    book_dir = OUTPUT_DIR / category / safe_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    chapter = {
        "book_id": safe_id,
        "chapter_id": 1,
        "title_ar": title,
        "title_en": "",
        "entries": entries,
    }

    ch_json = json.dumps(chapter, ensure_ascii=False, indent=2)
    (chapters_dir / "1.json").write_text(ch_json, encoding="utf-8")
    total_bytes = len(ch_json.encode("utf-8"))

    metadata = {
        "id": safe_id,
        "title_ar": title,
        "title_en": "",
        "author_ar": author_ar,
        "author_en": "",
        "category": category,
        "chapter_count": 1,
        "entry_count": len(entries),
        "total_size_bytes": total_bytes,
        "source": "islamhouse",
        "islamhouse_id": book_id,
    }

    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")
    metadata["total_size_bytes"] = total_bytes + len(meta_json.encode("utf-8"))

    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")

    return metadata


def main():
    parser = argparse.ArgumentParser(description="Fetch books from IslamHouse API")
    parser.add_argument("--lang", default="ar", help="Language code (default: ar)")
    parser.add_argument("--limit", type=int, default=0, help="Max books to fetch (0 = all)")
    parser.add_argument("--per-page", type=int, default=50, help="Results per API page")
    args = parser.parse_args()

    print("=" * 60)
    print(f"Fetching books from IslamHouse.com ({args.lang})")
    print("=" * 60)

    # Fetch categories first
    print("\nFetching categories...")
    categories = fetch_categories(args.lang)
    if categories:
        print(f"  Found {len(categories)} categories")
    else:
        print("  Warning: could not fetch categories, using default")

    # Fetch books page by page
    all_metadata = []
    page = 1
    total_fetched = 0

    print("\nFetching books...")
    while True:
        data = fetch_books_list(args.lang, page=page, per_page=args.per_page)
        if not data or "data" not in data:
            break

        books = data["data"]
        if not books:
            break

        for book_summary in tqdm(books, desc=f"Page {page}", leave=False):
            # Fetch full book detail
            book_id = book_summary.get("id")
            if not book_id:
                continue

            detail = fetch_book_detail(book_id, args.lang)
            if not detail or "data" not in detail:
                continue

            result = process_book(detail["data"], args.lang)
            if result:
                all_metadata.append(result)

            total_fetched += 1
            if args.limit > 0 and total_fetched >= args.limit:
                break

            time.sleep(0.3)  # Rate limit

        if args.limit > 0 and total_fetched >= args.limit:
            break

        # Check if there are more pages
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break

        page += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Fetched {len(all_metadata)} books (from {total_fetched} checked)")

    if all_metadata:
        total_entries = sum(m.get("entry_count", 0) for m in all_metadata)
        total_size = sum(m["total_size_bytes"] for m in all_metadata)
        print(f"Total entries: {total_entries:,}")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")

        categories_count: dict[str, int] = {}
        for m in all_metadata:
            cat = m["category"]
            categories_count[cat] = categories_count.get(cat, 0) + 1
        print("\nBy category:")
        for cat, count in sorted(categories_count.items()):
            print(f"  {cat}: {count} books")


if __name__ == "__main__":
    main()
