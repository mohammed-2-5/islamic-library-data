# Builds the three short creed matns of Muhammad ibn Abd al-Wahhab into books.
#
#   ثلاثة الأصول وأدلتها, القواعد الأربع, نواقض الإسلام
#
# Text from ar.wikisource.org, which carries them from printed editions and is
# the only source found with the Arabic intact. The obvious alternative, the
# PDFs on islamhouse.com, cannot be used as data at all: the authorised Ibn Baz
# commentary is a scan with no text layer on any of its 80 pages, and the matn
# PDF's own text layer is scrambled — across 20,000 characters of it the word
# "الله" never once appears correctly, coming out as "هللا", and "ثلاثة" as
# "ثالثة". That damage is a ligature transposition with no reliable inverse, and
# guessing at the wording of Qur'anic verses is not something a script may do.
#
# So the printed edition was used to check rather than to extract. Pages of
# islamhouse's tahqiq edition (ar-the-three-fundamentals-r.pdf) were rendered as
# images and read: the opening — al-Bukhari's chapter heading, the three
# masa'il, the ayat of al-Muzzammil — matches this text word for word, and the
# printed table of contents on page 25 gives the same section order used for the
# chapters below:
#
#   ما يجب على كل مسلم أن يتعلمه · الحنيفية · أنواع العبادة ·
#   الأصل الثاني ومراتبه الثلاث · الأصل الثالث
#
# The verse references the source keeps in <ref> tags are folded into the text
# in brackets rather than dropped, because a proof-text without its sura is
# half a proof.

import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORY = 'aqeedah'
API = ('https://ar.wikisource.org/w/api.php?action=parse&page=%s'
       '&prop=wikitext&format=json&formatversion=2')

BISMILLAH = 'بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ'

BOOKS = [
    {
        'id': 'thalathat_al_usul',
        'page': 'الأصول الثلاثة',
        'title_ar': 'ثلاثة الأصول وأدلتها',
        'title_en': 'The Three Fundamental Principles',
        # Chapters follow the printed edition's own table of contents.
        'chapters': [
            ('ما يجب على كل مسلم أن يتعلمه', None, 'الأصل الأول'),
            ('الأصل الأول: معرفة العبد ربه', 'الأصل الأول', 'الأصل الثاني'),
            ('الأصل الثاني: معرفة دين الإسلام بالأدلة', 'الأصل الثاني', 'الأصل الثالث'),
            ('الأصل الثالث: معرفة نبيكم محمد صلى الله عليه وسلم', 'الأصل الثالث', None),
        ],
    },
    {
        'id': 'al_qawaid_al_arba',
        'page': 'القواعد الأربع',
        'title_ar': 'القواعد الأربع',
        'title_en': 'The Four Rules',
        'chapters': [
            ('المقدمة', None, 'القاعدة الأولى'),
            ('القاعدة الأولى', 'القاعدة الأولى', 'القاعدة الثانية'),
            ('القاعدة الثانية', 'القاعدة الثانية', 'القاعدة الثالثة'),
            ('القاعدة الثالثة', 'القاعدة الثالثة', 'القاعدة الرابعة'),
            ('القاعدة الرابعة', 'القاعدة الرابعة', None),
        ],
    },
    {
        'id': 'nawaqid_al_islam',
        'page': 'نواقض الإسلام',
        'title_ar': 'نواقض الإسلام',
        'title_en': "The Nullifiers of Islam",
        'chapters': [('نواقض الإسلام العشرة', None, None)],
    },
]


def fetch(page):
    request = urllib.request.Request(
        API % urllib.parse.quote(page), headers={'User-Agent': 'azkar-library'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))['parse']['wikitext']


def to_plain(text):
    """Wikitext to the reader's plain Arabic, keeping the proof-texts whole."""
    text = re.sub(r'\{\{\s*بسملة\s*\}\}', BISMILLAH, text)
    text = re.sub(r'\{\{\s*صل\s*\}\}', 'صلى الله عليه وسلم', text)
    text = re.sub(r'\{\{\s*رحمه الله[^}]*\}\}', 'رحمه الله تعالى', text)
    # {{قرآن|س=..|آ=..|the verse}} — keep the verse, in its brackets.
    text = re.sub(r'\{\{\s*قرآن\s*\|(?:[^|}]*\|)*([^|}]{15,})\}\}',
                  lambda m: '﴿%s﴾' % m.group(1).strip(), text)
    # Templates nest, so one pass leaves the outer one behind: strip until the
    # text stops changing rather than assuming a single level.
    while True:
        stripped = re.sub(r'\{\{[^{}]*\}\}', ' ', text)
        if stripped == text:
            break
        text = stripped
    text = re.sub(r'<ref[^>]*>\s*(.*?)\s*</ref>',
                  lambda m: ' [%s]' % re.sub(r'\s+', ' ', m.group(1)), text,
                  flags=re.S)
    text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('__لاتحريرقسم__', '')
    # Wiki bold and italic markers. Left in, they show up as stray quotes and
    # can be split off into an entry of their own.
    text = re.sub(r"'{2,}", '', text)
    text = re.sub(r'^=+\s*(.+?)\s*=+\s*$', r'\1', text, flags=re.M)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def slice_between(text, start, end):
    first = 0 if start is None else text.index(start)
    last = len(text) if end is None else text.index(end, first + 1)
    return text[first:last]


def entries(text):
    rows = []
    for block in re.split(r'\n\s*\n', text):
        block = block.strip()
        if len(block) > 1:
            rows.append({'id': len(rows) + 1, 'text_ar': block})
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    catalog_path = os.path.join(ROOT, 'data', 'catalog.json')
    catalog = json.load(io.open(catalog_path, encoding='utf-8'))
    by_id = {book['id']: book for book in catalog['books']}

    for spec in BOOKS:
        plain = to_plain(fetch(spec['page']))
        if 'الله' not in plain or 'هللا' in plain:
            sys.exit('%s: the Arabic did not survive the fetch' % spec['id'])

        folder = os.path.join(ROOT, 'data', 'books', CATEGORY, spec['id'])
        os.makedirs(os.path.join(folder, 'chapters'), exist_ok=True)

        total_entries = 0
        size = 0
        for number, (title, start, end) in enumerate(spec['chapters'], 1):
            rows = entries(slice_between(plain, start, end))
            if not rows:
                sys.exit('%s: chapter %d came out empty' % (spec['id'], number))
            total_entries += len(rows)
            payload = {
                'book_id': spec['id'],
                'chapter_id': number,
                'title_ar': title,
                'title_en': '',
                'entries': rows,
            }
            path = os.path.join(folder, 'chapters', '%d.json' % number)
            with io.open(path, 'w', encoding='utf-8', newline='\n') as out:
                json.dump(payload, out, ensure_ascii=False, indent=2)
                out.write('\n')
            size += os.path.getsize(path)

        metadata = {
            'id': spec['id'],
            'title_ar': spec['title_ar'],
            'title_en': spec['title_en'],
            'author_ar': 'الإمام محمد بن عبد الوهاب',
            'author_en': 'Muhammad ibn Abd al-Wahhab',
            'category': CATEGORY,
            'chapter_count': len(spec['chapters']),
            'entry_count': total_entries,
            'total_size_bytes': size,
            'source': 'wikisource',
            'source_url': 'https://ar.wikisource.org/wiki/' + spec['page'],
        }
        with io.open(os.path.join(folder, 'metadata.json'), 'w',
                     encoding='utf-8', newline='\n') as out:
            json.dump(metadata, out, ensure_ascii=False, indent=2)
            out.write('\n')

        listing = dict(metadata)
        listing.pop('entry_count', None)
        listing.pop('source_url', None)
        listing['featured'] = False
        if spec['id'] in by_id:
            by_id[spec['id']].update(listing)
        else:
            catalog['books'].append(listing)
        print('  %-20s %d chapters, %d entries, %d bytes'
              % (spec['id'], len(spec['chapters']), total_entries, size))

    with io.open(catalog_path, 'w', encoding='utf-8', newline='\n') as out:
        json.dump(catalog, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print('\ncatalog now lists %d books' % len(catalog['books']))


if __name__ == '__main__':
    main()
