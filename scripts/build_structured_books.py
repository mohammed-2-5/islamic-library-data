"""Build OpenITI books chapter by chapter of the book itself.

fetch_openiti.py cuts every book into chapters of fifty merged entries,
whatever its headings say, names each chapter after the section that closed
the one before it, and drops every heading from the text. For a short matn
that gave one chapter for the whole book; for a long one, a table of contents
whose names belong to the chapter before. Fiqh is read by looking things up —
«باب المياه», «كتاب الصلاة» — so here:

- in a book built on كتب, each «كتاب» starts a chapter, and its name is the
  chapter's title. Some digitisations mark it as a heading, some as a line of
  text («# كتاب الصلاة», «# = كتاب الطهارة =»), some as both. A كتاب too long
  to find one's way in goes on as a chapter per باب;
- a book without كتب starts a chapter at its own top headings, a few
  sections to a chapter, named after the first;
- every other heading (باب، فصل، …) is kept as its own line, at the head of
  the entry it opens, so the reader still sees where it is;
- a numbered heading («### | 1 -») becomes the number of the line under it;
- placeholder headings (empty, «مدخل», «....») are dropped, and so is the
  modern editor's introduction and endnotes;
- a paragraph split by a page break mid-sentence is joined again;
- footnote marks whose notes the digitisation did not keep are removed, in
  whichever form that book's digitisation left them;
- HTML left over from the source pages is stripped.

Usage: python scripts/build_structured_books.py [book_id ...]
Writes data/books/{category}/{id}/ in the same shape as fetch_openiti.py.
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_openiti import BOOKS_TO_FETCH, OUTPUT_DIR, RAW_BASE, fetch_raw  # noqa: E402
from utils.arabic_normalize import clean_text  # noqa: E402

STUDY_TEXTS = [
    'akhsar_al_mukhtasarat', 'zad_al_mustaqni', 'dalil_al_talib',
    'al_rawd_al_murbi', 'nayl_al_maarib', 'matn_abi_shuja', 'fath_al_qarib',
    'umdat_al_salik', 'kifayat_al_akhyar',
]

# Books fetch_openiti.py once built in fifty-entry chapters, rebuilt here.
#   file     — the OpenITI version read
#   id       — the id they are published under now. Phones cache a book's
#              chapters by id with no version: under the old id, a phone that
#              had the book would show its old chapters mixed with the new.
#   chapters — 'kitab' (default) or 'sections' (see the module docstring)
#   level    — for 'sections': the deepest heading level a chapter starts at
#   starts   — for 'sections': the headings that always start a chapter (a
#              باب, a part); the others start one when it has grown long
#   split    — for 'kitab': a كتاب longer than this many characters goes on
#              as a chapter per باب
#   start    — the first line of the book: before it, the modern editor's
#              introduction, dropped
#   end      — the first heading of the editor's back matter, dropped from
#              there on; drop — headings of his in the book's text
#   rejoin   — «headings» that are the end of the sentence before them
#   glued    — (end of a paragraph, heading it is): a heading written on the
#              last line of the paragraph before it; leading — headings
#              written at the start of the paragraph they open
#   numbers  — the hadith number is a line of its own («# 1 -»), kept as the
#              number of the line under it; headings start with the كتاب's
#              number («1 - كتاب وقوت الصلاة»), dropped from the heading
REBUILT: dict[str, dict] = {
    'adhkar_nawawi': {'file': '0676Nawawi.Adhkar.Shamela0001956-ara1',
                      'id': 'adhkar_nawawi_v2', 'split': 15000},
    'al_kafi_fiqh': {'file': '0620IbnQudamaMaqdisi.KafiFiFiqh.Shamela0021731-ara1',
                     'id': 'al_kafi_fiqh_v2', 'split': 100000},
    'al_majmu_nawawi': {'file': '0676Nawawi.Majmuc.Shamela0002186-ara1',
                        'id': 'al_majmu_nawawi_v2', 'split': 150000,
                        'drop': ('المجموع شرح المهذب ((مع تكملة السبكي والمطيعي))',)},
    'al_mughni': {'file': '0620IbnQudamaMaqdisi.Mughni.ShamAY0034266-ara1',
                  'id': 'al_mughni_v2', 'split': 150000},
    'al_muqni_fiqh': {'file': '0620IbnQudamaMaqdisi.MuqnicFiFiqh.Sham19Y0019233-ara1',
                      'id': 'al_muqni_fiqh_v2', 'start': 'مقدمة المؤلف',
                      'end': 'مصادر ومراجع التحقيق', 'drop': ('خاتمة الكتاب والتحقيق',)},
    'al_umm': {'file': '0204Shafici.Umm.Shamela0001655-ara1',
               'id': 'al_umm_v2', 'split': 100000},
    'kafi_ibn_abd_barr': {'file': '0463IbnCabdBarr.KafiFiFiqh.Shamela0007367-ara1',
                          'id': 'kafi_ibn_abd_barr_v2'},
    'minhaj_talibin': {'file': '0676Nawawi.MinhajTalibin.Shamela0012096-ara1',
                       'id': 'minhaj_talibin_v2'},
    'muwatta_malik': {'file': '0179MalikIbnAnas.Muwatta.Shamela0001699-ara1',
                      'id': 'muwatta_malik_v2', 'numbers': True},
    'rawdat_al_talibin': {'file': '0676Nawawi.RawdatTalibin.Shamela0000499-ara1',
                          'id': 'rawdat_al_talibin_v2', 'split': 100000,
                          'rejoin': ('كتاب «الرهن».',)},
    'umdat_al_fiqh': {'file': '0620IbnQudamaMaqdisi.CumdatFiqh.Shamela0011315-ara1',
                      'id': 'umdat_al_fiqh_v2'},
    'al_mustasfa': {'file': '0505Ghazali.Mustasfa.Shamela0005459-ara1',
                    'id': 'al_mustasfa_v2', 'chapters': 'sections',
                    'starts': r'^(القطب|الفن|الباب|القسم|الأصل|كتاب|خاتمة)'},
    'al_risala_shafii': {'file': '0204Shafici.Risala.Shamela0008180-ara1',
                         'id': 'al_risala_shafii_v2', 'chapters': 'sections',
                         'start': 'بسم الله الرحمن الرحيم... الربيع بن سليمان',
                         'level': 9,           # its باب lines in the text too
                         'starts': r'^باب'},
    'ihkam_usul_ahkam': {'file': '0456IbnHazm.IhkamFiUsulAhkam.Shamela0010432-ara1',
                         'id': 'ihkam_usul_ahkam_v2', 'chapters': 'sections',
                         'starts': r'^الباب ',
                         'glued': [('في إثبات حجج العقول', 'الباب الثالث في إثبات حجج العقول')],
                         'leading': (
                             'الباب الخامس في الألفاظ الدائرة بين أهل النظر',
                             'الباب السادس هل الأشياء في العقل قبل ورود الشرع على الحظر أو على الإباحة',
                             'الباب العشرون الكلام في النسخ',
                             'الباب الأربعون وهو باب الكلام في الاجتهاد ما هو وبيانه ومن هو معذور'
                             ' باجتهاده ومن ليس معذورا به ومن يقطع على أنه خطأ عند الله تعالى فيما'
                             ' أراد إليه اجتهاده ومن لا يقع على أنه مخطىء عند الله عز وجل وإن خالفناه',
                         )},
    'ilam_al_muwaqqiin': {'file': '0751IbnQayyimJawziyya.AclamMuwaqqicin.Shamela0011496-ara1',
                          'id': 'ilam_al_muwaqqiin_v2', 'chapters': 'sections'},
    'qawaid_nuraniyyah': {'file': '0728IbnTaymiyya.QawacidNuraniyya.Shamela0021729-ara1',
                          'id': 'qawaid_nuraniyyah_v2', 'chapters': 'sections'},
    'rawdat_al_nazir': {'file': '0620IbnQudamaMaqdisi.RawdatNazir.ShamAY0034197-ara1',
                        'id': 'rawdat_al_nazir_v2', 'chapters': 'sections',
                        'starts': r'^(باب|القسم|الأصل)',
                        'drop': ('كتاب روضة الناظر وجنة المناظر',),
                        # Cut short mid-word, with a page of a gharib
                        # dictionary after it; JK000156 is the same text.
                        'ending': {'file': '0620IbnQudamaMaqdisi.RawdatNazir.Shamela0012010-ara1',
                                   'from': 'ومنع ذلك قوم',
                                   'through': 'وصلى الله على خير رسله'}},
    'siyasa_shariyya': {'file': '0728IbnTaymiyya.SiyasaSharciyya.Shamela0031237-ara1',
                        'id': 'siyasa_shariyya_v2', 'chapters': 'sections',
                        'starts': r'^(القسم|الباب)'},
    'turuq_hukmiyya': {'file': '0751IbnQayyimJawziyya.TuruqHukmiyya.Shamela0011495-ara1',
                       'id': 'turuq_hukmiyya_v2', 'chapters': 'sections'},
    'zad_al_maad': {'file': '0751IbnQayyimJawziyya.ZadMacad.Shamela0021713-ara1',
                    'id': 'zad_al_maad_v2', 'chapters': 'sections'},
}

# Every book this script builds; fetch_openiti.py leaves them alone.
STRUCTURED = set(STUDY_TEXTS) | set(REBUILT)

# A chapter of a 'sections' book closes at the next top heading once it holds
# this many characters.
SECTION_CHAPTER_CHARS = 40000

# How each digitisation left the marks of footnotes it did not keep.
#   digits — glued to the word or the quote: «ذكره1», «"أكثر"1», «الحدث 1وزوال»;
#            these texts have no other numbers but Qur'an references
#   parens — «(1)»
#   loose  — a lone digit between two words: «وإن 2 كان»
FOOTNOTE_MARKS = {
    'zad_al_mustaqni': 'digits',
    'dalil_al_talib': 'digits',
    'nayl_al_maarib': 'parens',
    'kifayat_al_akhyar': 'loose',
    'adhkar_nawawi': 'parens',
    'al_majmu_nawawi': 'parens',
    'al_muqni_fiqh': 'parens',
    'siyasa_shariyya': 'parens',
    'turuq_hukmiyya': 'parens',
    'rawdat_al_nazir:ending': 'digits',     # its edition's notes, «فيها4»
    'umdat_al_fiqh': 'digits',
    'al_risala_shafii': 'parens',
}

# One-off slips a pattern would get wrong. Fath al-Qarib's two footnote marks
# sit among the real numbers of its ten head wounds «(1) حارصة … (10) ودامغة»,
# and its one «ﷺ» came through as a Latin «S».
FIXES = {
    'fath_al_qarib': [('عافيت» (1) إلخ', 'عافيت» إلخ'),
                      ('في الاستفتاح. (1)', 'في الاستفتاح.'),
                      ('على النبي S)', 'على النبي ﷺ)')],
    'umdat_al_salik': [('ومستدبره./ 9', 'ومستدبره.')],
    'dalil_al_talib': [('بسم الله الر حمن الرحيم', 'بسم الله الرحمن الرحيم')],
    'muwatta_malik': [('#ويسعى@348', 'ويسعى')],
    'al_risala_shafii': [('جص 193>', '')],
    'rawdat_al_nazir': [('القسم الثاني  بسم الله', 'بسم الله')],
}

# Text that is not the book: the second volume's title page and imprint, in
# the middle of Nayl al-Ma'arib, dropped from its first line to the next
# heading; the tail of a sentence whose start the digitisation lost, which
# opened Kifayat al-Akhyar; the corrector's notes closing the volumes of the
# Majmu'.
DROP_TO_HEADING = {'nayl_al_maarib': ('(تم الجزء الأول',)}
DROP_PARAGRAPH = {
    'kifayat_al_akhyar': ('عطاء الذكر هو مجالس الحلال والحرام',),
    'al_majmu_nawawi': ('* قال مصححه', 'قال مصححه', '* والشرح الكبير للامام المحقق',
                        'بعون الله تعالى قد تم طبع'),
}

# The title page and imprint every volume of a rebuilt book opens with, and
# the publisher's card a Shamela file opens with: short lines dropped.
FRONT_MATTER = re.compile(
    r'^(المؤلف|الناشر|المحقق|الطبعة|عدد الأجزاء|مصدر الكتاب)\s*:'
    r'|^\[ترقيم الكتاب|^\(طبعة|^ويليه\b|^دار الفكر$|المتوفى:? سنة \d+|\(المتوفى:? ?\d+'
    r'|طبع \(?الجزء|^جميع الحقوق')
TITLE_LINES = {
    'al_majmu_nawawi': ('المجموع شرح المهذب', 'للامام ابي زكريا', 'للإمام أبي زكريا',
                        'فتح العزيز', 'التلخيص الحبير', 'للامام ابي القاسم',
                        'للإمام أبي القاسم', 'للحافظ'),
}

# Lines that open a كتاب in the printed book but were written «باب» here.
CHAPTER_LINES = {
    'nayl_al_maarib': {'باب الزكاة', 'باب النكاح'},
}

# Lines of text that are a «فصل» in the book, written as a باب's name here —
# the other digitisations of Dalil al-Talib have «فصل» there.
FASL_LINES = {
    'dalil_al_talib': {'باب الكتابة'},
}

# Books whose numbered headings are noise («0 -», a lone «2 -»).
NUMBERS_ARE_NOISE = {'kifayat_al_akhyar'}

# Books punctuated by their editors, where a line that ends without a stop
# was cut mid-sentence by the digitisation: «… وتوضأ وضوءه» / «للصلاة، ثم …».
RUN_ON_BOOKS = {'al_rawd_al_murbi', 'nayl_al_maarib', 'fath_al_qarib',
                'muwatta_malik', 'al_mughni', 'al_umm', 'al_risala_shafii', 'al_mustasfa',
                'adhkar_nawawi', 'ilam_al_muwaqqiin'}
PARA_END = re.compile(r'[.:؟!»"\])}*]\s*$')
NEW_PART = re.compile(r'^[\[{("]?(فصل|فرع|تنبيه|باب|كتاب|مسألة)\b|^(-|\[|\d+ -|\(\d+\))')

MAX_ENTRY_CHARS = 3000
# A paragraph longer than this — whole pages run together by the
# digitisation — is cut at its sentences, as fetch_openiti.py did.
LONG_PARAGRAPH = 6000
MARKERS = re.compile(r'PageV\d+P\d+|ms\d+')
SENTENCE_END = re.compile(r'[.:؟!»)\]}]\s*$')
PLACEHOLDER = re.compile(r'^(\W*|مدخل)$')
NUMBERED = re.compile(r'^(\d+(?:\s*-\s*\d+)*)\s*-?$')
KITAB = re.compile(r'^كتاب\s\S')
CLAUSE_END = re.compile(r'[.:؟!،]\s*$')
LETTER = re.compile(r'[ء-ي]')
QURAN_REF = re.compile(r'\[[^\[\]]{1,20}:\s*\d+(?:\s*-\s*\d+)?\]')
LIST_ITEM = re.compile(r'^(-|\[\d+\]|\(\d+\)|\d+\)|\d+(?: - \d+)* -)\s')
IN_TEXT = 9   # the level of a heading found in a line of text
# The lines a volume opens with, before the book goes on.
VOLUME_OPENER = re.compile(r'^(بسم الله الرحمن الرحيم|وصلى الله على (سيدنا )?محمد|رب يسر|وبه نستعين)')


def strip_marks(text: str, mode: str | None) -> str:
    text = re.sub(r'\s*\(¬\d+\)', '', text)
    if mode == 'parens':
        text = re.sub(r'\s*\(\d{1,3}\)', '', text)
    elif mode == 'loose':
        text = re.sub(r'(?<=[ء-ي]) \d{1,2}(?= [ء-ي(]|$)', '', text)
    elif mode == 'digits':
        kept: list[str] = []

        def keep(m):
            kept.append(m.group())
            return chr(0xE000 + len(kept) - 1)

        text = QURAN_REF.sub(keep, text)
        # A mark wedged between two words: «و2لكن» is one word, «أو3القعود» two.
        text = re.sub(r'(?<![ء-ي])أو\d+(?=[ء-ي])', 'أو ', text)
        text = re.sub(r'\d+', '', text)
        text = re.sub('[-]', lambda m: kept[ord(m.group()) - 0xE000], text)
    return text


def split_long(text: str) -> list[str]:
    """Pieces of about MAX_ENTRY_CHARS, cut after a full stop."""
    pieces, current = [], ''
    for sentence in re.split(r'(?<=[.؟!])\s+', text):
        if current and len(current) + len(sentence) > MAX_ENTRY_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f'{current} {sentence}' if current else sentence
    if current:
        pieces.append(current)
    # No full stop in a whole page: cut between words instead.
    out = []
    for piece in pieces:
        while len(piece) > LONG_PARAGRAPH:
            cut = piece.rfind(' ', 0, MAX_ENTRY_CHARS)
            out.append(piece[:cut])
            piece = piece[cut + 1:]
        out.append(piece)
    return out


def clean_line(text: str, book_id: str) -> str:
    # «… في PageV01P207 # ذممهما»: a paragraph mark at a page break, mid-sentence.
    text = re.sub(r'(PageV\d+P\d+|ms\d+)\s*#\s', ' ', text)
    text = MARKERS.sub('', text)
    text = html.unescape(text)
    # A tooltip's tag holds tags of its own: «<span onmouseover="Tip('<b>…')"
    # onmouseout="UnTip()">» — up to its end, or the first «>» cuts it short.
    text = re.sub(r'<span[^\n]*?onmouseout="UnTip\(\)">', '', text)
    text = re.sub(r"',\s*WIDTH,.*?onmouseout=\"UnTip\(\)\">", '', text)
    text = re.sub(r'\S*onmouseout="UnTip\(\)">', '', text)
    text = re.sub(r'<[^>]*>', '', text)
    for old, new in FIXES.get(book_id, []):
        text = text.replace(old, new)
    text = strip_marks(text, FOOTNOTE_MARKS.get(book_id))
    text = re.sub(r'\bظظ\b', '', text)
    if book_id in REBUILT:
        text = re.sub(r'\s*[<>]\s*', ' ', text)            # a tag's stray half
        text = re.sub(r'\s*\[ص: ?\d+\]', '', text)        # the edition's page
        text = re.sub(r'(?<=\}) \d{1,3}(?= [ء-ي])', '', text)  # «{…} 1 يشترط»
    text = clean_text(text)
    return re.sub(r'\s+([.،,:؛؟!)\]»])', r'\1', text)


def clean_heading(raw: str, book_id: str) -> str:
    text = re.sub(r'^(AUTO|CHECK)(\s+|$)', '', MARKERS.sub('', raw).strip())
    if book_id in REBUILT:
        # «### | AUTO ### || AUTO مقدمة الخرقي»: a heading tagged twice.
        text = re.sub(r'^((AUTO|CHECK)\s+|###\s*[|$]*\s*)+', '', text)
        if re.fullmatch(r'\[?ص: ?\d+\]?|(الجزء|المجلد)\s+\S+(\s+\S+)?', text.strip()):
            return ''                  # the edition's page or volume
    numbered = NUMBERED.match(text.strip())
    if numbered:                 # before a book's digit marks are stripped
        return re.sub(r'\s*-\s*', ' - ', numbered.group(1))
    if REBUILT.get(book_id, {}).get('numbers'):
        text = re.sub(r'^\d+\s*-\s*(?=\D)', '', text)
    text = clean_line(text, book_id)
    text = text.strip('•= ').strip()
    if book_id in REBUILT:
        text = text.lstrip('*').strip()
        text = re.sub(r'^[{(\[]([^{}()\[\]]*)[})\]]$', r'\1', text)
    text = re.sub(r'^\[(.*)\]$', r'\1', text)
    if book_id in REBUILT:       # «(باب …)»: a heading, not the matn's words
        text = re.sub(r'^\(([^()]*)\)$', r'\1', text)
        # «[فصل]:», «باب.», «فرع:»: the word alone.
        bare = re.sub(r'[^ء-ي ]', '', text).strip()
        if bare in ('فصل', 'فرع', 'باب', 'كتاب', 'تنبيه', 'مسألة', 'فائدة', 'فروع'):
            text = bare
    return re.sub(r'\d+$', '', text).strip()


def heading_in_text(text: str, book_id: str) -> str | None:
    """A line of text that is a heading: «كتاب الصلاة», «= كتاب … =», «فصل»."""
    if len(text) > 60:
        return None
    if text.startswith('=') and text.endswith('='):
        return text.strip('= ')
    bare = re.sub(r'\d+$', '', text).strip()
    if KITAB.match(bare) and not CLAUSE_END.search(bare) and (
            '،' not in bare or book_id in REBUILT):
        return bare
    if bare == 'فصل' or bare in CHAPTER_LINES.get(book_id, ()):
        return bare
    if bare in FASL_LINES.get(book_id, ()):
        return 'فصل'
    if re.match(r'^باب\s\S', bare) and len(bare) <= 50 and not CLAUSE_END.search(bare) \
            and '،' not in bare:
        return bare
    return None


def parse(raw: str, book_id: str) -> list[tuple[str, list[str], int]]:
    """[(heading, paragraphs, level)] in order; the first heading is ''."""
    body = raw.split('#META#Header#End#', 1)[-1]
    sections: list[tuple[str, list[str], int]] = [('', [], 1)]
    para = ''
    join_next = False
    editor = False
    dropping = False
    heading_open = False          # the last line was a heading's
    rebuilt = book_id in REBUILT
    numbered_lines = REBUILT.get(book_id, {}).get('numbers', False)
    section_number = ''           # «(3)» on a line of its own, before its فصل

    def add(text: str):
        nonlocal section_number
        heading = heading_in_text(text, book_id)
        if heading:
            if section_number:
                heading, section_number = f'{section_number} {heading}', ''
            sections.append((heading, [], IN_TEXT))
            return
        if section_number:
            text, section_number = f'{section_number} {text}', ''
        previous = sections[-1][1]
        if rebuilt and len(text) > LONG_PARAGRAPH:
            previous.extend(split_long(text))
            return
        # «: كأحدهم.» — the end of the line before, put on a line of its own.
        if previous and re.match(r'^[:.،؛]', text):
            previous[-1] += text if text[0] in ':.' else ' ' + text
            return
        # Where the digitisation cut a sentence in two, in the books whose
        # sentences end in punctuation.
        if book_id in RUN_ON_BOOKS and previous and not PARA_END.search(previous[-1]) \
                and not NEW_PART.match(text) and not (rebuilt and (
                    # a line of verse, «… ...  …», has no stop to end on;
                    # nor does a heading «(قال الشافعي):» opens
                    '...' in previous[-1] or '...' in text or text.startswith('(قال'))):
            previous[-1] += ' ' + text
            return
        previous.append(text)

    def close_para():
        nonlocal para, dropping, section_number
        text = clean_line(para, book_id)
        para = ''
        if text.startswith(DROP_TO_HEADING.get(book_id, ())):
            dropping = True
        if editor or dropping:
            return
        if not LETTER.search(text):
            if numbered_lines and NUMBERED.match(text):
                sections.append((text, [], IN_TEXT))
            elif rebuilt and re.fullmatch(r'\(\d+\)', text):
                section_number = text
            return
        if text.startswith(DROP_PARAGRAPH.get(book_id, ())):
            return
        if rebuilt and len(text) < 120 and (
                FRONT_MATTER.search(text) or text.startswith(TITLE_LINES.get(book_id, ()))):
            return
        # «… ولا يجوز الصياح. باب ما يحرم لبسه»: the next heading, on the
        # last line of the paragraph before it.
        glued = re.match(r'^(.*[.:؟!])\s+(باب\s[^.:،؟!]{2,40})$', text) \
            or re.match(r'^(.*\S)\s+(فصل)$', text)
        if glued:
            add(glued.group(1))
            sections.append((glued.group(2), [], IN_TEXT))
        else:
            add(text)

    for line in body.split('\n'):
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith('### '):
            close_para()
            join_next = False
            dropping = False
            editor = '|EDITOR|' in line
            if editor:
                continue
            marks = re.match(r'###\s*([|$]*)', line).group(1)
            level = max(1, marks.count('|'))
            text = re.sub(r'^###\s*[|$]*\s*', '', line)
            # A sub-heading the tagger was unsure of sits a few lines before
            # its section; the «فصل» line in the text marks the real start.
            if level > 1 and re.match(r'(\S+\s+)?CHECK\s', MARKERS.sub('', text).strip()):
                continue
            sections.append((text, [], level))
            heading_open = rebuilt
            continue
        if line.startswith('~~'):
            if heading_open:
                # «### ||| (1) مسألة: قال أبو القاسم … (والطهارة بالماء» goes
                # on «~~الطاهر المطلق …»: one heading, over several lines.
                heading, paragraphs, level = sections[-1]
                sections[-1] = (f'{heading} {line[2:].strip()}', paragraphs, level)
                continue
            para += ' ' + line[2:].strip()
            join_next = bool(re.search(r'PageV\d+P\d+\s*$', line))
            continue
        heading_open = False
        text = line[1:].strip() if line.startswith('#') else line.strip()
        if MARKERS.fullmatch(text):
            join_next = join_next or bool(para)
            continue
        # A paragraph that follows a page break inside a sentence is the same
        # paragraph, cut by the page.
        ends_page = bool(re.search(r'PageV\d+P\d+\s*$', line))
        # A hadith's number on its own line («# 5 -») starts the next one.
        number_line = rebuilt and not LETTER.search(MARKERS.sub('', text))
        # …and so does a باب, in a book without stops to tell them apart.
        part_line = rebuilt and re.match(r'(الباب|باب|كتاب|فصل)\s', MARKERS.sub('', text))
        if join_next and para and not number_line and not part_line \
                and not SENTENCE_END.search(clean_line(para, book_id)):
            para += ' ' + text
        else:
            close_para()
            para = text
        join_next = ends_page
    close_para()
    return sections


def join_bare_headings(sections, book_id: str):
    """«### | كتاب» then «### | الوقف»; «### | باب» then «# المواقيت»: one
    heading split in two. A first line with a definition after its colon
    («الإحرام: نية النسك.») names the باب and stays as its first line; a long
    first line is the باب's text, and the bare word stays alone."""
    out = []
    pending = None
    for raw_heading, paragraphs, level in sections:
        heading = clean_heading(raw_heading, book_id)
        if pending:
            word, level = pending
            if heading:
                heading = f'{word} {heading}'
            elif paragraphs:
                heading, paragraphs = name_from_first_line(word, paragraphs)
            else:
                heading = word
            pending = None
        if heading in ('كتاب', 'باب'):
            if not paragraphs:
                pending = (heading, level)
                continue
            heading, paragraphs = name_from_first_line(heading, paragraphs)
        out.append((heading, paragraphs, level))
    return out


def name_from_first_line(word: str, paragraphs: list[str]) -> tuple[str, list[str]]:
    first = paragraphs[0]
    if ':' in first and len(first.split(':', 1)[0]) <= 60:
        return f'{word} {first.split(":", 1)[0].strip()}', paragraphs
    if len(first) <= 80:
        return f'{word} {first}', paragraphs[1:]
    return word, paragraphs


def same_name(a: str, b: str) -> bool:
    letters = lambda s: re.sub(r'[^ء-ي]', '', s)  # noqa: E731
    return letters(a) == letters(b)


def echoes(text: str, title: str) -> bool:
    """«كتاب الوقف» or «الوقف» under the chapter «كتاب الوقف»."""
    return same_name(text, title) or same_name('كتاب ' + text, title)


def as_title(heading: str) -> str:
    title = re.sub(r'\s+', ' ', re.sub(r'[()\[\]{}*«»]', '', heading)).strip()
    return title.rstrip('.:،').strip()


def from_start(sections, start: str | None, end: str | None = None, drop=(),
               rejoin=(), glued=(), leading=()):
    """The sections from the book's first line to its last; the editor's
    before and after it go, and so do his headings in between."""
    if end:
        for i, (heading, _, _) in enumerate(sections):
            if heading == end or heading.startswith(end + ' '):
                sections = sections[:i]
                break
        else:
            raise SystemExit(f"the editor's back matter «{end}» was not found")
    sections = [(h if h not in drop else '', p, lv) for h, p, lv in sections]
    out = []
    for heading, paragraphs, level in sections:
        if heading in rejoin and out and out[-1][1]:
            out[-1][1][-1] += ' ' + heading
            heading = ''
        out.append((heading, list(paragraphs), level))
    sections = out
    for tail, named in glued:
        for i, (heading, paragraphs, level) in enumerate(sections):
            hit = next((j for j, t in enumerate(paragraphs) if t.endswith(tail)), None)
            if hit is not None:
                paragraphs[hit] = paragraphs[hit][:-len(tail)].rstrip()
                sections[i + 1:i + 1] = [(named, paragraphs[hit + 1:], 1)]
                del paragraphs[hit + 1:]
                break
        else:
            raise SystemExit(f'the glued heading «{tail}» was not found')
    for named in leading:
        for i, (heading, paragraphs, level) in enumerate(sections):
            hit = next((j for j, t in enumerate(paragraphs) if t.startswith(named)), None)
            if hit is not None:
                rest = paragraphs[hit][len(named):].strip()
                sections[i + 1:i + 1] = [(named, ([rest] if rest else []) + paragraphs[hit + 1:], 1)]
                del paragraphs[hit:]
                break
        else:
            raise SystemExit(f'the leading heading «{named}» was not found')
    if not start:
        return sections
    for i, (heading, paragraphs, level) in enumerate(sections):
        if heading.startswith(start):
            return sections[i:]
        for j, text in enumerate(paragraphs):
            if text.startswith(start):
                return [('', paragraphs[j:], level)] + sections[i + 1:]
    raise SystemExit(f'the book\'s first line «{start}» was not found')


def to_chapters(book_id: str, out_id: str, sections, config: dict) -> list[dict]:
    mode = config.get('chapters', 'kitab')
    rebuilt = book_id in REBUILT
    top_level = config.get('level', 1)
    split = config.get('split')
    starts = config.get('starts')
    chapters: list[dict] = []
    title = 'مقدمة'
    kitab = ''
    entries: list[dict] = []
    parts: list[str] = []
    size = 0
    chapter_size = 0
    entry_id = 1
    number = ''
    # Rebuilt books stack an editor's heading over the book's own («[في هديه
    # في حجه]», «فصل», «في هديه في حجه»), or repeat a باب's name across the
    # basmala of a new volume: headings since the last line of the book's
    # text, so one said again is said once.
    recent: list[str] = []
    entry_has_text = False
    chapter_has_text = False
    last_bab = ''

    def flush_entry():
        nonlocal parts, size, entry_id, entry_has_text
        entry_has_text = False
        if parts:
            text = parts[0]
            for part in parts[1:]:
                text += ('\n' if LIST_ITEM.match(part) else '\n\n') + part
            entries.append({'id': entry_id, 'text_ar': text,
                            'text_en': '', 'reference': ''})
            entry_id += 1
        parts, size = [], 0

    def flush_chapter():
        nonlocal entries, chapter_size, chapter_has_text
        chapter_has_text = False
        flush_entry()
        if entries:
            chapters.append({'book_id': out_id, 'chapter_id': len(chapters) + 1,
                             'title_ar': title, 'title_en': '', 'entries': entries})
        entries, chapter_size = [], 0

    for heading, paragraphs, level in from_start(join_bare_headings(sections, book_id),
                                                 config.get('start'), config.get('end'),
                                                 config.get('drop', ()),
                                                 config.get('rejoin', ()),
                                                 config.get('glued', ()),
                                                 config.get('leading', ())):
        numbered = NUMBERED.match(heading)
        # The كتاب's name written again, as heading and as text, under itself.
        echo = lambda text: not entries and not parts and echoes(text, title)  # noqa: E731
        empty = not entries and not parts
        if numbered:
            if book_id not in NUMBERS_ARE_NOISE and numbered.group(1) != '0':
                number = (number + ' - ' if number else '') + numbered.group(1)
        elif mode == 'kitab' and (KITAB.match(heading)
                                  or heading in CHAPTER_LINES.get(book_id, ())):
            # A volume that opens with the كتاب the one before closed on,
            # before a line of its text: the same كتاب.
            again = rebuilt and same_name(heading, title)
            if not echo(heading) and not again:
                flush_chapter()
                title = kitab = as_title(heading)
                last_bab = ''
        elif rebuilt and heading and any(same_name(heading, h) for h in recent):
            pass
        elif rebuilt and heading.startswith('باب ') and same_name(heading, last_bab):
            pass                       # the باب's name as a page's running head
        elif heading and not PLACEHOLDER.match(heading) and not echo(heading):
            starts_chapter = (
                mode == 'sections' and level <= top_level
                and (empty or chapter_size >= SECTION_CHAPTER_CHARS or title == 'مقدمة'
                     or (starts and re.match(starts, as_title(heading))))
            ) or (
                mode == 'kitab' and split and heading.startswith('باب ')
                and chapter_size >= split
            )
            if starts_chapter:
                flush_chapter()
                title = (f'{kitab} — {as_title(heading)}' if mode == 'kitab' and kitab
                         else as_title(heading))
            # A باب's opening written twice, as text and again under its
            # heading: keep the second.
            earlier = parts[1:]
            if parts and parts[0] == heading and len(paragraphs) >= len(earlier) and all(
                    later.startswith(text) for text, later in zip(earlier, paragraphs)):
                parts, size = [], 0
            if not (rebuilt and parts and not entry_has_text):
                flush_entry()        # a باب opens its own entry
            parts.append(heading)
            recent.append(heading)
            if heading.startswith('باب '):
                last_bab = heading
            size += len(heading)
            chapter_size += len(heading)
        for text in paragraphs:
            if echo(text):
                continue
            # A heading said again as the line under it.
            if rebuilt and any(same_name(text, h) for h in recent):
                continue
            if number:
                text, number = f'{number} - {text}', ''
            if size and size + len(text) > MAX_ENTRY_CHARS:
                flush_entry()
            parts.append(text)
            size += len(text)
            chapter_size += len(text)
            if not VOLUME_OPENER.match(text) or len(text) > 120:
                recent, entry_has_text, chapter_has_text = [], True, True
    flush_chapter()
    return chapters


def read_version(book: dict, filename: str) -> str:
    # OPENITI_CACHE: a folder of version files already downloaded, read first.
    cached = Path(os.environ.get('OPENITI_CACHE', '.')) / filename
    if os.environ.get('OPENITI_CACHE') and cached.exists():
        return cached.read_text(encoding='utf-8')
    url = f"{RAW_BASE}/{book['author_dir']}/{book['book_dir']}/{filename}"
    raw = fetch_raw(url)
    if not raw:
        raise SystemExit(f'download failed: {url}')
    return raw


def with_ending(book: dict, sections, ending: dict):
    """The book's last lines, lost from the version read, from another one:
    the paragraph starting with ending['from'] there and all after it, up to
    and with the one starting with ending['through']."""
    def last_index(paragraphs_of):
        for i in range(len(paragraphs_of) - 1, -1, -1):
            for j in range(len(paragraphs_of[i][1]) - 1, -1, -1):
                if paragraphs_of[i][1][j].startswith(ending['from']):
                    return i, j
        raise SystemExit(f"the ending «{ending['from']}» was not found")

    other = parse(read_version(book, ending['file']), f"{book['book_id']}:ending")
    i, j = last_index(other)
    lines = [t for _, paragraphs, _ in other[i:] for t in paragraphs]
    lines = lines[lines.index(other[i][1][j]):]
    through = next(n for n, t in enumerate(lines) if t.startswith(ending['through']))
    i, j = last_index(sections)
    heading, paragraphs, level = sections[i]
    return sections[:i] + [(heading, paragraphs[:j] + lines[:through + 1], level)]


def build(book: dict) -> dict:
    book_id = book['book_id']
    config = REBUILT.get(book_id, {})
    out_id = config.get('id', book_id)
    raw = read_version(book, config.get('file', book.get('filename')))
    sections = parse(raw, book_id)
    if 'ending' in config:
        sections = with_ending(book, sections, config['ending'])
    chapters = to_chapters(book_id, out_id, sections, config)

    # The old id leaves the catalog with its folder.
    old_dir = OUTPUT_DIR / book['category'] / book_id
    if out_id != book_id and old_dir.exists():
        shutil.rmtree(old_dir)
    book_dir = OUTPUT_DIR / book['category'] / out_id
    if book_dir.exists():
        shutil.rmtree(book_dir)
    chapters_dir = book_dir / 'chapters'
    chapters_dir.mkdir(parents=True)
    total_bytes = 0
    for chapter in chapters:
        text = json.dumps(chapter, ensure_ascii=False, indent=2)
        (chapters_dir / f"{chapter['chapter_id']}.json").write_text(text, encoding='utf-8')
        total_bytes += len(text.encode('utf-8'))
    metadata = {
        'id': out_id, 'title_ar': book['title_ar'], 'title_en': book['title_en'],
        'author_ar': book['author_ar'], 'author_en': book['author_en'],
        'category': book['category'], 'chapter_count': len(chapters),
        'entry_count': sum(len(c['entries']) for c in chapters),
        'total_size_bytes': total_bytes, 'source': 'openiti',
    }
    meta_text = json.dumps(metadata, ensure_ascii=False, indent=2)
    metadata['total_size_bytes'] = total_bytes + len(meta_text.encode('utf-8'))
    (book_dir / 'metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


def main(ids: list[str]) -> None:
    by_id = {b['book_id']: b for b in BOOKS_TO_FETCH}
    for book_id in ids or STUDY_TEXTS + list(REBUILT):
        meta = build(by_id[book_id])
        print(f"{meta['id']:24} chapters={meta['chapter_count']:>3} "
              f"entries={meta['entry_count']:>4} bytes={meta['total_size_bytes']:>9,}")


if __name__ == '__main__':
    main(sys.argv[1:])
