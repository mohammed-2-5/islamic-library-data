#!/usr/bin/env python3
"""
Islamic Library Data — Explorer
================================
A quick-reference CLI for browsing and querying all datasets in this repo.

Usage:
    python scripts/explore.py                   # interactive menu
    python scripts/explore.py stats             # print full stats
    python scripts/explore.py surah 2           # info about Al-Baqarah
    python scripts/explore.py azkar morning     # list morning azkar
    python scripts/explore.py hadith bukhari 1  # first hadith in Bukhari
    python scripts/explore.py names 1           # first of 99 Names of Allah
    python scripts/explore.py prophet adam      # Adam's story summary
    python scripts/explore.py library           # list all library books
    python scripts/explore.py library tafseer   # library books by category
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Helpers ──────────────────────────────────────────────────────────────────

def load(path):
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as f:
        return json.load(f)


def exists(path):
    return os.path.exists(os.path.join(ROOT, path))


def hr(char="─", width=60):
    print(char * width)


def header(title):
    hr("═")
    print(f"  {title}")
    hr("═")


# ── Stats ─────────────────────────────────────────────────────────────────────

def cmd_stats():
    header("Islamic Library Data — Full Stats")

    # Quran
    print("\n📖  QURAN")
    ar_chapters = len([f for f in os.listdir(os.path.join(ROOT, "quran/chapters/ar")) if f.endswith(".json")])
    en_chapters = len([f for f in os.listdir(os.path.join(ROOT, "quran/chapters/en")) if f.endswith(".json")])
    tajweed_files = len(os.listdir(os.path.join(ROOT, "quran/tajweed")))
    segs = load("quran/quran_segments.json")
    seg_count = sum(len(v) for v in segs.values()) if isinstance(segs, dict) else len(segs)
    print(f"   Surah metadata  : {ar_chapters} AR + {en_chapters} EN")
    print(f"   Tajweed rules   : {tajweed_files} surah files")
    print(f"   Thematic segments: {seg_count}")

    # Azkar
    print("\n🤲  AZKAR & DUAS")
    azkar_dir = os.path.join(ROOT, "azkar")
    for fname in sorted(os.listdir(azkar_dir)):
        if not fname.endswith(".json"):
            continue
        d = load(f"azkar/{fname}")
        items = len(d) if isinstance(d, list) else len(d.get("azkar", d.get("items", [])))
        print(f"   {fname:<35} {items} items")

    # Hadith
    print("\n📚  HADITH COLLECTIONS")
    for fname in sorted(os.listdir(os.path.join(ROOT, "hadith"))):
        if not fname.endswith(".json"):
            continue
        d = load(f"hadith/{fname}")
        count = len(d) if isinstance(d, list) else sum(len(v) for v in d.values() if isinstance(v, list))
        size_mb = os.path.getsize(os.path.join(ROOT, "hadith", fname)) / 1024 / 1024
        print(f"   {fname:<25} {count:>6} hadith  ({size_mb:.1f} MB)")

    # Forties
    print("\n📜  40 HADITH COLLECTIONS")
    for fname in sorted(os.listdir(os.path.join(ROOT, "forties"))):
        if not fname.endswith(".json"):
            continue
        d = load(f"forties/{fname}")
        count = len(d) if isinstance(d, list) else len(d.get("hadiths", []))
        print(f"   {fname:<35} {count} hadith")

    # Prophet stories
    print("\n🕌  PROPHET STORIES")
    idx = load("prophet_stories/index.json")
    stories = idx if isinstance(idx, list) else idx.get("stories", list(idx.values()))
    print(f"   {len(stories)} prophet stories")
    quiz_dir = os.path.join(ROOT, "prophet_stories/quizzes")
    if os.path.exists(quiz_dir):
        print(f"   {len(os.listdir(quiz_dir))} quiz files")

    # Names
    print("\n✨  99 NAMES OF ALLAH")
    names = load("names_of_allah/names_of_allah.json")
    count = len(names) if isinstance(names, list) else len(names.get("names", []))
    print(f"   {count} names with meanings")

    # Tafseer
    print("\n📝  TAFSEER")
    tf = load("tafseer/muyassar.json")
    count = len(tf) if isinstance(tf, list) else sum(len(v) for v in tf.values() if isinstance(v, list))
    size_mb = os.path.getsize(os.path.join(ROOT, "tafseer/muyassar.json")) / 1024 / 1024
    print(f"   Tafseer Muyassar: {count} entries ({size_mb:.1f} MB)")

    # Library
    print("\n📦  ISLAMIC LIBRARY (CDN books)")
    cat = load("data/catalog.json")
    books = cat["books"]
    pdf_books = [b for b in books if b.get("pdf_url")]
    text_books = [b for b in books if not b.get("pdf_url")]
    from collections import Counter
    cats = Counter(b["category"] for b in books)
    print(f"   Total: {len(books)} books  ({len(pdf_books)} PDF + {len(text_books)} text)")
    for c, n in cats.most_common():
        print(f"     {c:<12} {n}")

    # Fonts
    print("\n🔤  FONTS")
    fonts_dir = os.path.join(ROOT, "fonts")
    for fname in sorted(os.listdir(fonts_dir)):
        path = os.path.join(fonts_dir, fname)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / 1024 / 1024
            print(f"   {fname:<35} {size_mb:.1f} MB")

    # Audio
    print("\n🔊  AUDIO")
    for fname in sorted(os.listdir(os.path.join(ROOT, "audio"))):
        path = os.path.join(ROOT, "audio", fname)
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"   {fname:<35} {size_mb:.1f} MB")

    print()
    hr()


# ── Surah ─────────────────────────────────────────────────────────────────────

def cmd_surah(num):
    try:
        n = int(num)
    except ValueError:
        print("Usage: surah <1-114>")
        return

    ar_path = f"quran/chapters/ar/{n}.json"
    en_path = f"quran/chapters/en/{n}.json"

    if not exists(ar_path):
        print(f"Surah {n} not found.")
        return

    ar = load(ar_path)
    en = load(en_path) if exists(en_path) else {}

    header(f"Surah {n}")
    print(f"  Arabic name   : {ar.get('name', ar.get('nameAr', ''))}")
    print(f"  Transliteration: {en.get('transliteration', en.get('name', ''))}")
    print(f"  Translation   : {en.get('translation', en.get('englishName', ''))}")
    print(f"  Revelation    : {ar.get('revelationType', en.get('revelationType', ''))}")
    print(f"  Verses        : {ar.get('versesCount', ar.get('numberOfAyahs', ''))}")
    print()

    # Tajweed file
    tj_path = f"quran/tajweed/{n}.json"
    if exists(tj_path):
        tj = load(tj_path)
        count = len(tj) if isinstance(tj, list) else len(tj.get("ayahs", []))
        print(f"  Tajweed rules : {count} ayah entries in tajweed/{n}.json")
    print()


# ── Azkar ─────────────────────────────────────────────────────────────────────

_AZKAR_MAP = {
    "morning": "azkar-sabah.json",
    "evening": "azkar-masaa.json",
    "ruqyah": "ruqyah-shariah.json",
    "duas": "famous-doaa.json",
    "travel": "travel.json",
    "food": "food.json",
    "sleep": "sleep.json",
    "mosque": "mosque.json",
    "home": "home.json",
    "wudu": "wudu.json",
    "prayer": "after_prayer.json",
}

def cmd_azkar(category="morning"):
    fname = _AZKAR_MAP.get(category.lower())
    if fname is None:
        print(f"Unknown category '{category}'. Choose from: {', '.join(_AZKAR_MAP)}")
        return

    d = load(f"azkar/{fname}")
    items = d if isinstance(d, list) else d.get("azkar", d.get("items", []))

    header(f"Azkar — {category} ({fname})")
    for i, item in enumerate(items[:5], 1):
        text = item.get("text", item.get("arabic", item.get("content", "")))
        ref = item.get("reference", item.get("source", ""))
        count = item.get("count", "")
        print(f"  [{i}] {text[:80]}{'…' if len(text) > 80 else ''}")
        if ref:
            print(f"       ↳ {ref}  ×{count}" if count else f"       ↳ {ref}")
        print()
    if len(items) > 5:
        print(f"  … and {len(items) - 5} more. Load azkar/{fname} for full data.\n")


# ── Hadith ────────────────────────────────────────────────────────────────────

def cmd_hadith(collection="bukhari", num=1):
    fname = f"hadith/{collection}.json"
    if not exists(fname):
        print(f"Collection '{collection}' not found. Available: bukhari, muslim, malik, ahmed")
        return

    d = load(fname)
    hadiths = d if isinstance(d, list) else []
    if not hadiths:
        for v in d.values():
            if isinstance(v, list):
                hadiths.extend(v)

    try:
        idx = int(num) - 1
        h = hadiths[idx]
    except (ValueError, IndexError):
        print(f"Hadith #{num} not found (collection has {len(hadiths)} hadith)")
        return

    header(f"{collection.title()} — Hadith #{num}")
    for key in ("arabic", "text_ar", "ar"):
        if key in h:
            print(f"  Arabic : {h[key][:200]}{'…' if len(h[key]) > 200 else ''}")
            break
    for key in ("english", "text_en", "en", "text"):
        if key in h:
            print(f"  English: {h[key][:200]}{'…' if len(h[key]) > 200 else ''}")
            break
    for key in ("narrator", "narrator_en", "chain"):
        if key in h:
            print(f"  Narrator: {h[key]}")
            break
    print()


# ── Names of Allah ────────────────────────────────────────────────────────────

def cmd_names(num=1):
    d = load("names_of_allah/names_of_allah.json")
    names = d if isinstance(d, list) else d.get("names", [])
    try:
        idx = int(num) - 1
        n = names[idx]
    except (ValueError, IndexError):
        print(f"Name #{num} not found (total: {len(names)})")
        return

    header(f"Name #{num} of Allah")
    for k, v in n.items():
        print(f"  {k:<20}: {v}")
    print()


# ── Prophet stories ───────────────────────────────────────────────────────────

def cmd_prophet(name="adam"):
    fname = f"prophet_stories/{name.lower()}.json"
    if not exists(fname):
        idx = load("prophet_stories/index.json")
        stories = idx if isinstance(idx, list) else list(idx.values())
        available = [s.get("id", s.get("name", "")).lower() for s in stories if isinstance(s, dict)]
        print(f"Story '{name}' not found. Available: {', '.join(available)}")
        return

    d = load(fname)
    header(f"Prophet Story — {name.title()}")
    title = d.get("title", d.get("name", ""))
    print(f"  Title   : {title}")
    chapters = d.get("chapters", d.get("sections", []))
    print(f"  Chapters: {len(chapters)}")
    if chapters:
        first = chapters[0]
        ch_title = first.get("title", first.get("titleAr", ""))
        content = first.get("content", first.get("text", ""))
        if content:
            print(f"  First chapter: {ch_title}")
            print(f"  Preview: {str(content)[:200]}…")
    print()


# ── Library ───────────────────────────────────────────────────────────────────

def cmd_library(category=None):
    cat = load("data/catalog.json")
    books = cat["books"]
    if category:
        books = [b for b in books if b["category"] == category]

    header(f"Library Books{f' — {category}' if category else ''} ({len(books)})")
    for b in books:
        pdf = "📄 PDF" if b.get("pdf_url") else "📝 text"
        size = b.get("pdf_size_bytes", b.get("total_size_bytes", 0)) / 1024 / 1024
        print(f"  {b['id']:<35} {pdf}  {size:.1f} MB  [{b['category']}]")
    print()


# ── Menu ──────────────────────────────────────────────────────────────────────

def interactive_menu():
    header("Islamic Library Data Explorer")
    print("  Commands:")
    print("    stats                — full data statistics")
    print("    surah <1-114>        — surah info")
    print("    azkar <category>     — morning/evening/duas/ruqyah/travel/food/…")
    print("    hadith <col> <num>   — bukhari/muslim/malik/ahmed + hadith number")
    print("    names <1-99>         — one of the 99 Names of Allah")
    print("    prophet <name>       — adam/ibrahim/musa/isa/…")
    print("    library [category]   — hadith/tafseer/fiqh/aqeedah/…")
    print("    exit                 — quit")
    print()
    while True:
        try:
            raw = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        parts = raw.split()
        _dispatch(parts)


def _dispatch(parts):
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd == "stats":
        cmd_stats()
    elif cmd == "surah":
        cmd_surah(parts[1] if len(parts) > 1 else "1")
    elif cmd == "azkar":
        cmd_azkar(parts[1] if len(parts) > 1 else "morning")
    elif cmd == "hadith":
        cmd_hadith(
            parts[1] if len(parts) > 1 else "bukhari",
            parts[2] if len(parts) > 2 else "1",
        )
    elif cmd == "names":
        cmd_names(parts[1] if len(parts) > 1 else "1")
    elif cmd == "prophet":
        cmd_prophet(parts[1] if len(parts) > 1 else "adam")
    elif cmd == "library":
        cmd_library(parts[1] if len(parts) > 1 else None)
    elif cmd in ("exit", "quit", "q"):
        sys.exit(0)
    else:
        print(f"Unknown command '{cmd}'. Type 'stats' or use --help.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        interactive_menu()
    else:
        _dispatch(args)
