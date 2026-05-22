#!/usr/bin/env python3
"""
organize_learning.py
====================
Builds a rich, polished `_Organized/` tree for the Learning content.

Pipeline
--------
1. Discover in-scope files (Education/, Identity/, JScript/, Microsoft_Fullstack/
   + 4 loose root files).
2. For each file:
     - Extract raw text (md / docx / pdf / html → plain words).
     - Compute byte MD5, normalised-content MD5, and 5-word shingle set.
     - Extract title, headings (TOC), word count, reading time, snippet.
3. Cluster duplicates in 4 dimensions:
     - byte-identical (same file MD5)
     - content-identical (same MD5 of normalised text — catches DOCX↔PDF
       exports of the same source)
     - near-duplicate (Jaccard ≥ 0.80 on shingles, but not in content cluster)
     - same name-stem (legacy filename heuristic — kept for completeness)
4. Render every source file as a rich HTML page:
     - Sticky topbar with breadcrumbs and download link
     - Sticky TOC sidebar (auto-extracted headings)
     - Hero section with title, format pill, word count, reading time, source
     - Banner(s) for any duplicate clusters the file is in
     - Body with syntax highlighting, callouts, copy-code buttons
     - "More in this category" related-docs grid
5. Render `_Category.html` per category with description, stats, and a doc
   card grid (with live filter input).
6. Render polished `00-Index.html` master index with hero, summary stats,
   live search, and category cards.
7. Write `_Duplicates.md` and `_Manifest.json` reports.

Idempotent: re-running wipes `_Organized/` contents and rebuilds from sources.
Source files are NEVER modified — everything is copied + rendered into
`_Organized/`.

Reuses `build_webbook.md_to_html` and `build_webbook.highlight_code` for
markdown rendering and C# syntax highlighting.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import build_webbook as bw

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

BASE = Path(r'C:\Users\User\Desktop\AGILE\Learning')
OUT = BASE / '_Organized'

IN_SCOPE_DIRS: list[tuple[str, bool]] = [
    ('Education', True),
    ('Identity', True),
    ('JScript', True),
    ('Microsoft_Fullstack', True),
]

LOOSE_ROOT_FILES = [
    'Actions&Events.docx',
    'Adding-New-Category.html',
    'CookieHandlingBlazorServerApplications.docx',
    '📘 Loadings_Includes_virtuals.docx',
]

CONTENT_EXTS = {'.md', '.html', '.htm', '.docx', '.pdf'}

# Categorization rules (regex on rel path → category folder). First match wins.
CATEGORY_RULES: list[tuple[str, str]] = [
    (r'Education/FactoryFloor/',                    '16-Domain-Examples-FactoryFloor'),
    (r'Education/Stock/',                           '17-Domain-Examples-Stock'),
    (r'Education/Educational_ML/',                  '18-Machine-Learning'),
    (r'Education/ForDummies/',                      '19-For-Dummies'),
    (r'Education/Basics/',                          '01-Basics'),
    (r'Education/SQL/',                             '07-Database-EF-SQL'),
    (r'Loadings_Includes_virtuals',                 '07-Database-EF-SQL'),
    (r'\b(EF[-_]?Core|Audit-Trail|Migration|Soft-Delete|Base-Entity)', '07-Database-EF-SQL'),
    (r'Database-Reset',                             '07-Database-EF-SQL'),
    (r'Migration-And-Seeding',                      '07-Database-EF-SQL'),
    (r'Education/Git/',                             '20-Git'),
    (r'^Identity/',                                 '06-Auth-and-Identity'),
    (r'(Role-Based-Authorization|Authorization-Architecture|Password-Security|BCrypt|login\.html)', '06-Auth-and-Identity'),
    (r'^JScript/',                                  '12-JavaScript'),
    (r'Blazor-JS-Interop',                          '12-JavaScript'),
    (r'^Microsoft_Fullstack/.*Test',                '13-Testing'),
    (r'Unit[-_]?Test',                              '13-Testing'),
    (r'^Microsoft_Fullstack/ASync',                 '08-Concurrency-and-Async'),
    (r'(SemaphoreSlim|ConcurrentDictionary|Background-Services|IMemoryCache|Caching|Smart-Scheduling)', '08-Concurrency-and-Async'),
    (r'(SignalR|Notification|Chat-System|Realtime|Real-Time)', '09-Realtime-SignalR'),
    (r'(Cookie.*Blazor|Blazor)',                    '03-Blazor'),
    (r'Actions&Events',                             '03-Blazor'),
    (r'Adding-New-Category',                        '03-Blazor'),
    (r'(Clean-Architecture|Adapter-Pattern|Strategy-Pattern|Export-Service-Strategy|Validator-Pipeline|Chain-Of-Responsibility)', '02-Architecture-and-Patterns'),
    (r'(Schedule-Conflict|Schedule-Grid|Generic-Schedule)', '05-Scheduling'),
    (r'(Geofencing|Haversine|IMAP|SMTP|Email-Integration|Facial-Recognition)', '10-Integrations'),
    (r'(Web-Fundamentals|tutorial\.html)',          '11-Web-Fundamentals'),
    (r'(CSharp|Flags-Enum|Expression-Trees|Named-Tuples|delegates-lambdas|generics-builders)', '04-CSharp-Language'),
    (r'(Polite-Code|Polite|Code-Style|Clean-Code)', '14-Code-Quality'),
    (r'Feature-Flags',                              '15-Feature-Management'),
    (r'Education/README\.md',                       '00-Meta'),
]

DEFAULT_CATEGORY = '99-Uncategorised'

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    '00-Meta':                          'Project metadata and overview documents.',
    '01-Basics':                        'Foundational guides for Blazor, C# and core .NET concepts. Start here if you are new to the stack.',
    '02-Architecture-and-Patterns':     'Software architecture, design patterns and high-level system organisation — clean architecture, adapter, strategy, validator pipelines.',
    '03-Blazor':                        'Blazor Server features: components, lifecycle, JS interop, cookies and authentication-aware UI.',
    '04-CSharp-Language':               'C# language features: flag enums, expression trees, named tuples, delegates, generics and builder patterns.',
    '05-Scheduling':                    'Schedule conflict detection and generic schedule grids for time-based domain logic.',
    '06-Auth-and-Identity':             'Role-based authorization, password hashing and identity architecture.',
    '07-Database-EF-SQL':               'Entity Framework Core, migrations, audit trails, soft deletes and SQL schema design.',
    '08-Concurrency-and-Async':         'Async patterns, semaphores, concurrent collections, background services and caching strategies.',
    '09-Realtime-SignalR':              'SignalR for real-time communication: chat, notifications and recipient resolution pipelines.',
    '10-Integrations':                  'External integrations: facial recognition, geofencing, IMAP/SMTP email.',
    '11-Web-Fundamentals':              'Web protocol basics — HTTP, browser plumbing, request lifecycles.',
    '12-JavaScript':                    'JavaScript techniques, jQuery, Select2, AG Grid and JS interop from Blazor.',
    '13-Testing':                       'Unit testing strategies and patterns for .NET.',
    '14-Code-Quality':                  'Code style, polite-code principles and refactoring guidance.',
    '15-Feature-Management':            'Feature flag hierarchies and runtime feature toggling.',
    '16-Domain-Examples-FactoryFloor':  'End-to-end walkthroughs of a Factory Floor production system. ENG and PT versions.',
    '17-Domain-Examples-Stock':         'End-to-end walkthroughs of a Stock service system. ENG and PT versions.',
    '18-Machine-Learning':              'Educational ML: backpropagation, neural networks, sigmoid derivatives, training flows.',
    '19-For-Dummies':                   'Simplified ELI5-style versions of key topics for quick refreshers.',
    '20-Git':                           'Git operations, repo separation and branching strategies.',
    '99-Uncategorised':                 'Files that did not match any category rule.',
}


def categorise(rel_path: str) -> str:
    p = rel_path.replace('\\', '/')
    for pattern, cat in CATEGORY_RULES:
        if re.search(pattern, p, re.IGNORECASE):
            return cat
    return DEFAULT_CATEGORY


# ════════════════════════════════════════════════════════════════════════════
# DISCOVERY
# ════════════════════════════════════════════════════════════════════════════

def discover_files() -> list[Path]:
    found: list[Path] = []
    for rel, recursive in IN_SCOPE_DIRS:
        root = BASE / rel
        if not root.exists():
            continue
        for p in (root.rglob('*') if recursive else root.iterdir()):
            if p.is_file() and p.suffix.lower() in CONTENT_EXTS:
                found.append(p)
    for fname in LOOSE_ROOT_FILES:
        p = BASE / fname
        if p.exists():
            found.append(p)
    found.sort(key=lambda x: str(x).lower())
    return found


# ════════════════════════════════════════════════════════════════════════════
# HASHING + NAMING HELPERS
# ════════════════════════════════════════════════════════════════════════════

def md5_bytes(path: Path) -> str:
    h = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"|?*]', '_', name)


def normalize_stem(stem: str) -> str:
    s = stem.lower()
    s = re.sub(r'\s*\(\d+\)\s*$', '', s)
    s = re.sub(r'[\s_\-]+', '', s)
    s = re.sub(r'editable$', '', s)
    return s


# ════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION (per format)
# ════════════════════════════════════════════════════════════════════════════
# .md      → raw markdown text
# .docx    → markdown reconstruction via python-docx (handles document.xml +
#            document2.xml; ignores body-level <w:sdt> TOC junk)
# .pdf     → list of per-page text via pdftotext -layout
# .html    → for fingerprinting we strip tags; for rendering we either copy
#            verbatim (full doc) or wrap (fragment)

def extract_md_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def _docx_para_md(p_el, part) -> str:
    from docx.text.paragraph import Paragraph
    para = Paragraph(p_el, part)
    text = (para.text or '').strip()
    if not text:
        return ''
    style_name = ''
    try:
        style_name = para.style.name or ''
    except Exception:
        pass
    m = re.match(r'Heading\s*(\d)', style_name)
    if m:
        lvl = min(int(m.group(1)), 6)
        return '#' * lvl + ' ' + text
    if style_name == 'Title':
        return '# ' + text
    return text


def _docx_table_md(tbl_el, part) -> str:
    from docx.table import Table
    tbl = Table(tbl_el, part)
    rows: list[list[str]] = []
    for row in tbl.rows:
        cells = [(c.text or '').strip() for c in row.cells]
        if cells:
            rows.append(cells)
    if not rows:
        return ''
    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append('')
    lines: list[str] = []
    for i, row in enumerate(rows):
        safe = [c.replace('|', '\\|').replace('\n', ' ') for c in row]
        lines.append('| ' + ' | '.join(safe) + ' |')
        if i == 0:
            lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
    return '\n'.join(lines)


def extract_docx_md(path: Path) -> str:
    try:
        import docx as docx_lib
    except ImportError:
        return ''
    try:
        doc = docx_lib.Document(str(path))
    except Exception as e:
        return f'[Error opening DOCX: {e}]'
    parts: list[str] = []
    for child in doc.element.body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'p':
            md = _docx_para_md(child, doc.part)
            if md:
                parts.append(md)
        elif tag == 'tbl':
            md = _docx_table_md(child, doc.part)
            if md:
                parts.append(md)
    return '\n\n'.join(parts)


def extract_pdf_pages(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', '-enc', 'UTF-8', str(path), '-'],
            capture_output=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    text = result.stdout.decode('utf-8', errors='replace')
    if not text.strip():
        return []
    return [p for p in text.split('\f') if p.strip()]


def extract_html_visible_text(raw: str) -> str:
    raw = re.sub(r'<script[\s\S]*?</script>', ' ', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<style[\s\S]*?</style>', ' ', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<[^>]+>', ' ', raw)
    return html_module.unescape(raw)


# ════════════════════════════════════════════════════════════════════════════
# CONTENT NORMALISATION + SIMILARITY
# ════════════════════════════════════════════════════════════════════════════

_NORM_KEEP = re.compile(r'[a-z0-9]+')


def normalize_for_compare(text: str) -> str:
    """Strip code/URLs, lowercase, keep only alphanumeric tokens. Used to
    compare DOCX vs PDF vs MD on equal footing."""
    if not text:
        return ''
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`\n]+`', ' ', text)
    text = re.sub(r'https?://\S+', ' ', text)
    text = text.lower()
    return ' '.join(_NORM_KEEP.findall(text))


def content_md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def shingles(text: str, k: int = 5) -> set[str]:
    words = text.split()
    if len(words) < k:
        return {' '.join(words)} if words else set()
    return {' '.join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ════════════════════════════════════════════════════════════════════════════
# TITLE + HEADING + SNIPPET EXTRACTION
# ════════════════════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def prettify_filename(stem: str) -> str:
    """Turn 'CSharp_Generics_Guide' / '01-Understanding-Clean-Architecture'
    into a human-readable title."""
    s = re.sub(r'^\d+[-_]+', '', stem)        # strip leading "01-"
    s = re.sub(r'[-_]+', ' ', s)
    return s.strip()


def extract_title_from_md(md_text: str, fallback: str) -> str:
    in_code = False
    first_line = None
    for line in md_text.split('\n')[:60]:
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^#{1,3}\s+(.+?)\s*#*\s*$', line)
        if m:
            t = m.group(1).strip()
            if t and not _BAD_TITLE.match(t):
                return t[:140]
        if first_line is None and line.strip():
            first_line = line.strip()
    if first_line:
        return first_line[:140]
    return prettify_filename(fallback)


_BAD_TITLE = re.compile(r'^[\s\W_]+$')


def extract_title_from_html(raw: str, fallback: str) -> str:
    m = re.search(r'<title[^>]*>(.*?)</title>', raw, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r'\s+', ' ', html_module.unescape(m.group(1))).strip()
        if t:
            return t[:140]
    m = re.search(r'<h1[^>]*>(.*?)</h1>', raw, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1))
        t = re.sub(r'\s+', ' ', html_module.unescape(t)).strip()
        if t:
            return t[:140]
    return prettify_filename(fallback)


def extract_md_headings(md_text: str) -> list[tuple[int, str, str]]:
    headings: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    in_code = False
    for line in md_text.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.+?)(?:\s*\{#[\w-]+\})?\s*$', line)
        if m:
            lvl = len(m.group(1))
            text = m.group(2).strip().rstrip('#').strip()
            if not text:
                continue
            base = slugify(text) or f'h{lvl}-{len(headings) + 1}'
            n = seen.get(base, 0) + 1
            seen[base] = n
            anchor = base if n == 1 else f'{base}-{n}'
            headings.append((lvl, text, anchor))
    return headings


def extract_html_headings(raw: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    pattern = re.compile(r'<h([1-3])\b([^>]*)>(.*?)</h\1>', re.IGNORECASE | re.DOTALL)
    for m in pattern.finditer(raw):
        lvl = int(m.group(1))
        attrs = m.group(2)
        inner = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        inner = html_module.unescape(inner)
        if not inner:
            continue
        id_m = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
        if id_m:
            anchor = id_m.group(1)
        else:
            base = slugify(inner) or f'h{lvl}-{len(out) + 1}'
            n = seen.get(base, 0) + 1
            seen[base] = n
            anchor = base if n == 1 else f'{base}-{n}'
        out.append((lvl, inner, anchor))
    return out


def make_snippet(text: str, max_chars: int = 240) -> str:
    if not text:
        return ''
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    cleaned = re.sub(r'`[^`]+`', '', cleaned)
    cleaned = re.sub(r'^#+\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^[\*\-+]\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(' ', 1)[0] + '…'
    return cleaned


# ════════════════════════════════════════════════════════════════════════════
# DUPLICATE CLUSTERING
# ════════════════════════════════════════════════════════════════════════════

def build_clusters(records, key) -> dict:
    clusters = defaultdict(list)
    for r in records:
        v = r.get(key)
        if v:
            clusters[v].append(r['src_rel'])
    return {k: sorted(set(v)) for k, v in clusters.items() if len(set(v)) >= 2}


def build_near_clusters(records, threshold: float = 0.80) -> list[list[str]]:
    """Greedy clustering by Jaccard ≥ threshold. Skips records that are
    already content-identical to one another (those go in the content
    cluster, not the near cluster). O(n²) — fine for ~100 files."""
    clusters: list[list[str]] = []
    assigned: set[str] = set()
    n = len(records)
    for i in range(n):
        ri = records[i]
        if ri['src_rel'] in assigned or not ri['shingles']:
            continue
        cluster = [ri['src_rel']]
        for j in range(i + 1, n):
            rj = records[j]
            if rj['src_rel'] in assigned or not rj['shingles']:
                continue
            if ri['h_content'] and ri['h_content'] == rj['h_content']:
                continue  # belongs in content cluster, not near
            sim = jaccard(ri['shingles'], rj['shingles'])
            if sim >= threshold:
                cluster.append(rj['src_rel'])
        if len(cluster) >= 2:
            clusters.append(cluster)
            for x in cluster:
                assigned.add(x)
    return clusters


# ════════════════════════════════════════════════════════════════════════════
# RICH HTML TEMPLATE — CSS + JS
# ════════════════════════════════════════════════════════════════════════════

RICH_CSS = r'''
:root {
  --bg: #0a0e1a;
  --bg-1: #0f1525;
  --bg-2: #131b30;
  --bg-3: #1a2238;
  --border: #1f2940;
  --border-2: #2a3551;
  --text: #e8edf5;
  --text-dim: #93a3bf;
  --text-mut: #5f6b86;
  --accent: #6aa6ff;
  --accent-2: #b86aff;
  --ok: #4ade80;
  --warn: #fbbf24;
  --bad: #f87171;
  --info: #38bdf8;
  --code-bg: #0c1322;
  --code-border: #1c263c;
  --shadow: 0 8px 32px rgba(0,0,0,0.5);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font: 16px/1.7 -apple-system, "Inter", "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ─── Top bar ────────────────────────────────────────────────────── */
.topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(10,14,26,0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  padding: 12px 28px;
  display: flex; align-items: center; gap: 16px;
}
.topbar .crumbs {
  flex: 1; font-size: 13px; color: var(--text-dim);
  display: flex; align-items: center; gap: 8px; min-width: 0; overflow: hidden;
}
.topbar .crumbs span.sep { color: var(--text-mut); }
.topbar .crumbs .current {
  color: var(--text); font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.topbar .crumbs a { color: var(--text-dim); text-decoration: none; }
.topbar .crumbs a:hover { color: var(--accent); }
.topbar .actions { display: flex; gap: 6px; flex-shrink: 0; }
.topbar .action {
  font-size: 13px; padding: 6px 14px; border-radius: 7px;
  color: var(--text-dim); text-decoration: none;
  border: 1px solid transparent; transition: all .15s;
}
.topbar .action:hover {
  color: var(--text); background: var(--bg-2); border-color: var(--border);
  text-decoration: none;
}

/* ─── Document layout ────────────────────────────────────────────── */
.layout {
  display: grid; grid-template-columns: 268px 1fr;
  max-width: 1340px; margin: 0 auto; align-items: start;
}
.layout.no-toc { grid-template-columns: 1fr; max-width: 920px; }

.toc-sidebar {
  position: sticky; top: 70px;
  align-self: start;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  padding: 36px 8px 36px 28px;
  border-right: 1px solid var(--border);
  scrollbar-width: thin; scrollbar-color: var(--border-2) transparent;
}
.toc-sidebar::-webkit-scrollbar { width: 6px; }
.toc-sidebar::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
.toc-sidebar h3 {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--text-mut); margin: 0 0 14px; padding-left: 14px; font-weight: 600;
}
.toc-sidebar ol { list-style: none; margin: 0; padding: 0; }
.toc-sidebar li { margin: 0; }
.toc-sidebar a {
  display: block;
  padding: 5px 14px;
  border-left: 2px solid transparent;
  color: var(--text-dim);
  text-decoration: none;
  font-size: 13px;
  line-height: 1.5;
  transition: all .15s;
  word-break: break-word;
}
.toc-sidebar a:hover { color: var(--text); border-left-color: var(--border-2); text-decoration: none; }
.toc-sidebar a.active {
  color: var(--accent); border-left-color: var(--accent);
  background: rgba(106,166,255,0.07);
}
.toc-sidebar .lvl-3 a { padding-left: 28px; font-size: 12.5px; }
.toc-sidebar .lvl-4 a, .toc-sidebar .lvl-5 a, .toc-sidebar .lvl-6 a {
  padding-left: 42px; font-size: 12px;
}

.content { padding: 40px 64px 120px; min-width: 0; }

/* ─── Hero ───────────────────────────────────────────────────────── */
.doc-hero {
  border-bottom: 1px solid var(--border);
  padding-bottom: 28px;
  margin-bottom: 36px;
}
.doc-hero .eyebrow {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--accent); font-weight: 600;
}
.doc-hero h1 {
  font-size: 38px; line-height: 1.15;
  margin: 10px 0 18px;
  font-weight: 700; letter-spacing: -0.02em;
  color: var(--text);
}
.doc-hero .meta-row {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  font-size: 12.5px;
}
.meta-pill {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--bg-2); border: 1px solid var(--border);
  padding: 5px 12px; border-radius: 14px;
  font-size: 12px; color: var(--text-dim);
}
.meta-pill .num { color: var(--text); font-weight: 600; font-feature-settings: "tnum"; }
.meta-pill.fmt-md   { color: #6aa6ff; border-color: rgba(106,166,255,0.30); background: rgba(106,166,255,0.06); }
.meta-pill.fmt-pdf  { color: #f87171; border-color: rgba(248,113,113,0.30); background: rgba(248,113,113,0.06); }
.meta-pill.fmt-docx { color: #38bdf8; border-color: rgba(56,189,248,0.30); background: rgba(56,189,248,0.06); }
.meta-pill.fmt-html { color: #fbbf24; border-color: rgba(251,191,36,0.30); background: rgba(251,191,36,0.06); }
.meta-pill.fmt-htm  { color: #fbbf24; border-color: rgba(251,191,36,0.30); background: rgba(251,191,36,0.06); }
.meta-pill.source code { background: transparent; padding: 0; border: 0; font-size: 11px; color: var(--text-dim); }

/* ─── Article body ───────────────────────────────────────────────── */
article { font-size: 16px; line-height: 1.78; color: var(--text); max-width: 78ch; }
article > * + * { margin-top: 1.0em; }
article p { margin: 0; }
article h1, article h2, article h3, article h4 {
  font-weight: 650; letter-spacing: -0.01em; color: var(--text);
  scroll-margin-top: 80px; position: relative;
}
article h1 { font-size: 28px; margin-top: 56px; }
article h2 {
  font-size: 24px; margin-top: 56px; padding-top: 18px;
  border-top: 1px solid var(--border);
}
article h3 { font-size: 19px; margin-top: 36px; }
article h4 { font-size: 16.5px; margin-top: 24px; color: var(--text-dim); }
article h2::before, article h3::before {
  content: '#'; position: absolute; left: -28px;
  color: var(--text-mut); font-weight: 400;
  opacity: 0; transition: opacity .15s;
}
article h2:hover::before, article h3:hover::before { opacity: 1; }

article ul, article ol { padding-left: 1.5em; margin: 0; }
article li { margin: .35em 0; }
article li > p { margin: 0; }

article hr {
  border: 0; height: 1px; background: var(--border); margin: 36px 0;
}

article blockquote {
  border-left: 3px solid var(--accent);
  background: rgba(106,166,255,0.05);
  padding: 14px 18px;
  margin: 22px 0;
  border-radius: 0 8px 8px 0;
  color: var(--text-dim);
}
article blockquote p { margin: 0; }

/* ─── Code ───────────────────────────────────────────────────────── */
article pre {
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  border-radius: 10px;
  padding: 18px 20px;
  overflow-x: auto;
  font-size: 13.5px;
  line-height: 1.65;
  scrollbar-width: thin; scrollbar-color: var(--border-2) transparent;
}
article pre::-webkit-scrollbar { height: 7px; }
article pre::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }
article code, article pre {
  font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  font-feature-settings: "calt" 1;
}
article code.il {
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  padding: 1px 7px; border-radius: 5px;
  font-size: 0.88em;
  color: var(--accent);
}
.code-block { position: relative; }
.code-block .copy-btn {
  position: absolute; top: 8px; right: 8px;
  background: var(--bg-3); border: 1px solid var(--border);
  color: var(--text-dim); padding: 4px 11px; border-radius: 5px;
  font-size: 11px; font-family: inherit; cursor: pointer;
  opacity: 0; transition: all .15s;
}
.code-block:hover .copy-btn { opacity: 1; }
.code-block .copy-btn:hover { color: var(--text); border-color: var(--accent); }
.code-block .copy-btn.copied { color: var(--ok); border-color: var(--ok); }

/* Syntax highlighting (matches build_webbook span classes) */
article pre .kw   { color: #c084fc; font-weight: 500; }
article pre .type { color: #67e8f9; }
article pre .str  { color: #fcd34d; }
article pre .num  { color: #fb923c; }
article pre .cmt  { color: #6b7d99; font-style: italic; }

/* ─── Tables ─────────────────────────────────────────────────────── */
article .tbl-wrap {
  overflow-x: auto; margin: 22px 0;
  border-radius: 10px; border: 1px solid var(--border);
}
article table { border-collapse: collapse; width: 100%; font-size: 14px; }
article th {
  background: var(--bg-3); padding: 11px 14px; text-align: left;
  font-weight: 600; color: var(--text);
  border-bottom: 1px solid var(--border-2);
}
article td {
  padding: 11px 14px; border-top: 1px solid var(--border); vertical-align: top;
}
article tr:nth-child(even) td { background: rgba(255,255,255,0.013); }

/* ─── ASCII art / diagram boxes ──────────────────────────────────── */
article .diagram-box {
  background: linear-gradient(135deg, #1c2540 0%, #0e1424 100%);
  border: 1px solid var(--border-2);
  border-radius: 12px;
  padding: 22px 26px;
  margin: 24px 0;
  box-shadow: var(--shadow);
}
article .diagram-box pre {
  background: transparent; border: 0; padding: 0;
  color: #e8edf5; font-size: 13px; line-height: 1.55;
}

/* ─── Image refs (md image syntax) ───────────────────────────────── */
article .img-ref {
  display: inline-block;
  background: var(--bg-2);
  color: var(--text-mut);
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-style: normal;
  border: 1px dashed var(--border-2);
}

/* ─── Duplicate banners ──────────────────────────────────────────── */
.dup-banner {
  background: linear-gradient(135deg, rgba(251,191,36,0.10), rgba(251,191,36,0.04));
  border: 1px solid rgba(251,191,36,0.35);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 18px;
  font-size: 14px; line-height: 1.55;
  display: flex; gap: 14px; align-items: flex-start;
}
.dup-banner + .dup-banner { margin-top: 0; }
.dup-banner .icon { font-size: 22px; line-height: 1.2; flex-shrink: 0; }
.dup-banner .body { flex: 1; min-width: 0; }
.dup-banner h4 { margin: 0 0 6px; font-size: 14px; font-weight: 600; color: var(--warn); }
.dup-banner p { margin: 0; color: var(--text-dim); }
.dup-banner ul { margin: 6px 0 0; padding-left: 22px; color: var(--text-dim); }
.dup-banner ul li { margin: 3px 0; word-break: break-word; }
.dup-banner code {
  background: var(--bg-3); padding: 2px 7px; border-radius: 5px;
  font-size: 0.92em; color: var(--text);
}
.dup-banner.exact {
  border-color: rgba(248,113,113,0.40);
  background: linear-gradient(135deg, rgba(248,113,113,0.10), rgba(248,113,113,0.04));
}
.dup-banner.exact h4 { color: var(--bad); }
.dup-banner.near {
  border-color: rgba(56,189,248,0.40);
  background: linear-gradient(135deg, rgba(56,189,248,0.10), rgba(56,189,248,0.04));
}
.dup-banner.near h4 { color: var(--info); }
.banner-stack { display: flex; flex-direction: column; gap: 12px; margin-bottom: 32px; }

/* ─── PDF page cards ─────────────────────────────────────────────── */
.pdf-page {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin: 24px 0;
  overflow: hidden;
  scroll-margin-top: 80px;
}
.pdf-page .page-head {
  background: var(--bg-3);
  padding: 9px 20px;
  font-size: 11px; font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 1.4px;
  border-bottom: 1px solid var(--border);
}
.pdf-page .page-body { padding: 18px 24px 22px; }
.pdf-page pre {
  margin: 0; background: transparent; border: 0; padding: 0;
  white-space: pre-wrap; word-wrap: break-word;
  color: var(--text); font-size: 13px; line-height: 1.6;
}

.empty-note {
  background: var(--bg-2);
  border: 1px dashed var(--border-2);
  border-radius: 10px;
  padding: 18px 22px;
  color: var(--text-dim);
  font-style: italic;
}

/* ─── Related docs panel ─────────────────────────────────────────── */
.related {
  margin-top: 64px;
  padding-top: 32px;
  border-top: 1px solid var(--border);
}
.related h2 {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--text-mut); margin: 0 0 18px;
  border: 0; padding: 0; font-weight: 600;
}
.related-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.related-card {
  display: block;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  text-decoration: none;
  color: var(--text);
  transition: all .15s;
}
.related-card:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
}
.related-card .title {
  font-weight: 600; font-size: 13.5px; line-height: 1.35;
  color: var(--text);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.related-card .meta {
  font-size: 11px; color: var(--text-mut); margin-top: 6px;
  display: flex; gap: 8px; align-items: center;
}
.related-card .meta .badge {
  padding: 1px 6px; border-radius: 3px;
  background: var(--bg-3); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px;
}

/* ════════════════════════════════════════════════════════════════════ */
/* MASTER INDEX PAGE                                                    */
/* ════════════════════════════════════════════════════════════════════ */

.index-hero {
  text-align: center;
  padding: 72px 24px 48px;
  border-bottom: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.index-hero::before {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 40% at 50% 0%, rgba(106,166,255,0.10), transparent 70%),
    radial-gradient(ellipse 40% 30% at 80% 30%, rgba(184,106,255,0.07), transparent 70%);
  pointer-events: none;
}
.index-hero > * { position: relative; z-index: 1; }
.index-hero .eyebrow {
  color: var(--accent); font-size: 12px;
  text-transform: uppercase; letter-spacing: 1.6px; font-weight: 600;
}
.index-hero h1 {
  font-size: 52px; margin: 14px 0 8px;
  font-weight: 750; letter-spacing: -0.025em;
  background: linear-gradient(135deg, #6aa6ff 0%, #b86aff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.index-hero p {
  color: var(--text-dim); font-size: 17px;
  max-width: 680px; margin: 12px auto 0; line-height: 1.65;
}

.search-row {
  display: flex; gap: 12px;
  max-width: 720px; margin: 32px auto 0;
}
.search-row input {
  flex: 1;
  background: var(--bg-2);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 15px;
  padding: 14px 20px;
  border-radius: 12px;
  outline: none;
  font-family: inherit;
  transition: border-color .15s, box-shadow .15s;
}
.search-row input::placeholder { color: var(--text-mut); }
.search-row input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(106,166,255,0.13);
}

.summary-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  max-width: 1080px; margin: 36px auto 48px; padding: 0 24px;
}
.stat-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 20px;
  text-align: center;
  transition: border-color .15s;
}
.stat-card:hover { border-color: var(--border-2); }
.stat-card .num {
  font-size: 30px; font-weight: 700; color: var(--accent);
  font-feature-settings: "tnum"; line-height: 1.1;
}
.stat-card .lbl {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--text-mut); margin-top: 6px;
}

.cat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 18px;
  max-width: 1320px; margin: 0 auto; padding: 0 24px 80px;
}
.cat-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 24px;
  transition: border-color .15s, transform .15s;
}
.cat-card:hover { border-color: var(--border-2); }
.cat-card .head {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 8px;
}
.cat-card .head a {
  font-size: 17px; font-weight: 650; color: var(--text);
  text-decoration: none; letter-spacing: -0.005em;
}
.cat-card .head a:hover { color: var(--accent); }
.cat-card .head .count { font-size: 12px; color: var(--text-mut); }
.cat-card .desc {
  font-size: 13px; color: var(--text-dim); line-height: 1.55;
  margin: 0 0 14px;
}
.cat-card ul { list-style: none; margin: 0; padding: 0; }
.cat-card li {
  display: flex; align-items: center; gap: 8px; justify-content: space-between;
  padding: 6px 0;
  border-top: 1px dotted var(--border);
  font-size: 13px;
}
.cat-card li:first-child { border-top: 0; }
.cat-card li a {
  flex: 1; min-width: 0;
  color: var(--text-dim); text-decoration: none;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cat-card li a:hover { color: var(--accent); }
.cat-card li .badges { flex-shrink: 0; display: flex; gap: 4px; }
.cat-card li .ext {
  font-size: 9px; padding: 1px 6px; border-radius: 3px;
  background: var(--bg-3); color: var(--text-mut);
  text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;
}
.cat-card li .dup {
  font-size: 9px; padding: 1px 6px; border-radius: 3px;
  background: rgba(248,113,113,0.18); color: var(--bad); font-weight: 600;
}

/* ════════════════════════════════════════════════════════════════════ */
/* CATEGORY LANDING PAGE                                                */
/* ════════════════════════════════════════════════════════════════════ */

.cat-hero {
  padding: 56px 32px 32px;
  border-bottom: 1px solid var(--border);
  max-width: 1180px; margin: 0 auto;
}
.cat-hero .eyebrow {
  color: var(--accent); font-size: 12px;
  text-transform: uppercase; letter-spacing: 1.4px; font-weight: 600;
}
.cat-hero h1 {
  font-size: 42px; margin: 10px 0 14px;
  font-weight: 700; letter-spacing: -0.02em;
}
.cat-hero p {
  color: var(--text-dim); font-size: 16px;
  max-width: 760px; margin: 0; line-height: 1.65;
}
.cat-hero .stats {
  display: flex; gap: 18px; margin-top: 22px;
  font-size: 13px; color: var(--text-mut);
}
.cat-hero .stats .num { color: var(--text); font-weight: 600; }
.cat-hero .search-row {
  max-width: 520px; margin: 24px 0 0;
}
.cat-hero .search-row input { padding: 12px 18px; font-size: 14px; }

.doc-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
  max-width: 1180px; margin: 36px auto 96px;
  padding: 0 32px;
}
.doc-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 20px;
  text-decoration: none;
  color: var(--text);
  transition: all .18s;
  display: flex; flex-direction: column; gap: 10px;
}
.doc-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
  box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
.doc-card .head {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
}
.doc-card .title {
  font-size: 15px; font-weight: 650; line-height: 1.35;
  color: var(--text); flex: 1;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.doc-card .badges { display: flex; gap: 4px; flex-shrink: 0; }
.doc-card .badge {
  font-size: 9px; padding: 2px 7px; border-radius: 3px;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px;
  background: var(--bg-3); color: var(--text-mut);
}
.doc-card .badge.dup { background: rgba(248,113,113,0.18); color: var(--bad); }
.doc-card .snippet {
  font-size: 13px; color: var(--text-dim); line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  flex: 1;
}
.doc-card .meta {
  display: flex; gap: 14px; font-size: 11px; color: var(--text-mut);
  border-top: 1px solid var(--border); padding-top: 10px;
  margin-top: auto;
}
.doc-card .meta .num { color: var(--text-dim); font-weight: 600; font-feature-settings: "tnum"; }

.empty-msg {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-mut);
  font-size: 14px;
}

/* ─── Mobile ─────────────────────────────────────────────────────── */
@media (max-width: 960px) {
  .layout { grid-template-columns: 1fr; }
  .toc-sidebar { display: none; }
  .content { padding: 28px 24px 80px; }
  .doc-hero h1 { font-size: 30px; }
  .topbar { padding: 10px 18px; }
  .index-hero h1 { font-size: 38px; }
  .index-hero { padding: 48px 20px 36px; }
  .cat-hero h1 { font-size: 32px; }
  .cat-hero { padding: 36px 20px 24px; }
  .doc-cards { padding: 0 20px; }
}
'''

RICH_JS = r'''
// ─── Active TOC item on scroll ────────────────────────────────────
(function() {
  const tocLinks = document.querySelectorAll('.toc-sidebar a[href^="#"]');
  if (!tocLinks.length) return;
  const headings = Array.from(document.querySelectorAll(
    'article h1[id], article h2[id], article h3[id], article h4[id], .pdf-page[id]'
  ));
  if (!headings.length) return;
  function setActive(id) {
    tocLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + id));
  }
  let lastVisible = headings[0].id;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) lastVisible = e.target.id;
    });
    setActive(lastVisible);
  }, { rootMargin: '-20% 0px -70% 0px', threshold: 0 });
  headings.forEach(h => observer.observe(h));
  setActive(headings[0].id);
})();

// ─── Copy code buttons ────────────────────────────────────────────
(function() {
  document.querySelectorAll('article pre').forEach(pre => {
    if (pre.closest('.diagram-box')) return;
    if (pre.closest('.pdf-page')) return;
    if (pre.parentElement && pre.parentElement.classList.contains('code-block')) return;
    const wrap = document.createElement('div');
    wrap.className = 'code-block';
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.type = 'button';
    btn.textContent = 'Copy';
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code') || pre;
      const text = code.innerText;
      const done = () => {
        btn.textContent = 'Copied';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => {});
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
    wrap.appendChild(btn);
  });
})();

// ─── Live filter (master index + category page) ──────────────────
(function() {
  const search = document.getElementById('search-input');
  if (!search) return;
  const items = document.querySelectorAll('[data-search]');
  const parents = document.querySelectorAll('[data-search-parent]');
  function apply() {
    const q = search.value.toLowerCase().trim();
    items.forEach(el => {
      const match = !q || el.dataset.search.includes(q);
      el.style.display = match ? '' : '';
      if (!match) {
        el.style.display = 'none';
      } else {
        el.style.display = '';
      }
    });
    parents.forEach(parent => {
      const visible = Array.from(parent.querySelectorAll('[data-search]'))
        .some(el => el.style.display !== 'none');
      parent.style.display = visible ? '' : 'none';
    });
  }
  search.addEventListener('input', apply);
})();
'''


# ════════════════════════════════════════════════════════════════════════════
# RENDERING: per-document rich page
# ════════════════════════════════════════════════════════════════════════════

def html_url(name: str) -> str:
    """URL-safe encoded filename for use in href attributes."""
    return urllib.parse.quote(name)


def build_banner_for_doc(r, byte_clusters, content_clusters, near_clusters_lookup, near_clusters) -> str:
    """Return HTML for any duplicate banners that apply to this record."""
    sections: list[str] = []

    if r['byte_cluster']:
        others = [p for p in byte_clusters[r['byte_cluster']] if p != r['src_rel']]
        if others:
            lis = ''.join(f'<li><code>{html_module.escape(p)}</code></li>' for p in sorted(others))
            sections.append(
                f'<div class="dup-banner exact"><div class="icon">⊜</div><div class="body">'
                f'<h4>Byte-identical duplicate</h4>'
                f'<p>This file is a literal copy of:</p>'
                f'<ul>{lis}</ul>'
                f'</div></div>'
            )

    if r['content_cluster']:
        others = [p for p in content_clusters[r['content_cluster']] if p != r['src_rel']]
        # Only show if NOT already covered by byte-identical
        byte_others = set()
        if r['byte_cluster']:
            byte_others = set(byte_clusters[r['byte_cluster']]) - {r['src_rel']}
        new_others = [o for o in others if o not in byte_others]
        if new_others:
            lis = ''.join(f'<li><code>{html_module.escape(p)}</code></li>' for p in sorted(new_others))
            sections.append(
                f'<div class="dup-banner"><div class="icon">≡</div><div class="body">'
                f'<h4>Same content, different format</h4>'
                f'<p>The extracted text matches (after normalisation):</p>'
                f'<ul>{lis}</ul>'
                f'</div></div>'
            )

    if r['near_cluster']:
        cid = int(r['near_cluster'].split('-')[1])
        peers = [p for p in near_clusters[cid] if p != r['src_rel']]
        if peers:
            lis = ''.join(f'<li><code>{html_module.escape(p)}</code></li>' for p in sorted(peers))
            sections.append(
                f'<div class="dup-banner near"><div class="icon">≈</div><div class="body">'
                f'<h4>Near-duplicate content</h4>'
                f'<p>Significant text overlap (Jaccard ≥ 0.80) with:</p>'
                f'<ul>{lis}</ul>'
                f'</div></div>'
            )

    if not sections:
        return ''
    return '<div class="banner-stack">' + ''.join(sections) + '</div>'


def build_related_html(r, all_records) -> str:
    siblings = [
        x for x in all_records
        if x['category'] == r['category'] and x['src_rel'] != r['src_rel']
    ]
    siblings.sort(key=lambda x: x['title'].lower())
    if not siblings:
        return ''
    cards: list[str] = []
    for s in siblings[:6]:
        href = html_url(s['html_name'])
        title = html_module.escape(s['title'])
        ext = html_module.escape(s['ext_label'])
        cards.append(
            f'<a class="related-card" href="{href}">'
            f'<div class="title">{title}</div>'
            f'<div class="meta"><span class="badge">{ext}</span>'
            f'<span>{s["word_count"]:,} words</span></div>'
            f'</a>'
        )
    return (
        '<aside class="related"><h2>More in this category</h2>'
        '<div class="related-grid">' + ''.join(cards) + '</div></aside>'
    )


def render_rich_doc_page(r, body_html: str, banner_html: str, related_html: str) -> str:
    cat = r['category']
    crumbs = (
        f'<a href="../00-Index.html">Learning</a>'
        f'<span class="sep">›</span>'
        f'<a href="_Category.html">{html_module.escape(cat)}</a>'
        f'<span class="sep">›</span>'
        f'<span class="current">{html_module.escape(r["title"])}</span>'
    )
    actions = (
        f'<a class="action" href="{html_url(r["organized_name"])}" download>↓ Download</a>'
        f'<a class="action" href="../00-Index.html">All docs</a>'
    )

    # TOC
    toc_html = ''
    if r['headings']:
        items: list[str] = []
        for lvl, text, anchor in r['headings']:
            cls = f'lvl-{min(max(lvl, 2), 6)}'
            items.append(
                f'<li class="{cls}"><a href="#{html_module.escape(anchor)}">{html_module.escape(text)}</a></li>'
            )
        toc_html = (
            '<aside class="toc-sidebar">'
            '<h3>On this page</h3>'
            '<ol>' + ''.join(items) + '</ol>'
            '</aside>'
        )

    fmt_class = 'fmt-' + r['ext'].lstrip('.').lower()
    hero = (
        '<header class="doc-hero">'
        f'<div class="eyebrow">{html_module.escape(cat)}</div>'
        f'<h1>{html_module.escape(r["title"])}</h1>'
        '<div class="meta-row">'
        f'<span class="meta-pill {fmt_class}">{html_module.escape(r["ext_label"])}</span>'
        f'<span class="meta-pill"><span class="num">{r["word_count"]:,}</span> words</span>'
        f'<span class="meta-pill"><span class="num">{r["reading_min"]}</span> min read</span>'
        f'<span class="meta-pill source">Source: <code>{html_module.escape(r["src_rel"])}</code></span>'
        '</div>'
        '</header>'
    )

    layout_class = 'layout' if r['headings'] else 'layout no-toc'

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html_module.escape(r["title"])}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{RICH_CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs">{crumbs}</div>
<div class="actions">{actions}</div>
</nav>
<div class="{layout_class}">
{toc_html}
<main class="content">
{hero}
{banner_html}
<article>
{body_html}
</article>
{related_html}
</main>
</div>
<script>{RICH_JS}</script>
</body>
</html>
'''


# ════════════════════════════════════════════════════════════════════════════
# RENDERING: category landing page
# ════════════════════════════════════════════════════════════════════════════

def render_category_page(category: str, docs: list[dict]) -> str:
    docs_sorted = sorted(docs, key=lambda r: r['title'].lower())
    desc = CATEGORY_DESCRIPTIONS.get(category, '')
    total_words = sum(d['word_count'] for d in docs_sorted)
    total_minutes = sum(d['reading_min'] for d in docs_sorted)

    cards: list[str] = []
    for d in docs_sorted:
        href = html_url(d['html_name'])
        badges = [f'<span class="badge">{html_module.escape(d["ext_label"])}</span>']
        if d['byte_cluster'] or d['content_cluster'] or d['near_cluster']:
            badges.append('<span class="badge dup">DUP</span>')
        snippet = html_module.escape(d.get('snippet') or 'No preview available.')
        search_blob = f'{d["title"]} {d["ext_label"]}'.lower()
        cards.append(
            f'<a class="doc-card" href="{href}" data-search="{html_module.escape(search_blob)}">'
            f'<div class="head"><div class="title">{html_module.escape(d["title"])}</div>'
            f'<div class="badges">{"".join(badges)}</div></div>'
            f'<div class="snippet">{snippet}</div>'
            f'<div class="meta">'
            f'<span><span class="num">{d["word_count"]:,}</span> words</span>'
            f'<span><span class="num">{d["reading_min"]}</span> min</span>'
            f'</div>'
            f'</a>'
        )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html_module.escape(category)} — Learning</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{RICH_CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs">
<a href="../00-Index.html">Learning</a>
<span class="sep">›</span>
<span class="current">{html_module.escape(category)}</span>
</div>
<div class="actions"><a class="action" href="../00-Index.html">All categories</a></div>
</nav>
<section class="cat-hero">
<div class="eyebrow">Category</div>
<h1>{html_module.escape(category)}</h1>
<p>{html_module.escape(desc)}</p>
<div class="stats">
<span><span class="num">{len(docs_sorted)}</span> documents</span>
<span><span class="num">{total_words:,}</span> words total</span>
<span>~<span class="num">{total_minutes}</span> min reading</span>
</div>
<div class="search-row">
<input id="search-input" type="search" placeholder="Filter docs in this category…" autocomplete="off">
</div>
</section>
<div class="doc-cards">
{"".join(cards)}
</div>
<script>{RICH_JS}</script>
</body>
</html>
'''


# ════════════════════════════════════════════════════════════════════════════
# RENDERING: master index
# ════════════════════════════════════════════════════════════════════════════

def render_master_index(records, by_cat, byte_clusters, content_clusters, near_clusters) -> str:
    total = len(records)
    cats = sorted(by_cat.keys())
    n_byte = len(byte_clusters)
    n_content = len(content_clusters)
    n_near = len(near_clusters)
    n_dup = sum(1 for r in records if r['byte_cluster'] or r['content_cluster'] or r['near_cluster'])
    total_words = sum(r['word_count'] for r in records)

    cards: list[str] = []
    for cat in cats:
        docs = sorted(by_cat[cat], key=lambda r: r['title'].lower())
        items: list[str] = []
        for d in docs:
            badges = [f'<span class="ext">{html_module.escape(d["ext_label"])}</span>']
            if d['byte_cluster'] or d['content_cluster'] or d['near_cluster']:
                badges.append('<span class="dup">DUP</span>')
            href = html_url(f'{cat}/{d["html_name"]}')
            search_blob = f'{d["title"]} {d["ext_label"]} {cat}'.lower()
            items.append(
                f'<li data-search="{html_module.escape(search_blob)}">'
                f'<a href="{href}">{html_module.escape(d["title"])}</a>'
                f'<span class="badges">{"".join(badges)}</span></li>'
            )
        desc = CATEGORY_DESCRIPTIONS.get(cat, '')
        cat_href = html_url(f'{cat}/_Category.html')
        cards.append(
            f'<article class="cat-card" data-search-parent>'
            f'<div class="head"><a href="{cat_href}">{html_module.escape(cat)}</a>'
            f'<span class="count">{len(docs)} files</span></div>'
            f'<p class="desc">{html_module.escape(desc)}</p>'
            f'<ul>{"".join(items)}</ul>'
            f'</article>'
        )

    body = f'''
<section class="index-hero">
<div class="eyebrow">Learning content library</div>
<h1>Learning Index</h1>
<p>Auto-organised view of {total} files across {len(cats)} categories. Every source has a rich HTML sibling. Duplicates are flagged at three precision levels: byte-identical, content-identical (post text-normalisation, catches DOCX↔PDF exports of the same source), and near-duplicate (Jaccard ≥ 0.80 on word shingles).</p>
<div class="search-row">
<input id="search-input" type="search" placeholder="Search documents and categories…" autocomplete="off">
</div>
</section>
<section class="summary-stats">
<div class="stat-card"><div class="num">{total}</div><div class="lbl">Files</div></div>
<div class="stat-card"><div class="num">{len(cats)}</div><div class="lbl">Categories</div></div>
<div class="stat-card"><div class="num">{total_words:,}</div><div class="lbl">Total words</div></div>
<div class="stat-card"><div class="num">{n_byte}</div><div class="lbl">Byte dup clusters</div></div>
<div class="stat-card"><div class="num">{n_content}</div><div class="lbl">Content dup clusters</div></div>
<div class="stat-card"><div class="num">{n_near}</div><div class="lbl">Near dup clusters</div></div>
<div class="stat-card"><div class="num">{n_dup}</div><div class="lbl">Files flagged</div></div>
</section>
<div class="cat-grid">
{"".join(cards)}
</div>
'''
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Learning Index</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{RICH_CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs"><span class="current">Learning</span></div>
<div class="actions">
<a class="action" href="_Duplicates.md">Duplicates report</a>
<a class="action" href="_Manifest.json">Manifest JSON</a>
</div>
</nav>
{body}
<script>{RICH_JS}</script>
</body>
</html>
'''


# ════════════════════════════════════════════════════════════════════════════
# RENDERING: duplicates report (markdown)
# ════════════════════════════════════════════════════════════════════════════

def render_duplicates_report(byte_clusters, content_clusters, near_clusters, name_clusters) -> str:
    out: list[str] = []
    out.append('# Duplicates Report')
    out.append('')
    out.append('Generated by `organize_learning.py`. Four kinds of duplication are detected:')
    out.append('')
    out.append('1. **Byte-identical** — same MD5 hash on the raw file bytes. Truly identical.')
    out.append('2. **Content-identical** — same MD5 of the *normalised* extracted text. Catches')
    out.append('   `Foo.docx` and its `Foo.pdf` export when the text content matches even though')
    out.append('   the file bytes do not.')
    out.append('3. **Near-duplicate** — Jaccard similarity ≥ 0.80 on 5-word shingles. Catches')
    out.append('   slight variations (rewordings, extra paragraphs, format-conversion noise).')
    out.append('4. **Same name-stem** — legacy filename heuristic, included for completeness.')
    out.append('   Often overlaps with the content-identical clusters.')
    out.append('')

    def section(title: str, clusters):
        out.append(f'## {title}')
        out.append('')
        if not clusters:
            out.append('_None found._')
            out.append('')
            return
        for key, paths in sorted(clusters.items(), key=lambda x: -len(x[1])):
            out.append(f'### `{key}` — {len(paths)} files')
            for p in sorted(paths):
                out.append(f'- `{p}`')
            out.append('')

    section('1. Byte-identical clusters', byte_clusters)
    section('2. Content-identical clusters', content_clusters)

    out.append('## 3. Near-duplicate clusters (Jaccard ≥ 0.80)')
    out.append('')
    if not near_clusters:
        out.append('_None found._')
        out.append('')
    else:
        for i, members in enumerate(near_clusters, 1):
            out.append(f'### Near-cluster {i} — {len(members)} files')
            for p in sorted(members):
                out.append(f'- `{p}`')
            out.append('')

    section('4. Same name-stem clusters (legacy heuristic)', name_clusters)

    return '\n'.join(out)


# ════════════════════════════════════════════════════════════════════════════
# MANIFEST
# ════════════════════════════════════════════════════════════════════════════

def build_manifest(records, byte_clusters, content_clusters, near_clusters, name_clusters) -> dict:
    return {
        'base': str(BASE),
        'total_files': len(records),
        'categories': sorted({r['category'] for r in records}),
        'cluster_counts': {
            'byte': len(byte_clusters),
            'content': len(content_clusters),
            'near': len(near_clusters),
            'name': len(name_clusters),
        },
        'byte_clusters': byte_clusters,
        'content_clusters': content_clusters,
        'near_clusters': near_clusters,
        'name_clusters': name_clusters,
        'files': [
            {
                'src_rel': r['src_rel'],
                'category': r['category'],
                'organized_name': r['organized_name'],
                'html_name': r['html_name'],
                'title': r['title'],
                'ext': r['ext'],
                'word_count': r['word_count'],
                'reading_min': r['reading_min'],
                'md5_bytes': r['h_bytes'],
                'md5_content': r['h_content'],
                'is_byte_dup': bool(r['byte_cluster']),
                'is_content_dup': bool(r['content_cluster']),
                'is_near_dup': bool(r['near_cluster']),
                'is_name_dup': bool(r['name_cluster']),
            }
            for r in records
        ],
    }


# ════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════════════════════════════════════

def _force_remove(func, p, exc_info):
    """rmtree onerror handler — retry on PermissionError up to 5 times."""
    for attempt in range(5):
        try:
            os.chmod(p, 0o777)
        except Exception:
            pass
        try:
            func(p)
            return
        except PermissionError:
            time.sleep(0.4 * (attempt + 1))
        except FileNotFoundError:
            return
    # Last-resort: leave the file, print a warning
    print(f'[organize] WARN could not delete {p}; continuing.')


def _wipe_contents(path: Path) -> None:
    """Empty a directory's contents without removing the directory itself.
    Resilient against Windows 'in use by another process' errors."""
    for child in list(path.iterdir()):
        for attempt in range(5):
            try:
                if child.is_dir() and not child.is_symlink():
                    # Python 3.12+: shutil.rmtree onexc; older: onerror
                    try:
                        shutil.rmtree(child, onexc=_force_remove)
                    except TypeError:
                        shutil.rmtree(child, onerror=lambda f, p, e: _force_remove(f, p, e))
                else:
                    try:
                        os.chmod(child, 0o777)
                    except Exception:
                        pass
                    child.unlink()
                break
            except PermissionError:
                if attempt == 4:
                    print(f'[organize] WARN could not delete {child}; continuing.')
                    break
                time.sleep(0.4 * (attempt + 1))


# Inline (no external CSS) banner used inside complete pre-existing HTML files
# whose own stylesheet we don't want to clash with.
EMBED_BANNER_BASE = (
    'background:linear-gradient(135deg,rgba(251,191,36,0.10),rgba(251,191,36,0.04));'
    'border:1px solid rgba(251,191,36,0.40);'
    'border-radius:10px;'
    'padding:14px 18px;margin:16px;'
    'font:14px/1.55 -apple-system,Inter,Segoe UI,system-ui,sans-serif;'
    'color:#fbbf24;'
    'box-shadow:0 4px 16px rgba(0,0,0,0.25);'
)


def build_embed_banner(r, byte_clusters, content_clusters, near_clusters) -> str:
    """A self-contained banner DIV with inline styles, suitable for injection
    into existing fully-styled HTML pages."""
    lines: list[str] = []
    if r['byte_cluster']:
        others = [p for p in byte_clusters[r['byte_cluster']] if p != r['src_rel']]
        if others:
            lines.append(
                'BYTE-IDENTICAL DUPLICATE — also exists as: '
                + ', '.join(others)
            )
    if r['content_cluster']:
        others = [p for p in content_clusters[r['content_cluster']] if p != r['src_rel']]
        if others:
            lines.append('SAME CONTENT, DIFFERENT FORMAT — also: ' + ', '.join(others))
    if r['near_cluster']:
        cid = int(r['near_cluster'].split('-')[1])
        peers = [p for p in near_clusters[cid] if p != r['src_rel']]
        if peers:
            lines.append('NEAR-DUPLICATE (Jaccard ≥ 0.80) of: ' + ', '.join(peers))
    if not lines:
        return ''
    body = '<br>'.join(html_module.escape(l) for l in lines)
    return f'<div style="{EMBED_BANNER_BASE}">{body}</div>'


# ════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print(f'[organize] BASE = {BASE}')
    if OUT.exists():
        print(f'[organize] Wiping existing {OUT.name}/ contents')
        _wipe_contents(OUT)
    else:
        OUT.mkdir(parents=True)

    files = discover_files()
    print(f'[organize] Discovered {len(files)} in-scope files')

    # ── Phase 1: extract everything ────────────────────────────────────────
    records: list[dict] = []
    for src in files:
        rel = src.relative_to(BASE).as_posix()
        ext = src.suffix.lower()
        category = categorise(rel)
        h_bytes = md5_bytes(src)

        # Format-specific extraction
        try:
            if ext == '.md':
                md_text = extract_md_text(src)
                raw_text = md_text
                headings = extract_md_headings(md_text)
                title = extract_title_from_md(md_text, src.stem)
                payload = ('md', md_text)
            elif ext == '.docx':
                md_text = extract_docx_md(src)
                raw_text = md_text
                headings = extract_md_headings(md_text)
                title = extract_title_from_md(md_text, src.stem)
                payload = ('md', md_text)
            elif ext == '.pdf':
                pages = extract_pdf_pages(src)
                raw_text = '\n\n'.join(pages)
                headings = [(2, f'Page {i + 1}', f'page-{i + 1}') for i in range(len(pages))]
                title = prettify_filename(src.stem)
                payload = ('pdf', pages)
            else:
                raw = src.read_text(encoding='utf-8', errors='replace')
                visible = extract_html_visible_text(raw)
                raw_text = visible
                looks_full = bool(re.search(r'<html[\s>]', raw, re.IGNORECASE))
                if looks_full:
                    headings = extract_html_headings(raw)
                    title = extract_title_from_html(raw, src.stem)
                    payload = ('html-full', raw)
                else:
                    headings = []
                    title = prettify_filename(src.stem)
                    payload = ('html-fragment', raw)
        except Exception as e:
            print(f'[organize] WARN extracting {rel}: {e}')
            raw_text = ''
            headings = []
            title = prettify_filename(src.stem)
            payload = ('error', str(e))

        norm = normalize_for_compare(raw_text)
        c_md5 = content_md5(norm) if norm else ''
        sh = shingles(norm) if norm else set()
        wc = len(norm.split()) if norm else 0

        records.append({
            'src': src,
            'src_rel': rel,
            'category': category,
            'ext': ext,
            'ext_label': ext.lstrip('.').upper(),
            'title': title,
            'organized_name': '',
            'html_name': '',
            'h_bytes': h_bytes,
            'h_content': c_md5,
            'shingles': sh,
            'word_count': wc,
            'reading_min': max(1, round(wc / 200)),
            'headings': headings,
            'payload': payload,
            'snippet': make_snippet(raw_text),
            'stem_norm': normalize_stem(src.stem),
            'byte_cluster': '',
            'content_cluster': '',
            'near_cluster': '',
            'name_cluster': '',
        })

    # ── Phase 2: name resolution (avoid collisions inside each category) ──
    used_orig: dict[str, set[str]] = defaultdict(set)
    used_html: dict[str, set[str]] = defaultdict(set)
    for r in records:
        cat = r['category']
        base = safe_filename(r['src'].name)
        cand = base
        n = 2
        while cand.lower() in used_orig[cat]:
            stem, e = os.path.splitext(base)
            cand = f'{stem}__{n}{e}'
            n += 1
        used_orig[cat].add(cand.lower())
        r['organized_name'] = cand

        clean_stem = re.sub(r'\.(md|docx|pdf|html?)$', '', cand, flags=re.IGNORECASE)
        html_cand = f'{clean_stem}.html'
        if html_cand.lower() in used_html[cat]:
            tag = r['ext'].lstrip('.').lower()
            html_cand = f'{clean_stem}__{tag}.html'
            n = 2
            while html_cand.lower() in used_html[cat]:
                html_cand = f'{clean_stem}__{tag}_{n}.html'
                n += 1
        used_html[cat].add(html_cand.lower())
        r['html_name'] = html_cand

    # ── Phase 3: clustering ────────────────────────────────────────────────
    byte_clusters = build_clusters(records, 'h_bytes')
    content_clusters = build_clusters(records, 'h_content')
    near_clusters = build_near_clusters(records, threshold=0.80)
    name_clusters = build_clusters(records, 'stem_norm')

    near_lookup: dict[str, int] = {}
    for cid, members in enumerate(near_clusters):
        for m in members:
            near_lookup[m] = cid

    for r in records:
        if r['h_bytes'] in byte_clusters:
            r['byte_cluster'] = r['h_bytes']
        if r['h_content'] and r['h_content'] in content_clusters:
            r['content_cluster'] = r['h_content']
        if r['src_rel'] in near_lookup:
            r['near_cluster'] = f'near-{near_lookup[r["src_rel"]]}'
        if r['stem_norm'] in name_clusters:
            r['name_cluster'] = r['stem_norm']

    # ── Phase 4: per-document rendering ────────────────────────────────────
    for r in records:
        cat_dir = OUT / r['category']
        cat_dir.mkdir(parents=True, exist_ok=True)
        # Copy original
        try:
            shutil.copy2(r['src'], cat_dir / r['organized_name'])
        except Exception as e:
            print(f'[organize] WARN copy {r["src_rel"]}: {e}')
            continue

        html_dest = cat_dir / r['html_name']
        kind, payload = r['payload']
        banner_html = build_banner_for_doc(
            r, byte_clusters, content_clusters, near_lookup, near_clusters,
        )
        related_html = build_related_html(r, records)

        try:
            if kind == 'md':
                if payload and payload.strip():
                    body = bw.md_to_html(payload)
                else:
                    body = '<p class="empty-note">No extractable text in the source file.</p>'
                page = render_rich_doc_page(r, body, banner_html, related_html)
                html_dest.write_text(page, encoding='utf-8')
            elif kind == 'pdf':
                if not payload:
                    body = '<p class="empty-note">No extractable text — this is most likely a scanned/image-only PDF. Use OCR to recover text.</p>'
                else:
                    parts: list[str] = []
                    for i, page_text in enumerate(payload, 1):
                        parts.append(
                            f'<div class="pdf-page" id="page-{i}">'
                            f'<div class="page-head">Page {i}</div>'
                            f'<div class="page-body"><pre>{html_module.escape(page_text.rstrip())}</pre></div>'
                            f'</div>'
                        )
                    body = '\n'.join(parts)
                page = render_rich_doc_page(r, body, banner_html, related_html)
                html_dest.write_text(page, encoding='utf-8')
            elif kind == 'html-full':
                # Existing fully-styled HTML — copy verbatim, inject embed banner
                # only if applicable. Don't wrap in our shell (would clash with
                # the page's own CSS / JS).
                raw = payload
                embed_banner = build_embed_banner(r, byte_clusters, content_clusters, near_clusters)
                if embed_banner:
                    raw = re.sub(
                        r'(<body[^>]*>)',
                        r'\1\n' + embed_banner,
                        raw, count=1, flags=re.IGNORECASE,
                    )
                html_dest.write_text(raw, encoding='utf-8')
            elif kind == 'html-fragment':
                body = payload
                page = render_rich_doc_page(r, body, banner_html, related_html)
                html_dest.write_text(page, encoding='utf-8')
            else:
                body = f'<p class="empty-note">Unsupported source: {html_module.escape(str(payload))}</p>'
                page = render_rich_doc_page(r, body, banner_html, related_html)
                html_dest.write_text(page, encoding='utf-8')
        except Exception as e:
            print(f'[organize] WARN render {r["src_rel"]}: {e}')

    # ── Phase 5: per-category landing pages ────────────────────────────────
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r['category']].append(r)
    for cat, docs in by_cat.items():
        page = render_category_page(cat, docs)
        (OUT / cat / '_Category.html').write_text(page, encoding='utf-8')

    # ── Phase 6: master index, dup report, manifest ────────────────────────
    (OUT / '00-Index.html').write_text(
        render_master_index(records, by_cat, byte_clusters, content_clusters, near_clusters),
        encoding='utf-8',
    )
    (OUT / '_Duplicates.md').write_text(
        render_duplicates_report(byte_clusters, content_clusters, near_clusters, name_clusters),
        encoding='utf-8',
    )
    (OUT / '_Manifest.json').write_text(
        json.dumps(
            build_manifest(records, byte_clusters, content_clusters, near_clusters, name_clusters),
            indent=2, ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    print(f'[organize] {len(records)} files written to {OUT.name}/')
    print(f'[organize] {len(byte_clusters)} byte-identical clusters')
    print(f'[organize] {len(content_clusters)} content-identical clusters')
    print(f'[organize] {len(near_clusters)} near-duplicate clusters (Jaccard ≥ 0.80)')
    print(f'[organize] {len(name_clusters)} name-stem clusters')
    flagged = sum(1 for r in records if r['byte_cluster'] or r['content_cluster'] or r['near_cluster'])
    print(f'[organize] {flagged} files flagged as duplicate of some kind')
    print(f'[organize] Open: {OUT / "00-Index.html"}')


if __name__ == '__main__':
    main()
