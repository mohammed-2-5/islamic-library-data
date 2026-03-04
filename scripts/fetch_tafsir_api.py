"""Fetch tafaseer from spa5k/tafsir_api and normalize to our schema.

Source: https://github.com/spa5k/tafsir_api
CDN: cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir/

Each tafseer has 114 JSON files (one per surah) with ayah-level commentary.
We group ayahs into surah-based chapters for our schema.

Outputs normalized JSON to data/books/tafseer/{slug}/
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text

# ── Configuration ────────────────────────────────────────────────────────────

CDN_BASE = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books" / "tafseer"

# Only include Arabic tafaseer for the library (primary audience)
# English ones can be added later if needed
ARABIC_TAFASEER = [
    {
        "slug": "ar-tafsir-ibn-kathir",
        "id": "tafsir_ibn_kathir",
        "name_ar": "تفسير ابن كثير",
        "name_en": "Tafsir Ibn Kathir",
        "author_ar": "الحافظ ابن كثير",
        "author_en": "Hafiz Ibn Kathir",
    },
    {
        "slug": "ar-tafsir-al-tabari",
        "id": "tafsir_al_tabari",
        "name_ar": "تفسير الطبري",
        "name_en": "Tafsir al-Tabari",
        "author_ar": "الإمام الطبري",
        "author_en": "Imam al-Tabari",
    },
    {
        "slug": "ar-tafsir-muyassar",
        "id": "tafsir_muyassar",
        "name_ar": "التفسير الميسر",
        "name_en": "Tafsir Muyassar",
        "author_ar": "مجمع الملك فهد",
        "author_en": "King Fahd Complex",
    },
    {
        "slug": "ar-tafseer-al-qurtubi",
        "id": "tafsir_al_qurtubi",
        "name_ar": "تفسير القرطبي",
        "name_en": "Tafsir al-Qurtubi",
        "author_ar": "الإمام القرطبي",
        "author_en": "Imam al-Qurtubi",
    },
    {
        "slug": "ar-tafseer-al-saddi",
        "id": "tafsir_al_saadi",
        "name_ar": "تفسير السعدي",
        "name_en": "Tafsir al-Saadi",
        "author_ar": "الشيخ عبد الرحمن السعدي",
        "author_en": "Sheikh Abdur-Rahman al-Saadi",
    },
    {
        "slug": "ar-tafseer-tanwir-al-miqbas",
        "id": "tafsir_tanwir_al_miqbas",
        "name_ar": "تنوير المقباس من تفسير ابن عباس",
        "name_en": "Tanwir al-Miqbas",
        "author_ar": "ابن عباس",
        "author_en": "Ibn Abbas",
    },
    {
        "slug": "ar-tafsir-al-wasit",
        "id": "tafsir_al_wasit",
        "name_ar": "التفسير الوسيط",
        "name_en": "Tafsir al-Wasit",
        "author_ar": "محمد سيد طنطاوي",
        "author_en": "Muhammad Sayyid Tantawi",
    },
    {
        "slug": "ar-tafsir-al-baghawi",
        "id": "tafsir_al_baghawi",
        "name_ar": "تفسير البغوي",
        "name_en": "Tafsir al-Baghawi",
        "author_ar": "الإمام البغوي",
        "author_en": "Imam al-Baghawi",
    },
]

# English tafaseer (included for bilingual support)
ENGLISH_TAFASEER = [
    {
        "slug": "en-tafisr-ibn-kathir",
        "id": "tafsir_ibn_kathir_en",
        "name_ar": "تفسير ابن كثير (مختصر - إنجليزي)",
        "name_en": "Tafsir Ibn Kathir (Abridged)",
        "author_ar": "الحافظ ابن كثير",
        "author_en": "Hafiz Ibn Kathir",
    },
    {
        "slug": "en-al-jalalayn",
        "id": "tafsir_al_jalalayn_en",
        "name_ar": "تفسير الجلالين (إنجليزي)",
        "name_en": "Tafsir al-Jalalayn",
        "author_ar": "جلال الدين المحلي وجلال الدين السيوطي",
        "author_en": "Al-Jalalayn",
    },
]

ALL_TAFASEER = ARABIC_TAFASEER + ENGLISH_TAFASEER

# Surah names for chapter titles
SURAH_NAMES = [
    ("الفاتحة", "Al-Fatihah"), ("البقرة", "Al-Baqarah"), ("آل عمران", "Aal-Imran"),
    ("النساء", "An-Nisa"), ("المائدة", "Al-Ma'idah"), ("الأنعام", "Al-An'am"),
    ("الأعراف", "Al-A'raf"), ("الأنفال", "Al-Anfal"), ("التوبة", "At-Tawbah"),
    ("يونس", "Yunus"), ("هود", "Hud"), ("يوسف", "Yusuf"),
    ("الرعد", "Ar-Ra'd"), ("إبراهيم", "Ibrahim"), ("الحجر", "Al-Hijr"),
    ("النحل", "An-Nahl"), ("الإسراء", "Al-Isra"), ("الكهف", "Al-Kahf"),
    ("مريم", "Maryam"), ("طه", "Ta-Ha"), ("الأنبياء", "Al-Anbiya"),
    ("الحج", "Al-Hajj"), ("المؤمنون", "Al-Mu'minun"), ("النور", "An-Nur"),
    ("الفرقان", "Al-Furqan"), ("الشعراء", "Ash-Shu'ara"), ("النمل", "An-Naml"),
    ("القصص", "Al-Qasas"), ("العنكبوت", "Al-Ankabut"), ("الروم", "Ar-Rum"),
    ("لقمان", "Luqman"), ("السجدة", "As-Sajdah"), ("الأحزاب", "Al-Ahzab"),
    ("سبأ", "Saba"), ("فاطر", "Fatir"), ("يس", "Ya-Sin"),
    ("الصافات", "As-Saffat"), ("ص", "Sad"), ("الزمر", "Az-Zumar"),
    ("غافر", "Ghafir"), ("فصلت", "Fussilat"), ("الشورى", "Ash-Shura"),
    ("الزخرف", "Az-Zukhruf"), ("الدخان", "Ad-Dukhan"), ("الجاثية", "Al-Jathiyah"),
    ("الأحقاف", "Al-Ahqaf"), ("محمد", "Muhammad"), ("الفتح", "Al-Fath"),
    ("الحجرات", "Al-Hujurat"), ("ق", "Qaf"), ("الذاريات", "Adh-Dhariyat"),
    ("الطور", "At-Tur"), ("النجم", "An-Najm"), ("القمر", "Al-Qamar"),
    ("الرحمن", "Ar-Rahman"), ("الواقعة", "Al-Waqi'ah"), ("الحديد", "Al-Hadid"),
    ("المجادلة", "Al-Mujadilah"), ("الحشر", "Al-Hashr"), ("الممتحنة", "Al-Mumtahanah"),
    ("الصف", "As-Saff"), ("الجمعة", "Al-Jumu'ah"), ("المنافقون", "Al-Munafiqun"),
    ("التغابن", "At-Taghabun"), ("الطلاق", "At-Talaq"), ("التحريم", "At-Tahrim"),
    ("الملك", "Al-Mulk"), ("القلم", "Al-Qalam"), ("الحاقة", "Al-Haqqah"),
    ("المعارج", "Al-Ma'arij"), ("نوح", "Nuh"), ("الجن", "Al-Jinn"),
    ("المزمل", "Al-Muzzammil"), ("المدثر", "Al-Muddaththir"), ("القيامة", "Al-Qiyamah"),
    ("الإنسان", "Al-Insan"), ("المرسلات", "Al-Mursalat"), ("النبأ", "An-Naba"),
    ("النازعات", "An-Nazi'at"), ("عبس", "Abasa"), ("التكوير", "At-Takwir"),
    ("الانفطار", "Al-Infitar"), ("المطففين", "Al-Mutaffifin"), ("الانشقاق", "Al-Inshiqaq"),
    ("البروج", "Al-Buruj"), ("الطارق", "At-Tariq"), ("الأعلى", "Al-A'la"),
    ("الغاشية", "Al-Ghashiyah"), ("الفجر", "Al-Fajr"), ("البلد", "Al-Balad"),
    ("الشمس", "Ash-Shams"), ("الليل", "Al-Layl"), ("الضحى", "Ad-Duha"),
    ("الشرح", "Ash-Sharh"), ("التين", "At-Tin"), ("العلق", "Al-Alaq"),
    ("القدر", "Al-Qadr"), ("البينة", "Al-Bayyinah"), ("الزلزلة", "Az-Zalzalah"),
    ("العاديات", "Al-Adiyat"), ("القارعة", "Al-Qari'ah"), ("التكاثر", "At-Takathur"),
    ("العصر", "Al-Asr"), ("الهمزة", "Al-Humazah"), ("الفيل", "Al-Fil"),
    ("قريش", "Quraysh"), ("الماعون", "Al-Ma'un"), ("الكوثر", "Al-Kawthar"),
    ("الكافرون", "Al-Kafirun"), ("النصر", "An-Nasr"), ("المسد", "Al-Masad"),
    ("الإخلاص", "Al-Ikhlas"), ("الفلق", "Al-Falaq"), ("الناس", "An-Nas"),
]

MAX_RETRIES = 3
RETRY_DELAY = 2


def fetch_json(url: str) -> dict | None:
    """Fetch JSON from URL with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  FAILED: {url}: {e}")
                return None


def process_tafseer(tafseer_info: dict) -> dict | None:
    """Fetch all 114 surah files for one tafseer and normalize."""
    slug = tafseer_info["slug"]
    book_id = tafseer_info["id"]
    book_dir = OUTPUT_DIR / book_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_entries = 0
    successful_surahs = 0

    for surah_num in tqdm(range(1, 115), desc=f"  {slug}", leave=False):
        url = f"{CDN_BASE}/tafsir/{slug}/{surah_num}.json"
        data = fetch_json(url)
        if data is None:
            continue

        ayahs = data.get("ayahs", [])
        surah_ar, surah_en = SURAH_NAMES[surah_num - 1]

        # Build chapter entries from ayahs
        entries = []
        for ayah in ayahs:
            text = clean_text(ayah.get("text", ""))
            if not text:
                continue
            entries.append({
                "id": ayah.get("ayah", 0),
                "text_ar": text,
                "text_en": "",
                "reference": f"Ayah {ayah.get('ayah', 0)}",
            })

        chapter = {
            "book_id": book_id,
            "chapter_id": surah_num,
            "title_ar": f"سورة {surah_ar}",
            "title_en": f"Surah {surah_en}",
            "entries": entries,
        }

        ch_json = json.dumps(chapter, ensure_ascii=False, indent=2)
        (chapters_dir / f"{surah_num}.json").write_text(ch_json, encoding="utf-8")
        total_bytes += len(ch_json.encode("utf-8"))
        total_entries += len(entries)
        successful_surahs += 1

        time.sleep(0.1)  # Be nice to CDN

    if successful_surahs == 0:
        print(f"  SKIPPED {slug}: no data fetched")
        return None

    # Write metadata
    metadata = {
        "id": book_id,
        "title_ar": tafseer_info["name_ar"],
        "title_en": tafseer_info["name_en"],
        "author_ar": tafseer_info["author_ar"],
        "author_en": tafseer_info["author_en"],
        "category": "tafseer",
        "chapter_count": successful_surahs,
        "entry_count": total_entries,
        "total_size_bytes": total_bytes,
        "source": "tafsir-api",
    }

    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")
    metadata["total_size_bytes"] = total_bytes + len(meta_json.encode("utf-8"))

    # Rewrite with updated size
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")

    print(f"  Done {book_id}: {successful_surahs}/114 surahs, "
          f"{total_entries} entries, {total_bytes / (1024*1024):.2f} MB")
    return metadata


def main():
    print("=" * 60)
    print("Fetching tafaseer from spa5k/tafsir_api")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_metadata = []

    print(f"\nProcessing {len(ALL_TAFASEER)} tafaseer...\n")

    for tafseer in ALL_TAFASEER:
        print(f"Fetching: {tafseer['name_en']} ({tafseer['slug']})")
        meta = process_tafseer(tafseer)
        if meta:
            all_metadata.append(meta)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Processed {len(all_metadata)}/{len(ALL_TAFASEER)} tafaseer")
    total_entries = sum(m.get("entry_count", 0) for m in all_metadata)
    total_size = sum(m["total_size_bytes"] for m in all_metadata)
    print(f"Total entries: {total_entries:,}")
    print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
