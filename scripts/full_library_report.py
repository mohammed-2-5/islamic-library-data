import json
import os
from pathlib import Path

# Category mapping
category_names = {
    'aqeedah': {'name_en': 'Aqeedah (Creed)', 'name_ar': 'العقيدة'},
    'fiqh': {'name_en': 'Fiqh (Jurisprudence)', 'name_ar': 'الفقه'},
    'hadith': {'name_en': 'Hadith', 'name_ar': 'الحديث'},
    'seerah': {'name_en': 'Seerah (Biography)', 'name_ar': 'السيرة'},
    'tafseer': {'name_en': 'Tafseer (Exegesis)', 'name_ar': 'التفسير'},
    'tazkiyah': {'name_en': 'Tazkiyah (Purification)', 'name_ar': 'التزكية'}
}

books_dir = Path('data/books')
all_books = []
category_stats = {}

# Scan each category directory
for category_dir in books_dir.iterdir():
    if not category_dir.is_dir():
        continue
    
    category_name = category_dir.name
    category_stats[category_name] = {
        'books': [],
        'total_chapters': 0,
        'total_size': 0,
        'arabic_books': 0,
        'english_books': 0,
        'complete_books': 0
    }
    
    # Scan each book in the category
    for book_dir in category_dir.iterdir():
        if not book_dir.is_dir():
            continue
        
        book_id = book_dir.name
        
        # Look for metadata or info file
        metadata_file = book_dir / 'metadata.json'
        info_file = book_dir / 'info.json'
        
        book_info = {
            'id': book_id,
            'category': category_name,
            'has_arabic': False,
            'has_english': False,
            'chapter_count': 0,
            'size_bytes': 0
        }
        
        # Count JSON files (chapters)
        json_files = list(book_dir.glob('**/*.json'))
        chapter_files = [f for f in json_files if f.name not in ['metadata.json', 'info.json']]
        book_info['chapter_count'] = len(chapter_files)
        
        # Check for language by looking at file names or content
        has_ar = any('_ar' in f.stem or 'arabic' in f.stem.lower() for f in chapter_files)
        has_en = any('_en' in f.stem or 'english' in f.stem.lower() for f in chapter_files)
        
        # If no language suffix, check if there are different language versions
        if not has_ar and not has_en:
            # Assume bilingual if no specific language marker
            book_info['has_arabic'] = True
            book_info['has_english'] = True
        else:
            book_info['has_arabic'] = has_ar
            book_info['has_english'] = has_en or not has_ar
        
        # Calculate total size
        for f in json_files:
            if f.exists():
                book_info['size_bytes'] += f.stat().st_size
        
        # Update category stats
        category_stats[category_name]['books'].append(book_info)
        category_stats[category_name]['total_chapters'] += book_info['chapter_count']
        category_stats[category_name]['total_size'] += book_info['size_bytes']
        if book_info['has_arabic']:
            category_stats[category_name]['arabic_books'] += 1
        if book_info['has_english']:
            category_stats[category_name]['english_books'] += 1
        if book_info['chapter_count'] > 0:
            category_stats[category_name]['complete_books'] += 1
        
        all_books.append(book_info)

# Calculate totals
total_books = len(all_books)
total_arabic = sum(1 for b in all_books if b['has_arabic'])
total_english = sum(1 for b in all_books if b['has_english'])
total_complete = sum(1 for b in all_books if b['chapter_count'] > 0)
total_incomplete = total_books - total_complete
total_chapters = sum(b['chapter_count'] for b in all_books)
total_size = sum(b['size_bytes'] for b in all_books)
total_size_mb = total_size / (1024 * 1024)

# Print Report
print('=' * 70)
print('ISLAMIC LIBRARY DATA - COMPREHENSIVE COLLECTION REPORT')
print('=' * 70)
print(f'Report Date: 2026-03-04')
print()

print('OVERALL SUMMARY')
print('-' * 70)
print(f'Total Books:              {total_books}')
print(f'Total Chapters/Files:     {total_chapters:,}')
print(f'Arabic Books:             {total_arabic} ({total_arabic/total_books*100:.1f}%)')
print(f'English Books:            {total_english} ({total_english/total_books*100:.1f}%)')
print(f'Complete Books:           {total_complete} ({total_complete/total_books*100:.1f}%)')
print(f'Incomplete Books:         {total_incomplete} ({total_incomplete/total_books*100:.1f}%)')
print(f'Total Collection Size:    {total_size_mb:.2f} MB')
print()

print('CATEGORY BREAKDOWN')
print('-' * 70)
print(f'{"Category":<30} {"Books":>6} {"Chapters":>10} {"Size (MB)":>12}')
print('-' * 70)
for cat_id in sorted(category_stats.keys()):
    stats = category_stats[cat_id]
    cat_info = category_names.get(cat_id, {'name_en': cat_id, 'name_ar': ''})
    cat_display = f"{cat_info['name_en']} ({cat_info['name_ar']})"
    size_mb = stats['total_size'] / (1024 * 1024)
    print(f'{cat_display:<30} {len(stats["books"]):>6} {stats["total_chapters"]:>10,} {size_mb:>12.2f}')
print()

print('DETAILED CATEGORY ANALYSIS')
print('=' * 70)
for cat_id in sorted(category_stats.keys()):
    stats = category_stats[cat_id]
    cat_info = category_names.get(cat_id, {'name_en': cat_id, 'name_ar': ''})
    
    print(f'\n{cat_info["name_en"]} ({cat_info["name_ar"]})')
    print('-' * 70)
    print(f'Books: {len(stats["books"])} | Chapters: {stats["total_chapters"]:,} | Size: {stats["total_size"]/(1024*1024):.2f} MB')
    print(f'Arabic: {stats["arabic_books"]} | English: {stats["english_books"]} | Complete: {stats["complete_books"]}')
    print('\nBooks in this category:')
    
    for book in sorted(stats['books'], key=lambda x: x['id']):
        lang_status = []
        if book['has_arabic']:
            lang_status.append('AR')
        if book['has_english']:
            lang_status.append('EN')
        lang_str = '+'.join(lang_status)
        
        status = '✓' if book['chapter_count'] > 0 else '✗'
        size_mb = book['size_bytes'] / (1024 * 1024)
        
        print(f'  {status} {book["id"]:<30} [{lang_str:5}] {book["chapter_count"]:4} chapters, {size_mb:7.2f} MB')

print('\n' + '=' * 70)
print('LEGEND: ✓ = Complete | ✗ = Incomplete | AR = Arabic | EN = English')
print('=' * 70)
