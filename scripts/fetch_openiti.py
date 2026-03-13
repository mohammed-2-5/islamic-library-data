"""Fetch classical Islamic texts from OpenITI via raw GitHub URLs.

Instead of cloning the massive OpenITI RELEASE repo, we fetch individual
texts directly from GitHub's raw content CDN.

Source: https://github.com/OpenITI/RELEASE
Format: mARkdown (custom markup, see: https://openiti.org/research/mARkdown)

Outputs normalized JSON to data/books/{category}/{book_id}/
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

# Fix Windows console encoding for Arabic text
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.arabic_normalize import clean_text

# ── Configuration ────────────────────────────────────────────────────────────

RAW_BASE = "https://raw.githubusercontent.com/OpenITI/RELEASE/master/data"
API_BASE = "https://api.github.com/repos/OpenITI/RELEASE/contents/data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "books"

MAX_RETRIES = 3
RETRY_DELAY = 3

# ── Books to fetch ───────────────────────────────────────────────────────────
# Format: (author_dir, book_dir, preferred_version, book_id, category, metadata)
#   - preferred_version: filename pattern to look for (mARkdown > Shamela)
#   - If None, we'll pick the first .mARkdown file found

BOOKS_TO_FETCH = [
    # ── Aqeedah (Islamic Creed) ──
    {
        "author_dir": "0150AbuHanifa",
        "book_dir": "0150AbuHanifa.FiqhAkbar",
        "book_id": "fiqh_akbar",
        "category": "aqeedah",
        "title_ar": "الفقه الأكبر",
        "title_en": "Al-Fiqh al-Akbar",
        "author_ar": "الإمام أبو حنيفة",
        "author_en": "Imam Abu Hanifa",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.CaqidaWasitiyya",
        "book_id": "aqeedah_wasitiyyah",
        "category": "aqeedah",
        "title_ar": "العقيدة الواسطية",
        "title_en": "Al-Aqeedah al-Wasitiyyah",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.CaqidaHamawiyya",
        "book_id": "aqeedah_hamawiyyah",
        "category": "aqeedah",
        "title_ar": "العقيدة الحموية",
        "title_en": "Al-Aqeedah al-Hamawiyyah",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.CaqidaTadmuriyya",
        "book_id": "aqeedah_tadmuriyyah",
        "category": "aqeedah",
        "title_ar": "العقيدة التدمرية",
        "title_en": "Al-Aqeedah al-Tadmuriyyah",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
    },
    {
        "author_dir": "0241IbnHanbal",
        "book_dir": "0241IbnHanbal.UsulSunna",
        "book_id": "usul_al_sunnah",
        "category": "aqeedah",
        "title_ar": "أصول السنة",
        "title_en": "Usul al-Sunnah",
        "author_ar": "الإمام أحمد بن حنبل",
        "author_en": "Imam Ahmad ibn Hanbal",
    },

    # ── Fiqh (Jurisprudence) ──
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.Adhkar",
        "book_id": "adhkar_nawawi",
        "category": "fiqh",
        "title_ar": "الأذكار",
        "title_en": "Al-Adhkar",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
    },
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.MinhajTalibin",
        "book_id": "minhaj_talibin",
        "category": "fiqh",
        "title_ar": "منهاج الطالبين",
        "title_en": "Minhaj al-Talibin",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
    },
    {
        "author_dir": "0456IbnHazm",
        "book_dir": "0456IbnHazm.Muhalla",
        "book_id": "al_muhalla",
        "category": "fiqh",
        "title_ar": "المحلى بالآثار",
        "title_en": "Al-Muhalla bil-Athar",
        "author_ar": "الإمام ابن حزم",
        "author_en": "Imam Ibn Hazm",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.Mughni",
        "book_id": "al_mughni",
        "category": "fiqh",
        "title_ar": "المغني",
        "title_en": "Al-Mughni",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.KafiFiFiqh",
        "book_id": "al_kafi_fiqh",
        "category": "fiqh",
        "title_ar": "الكافي في فقه الإمام أحمد",
        "title_en": "Al-Kafi fi Fiqh al-Imam Ahmad",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.CumdatFiqh",
        "book_id": "umdat_al_fiqh",
        "category": "fiqh",
        "title_ar": "عمدة الفقه",
        "title_en": "Umdat al-Fiqh",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.MuqnicFiFiqh",
        "book_id": "al_muqni_fiqh",
        "category": "fiqh",
        "title_ar": "المقنع في فقه الإمام أحمد",
        "title_en": "Al-Muqni fi Fiqh",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.RawdatNazir",
        "book_id": "rawdat_al_nazir",
        "category": "fiqh",
        "title_ar": "روضة الناظر وجنة المناظر",
        "title_en": "Rawdat al-Nazir",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
    },
    {
        "author_dir": "0179MalikIbnAnas",
        "book_dir": "0179MalikIbnAnas.Muwatta",
        "book_id": "muwatta_malik",
        "category": "fiqh",
        "title_ar": "الموطأ",
        "title_en": "Al-Muwatta",
        "author_ar": "الإمام مالك بن أنس",
        "author_en": "Imam Malik ibn Anas",
    },
    {
        "author_dir": "0204Shafici",
        "book_dir": "0204Shafici.Umm",
        "book_id": "al_umm",
        "category": "fiqh",
        "title_ar": "الأم",
        "title_en": "Al-Umm",
        "author_ar": "الإمام الشافعي",
        "author_en": "Imam al-Shafi'i",
    },
    {
        "author_dir": "0204Shafici",
        "book_dir": "0204Shafici.Risala",
        "book_id": "al_risala_shafii",
        "category": "fiqh",
        "title_ar": "الرسالة",
        "title_en": "Al-Risala",
        "author_ar": "الإمام الشافعي",
        "author_en": "Imam al-Shafi'i",
    },
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.RawdatTalibin",
        "book_id": "rawdat_al_talibin",
        "category": "fiqh",
        "title_ar": "روضة الطالبين وعمدة المفتين",
        "title_en": "Rawdat al-Talibin",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
            "filename": "0676Nawawi.RawdatTalibin.Shamela0000499-ara1",
    },
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.Majmuc",
        "book_id": "al_majmu_nawawi",
        "category": "fiqh",
        "title_ar": "المجموع شرح المهذب",
        "title_en": "Al-Majmu Sharh al-Muhadhdhab",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
            "filename": "0676Nawawi.Majmuc.Shamela0002186-ara1",
    },
    {
        "author_dir": "0505Ghazali",
        "book_dir": "0505Ghazali.Mustasfa",
        "book_id": "al_mustasfa",
        "category": "fiqh",
        "title_ar": "المستصفى من علم الأصول",
        "title_en": "Al-Mustasfa",
        "author_ar": "الإمام الغزالي",
        "author_en": "Imam al-Ghazali",
            "filename": "0505Ghazali.Mustasfa.Shamela0005459-ara1",
    },
    {
        "author_dir": "0505Ghazali",
        "book_dir": "0505Ghazali.Wajiz",
        "book_id": "al_wajiz",
        "category": "fiqh",
        "title_ar": "الوجيز في فقه الشافعي",
        "title_en": "Al-Wajiz",
        "author_ar": "الإمام الغزالي",
        "author_en": "Imam al-Ghazali",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.SiyasaSharciyya",
        "book_id": "siyasa_shariyya",
        "category": "fiqh",
        "title_ar": "السياسة الشرعية",
        "title_en": "Al-Siyasa al-Shar'iyyah",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
            "filename": "0728IbnTaymiyya.SiyasaSharciyya.Shamela0031237-ara1",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.QawacidNuraniyya",
        "book_id": "qawaid_nuraniyyah",
        "category": "fiqh",
        "title_ar": "القواعد النورانية الفقهية",
        "title_en": "Al-Qawa'id al-Nuraniyyah",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
            "filename": "0728IbnTaymiyya.QawacidNuraniyya.Shamela0021729-ara1.completed",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.AclamMuwaqqicin",
        "book_id": "ilam_al_muwaqqiin",
        "category": "fiqh",
        "title_ar": "إعلام الموقعين عن رب العالمين",
        "title_en": "I'lam al-Muwaqqi'in",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.AclamMuwaqqicin.Shamela0011496-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.ZadMacad",
        "book_id": "zad_al_maad",
        "category": "fiqh",
        "title_ar": "زاد المعاد في هدي خير العباد",
        "title_en": "Zad al-Ma'ad",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.ZadMacad.Shamela0021713-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.TuruqHukmiyya",
        "book_id": "turuq_hukmiyya",
        "category": "fiqh",
        "title_ar": "الطرق الحكمية في السياسة الشرعية",
        "title_en": "Al-Turuq al-Hukmiyyah",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.TuruqHukmiyya.Shamela0011495-ara1",
    },
    {
        "author_dir": "0463IbnCabdBarr",
        "book_dir": "0463IbnCabdBarr.KafiFiFiqh",
        "book_id": "kafi_ibn_abd_barr",
        "category": "fiqh",
        "title_ar": "الكافي في فقه أهل المدينة",
        "title_en": "Al-Kafi fi Fiqh Ahl al-Madinah",
        "author_ar": "ابن عبد البر",
        "author_en": "Ibn Abd al-Barr",
            "filename": "0463IbnCabdBarr.KafiFiFiqh.Shamela0007367-ara1",
    },
    {
        "author_dir": "0456IbnHazm",
        "book_dir": "0456IbnHazm.IhkamFiUsulAhkam",
        "book_id": "ihkam_usul_ahkam",
        "category": "fiqh",
        "title_ar": "الإحكام في أصول الأحكام",
        "title_en": "Al-Ihkam fi Usul al-Ahkam",
        "author_ar": "الإمام ابن حزم",
        "author_en": "Imam Ibn Hazm",
            "filename": "0456IbnHazm.IhkamFiUsulAhkam.Shamela0010432-ara1",
    },

    # ── Tazkiyah / Spirituality ──
    {
        "author_dir": "0505Ghazali",
        "book_dir": "0505Ghazali.IhyaCulumDin",
        "book_id": "ihya_ulum_al_din",
        "category": "tazkiyah",
        "title_ar": "إحياء علوم الدين",
        "title_en": "Ihya Ulum al-Din",
        "author_ar": "الإمام الغزالي",
        "author_en": "Imam al-Ghazali",
    },
    {
        "author_dir": "0505Ghazali",
        "book_dir": "0505Ghazali.BidayatHidaya",
        "book_id": "bidayat_al_hidaya",
        "category": "tazkiyah",
        "title_ar": "بداية الهداية",
        "title_en": "Bidayat al-Hidaya",
        "author_ar": "الإمام الغزالي",
        "author_en": "Imam al-Ghazali",
    },
    {
        "author_dir": "0728IbnTaymiyya",
        "book_dir": "0728IbnTaymiyya.AmradQulub",
        "book_id": "amrad_al_qulub",
        "category": "tazkiyah",
        "title_ar": "أمراض القلوب وشفاؤها",
        "title_en": "Diseases of the Hearts",
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Sheikh al-Islam Ibn Taymiyyah",
    },

    # ── Seerah (Biography) ──
    {
        "author_dir": "0213IbnHisham",
        "book_dir": "0213IbnHisham.SiraNabawiyya",
        "book_id": "sirat_ibn_hisham",
        "category": "seerah",
        "title_ar": "السيرة النبوية",
        "title_en": "Al-Sirah al-Nabawiyyah",
        "author_ar": "ابن هشام",
        "author_en": "Ibn Hisham",
    },

    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.MadarijSalikin",
        "book_id": "madarij_al_salikin",
        "category": "tazkiyah",
        "title_ar": "مدارج السالكين",
        "title_en": "Madarij al-Salikin",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.MadarijSalikin.Shamela0008370-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.CuddatSabirin",
        "book_id": "uddat_al_sabirin",
        "category": "tazkiyah",
        "title_ar": "عدة الصابرين وذخيرة الشاكرين",
        "title_en": "Uddat al-Sabirin",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.CuddatSabirin.Shamela0011274-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.DaWaDawa",
        "book_id": "al_da_wal_dawa",
        "category": "tazkiyah",
        "title_ar": "الداء والدواء (الجواب الكافي)",
        "title_en": "Al-Da' wa al-Dawa'",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.DaWaDawa.Shamela0000158-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.IghathatLahfan",
        "book_id": "ighathat_al_lahfan",
        "category": "tazkiyah",
        "title_ar": "إغاثة اللهفان من مصايد الشيطان",
        "title_en": "Ighathat al-Lahfan",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.IghathatLahfan.Shamela0007513-ara1",
    },
    {
        "author_dir": "0751IbnQayyimJawziyya",
        "book_dir": "0751IbnQayyimJawziyya.WabilSayyib",
        "book_id": "al_wabil_al_sayyib",
        "category": "tazkiyah",
        "title_ar": "الوابل الصيب من الكلم الطيب",
        "title_en": "Al-Wabil al-Sayyib",
        "author_ar": "ابن قيم الجوزية",
        "author_en": "Ibn Qayyim al-Jawziyyah",
            "filename": "0751IbnQayyimJawziyya.WabilSayyib.Shamela0000216-ara1",
    },
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.RiyadSalihin",
        "book_id": "riyad_al_salihin",
        "category": "tazkiyah",
        "title_ar": "رياض الصالحين",
        "title_en": "Riyad al-Salihin",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
            "filename": "0676Nawawi.RiyadSalihin.Shamela0000512-ara4",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.Tawwabin",
        "book_id": "al_tawwabin",
        "category": "tazkiyah",
        "title_ar": "كتاب التوابين",
        "title_en": "Al-Tawwabin",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
            "filename": "0620IbnQudamaMaqdisi.Tawwabin.Shamela0011317-ara1",
    },
    {
        "author_dir": "0620IbnQudamaMaqdisi",
        "book_dir": "0620IbnQudamaMaqdisi.RiqqaWaBuka",
        "book_id": "riqqa_wa_buka",
        "category": "tazkiyah",
        "title_ar": "الرقة والبكاء",
        "title_en": "Al-Riqqa wa al-Buka'",
        "author_ar": "ابن قدامة المقدسي",
        "author_en": "Ibn Qudama al-Maqdisi",
            "filename": "0620IbnQudamaMaqdisi.RiqqaWaBuka.Shamela0009384-ara1",
    },

    # ── Usul (Principles) ──
    {
        "author_dir": "0676Nawawi",
        "book_dir": "0676Nawawi.BustanCarifin",
        "book_id": "bustan_al_arifin",
        "category": "tazkiyah",
        "title_ar": "بستان العارفين",
        "title_en": "Bustan al-Arifin",
        "author_ar": "الإمام النووي",
        "author_en": "Imam al-Nawawi",
    },
]


def fetch_raw(url: str) -> str | None:
    """Fetch text from URL with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  FAILED: {url}: {e}")
                return None


def fetch_json_api(url: str) -> list | None:
    """Fetch directory listing from GitHub API."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"  API FAILED: {url}: {e}")
                return None


def find_markdown_file(book_info: dict) -> str | None:
    """Find the best mARkdown file for a book via GitHub API.

    Falls back to brute-force raw URL probing if the API is rate-limited.
    """
    base = f"{book_info['author_dir']}/{book_info['book_dir']}"

    # Try API first
    url = f"{API_BASE}/{base}"
    files = fetch_json_api(url)
    if files is not None:
        # Prefer .mARkdown files, then Shamela files
        markdown_files = [f for f in files if f["name"].endswith(".mARkdown")]
        shamela_files = [
            f for f in files
            if not f["name"].endswith((".yml", ".md"))
            and "Shamela" in f["name"]
        ]

        candidates = markdown_files or shamela_files
        if not candidates:
            print(f"  No text files found in {book_info['book_dir']}")
            return None

        chosen = candidates[0]
        return f"{RAW_BASE}/{base}/{chosen['name']}"

    # API failed (likely rate-limited) — use filename hint if available
    filename = book_info.get("filename")
    if filename:
        print(f"  Using filename hint: {filename}")
        return f"{RAW_BASE}/{base}/{filename}"

    print(f"  No text file found for {book_info['book_dir']} (API rate-limited, no filename hint)")
    return None


def parse_openiti_text(raw_text: str) -> list[dict]:
    """Parse OpenITI mARkdown format into sections.

    mARkdown conventions:
    - ### | heading  → section heading (level 3)
    - # text         → paragraph start (level 1)
    - ~~ text        → continuation of previous paragraph
    - PageV01P###    → page markers (strip)
    - ms# / ms###    → milestone markers (strip)
    - #META#...      → metadata (skip)
    - ######OpenITI# → file header (skip)
    """
    lines = raw_text.split("\n")
    sections = []
    current_section_title = ""
    current_paragraphs = []
    current_para = ""
    in_header = True

    for line in lines:
        line = line.rstrip()

        # Skip header metadata
        if in_header:
            if line.startswith("#META#Header#End#"):
                in_header = False
            continue

        # Skip empty lines and OpenITI markers
        if not line or line.startswith("######OpenITI"):
            continue

        # Skip page/milestone markers alone on a line
        if re.match(r"^(PageV\d+P\d+|ms\d+)\s*$", line):
            continue

        # Section heading
        if line.startswith("### |"):
            # Save previous section
            if current_para:
                current_paragraphs.append(current_para.strip())
                current_para = ""
            if current_paragraphs:
                sections.append({
                    "title": current_section_title,
                    "paragraphs": current_paragraphs,
                })
            current_section_title = line[5:].strip()
            # Clean markers from title
            current_section_title = re.sub(
                r"(PageV\d+P\d+|ms\d+)", "", current_section_title
            ).strip()
            current_paragraphs = []
            continue

        # Continuation line
        if line.startswith("~~"):
            text = line[2:].strip()
            text = re.sub(r"(PageV\d+P\d+|ms\d+)", "", text).strip()
            if text:
                current_para += " " + text
            continue

        # New paragraph (starts with # or plain text)
        if current_para:
            current_paragraphs.append(current_para.strip())
        if line.startswith("# "):
            text = line[2:].strip()
        else:
            text = line.strip()
        text = re.sub(r"(PageV\d+P\d+|ms\d+)", "", text).strip()
        current_para = text

    # Don't forget the last section
    if current_para:
        current_paragraphs.append(current_para.strip())
    if current_paragraphs:
        sections.append({
            "title": current_section_title,
            "paragraphs": current_paragraphs,
        })

    return sections


def sections_to_chapters(
    sections: list[dict],
    book_id: str,
    max_entries_per_chapter: int = 50,
    max_entry_chars: int = 3000,
) -> list[dict]:
    """Group sections into chapters with merged prose entries.

    Consecutive paragraphs within a section are merged into ~3000-char
    entries (joined with \\n\\n) so that books read as flowing prose
    rather than collections of numbered fragments.

    Very long individual paragraphs are still split at sentence
    boundaries before merging.
    """
    if not sections:
        return []

    chapters = []
    current_entries = []
    current_chapter_title = sections[0]["title"] or "مقدمة"
    chapter_num = 1
    entry_id = 1

    # Accumulator for merging paragraphs into a single entry.
    merge_parts: list[str] = []
    merge_chars = 0

    def flush_merge():
        nonlocal entry_id, merge_chars
        if not merge_parts:
            return
        current_entries.append({
            "id": entry_id,
            "text_ar": "\n\n".join(merge_parts),
            "text_en": "",
            "reference": "",
        })
        entry_id += 1
        merge_parts.clear()
        merge_chars = 0

    for section in sections:
        section_title = section["title"]

        for para in section["paragraphs"]:
            para = para.strip()
            if not para:
                continue

            # Split very long paragraphs at sentence boundaries
            texts = _split_long_text(para, max_entry_chars)

            for text in texts:
                text = clean_text(text)
                if not text or len(text) < 5:
                    continue

                merge_parts.append(text)
                merge_chars += len(text)

                if merge_chars >= max_entry_chars:
                    flush_merge()

        # Start new chapter if we hit the entry limit
        if len(current_entries) >= max_entries_per_chapter:
            flush_merge()
            chapters.append({
                "book_id": book_id,
                "chapter_id": chapter_num,
                "title_ar": current_chapter_title,
                "title_en": "",
                "entries": current_entries,
            })
            chapter_num += 1
            current_entries = []
            current_chapter_title = section_title or f"الجزء {chapter_num}"

    # Flush remaining merge buffer and last chapter
    flush_merge()
    if current_entries:
        chapters.append({
            "book_id": book_id,
            "chapter_id": chapter_num,
            "title_ar": current_chapter_title,
            "title_en": "",
            "entries": current_entries,
        })

    return chapters


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split long text at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    parts = []
    # Split on common Arabic/Unicode sentence endings
    sentences = re.split(r'(?<=[.。؟!])\s+', text)

    current = ""
    for sent in sentences:
        if current and len(current) + len(sent) > max_chars:
            parts.append(current.strip())
            current = sent
        else:
            current = current + " " + sent if current else sent

    if current.strip():
        parts.append(current.strip())

    # If sentences are still too long, hard-split
    result = []
    for p in parts:
        if len(p) <= max_chars * 1.5:
            result.append(p)
        else:
            # Hard-split at word boundaries
            words = p.split()
            chunk = ""
            for w in words:
                if chunk and len(chunk) + len(w) > max_chars:
                    result.append(chunk.strip())
                    chunk = w
                else:
                    chunk = chunk + " " + w if chunk else w
            if chunk.strip():
                result.append(chunk.strip())

    return result if result else [text]


def process_book(book_info: dict) -> dict | None:
    """Fetch and convert one OpenITI book."""
    book_id = book_info["book_id"]
    category = book_info["category"]
    book_dir = OUTPUT_DIR / category / book_id
    chapters_dir = book_dir / "chapters"

    # Skip if already downloaded
    if (book_dir / "metadata.json").exists():
        print(f"  SKIP (already exists): {book_info['title_en']}")
        return None

    chapters_dir.mkdir(parents=True, exist_ok=True)

    # Find the text file URL
    print(f"  Finding text file...")
    text_url = find_markdown_file(book_info)
    if not text_url:
        print(f"  SKIP: no text file found for {book_id}")
        return None

    # Download the text
    print(f"  Downloading: {text_url.split('/')[-1]}")
    raw_text = fetch_raw(text_url)
    if not raw_text:
        print(f"  SKIP: download failed for {book_id}")
        return None

    # Parse into sections
    sections = parse_openiti_text(raw_text)
    if not sections:
        print(f"  SKIP: no sections parsed for {book_id}")
        return None

    print(f"  Parsed {len(sections)} sections")

    # Convert to chapters
    chapters = sections_to_chapters(sections, book_id)
    if not chapters:
        print(f"  SKIP: no chapters generated for {book_id}")
        return None

    # Write chapter files
    total_bytes = 0
    total_entries = 0
    for chapter in chapters:
        ch_json = json.dumps(chapter, ensure_ascii=False, indent=2)
        (chapters_dir / f"{chapter['chapter_id']}.json").write_text(
            ch_json, encoding="utf-8"
        )
        total_bytes += len(ch_json.encode("utf-8"))
        total_entries += len(chapter["entries"])

    # Write metadata
    metadata = {
        "id": book_id,
        "title_ar": book_info["title_ar"],
        "title_en": book_info["title_en"],
        "author_ar": book_info["author_ar"],
        "author_en": book_info["author_en"],
        "category": category,
        "chapter_count": len(chapters),
        "entry_count": total_entries,
        "total_size_bytes": total_bytes,
        "source": "openiti",
    }
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")
    metadata["total_size_bytes"] = total_bytes + len(meta_json.encode("utf-8"))
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    (book_dir / "metadata.json").write_text(meta_json, encoding="utf-8")

    print(
        f"  Done {book_id}: {len(chapters)} chapters, "
        f"{total_entries} entries, {total_bytes / 1024:.1f} KB"
    )
    return metadata


def main():
    print("=" * 60)
    print("Fetching classical texts from OpenITI")
    print("=" * 60)

    all_metadata = []

    for book in BOOKS_TO_FETCH:
        print(f"\n{book['title_en']} ({book['title_ar']})")
        meta = process_book(book)
        if meta:
            all_metadata.append(meta)
        time.sleep(1)  # Be nice to GitHub API

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done! Processed {len(all_metadata)}/{len(BOOKS_TO_FETCH)} books")
    if all_metadata:
        total_entries = sum(m.get("entry_count", 0) for m in all_metadata)
        total_size = sum(m["total_size_bytes"] for m in all_metadata)
        print(f"Total entries: {total_entries:,}")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
