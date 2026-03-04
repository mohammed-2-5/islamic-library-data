"""Validate all JSON files against expected schemas.

Checks:
- All metadata.json files have required fields
- All chapter files have required fields and non-empty entries
- catalog.json is well-formed
- No empty chapters or missing text
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOOKS_DIR = DATA_DIR / "books"
CATALOG_PATH = DATA_DIR / "catalog.json"

METADATA_REQUIRED = {"id", "title_ar", "category", "chapter_count", "total_size_bytes", "source"}
CHAPTER_REQUIRED = {"book_id", "chapter_id", "entries"}
ENTRY_REQUIRED = {"id", "text_ar"}


class ValidationReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.stats = {
            "books": 0,
            "chapters": 0,
            "entries": 0,
            "empty_entries": 0,
            "total_bytes": 0,
        }

    def error(self, msg: str):
        self.errors.append(msg)
        print(f"  ERROR: {msg}")

    def warn(self, msg: str):
        self.warnings.append(msg)

    def summary(self):
        print(f"\n{'=' * 60}")
        print("Validation Summary")
        print(f"{'=' * 60}")
        print(f"  Books: {self.stats['books']}")
        print(f"  Chapters: {self.stats['chapters']}")
        print(f"  Entries: {self.stats['entries']}")
        print(f"  Empty entries: {self.stats['empty_entries']}")
        print(f"  Total size: {self.stats['total_bytes'] / (1024*1024):.2f} MB")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")
        if self.warnings:
            print(f"\nWarnings:")
            for w in self.warnings[:20]:
                print(f"  - {w}")
            if len(self.warnings) > 20:
                print(f"  ... and {len(self.warnings) - 20} more")
        if self.errors:
            print(f"\nErrors:")
            for e in self.errors:
                print(f"  - {e}")
        return len(self.errors) == 0


def validate_metadata(meta_path: Path, report: ValidationReport) -> dict | None:
    """Validate a metadata.json file."""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        report.error(f"Cannot read {meta_path}: {e}")
        return None

    missing = METADATA_REQUIRED - set(meta.keys())
    if missing:
        report.error(f"{meta_path}: missing fields: {missing}")

    if not meta.get("title_ar"):
        report.warn(f"{meta_path}: empty title_ar")

    if meta.get("chapter_count", 0) == 0:
        report.warn(f"{meta_path}: chapter_count is 0")

    return meta


def validate_chapter(ch_path: Path, report: ValidationReport):
    """Validate a single chapter JSON file."""
    try:
        chapter = json.loads(ch_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        report.error(f"Cannot read {ch_path}: {e}")
        return

    missing = CHAPTER_REQUIRED - set(chapter.keys())
    if missing:
        report.error(f"{ch_path}: missing fields: {missing}")
        return

    entries = chapter.get("entries", [])
    if not entries:
        report.warn(f"{ch_path}: no entries")

    report.stats["entries"] += len(entries)

    for entry in entries:
        entry_missing = ENTRY_REQUIRED - set(entry.keys())
        if entry_missing:
            report.error(f"{ch_path} entry {entry.get('id', '?')}: missing {entry_missing}")

        if not entry.get("text_ar", "").strip():
            report.stats["empty_entries"] += 1

    report.stats["total_bytes"] += ch_path.stat().st_size


def validate_catalog(report: ValidationReport):
    """Validate catalog.json."""
    if not CATALOG_PATH.exists():
        report.error("catalog.json not found")
        return

    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        report.error(f"Cannot read catalog.json: {e}")
        return

    if "version" not in catalog:
        report.error("catalog.json: missing 'version'")
    if "categories" not in catalog:
        report.error("catalog.json: missing 'categories'")
    if "books" not in catalog:
        report.error("catalog.json: missing 'books'")
        return

    book_ids = [b["id"] for b in catalog["books"]]
    if len(book_ids) != len(set(book_ids)):
        dupes = [bid for bid in book_ids if book_ids.count(bid) > 1]
        report.error(f"catalog.json: duplicate book IDs: {set(dupes)}")

    print(f"  catalog.json: {len(catalog['books'])} books, "
          f"{len(catalog['categories'])} categories")


def main():
    print("=" * 60)
    print("Validating Islamic Library Data")
    print("=" * 60)

    report = ValidationReport()

    # Validate catalog
    print("\nValidating catalog.json...")
    validate_catalog(report)

    # Validate books
    if BOOKS_DIR.exists():
        for category_dir in sorted(BOOKS_DIR.iterdir()):
            if not category_dir.is_dir():
                continue

            print(f"\nValidating {category_dir.name}/...")

            for book_dir in sorted(category_dir.iterdir()):
                if not book_dir.is_dir():
                    continue

                report.stats["books"] += 1

                # Validate metadata
                meta_path = book_dir / "metadata.json"
                if not meta_path.exists():
                    report.error(f"{book_dir.name}: no metadata.json")
                    continue
                meta = validate_metadata(meta_path, report)

                # Validate chapters
                chapters_dir = book_dir / "chapters"
                if not chapters_dir.exists():
                    report.error(f"{book_dir.name}: no chapters/ directory")
                    continue

                chapter_files = sorted(chapters_dir.glob("*.json"),
                                       key=lambda p: int(p.stem) if p.stem.isdigit() else 0)

                if not chapter_files:
                    report.error(f"{book_dir.name}: no chapter files")
                    continue

                report.stats["chapters"] += len(chapter_files)

                # Check chapter count matches metadata
                if meta and meta.get("chapter_count", 0) != len(chapter_files):
                    report.warn(f"{book_dir.name}: metadata says {meta.get('chapter_count')} chapters, "
                                f"found {len(chapter_files)} files")

                for ch_path in chapter_files:
                    validate_chapter(ch_path, report)
    else:
        report.error(f"Books directory not found: {BOOKS_DIR}")

    # Summary
    success = report.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
