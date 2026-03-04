"""Fetch hadith books from AhmedBaset/hadith-json and normalize to our schema.

Source: https://github.com/AhmedBaset/hadith-json
CDN: cdn.jsdelivr.net/gh/AhmedBaset/hadith-json@main/db/

Outputs normalized JSON to data/books/hadith/{book_id}/
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

# Add parent to path for utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text, strip_html

# ── Configuration ────────────────────────────────────────────────────────────

CDN_BASE = "https://cdn.jsdelivr.net/gh/AhmedBaset/hadith-json@main/db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books" / "hadith"

# Books organized by their subfolder in the source repo
BOOKS = {
    "the_9_books": [
        "bukhari", "muslim", "abudawud", "tirmidhi", "nasai",
        "ibnmajah", "ahmed", "malik", "darimi",
    ],
    "forties": [
        "nawawi40", "qudsi40", "shahwaliullah40",
    ],
    "other_books": [
        "aladab_almufrad", "bulugh_almaram", "mishkat_almasabih",
        "riyad_assalihin", "shamail_muhammadiyah",
    ],
}

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def fetch_json(url: str) -> dict | None:
    """Fetch JSON from URL with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} for {url}: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  FAILED: {url}: {e}")
                return None


def normalize_book(book_id: str, data: dict) -> tuple[dict, list[dict]]:
    """Convert source JSON to our normalized schema.

    Returns (metadata_dict, list_of_chapter_dicts).
    """
    meta = data["metadata"]
    chapters_src = data.get("chapters", [])
    hadiths_src = data.get("hadiths", [])

    # Build chapter lookup: chapter_id -> chapter info
    chapter_map = {}
    for ch in chapters_src:
        chapter_map[ch["id"]] = {
            "title_ar": clean_text(ch.get("arabic", "")),
            "title_en": clean_text(ch.get("english", "")),
        }

    # Group hadiths by chapter
    hadiths_by_chapter: dict[int, list[dict]] = {}
    for h in hadiths_src:
        ch_id = h.get("chapterId") or 0
        if ch_id not in hadiths_by_chapter:
            hadiths_by_chapter[ch_id] = []

        english = h.get("english", {})
        narrator = english.get("narrator", "") if isinstance(english, dict) else ""
        text_en = english.get("text", "") if isinstance(english, dict) else str(english)

        entry = {
            "id": h.get("idInBook", h.get("id", 0)),
            "text_ar": clean_text(h.get("arabic", "")),
            "text_en": clean_text(text_en),
            "narrator": clean_text(narrator),
            "reference": f"Hadith {h.get('idInBook', h.get('id', 0))}",
        }
        hadiths_by_chapter[ch_id].append(entry)

    # Sort chapters
    sorted_chapter_ids = sorted(hadiths_by_chapter.keys())

    # Build metadata
    metadata = {
        "id": book_id,
        "title_ar": clean_text(meta.get("arabic", {}).get("title", "")),
        "title_en": clean_text(meta.get("english", {}).get("title", "")),
        "author_ar": clean_text(meta.get("arabic", {}).get("author", "")),
        "author_en": clean_text(meta.get("english", {}).get("author", "")),
        "category": "hadith",
        "chapter_count": len(sorted_chapter_ids),
        "hadith_count": meta.get("length", len(hadiths_src)),
        "source": "hadith-json",
        "introduction_ar": clean_text(meta.get("arabic", {}).get("introduction", "")),
        "introduction_en": clean_text(meta.get("english", {}).get("introduction", "")),
    }

    # Build chapter files
    chapters = []
    for idx, ch_id in enumerate(sorted_chapter_ids, start=1):
        ch_info = chapter_map.get(ch_id, {"title_ar": "", "title_en": ""})
        chapter = {
            "book_id": book_id,
            "chapter_id": idx,
            "original_chapter_id": ch_id,
            "title_ar": ch_info["title_ar"],
            "title_en": ch_info["title_en"],
            "entries": hadiths_by_chapter[ch_id],
        }
        chapters.append(chapter)

    return metadata, chapters


def write_book(book_id: str, metadata: dict, chapters: list[dict]) -> int:
    """Write normalized book to disk. Returns total bytes written."""
    book_dir = OUTPUT_DIR / book_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0

    # Write metadata
    meta_path = book_dir / "metadata.json"
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    meta_path.write_text(meta_json, encoding="utf-8")
    total_bytes += len(meta_json.encode("utf-8"))

    # Update metadata with total size after writing chapters
    for ch in chapters:
        ch_path = chapters_dir / f"{ch['chapter_id']}.json"
        ch_json = json.dumps(ch, ensure_ascii=False, indent=2)
        ch_path.write_text(ch_json, encoding="utf-8")
        total_bytes += len(ch_json.encode("utf-8"))

    # Update metadata with total size
    metadata["total_size_bytes"] = total_bytes
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    meta_path.write_text(meta_json, encoding="utf-8")

    return total_bytes


def process_book(category: str, book_name: str) -> dict | None:
    """Fetch and process a single book. Returns metadata or None on failure."""
    url = f"{CDN_BASE}/by_book/{category}/{book_name}.json"
    print(f"  Fetching {book_name}...")
    data = fetch_json(url)
    if data is None:
        return None

    metadata, chapters = normalize_book(book_name, data)
    total_bytes = write_book(book_name, metadata, chapters)

    mb = total_bytes / (1024 * 1024)
    print(f"  OK {book_name}: {metadata['chapter_count']} chapters, "
          f"{metadata['hadith_count']} hadiths, {mb:.2f} MB")
    return metadata


def main():
    print("=" * 60)
    print("Fetching hadith books from AhmedBaset/hadith-json")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_metadata = []
    total_books = sum(len(books) for books in BOOKS.values())

    with tqdm(total=total_books, desc="Books") as pbar:
        for category, books in BOOKS.items():
            print(f"\n-- {category} --")
            for book_name in books:
                meta = process_book(category, book_name)
                if meta:
                    all_metadata.append(meta)
                pbar.update(1)
                time.sleep(0.5)  # Be nice to CDN

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Processed {len(all_metadata)}/{total_books} books")
    total_hadiths = sum(m["hadith_count"] for m in all_metadata)
    total_size = sum(m["total_size_bytes"] for m in all_metadata)
    print(f"Total hadiths: {total_hadiths:,}")
    print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
