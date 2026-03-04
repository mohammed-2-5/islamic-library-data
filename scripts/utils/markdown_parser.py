"""Parser for OpenITI mARkdown format.

OpenITI mARkdown is a custom markup format used by the Open Islamicate Texts Initiative.

Key syntax:
- Line 1: ######OpenITI# (magic value)
- #META# ... : metadata lines
- #META#Header#End# : end of metadata
- ### | : Level 1 header (chapter)
- ### || : Level 2 header (section)
- ### ||| : Level 3 header (subsection)
- # : Paragraph start
- ~~ : Line continuation (paragraph wrapping)
- PageV##P### : Page markers (e.g., PageV01P005)
- Milestone300 : 300-word unit markers (ignored)
- %~% : Poetry hemistich divider
- ### $ : Biography/dictionary entries
- ### @ : Historical events
"""

import re
from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    """A section (chapter) extracted from an OpenITI text."""
    level: int  # Header level (1-5)
    title: str  # Section title
    content: list[str] = field(default_factory=list)  # List of paragraphs


@dataclass
class ParsedText:
    """Complete parsed OpenITI text."""
    metadata: dict[str, str] = field(default_factory=dict)
    sections: list[ParsedSection] = field(default_factory=list)
    raw_paragraphs: list[str] = field(default_factory=list)


# Regex patterns
_META_LINE = re.compile(r'^#META#\s*(.+?)$')
_META_END = re.compile(r'^#META#Header#End#')
_MAGIC = re.compile(r'^######OpenITI#')
_HEADER = re.compile(r'^###\s+(\|+)\s*(.*)')
_PARAGRAPH = re.compile(r'^#\s+(.*)')
_CONTINUATION = re.compile(r'^~~\s*(.*)')
_PAGE_MARKER = re.compile(r'PageV(\d+)P(\d+)')
_MILESTONE = re.compile(r'^ms\d+|^Milestone\d+')
_EDITORIAL = re.compile(r'^###\s+\|EDITOR\|')
_BIO_ENTRY = re.compile(r'^###\s+\$+\s*(.*)')
_EVENT_ENTRY = re.compile(r'^###\s+@\s*(.*)')
_SEMANTIC_TAG = re.compile(r'@[A-Z]{2,3}##\d*')
_POETRY_DIVIDER = '%~%'


def _clean_line(line: str) -> str:
    """Remove OpenITI-specific markers from a line."""
    # Remove page markers
    line = _PAGE_MARKER.sub('', line)
    # Remove milestone markers
    line = _MILESTONE.sub('', line)
    # Remove semantic tags
    line = _SEMANTIC_TAG.sub('', line)
    # Clean up extra whitespace
    line = re.sub(r'\s+', ' ', line).strip()
    return line


def _extract_metadata(lines: list[str]) -> tuple[dict[str, str], int]:
    """Extract metadata from the beginning of the file.

    Returns (metadata_dict, line_index_after_metadata).
    """
    metadata: dict[str, str] = {}
    i = 0

    for i, line in enumerate(lines):
        line = line.strip()

        # Skip magic value
        if _MAGIC.match(line):
            continue

        # Check for metadata end
        if _META_END.match(line):
            return metadata, i + 1

        # Parse metadata line
        m = _META_LINE.match(line)
        if m:
            content = m.group(1).strip()
            if '::' in content:
                key, _, value = content.partition('::')
                metadata[key.strip()] = value.strip()
            elif ':' in content:
                key, _, value = content.partition(':')
                metadata[key.strip()] = value.strip()
        elif not line or line.startswith('#'):
            # If we hit a non-meta line before #META#Header#End#, stop
            if not line.startswith('#META'):
                break

    return metadata, i


def parse_openiti(text: str) -> ParsedText:
    """Parse an OpenITI mARkdown text into structured sections.

    Args:
        text: The raw mARkdown text content.

    Returns:
        ParsedText with metadata and sections.
    """
    lines = text.split('\n')
    result = ParsedText()

    # Extract metadata
    result.metadata, start_idx = _extract_metadata(lines)

    # Parse content
    current_section: ParsedSection | None = None
    current_paragraph: list[str] = []

    def flush_paragraph():
        """Save current paragraph to current section or raw paragraphs."""
        if current_paragraph:
            para_text = _clean_line(' '.join(current_paragraph))
            if para_text:
                if current_section is not None:
                    current_section.content.append(para_text)
                else:
                    result.raw_paragraphs.append(para_text)
            current_paragraph.clear()

    for i in range(start_idx, len(lines)):
        line = lines[i].rstrip()

        # Skip empty lines
        if not line:
            continue

        # Skip milestone markers
        if _MILESTONE.match(line.strip()):
            continue

        # Skip editorial sections
        if _EDITORIAL.match(line):
            continue

        # Check for headers (### | , ### || , etc.)
        m = _HEADER.match(line)
        if m:
            flush_paragraph()
            level = len(m.group(1))  # Count pipe symbols
            title = _clean_line(m.group(2))

            current_section = ParsedSection(level=level, title=title)
            result.sections.append(current_section)
            continue

        # Check for biography/dictionary entries (### $)
        m = _BIO_ENTRY.match(line)
        if m:
            flush_paragraph()
            title = _clean_line(m.group(1))
            current_section = ParsedSection(level=3, title=title)
            result.sections.append(current_section)
            continue

        # Check for historical events (### @)
        m = _EVENT_ENTRY.match(line)
        if m:
            flush_paragraph()
            title = _clean_line(m.group(1))
            current_section = ParsedSection(level=3, title=title)
            result.sections.append(current_section)
            continue

        # Check for paragraph start
        m = _PARAGRAPH.match(line)
        if m:
            flush_paragraph()
            para_text = m.group(1)
            # Handle poetry
            if _POETRY_DIVIDER in para_text:
                para_text = para_text.replace(_POETRY_DIVIDER, ' *** ')
            current_paragraph.append(para_text)
            continue

        # Check for line continuation
        m = _CONTINUATION.match(line)
        if m:
            current_paragraph.append(m.group(1))
            continue

        # Other lines - treat as content if we have a section
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            current_paragraph.append(stripped)

    # Flush last paragraph
    flush_paragraph()

    # If no sections found, create one from raw paragraphs
    if not result.sections and result.raw_paragraphs:
        section = ParsedSection(
            level=1,
            title=result.metadata.get("BookTitle", ""),
            content=result.raw_paragraphs,
        )
        result.sections = [section]
        result.raw_paragraphs = []

    return result


def get_book_title(metadata: dict[str, str]) -> str:
    """Extract book title from metadata."""
    for key in ("BookTitle", "Title", "TitleAr", "title"):
        if key in metadata and metadata[key]:
            return metadata[key]
    return ""


def get_author_name(metadata: dict[str, str]) -> str:
    """Extract author name from metadata."""
    for key in ("AuthorName", "Author", "AuthorAr", "author"):
        if key in metadata and metadata[key]:
            return metadata[key]
    return ""


def get_genre(metadata: dict[str, str]) -> str:
    """Extract genre/category from metadata."""
    for key in ("Genre", "genre", "Category", "category"):
        if key in metadata and metadata[key]:
            return metadata[key]
    return ""
