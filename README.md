# Islamic Library Data

Open-source collection of classical Islamic books in JSON format, served via jsDelivr CDN.

## Sources

| Source | Content | Books |
|--------|---------|-------|
| [AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json) | Hadith collections | ~17 |
| [spa5k/tafsir_api](https://github.com/spa5k/tafsir_api) | Tafseer works | ~27 |
| [OpenITI](https://github.com/OpenITI/RELEASE) | Classical Arabic texts | 10,000+ |
| [fekracomputers/IslamicLibraryAndroid](https://github.com/fekracomputers/IslamicLibraryAndroid) | Shamela library | 7,000+ |
| [IslamHouse.com API](https://islamhouse.com) | Dawah content | Varies |

## Categories

- **فقه** (Fiqh) — Jurisprudence
- **حديث** (Hadith) — Prophetic traditions
- **عقيدة** (Aqeedah) — Islamic creed
- **تفسير** (Tafseer) — Quran exegesis
- **سيرة** (Seerah) — Prophetic biography
- **رقائق** (Raqaiq) — Heart softeners
- **اللغة العربية** (Arabic Language)
- **عام** (General)

## Usage

```bash
pip install -r requirements.txt

# Fetch hadith books (easiest, start here)
python scripts/fetch_hadith_json.py

# Fetch tafaseer
python scripts/fetch_tafsir_api.py

# Convert Shamela SQLite books
python scripts/convert_shamela.py

# Convert OpenITI texts
python scripts/convert_openiti.py

# Fetch IslamHouse content
python scripts/fetch_islamhouse.py

# Deduplicate across sources
python scripts/deduplicate.py

# Build catalog and validate
python scripts/build_catalog.py
python scripts/validate.py
```

## CDN Access

All data is available via jsDelivr CDN:

```
https://cdn.jsdelivr.net/gh/{owner}/islamic-library-data@main/data/catalog.json
https://cdn.jsdelivr.net/gh/{owner}/islamic-library-data@main/data/books/{category}/{book_id}/metadata.json
https://cdn.jsdelivr.net/gh/{owner}/islamic-library-data@main/data/books/{category}/{book_id}/chapters/{n}.json
```

## License

Book texts are public domain (classical Islamic works, pre-1900 authors). Scripts are MIT licensed.
