"""Build the Hanbali and Shafi'i study texts, one chapter per «كتاب».

fetch_openiti.py cuts every book into chapters of fifty merged entries,
whatever its headings say. For a short matn that gave one chapter for the
whole book, with no كتاب or باب anywhere in it. These texts are read by
looking things up — «باب المياه», «كتاب الصلاة» — so here:

- each «كتاب» starts a chapter, and its name is the chapter's title. Some
  digitisations mark it as a heading, some as a line of text («# كتاب
  الصلاة», «# = كتاب الطهارة =»), some as both;
- every other heading (باب، فصل، …) is kept as its own line, at the head of
  the entry it opens, so the reader still sees where it is;
- a numbered heading («### | 1 -») becomes the number of the line under it;
- placeholder headings (empty, «مدخل», «....») are dropped, and so is the
  modern editor's introduction and endnotes;
- a paragraph split by a page break mid-sentence is joined again;
- footnote marks whose notes the digitisation did not keep are removed, in
  whichever form that book's digitisation left them;
- HTML left over from the source pages is stripped.

Usage: python scripts/build_study_texts.py [book_id ...]
Writes data/books/fiqh/{book_id}/ in the same shape as fetch_openiti.py.
"""
import html
import json
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
}

# Text that is not the book: the second volume's title page and imprint, in
# the middle of Nayl al-Ma'arib, dropped from its first line to the next
# heading; and the tail of a sentence whose start the digitisation lost,
# which opened Kifayat al-Akhyar.
DROP_TO_HEADING = {'nayl_al_maarib': ('(تم الجزء الأول',)}
DROP_PARAGRAPH = {'kifayat_al_akhyar': ('عطاء الذكر هو مجالس الحلال والحرام',)}

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
RUN_ON_BOOKS = {'al_rawd_al_murbi', 'nayl_al_maarib', 'fath_al_qarib'}
PARA_END = re.compile(r'[.:؟!»"\])}*]\s*$')
NEW_PART = re.compile(r'^[\[{("]?(فصل|فرع|تنبيه|باب|كتاب|مسألة)\b|^(-|\[|\d+ -|\(\d+\))')

MAX_ENTRY_CHARS = 3000
MARKERS = re.compile(r'PageV\d+P\d+|ms\d+')
SENTENCE_END = re.compile(r'[.:؟!»)\]}]\s*$')
PLACEHOLDER = re.compile(r'^(\W*|مدخل)$')
NUMBERED = re.compile(r'^(\d+(?:\s*-\s*\d+)*)\s*-?$')
KITAB = re.compile(r'^كتاب\s\S')
CLAUSE_END = re.compile(r'[.:؟!،]\s*$')
LETTER = re.compile(r'[\u0621-\u064A]')
QURAN_REF = re.compile(r'\[[^\[\]]{1,20}:\s*\d+(?:\s*-\s*\d+)?\]')
LIST_ITEM = re.compile(r'^(-|\[\d+\]|\(\d+\)|\d+\)|\d+(?: - \d+)* -)\s')


def strip_marks(text: str, mode: str | None) -> str:
    text = re.sub(r'\s*\(¬\d+\)', '', text)
    if mode == 'parens':
        text = re.sub(r'\s*\(\d{1,3}\)', '', text)
    elif mode == 'loose':
        text = re.sub(r'(?<=[\u0621-\u064A]) \d{1,2}(?= [\u0621-\u064A(]|$)', '', text)
    elif mode == 'digits':
        kept: list[str] = []

        def keep(m):
            kept.append(m.group())
            return chr(0xE000 + len(kept) - 1)

        text = QURAN_REF.sub(keep, text)
        # A mark wedged between two words: «و2لكن» is one word, «أو3القعود» two.
        text = re.sub(r'(?<![ء-ي])أو\d+(?=[ء-ي])', 'أو ', text)
        text = re.sub(r'\d+', '', text)
        text = re.sub('[\uE000-\uE0FF]', lambda m: kept[ord(m.group()) - 0xE000], text)
    return text


def clean_line(text: str, book_id: str) -> str:
    # «… في PageV01P207 # ذممهما»: a paragraph mark at a page break, mid-sentence.
    text = re.sub(r'(PageV\d+P\d+|ms\d+)\s*#\s', ' ', text)
    text = MARKERS.sub('', text)
    text = re.sub(r'<[^>]*>', '', html.unescape(text))
    for old, new in FIXES.get(book_id, []):
        text = text.replace(old, new)
    text = strip_marks(text, FOOTNOTE_MARKS.get(book_id))
    text = re.sub(r'\bظظ\b', '', text)
    text = clean_text(text)
    return re.sub(r'\s+([.،,:؛؟!)\]»])', r'\1', text)


def clean_heading(raw: str, book_id: str) -> str:
    text = re.sub(r'^(AUTO|CHECK)\s+', '', MARKERS.sub('', raw).strip())
    numbered = NUMBERED.match(text.strip())
    if numbered:                 # before a book's digit marks are stripped
        return re.sub(r'\s*-\s*', ' - ', numbered.group(1))
    text = clean_line(text, book_id)
    text = text.strip('•= ').strip()
    text = re.sub(r'^\[(.*)\]$', r'\1', text)
    return re.sub(r'\d+$', '', text).strip()


def heading_in_text(text: str, book_id: str) -> str | None:
    """A line of text that is a heading: «كتاب الصلاة», «= كتاب … =», «فصل»."""
    if len(text) > 60:
        return None
    if text.startswith('=') and text.endswith('='):
        return text.strip('= ')
    bare = re.sub(r'\d+$', '', text).strip()
    if KITAB.match(bare) and not CLAUSE_END.search(bare) and '،' not in bare:
        return bare
    if bare == 'فصل' or bare in CHAPTER_LINES.get(book_id, ()):
        return bare
    if bare in FASL_LINES.get(book_id, ()):
        return 'فصل'
    if re.match(r'^باب\s\S', bare) and len(bare) <= 50 and not CLAUSE_END.search(bare) \
            and '،' not in bare:
        return bare
    return None


def parse(raw: str, book_id: str) -> list[tuple[str, list[str]]]:
    """[(heading, paragraphs)] in order; the first heading is ''."""
    body = raw.split('#META#Header#End#', 1)[-1]
    sections: list[tuple[str, list[str]]] = [('', [])]
    para = ''
    join_next = False
    editor = False
    dropping = False

    def add(text: str):
        heading = heading_in_text(text, book_id)
        if heading:
            sections.append((heading, []))
            return
        previous = sections[-1][1]
        # «: كأحدهم.» — the end of the line before, put on a line of its own.
        if previous and re.match(r'^[:.،؛]', text):
            previous[-1] += text if text[0] in ':.' else ' ' + text
            return
        # Where the digitisation cut a sentence in two, in the books whose
        # sentences end in punctuation.
        if book_id in RUN_ON_BOOKS and previous and not PARA_END.search(previous[-1]) \
                and not NEW_PART.match(text):
            previous[-1] += ' ' + text
            return
        previous.append(text)

    def close_para():
        nonlocal para, dropping
        text = clean_line(para, book_id)
        para = ''
        if text.startswith(DROP_TO_HEADING.get(book_id, ())):
            dropping = True
        if editor or dropping or not LETTER.search(text):
            return
        if text.startswith(DROP_PARAGRAPH.get(book_id, ())):
            return
        # «… ولا يجوز الصياح. باب ما يحرم لبسه»: the next heading, on the
        # last line of the paragraph before it.
        glued = re.match(r'^(.*[.:؟!])\s+(باب\s[^.:،؟!]{2,40})$', text) \
            or re.match(r'^(.*\S)\s+(فصل)$', text)
        if glued:
            add(glued.group(1))
            sections.append((glued.group(2), []))
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
            sections.append((text, []))
            continue
        if line.startswith('~~'):
            para += ' ' + line[2:].strip()
            join_next = bool(re.search(r'PageV\d+P\d+\s*$', line))
            continue
        text = line[1:].strip() if line.startswith('#') else line.strip()
        if MARKERS.fullmatch(text):
            join_next = join_next or bool(para)
            continue
        # A paragraph that follows a page break inside a sentence is the same
        # paragraph, cut by the page.
        ends_page = bool(re.search(r'PageV\d+P\d+\s*$', line))
        if join_next and para and not SENTENCE_END.search(clean_line(para, book_id)):
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
    («الإحرام: نية النسك.») names the باب and stays as its first line."""
    out = []
    pending = ''
    for raw_heading, paragraphs in sections:
        heading = clean_heading(raw_heading, book_id)
        if pending:
            if heading:
                heading = f'{pending} {heading}'
            elif paragraphs:
                first = paragraphs[0]
                if ':' in first:
                    heading = f'{pending} {first.split(":", 1)[0].strip()}'
                else:
                    heading, paragraphs = f'{pending} {first}', paragraphs[1:]
            pending = ''
        if heading in ('كتاب', 'باب'):
            if not paragraphs:
                pending = heading
                continue
            first = paragraphs[0]
            if ':' in first:
                heading = f'{heading} {first.split(":", 1)[0].strip()}'
            else:
                heading, paragraphs = f'{heading} {first}', paragraphs[1:]
        out.append((heading, paragraphs))
    return out


def same_name(a: str, b: str) -> bool:
    letters = lambda s: re.sub(r'[^ء-ي]', '', s)  # noqa: E731
    return letters(a) == letters(b)


def echoes(text: str, title: str) -> bool:
    """«كتاب الوقف» or «الوقف» under the chapter «كتاب الوقف»."""
    return same_name(text, title) or same_name('كتاب ' + text, title)


def to_chapters(book_id: str, sections) -> list[dict]:
    chapters: list[dict] = []
    title = 'مقدمة'
    entries: list[dict] = []
    parts: list[str] = []
    size = 0
    entry_id = 1
    number = ''

    def flush_entry():
        nonlocal parts, size, entry_id
        if parts:
            text = parts[0]
            for part in parts[1:]:
                text += ('\n' if LIST_ITEM.match(part) else '\n\n') + part
            entries.append({'id': entry_id, 'text_ar': text,
                            'text_en': '', 'reference': ''})
            entry_id += 1
        parts, size = [], 0

    def flush_chapter():
        nonlocal entries
        flush_entry()
        if entries:
            chapters.append({'book_id': book_id, 'chapter_id': len(chapters) + 1,
                             'title_ar': title, 'title_en': '', 'entries': entries})
        entries = []

    for heading, paragraphs in join_bare_headings(sections, book_id):
        numbered = NUMBERED.match(heading)
        # The كتاب's name written again, as heading and as text, under itself.
        echo = lambda text: not entries and not parts and echoes(text, title)  # noqa: E731
        if numbered:
            if book_id not in NUMBERS_ARE_NOISE and numbered.group(1) != '0':
                number = (number + ' - ' if number else '') + numbered.group(1)
        elif KITAB.match(heading) or heading in CHAPTER_LINES.get(book_id, ()):
            if not echo(heading):
                flush_chapter()
                title = re.sub(r'[()]', '', heading)
        elif heading and not PLACEHOLDER.match(heading) and not echo(heading):
            # A باب's opening written twice, as text and again under its
            # heading: keep the second.
            earlier = parts[1:]
            if parts and parts[0] == heading and len(paragraphs) >= len(earlier) and all(
                    later.startswith(text) for text, later in zip(earlier, paragraphs)):
                parts, size = [], 0
            flush_entry()            # a باب opens its own entry
            parts.append(heading)
            size += len(heading)
        for text in paragraphs:
            if echo(text):
                continue
            if number:
                text, number = f'{number} - {text}', ''
            if size and size + len(text) > MAX_ENTRY_CHARS:
                flush_entry()
            parts.append(text)
            size += len(text)
    flush_chapter()
    return chapters


def build(book: dict) -> dict:
    book_id = book['book_id']
    url = f"{RAW_BASE}/{book['author_dir']}/{book['book_dir']}/{book['filename']}"
    raw = fetch_raw(url)
    if not raw:
        raise SystemExit(f'download failed: {url}')
    chapters = to_chapters(book_id, parse(raw, book_id))

    book_dir = OUTPUT_DIR / book['category'] / book_id
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
        'id': book_id, 'title_ar': book['title_ar'], 'title_en': book['title_en'],
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
    for book_id in ids or STUDY_TEXTS:
        meta = build(by_id[book_id])
        print(f"{book_id:24} chapters={meta['chapter_count']:>3} "
              f"entries={meta['entry_count']:>4} bytes={meta['total_size_bytes']:>9,}")


if __name__ == '__main__':
    main(sys.argv[1:])
