import json

# Load catalog
with open('data/catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

books = catalog['books']
total_books = len(books)

# Count by language availability
arabic_books = sum(1 for b in books if b.get('title_ar'))
english_books = sum(1 for b in books if b.get('title_en'))

# Count by completeness (assuming 'featured' or checking if chapter_count > 0)
complete_books = sum(1 for b in books if b.get('chapter_count', 0) > 0)
incomplete_books = total_books - complete_books

# Get category breakdown
categories = {}
for book in books:
    cat = book.get('category', 'Unknown')
    if cat not in categories:
        categories[cat] = {'count': 0, 'books': []}
    categories[cat]['count'] += 1
    categories[cat]['books'].append(book.get('title_en', book.get('title_ar', 'Unknown')))

# Total size
total_size = sum(b.get('total_size_bytes', 0) for b in books)
total_size_mb = total_size / (1024 * 1024)

print('=' * 60)
print('ISLAMIC LIBRARY DATA - COLLECTION REPORT')
print('=' * 60)
print(f'Generated: {catalog.get("generated", "N/A")}')
print(f'Catalog Version: {catalog.get("version", "N/A")}')
print()

print('SUMMARY')
print('-' * 60)
print(f'Total Books:         {total_books}')
print(f'Arabic Books:        {arabic_books}')
print(f'English Books:       {english_books}')
print(f'Complete Books:      {complete_books}')
print(f'Incomplete Books:    {incomplete_books}')
print(f'Total Size:          {total_size_mb:.2f} MB')
print()

print('CATEGORIES')
print('-' * 60)
for cat_id, cat_data in sorted(categories.items()):
    cat_info = next((c for c in catalog.get('categories', []) if c.get('id') == cat_id), {})
    cat_name = cat_info.get('name_en', cat_id)
    print(f'{cat_name:20} {cat_data["count"]:3} books')
print()

print('DETAILED BREAKDOWN BY CATEGORY')
print('-' * 60)
for cat_id, cat_data in sorted(categories.items()):
    cat_info = next((c for c in catalog.get('categories', []) if c.get('id') == cat_id), {})
    cat_name = cat_info.get('name_en', cat_id)
    cat_name_ar = cat_info.get('name_ar', '')
    print(f'\n{cat_name} ({cat_name_ar}): {cat_data["count"]} books')
    for i, book_title in enumerate(cat_data['books'][:10], 1):
        print(f'  {i}. {book_title}')
    if len(cat_data['books']) > 10:
        print(f'  ... and {len(cat_data["books"]) - 10} more')
