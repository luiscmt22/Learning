#!/usr/bin/env python3
"""Pre-extract text from all in-scope sources into _Curated/_extracted/ so
analyst agents can ingest them via the Read tool. Also writes _Curated/_manifest.json."""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling import (organize_learning)

from organize_learning import (
    discover_files, extract_md_text, extract_docx_md, extract_pdf_pages,
    extract_html_visible_text, BASE, categorise,
)

OUT = BASE / '_Curated'
EXTRACTS = OUT / '_extracted'
EXTRACTS.mkdir(parents=True, exist_ok=True)

files = discover_files()
print(f'Found {len(files)} files')

manifest = []
for src in files:
    rel = src.relative_to(BASE).as_posix()
    ext = src.suffix.lower()
    safe_name = rel.replace('/', '__').replace('\\', '__')
    text_path = None
    text = ''

    if ext == '.md':
        text = extract_md_text(src)
    elif ext == '.docx':
        text = extract_docx_md(src)
    elif ext == '.pdf':
        pages = extract_pdf_pages(src)
        text = '\n\n--- PAGE BREAK ---\n\n'.join(pages) if pages else ''
    elif ext in ('.html', '.htm'):
        raw = src.read_text(encoding='utf-8', errors='replace')
        stripped = extract_html_visible_text(raw)
        # collapse whitespace but keep newlines for readability
        lines = [' '.join(l.split()) for l in stripped.splitlines()]
        text = '\n'.join(l for l in lines if l)

    has_text = bool(text and text.strip())
    if has_text:
        text_path = EXTRACTS / (safe_name + '.txt')
        text_path.write_text(text, encoding='utf-8')

    manifest.append({
        'src_rel': rel,
        'src_abs': str(src),
        'src_ext': ext,
        'has_text': has_text,
        'text_abs': str(text_path) if text_path else None,
        'word_count': len(text.split()) if text else 0,
        'category_legacy': categorise(rel),
    })

(OUT / '_manifest.json').write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8',
)
print(f'Extracted {sum(1 for m in manifest if m["has_text"])} files with text')
print(f'Empty (image PDFs / errors): {sum(1 for m in manifest if not m["has_text"])}')
print(f'Manifest written: {OUT / "_manifest.json"}')
