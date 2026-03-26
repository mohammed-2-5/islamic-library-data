# Islamic App Data

A free, open-source data repository for building Islamic applications. Contains ready-to-use JSON datasets for the Quran, Hadith, Azkar, Duas, Prophet Stories, 99 Names of Allah, Islamic Library books, and more — with font files and audio included.

All data is served via **jsDelivr CDN** (free, fast, no API key needed).

---

## Contents

| Dataset | Files | Size | Description |
|---------|-------|------|-------------|
| 📖 Quran metadata | 342 JSON | 9.5 MB | Surah info (AR/EN), tajweed rules, thematic segments, symbols, duas, hizb/page maps |
| 📚 Hadith collections | 4 JSON | 28.5 MB | Bukhari (7,277), Muslim (7,190), Malik (1,594), Ahmad (4,341) |
| 📜 40 Hadith | 3 JSON | 0.2 MB | Nawawi, Qudsi, Shah Waliullah |
| 🤲 Azkar & Duas | 14 JSON | 0.1 MB | Morning, evening, ruqyah, 176 items across 14 categories |
| 🕌 Prophet stories | 51 JSON | 1.6 MB | 25 prophets with chapters, lessons, Quran refs + 25 quizzes |
| ✨ 99 Names | 1 JSON | 0.05 MB | Arabic, transliteration, AR/EN meanings, virtues |
| 📝 Tafseer | 1 JSON | 2.6 MB | Tafseer Muyassar (6,236 entries, full Quran) |
| 📦 Library catalog | CDN | 296 MB | 75 classical books (44 PDF + 31 text), downloadable on demand |
| 🔤 Fonts | 4 files | 0.8 MB | UthmanicHafs, AmiriQuran, UthmanTN1 tajweed color font |
| 🔤 QCF Mushaf fonts | 1 ZIP | 52 MB | QCF V2 fonts for pixel-perfect Mushaf rendering |
| 🔊 Audio | 4 MP3 | 5.6 MB | 4 adhan recordings |

---

## CDN Usage

Every file in this repo is instantly available via jsDelivr — no backend, no API key:

```
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/<path>
```

**Examples:**

```
# Surah Al-Fatiha (Arabic)
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/quran/chapters/ar/1.json

# Morning Azkar
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/azkar/azkar-sabah.json

# Library catalog
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/data/catalog.json

# Tajweed rules for Al-Baqarah
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/quran/tajweed/2.json

# Font file
https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master/fonts/UthmanicHafs_v18.ttf
```

---

## Data Reference

### 📖 Quran

#### `quran/chapters/ar/{1-114}.json` — Arabic surah metadata + verses

```json
{
  "id": 1,
  "name": "الفاتحة",
  "transliteration": "Al-Fatihah",
  "type": "Meccan",
  "total_verses": 7,
  "verses": [
    { "id": 1, "text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ" }
  ]
}
```

#### `quran/chapters/en/{1-114}.json` — English surah metadata + translation

```json
{
  "id": 1,
  "name": "Al-Fatihah",
  "translation": "The Opening",
  "type": "Meccan",
  "total_verses": 7,
  "verses": [
    { "id": 1, "text": "In the name of Allah, the Entirely Merciful, the Especially Merciful." }
  ]
}
```

#### `quran/tajweed/{1-114}.json` — Tajweed color rules per surah

Each file contains an array of ayah objects. Each word is annotated with its tajweed rule (ghunnah, ikhfa, madd, qalqalah, etc.) so you can render colored text.

#### `quran/quran_segments.json` — Thematic segments (745 segments across 114 surahs)

Maps surah → list of ayah ranges with a thematic label. Useful for grouping related verses in a reader.

#### `quran/hizb_quarters.json` — Hizb & quarter division markers

#### `quran/quran_symbols.json` — Tajweed symbol definitions (names + recommended colors)

#### `quran/quran_duas.json` — Duas extracted from the Quran

#### `quran/qcf_v2_pages.json` — QCF V2 Mushaf: page-to-ayah mapping (604 pages)

#### `quran/mushaf_pages.json` — Madina Mushaf page references

#### `quran/qcf_surah_starts.json` — Which page each surah starts on in QCF V2

---

### 📚 Hadith

#### `hadith/{collection}.json`

Available: `bukhari.json` · `muslim.json` · `malik.json` · `ahmed.json`

```json
{
  "id": "bukhari",
  "metadata": {
    "id": 1,
    "length": 7277,
    "arabic": "صحيح البخاري",
    "english": "Sahih Bukhari"
  },
  "chapters": [
    { "id": 1, "bookId": 1, "arabic": "كتاب الوحي", "english": "Revelation" }
  ],
  "hadiths": [
    {
      "id": 1,
      "idInBook": 1,
      "chapterId": 1,
      "bookId": 1,
      "arabic": "حَدَّثَنَا الْحُمَيْدِيُّ...",
      "english": "Narrated 'Umar bin Al-Khattab: I heard Allah's Messenger (ﷺ) saying..."
    }
  ]
}
```

| Collection | Hadiths | Size |
|-----------|---------|------|
| `bukhari.json` | 7,277 | 12.2 MB |
| `muslim.json` | 7,190 | 10.9 MB |
| `ahmed.json` | 4,341 | 2.3 MB |
| `malik.json` | 1,594 | 3.2 MB |

> **Tip:** These files are large. For mobile apps, fetch only the chapters you need via the library catalog endpoint instead of loading the full JSON.

---

### 📜 40 Hadith Collections

#### `forties/{collection}.json`

Available: `nawawi40.json` · `qudsi40.json` · `shahwaliullah40.json`

Same schema as hadith (`metadata` + `chapters` + `hadiths` array). Small and perfect for embedding directly in apps.

---

### 🤲 Azkar & Duas

#### `azkar/{file}.json`

| File | Category | Items |
|------|----------|-------|
| `azkar-sabah.json` | Morning adhkar | 35 |
| `azkar-masaa.json` | Evening adhkar | 27 |
| `ruqyah-shariah.json` | Ruqyah (healing) | 20 |
| `famous-doaa.json` | Famous duas | 30 |
| `travel.json` | Travel duas | 8 |
| `food.json` | Food/eating duas | 6 |
| `sleep.json` | Sleep duas | 4 |
| `mosque.json` | Mosque entry/exit | 5 |
| `home.json` | Home entry/exit | 4 |
| `wudu.json` | Wudu duas | 3 |
| `after_prayer.json` | Post-prayer adhkar | 12 |
| `morning_evening.json` | Brief morning/evening | 22 |
| `doaa-for-all-death-people.json` | Funeral duas | — |
| `doaa-for-dead-person.json` | Death dua | — |

**Schema:**
```json
[
  {
    "zekr": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ",
    "repeat": 100,
    "bless": "تُحَطُّ عنه خطاياه وإن كانت مثل زبد البحر"
  }
]
```

Fields vary per file. Common fields: `zekr` (Arabic text), `repeat` (count), `bless` (virtue/reward), `reference`, `description`.

---

### 🕌 Prophet Stories

#### `prophet_stories/index.json` — Master index (25 entries)

```json
[
  {
    "id": "adam",
    "nameAr": "آدم",
    "nameEn": "Adam",
    "order": 1,
    "summaryAr": "...",
    "summaryEn": "..."
  }
]
```

#### `prophet_stories/{name}.json` — Full story

Each file contains chapters with Arabic/English content, Quran references, lessons, and moral teachings.

#### `prophet_stories/quizzes/{name}.json` — Quiz questions (25 files)

**Available:** adam · idris · nuh · hud · salih · ibrahim · lut · ismail · ishaq · yaqub · yusuf · ayyub · shuaib · musa · harun · dawud · sulayman · ilyas · alyasa · dhul_kifl · yunus · zakariya · yahya · isa · muhammad

---

### ✨ 99 Names of Allah

#### `names_of_allah/names_of_allah.json`

```json
[
  {
    "id": 1,
    "name": "الله",
    "transliteration": "Allah",
    "meaning_ar": "الاسم الجامع لجميع صفات الكمال",
    "meaning_en": "The One worthy of all worship",
    "virtue": "..."
  }
]
```

---

### 📝 Tafseer

#### `tafseer/muyassar.json` — Tafseer Muyassar (6,236 entries)

A concise Arabic tafseer covering all ayahs. Each entry contains `{ surah, ayah, text }`.

> For downloadable, chapter-based tafseer Ibn Kathir and others, see the Library catalog below.

---

### 📦 Islamic Library

#### `data/catalog.json` — 75 classical books

```json
{
  "version": 1,
  "categories": [
    { "id": "hadith", "name_ar": "الحديث", "name_en": "Hadith", "icon": "menu_book" }
  ],
  "books": [
    {
      "id": "bukhari",
      "title_ar": "صحيح البخاري",
      "title_en": "Sahih Bukhari",
      "author_ar": "محمد بن إسماعيل البخاري",
      "author_en": "Muhammad ibn Ismail al-Bukhari",
      "category": "hadith",
      "chapter_count": 97,
      "total_size_bytes": 12500000,
      "source": "openiti",
      "featured": true,
      "pdf_url": "https://archive.org/download/.../bukhari.pdf",
      "pdf_size_bytes": 45000000
    }
  ]
}
```

- `pdf_url` present → downloadable PDF from archive.org (public domain)
- `pdf_url` absent → text reader via CDN chapters

**Categories and counts:**

| Category | Books | Notes |
|----------|-------|-------|
| fiqh | 21 | Islamic jurisprudence |
| tafseer | 18 | Quran commentaries |
| hadith | 17 | Prophetic traditions |
| tazkiyah | 12 | Spiritual purification |
| aqeedah | 3 | Islamic creed |
| seerah | 2 | Prophetic biography |
| tarikh | 2 | Islamic history |

#### `data/books/{category}/{book_id}/chapters/{n}.json` — Chapter text

```json
{
  "id": 1,
  "title_ar": "كتاب الوحي",
  "title_en": "Book of Revelation",
  "entries": [
    {
      "id": 1,
      "text_ar": "حَدَّثَنَا...",
      "text_en": "Narrated...",
      "narrator": "Umar ibn al-Khattab",
      "reference": "Bukhari 1"
    }
  ]
}
```

Load chapters on demand — each chapter is a separate CDN request, ideal for mobile pagination.

---

### 🔤 Fonts

| File | Use case |
|------|----------|
| `fonts/UthmanicHafs_v18.ttf` | Standard Quran display text (most common) |
| `fonts/AmiriQuran-Regular.ttf` | Alternative, scholarly Quran font |
| `fonts/UthmanTN1_Ver10.otf` | Tajweed color rendering (colored diacritics) |
| `fonts/HafsSmart_08.ttf` | Smart ligature font for compact display |
| `fonts/qcf_fonts.zip` | QCF V2 — pixel-perfect Mushaf (52 MB, extract for per-page `.ttf` files) |

**Using QCF V2:** Extract the ZIP, then load `p{page_num}.ttf` for each of the 604 Mushaf pages. Each font renders the exact layout of that page.

---

### 🔊 Audio

| File | Size |
|------|------|
| `audio/adhan1.mp3` | 835 KB — Default adhan |
| `audio/adhan2.mp3` | 909 KB |
| `audio/adhan3.mp3` | 2.7 MB |
| `audio/adhan4.mp3` | 1.3 MB |

---

## Quick Start

### Python

```python
import urllib.request, json

CDN = "https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master"

# Surah Al-Baqarah (Arabic)
with urllib.request.urlopen(f"{CDN}/quran/chapters/ar/2.json") as r:
    surah = json.load(r)
print(surah["name"], "—", surah["total_verses"], "verses")

# Morning azkar
with urllib.request.urlopen(f"{CDN}/azkar/azkar-sabah.json") as r:
    azkar = json.load(r)
print(f"{len(azkar)} morning adhkar loaded")

# First hadith in Bukhari
with urllib.request.urlopen(f"{CDN}/hadith/bukhari.json") as r:
    bukhari = json.load(r)
print(bukhari["hadiths"][0]["english"][:100])

# 99 Names of Allah
with urllib.request.urlopen(f"{CDN}/names_of_allah/names_of_allah.json") as r:
    names = json.load(r)
for n in names[:3]:
    print(n["name"], "—", n["meaning_en"])
```

### JavaScript / TypeScript

```js
const CDN = "https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master";

// Evening azkar
const azkar = await fetch(`${CDN}/azkar/azkar-masaa.json`).then(r => r.json());
console.log(`${azkar.length} evening adhkar`);

// Tajweed rules for Al-Fatiha
const tajweed = await fetch(`${CDN}/quran/tajweed/1.json`).then(r => r.json());

// Library catalog
const catalog = await fetch(`${CDN}/data/catalog.json`).then(r => r.json());
const pdfBooks = catalog.books.filter(b => b.pdf_url);
console.log(`${pdfBooks.length} books available as PDF`);

// Stream a specific chapter
const chapter = await fetch(`${CDN}/data/books/hadith/bukhari/chapters/1.json`).then(r => r.json());
console.log(`${chapter.entries.length} entries in chapter 1`);
```

### Flutter / Dart

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

const cdn = 'https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master';

// Load surah
final res = await http.get(Uri.parse('$cdn/quran/chapters/ar/1.json'));
final surah = jsonDecode(res.body);
print(surah['name']); // الفاتحة

// Load azkar
final azRes = await http.get(Uri.parse('$cdn/azkar/azkar-sabah.json'));
final List azkar = jsonDecode(azRes.body);
print('${azkar.length} morning adhkar');

// Use a font
// In pubspec.yaml:
//   fonts:
//     - family: UthmanicHafs
//       fonts:
//         - asset: fonts/UthmanicHafs_v18.ttf
// Then: TextStyle(fontFamily: 'UthmanicHafs')
```

### Android / Kotlin

```kotlin
val cdn = "https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master"

// OkHttp example
val client = OkHttpClient()
val request = Request.Builder().url("$cdn/azkar/azkar-sabah.json").build()
val response = client.newCall(request).execute()
val azkar = JSONArray(response.body?.string())
Log.d("Islamic", "${azkar.length()} morning adhkar")
```

### Swift / iOS

```swift
let cdn = "https://cdn.jsdelivr.net/gh/mohammed-2-5/islamic-library-data@master"
let url = URL(string: "\(cdn)/names_of_allah/names_of_allah.json")!

URLSession.shared.dataTask(with: url) { data, _, _ in
    if let data = data,
       let names = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] {
        print("\(names.count) names of Allah")
    }
}.resume()
```

---

## Explorer Script

Explore all datasets interactively from the terminal — no dependencies beyond Python 3.6+:

```bash
git clone https://github.com/mohammed-2-5/islamic-library-data.git
cd islamic-library-data

# Interactive mode (type commands at the prompt)
python scripts/explore.py

# One-shot commands
python scripts/explore.py stats                  # full data overview
python scripts/explore.py surah 2               # Surah Al-Baqarah info
python scripts/explore.py surah 114             # Surah An-Nas
python scripts/explore.py azkar morning         # first 5 morning adhkar
python scripts/explore.py azkar ruqyah          # ruqyah items
python scripts/explore.py hadith bukhari 1      # Bukhari hadith #1
python scripts/explore.py hadith muslim 500     # Muslim hadith #500
python scripts/explore.py names 1               # First of 99 Names
python scripts/explore.py names 99              # Last name (As-Sabur)
python scripts/explore.py prophet musa          # Moses story summary
python scripts/explore.py prophet muhammad      # Prophet Muhammad ﷺ
python scripts/explore.py library               # all 75 books
python scripts/explore.py library tafseer       # tafseer books only
python scripts/explore.py library fiqh          # fiqh books only
```

---

## Repository Structure

```
islamic-library-data/
├── quran/
│   ├── chapters/
│   │   ├── ar/{1-114}.json        ← Arabic text + verses per surah
│   │   └── en/{1-114}.json        ← English translation per surah
│   ├── tajweed/{1-114}.json       ← Tajweed color rules per surah
│   ├── quran_segments.json        ← Thematic segment groupings (745)
│   ├── quran_symbols.json         ← Tajweed symbol definitions
│   ├── quran_duas.json            ← Quranic supplications
│   ├── hizb_quarters.json         ← Hizb & quarter markers
│   ├── qcf_v2_pages.json          ← QCF V2 page↔ayah mapping
│   ├── mushaf_pages.json          ← Madina Mushaf page references
│   └── qcf_surah_starts.json      ← Surah start pages in QCF V2
├── hadith/
│   ├── bukhari.json               ← Sahih Bukhari  (7,277 hadiths, 12 MB)
│   ├── muslim.json                ← Sahih Muslim   (7,190 hadiths, 11 MB)
│   ├── malik.json                 ← Muwatta Malik  (1,594 hadiths)
│   └── ahmed.json                 ← Musnad Ahmad   (4,341 hadiths)
├── forties/
│   ├── nawawi40.json              ← Imam Nawawi's 40 Hadiths
│   ├── qudsi40.json               ← 40 Hadith Qudsi
│   └── shahwaliullah40.json       ← Shah Waliullah's 40 Hadiths
├── azkar/
│   ├── azkar-sabah.json           ← Morning adhkar (35 items)
│   ├── azkar-masaa.json           ← Evening adhkar (27 items)
│   ├── ruqyah-shariah.json        ← Ruqyah (20 items)
│   ├── famous-doaa.json           ← Famous duas (30 items)
│   └── ...                        ← travel, food, sleep, wudu, mosque, home
├── prophet_stories/
│   ├── index.json                 ← All 25 prophets index
│   ├── {name}.json                ← Full story per prophet (25 files)
│   └── quizzes/{name}.json        ← Quiz questions per prophet (25 files)
├── names_of_allah/
│   └── names_of_allah.json        ← 99 Names (AR/EN meanings + virtues)
├── tafseer/
│   └── muyassar.json              ← Tafseer Muyassar (6,236 entries, 2.6 MB)
├── data/
│   ├── catalog.json               ← 75 classical books catalog
│   └── books/{category}/{id}/
│       └── chapters/{n}.json      ← Chapter text (loaded on demand)
├── fonts/
│   ├── UthmanicHafs_v18.ttf       ← Standard Quran font
│   ├── AmiriQuran-Regular.ttf     ← Alternative Quran font
│   ├── UthmanTN1_Ver10.otf        ← Tajweed color font
│   ├── HafsSmart_08.ttf           ← Smart ligature font
│   └── qcf_fonts.zip              ← QCF V2 mushaf fonts (52 MB)
├── audio/
│   ├── adhan1.mp3                 ← Default adhan
│   ├── adhan2.mp3
│   ├── adhan3.mp3
│   └── adhan4.mp3
└── scripts/
    ├── explore.py                 ← Interactive data explorer (this file)
    ├── build_catalog.py           ← Rebuild library catalog from source
    └── ...                        ← Other data pipeline scripts
```

---

## License

- **Islamic texts** (Quran, Hadith, Azkar): Public domain classical texts. English translations used under their respective open licenses.
- **Fonts**: Distributed under their original open font licenses (KFGQPC, SIL OFL).
- **Code & scripts**: MIT License.

---

## Apps Using This Data

- [أذكار المسلم](https://github.com/mohammed-2-5) — Flutter Islamic app featuring Quran reader, prayer times, azkar, Islamic library, and more.

---

*Pull requests are welcome — new datasets, data quality fixes, translations, and documentation improvements are all appreciated.*
