#!/usr/bin/env python3
"""
render_curated.py
=================
Builds the curated `_Curated/` tree from `_analyses_merged.json` (produced by
the analyst-agent fleet) and the original source files.

Produces:
  _Curated/
    00-Index.html                ← master landing (CORE vs APPLICATIONS split)
    _Duplicates.md               ← content-based duplicate report
    _Curated_Manifest.json       ← machine-readable manifest of curated pages
    CORE/
      _Hub.html                  ← Concepts hub
      <family>/
        _Category.html
        <slug>.html              ← rich curated doc page
        <slug>.<ext>             ← original source copy
    APPLICATIONS/
      _Hub.html                  ← Implementations hub
      <domain>/
        _Category.html
        <slug>.html              ← rich curated tutorial page
        <slug>.<ext>             ← original source copy

Idempotent: re-running wipes the curated outputs and rebuilds. The two
existing meta folders (_analysis, _extracted) and the input JSONs are
preserved.

Reuses build_webbook.md_to_html / highlight_code for body rendering, plus
the extraction and clustering helpers from organize_learning.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\User\Desktop\AGILE\Learning')

import build_webbook as bw
from organize_learning import (
    extract_md_text,
    extract_pdf_pages,
    extract_html_visible_text,
    normalize_for_compare,
    content_md5 as content_md5_fn,
    shingles,
    jaccard,
    build_clusters,
    build_near_clusters,
    md5_bytes,
    slugify,
    extract_md_headings,
    extract_html_headings,
    safe_filename,
)


# ════════════════════════════════════════════════════════════════════════════
# SMARTER DOCX EXTRACTOR
# ════════════════════════════════════════════════════════════════════════════
# Many real-world DOCX files don't use the "Heading 1/2/3" paragraph styles —
# they use plain "Normal" with inline font-size and bold formatting to fake
# the visual hierarchy. The extractor in organize_learning.py only handles
# paragraph styles and produces a wall of unstructured prose for those docs.
#
# This smarter version inspects each paragraph's runs to detect:
#   - heading level (from font size: 22+→h1, 16+→h2, 13+ bold→h3, bold-only→h4)
#   - monospace runs (typically code blocks or ASCII art diagrams)
#   - lists (when style name contains "List" or text starts with bullet)
# Consecutive monospace lines are batched into a single ``` fence.

_MONOSPACE_FONTS = {'consolas', 'courier', 'courier new', 'cascadia mono',
                    'jetbrains mono', 'fira code', 'menlo', 'monaco', 'lucida console'}


def _para_metadata(p_el, part) -> dict:
    """Extract text + max font size + bold-ness + monospace-ness for a <w:p>."""
    from docx.text.paragraph import Paragraph
    para = Paragraph(p_el, part)
    text = (para.text or '').strip()
    if not text:
        return {'text': '', 'max_size': None, 'all_bold': False, 'any_bold': False,
                'monospace': False, 'style_name': '', 'list_indent': 0}

    max_size = None
    bold_count = 0
    total_count = 0
    monospace = True  # assume true, set false on first non-mono run
    saw_any_run = False

    for run in para.runs:
        if not run.text:
            continue
        saw_any_run = True
        total_count += 1
        # Bold
        if run.bold or (run.font and run.font.bold):
            bold_count += 1
        # Size
        if run.font and run.font.size:
            try:
                pt = run.font.size.pt
                if max_size is None or pt > max_size:
                    max_size = pt
            except Exception:
                pass
        # Font name
        font_name = ''
        if run.font and run.font.name:
            font_name = run.font.name.lower()
        if font_name not in _MONOSPACE_FONTS:
            monospace = False

    if not saw_any_run:
        monospace = False

    style_name = ''
    try:
        style_name = para.style.name or ''
    except Exception:
        pass

    return {
        'text': text,
        'max_size': max_size,
        'all_bold': total_count > 0 and bold_count == total_count,
        'any_bold': bold_count > 0,
        'monospace': monospace,
        'style_name': style_name,
    }


def _classify_paragraph(meta: dict) -> str:
    """Return one of: 'h1', 'h2', 'h3', 'h4', 'code', 'list', 'p'."""
    text = meta['text']
    style = meta['style_name']
    sz = meta['max_size']
    bold = meta['all_bold']

    # 1. Explicit heading style
    m = re.match(r'Heading\s*(\d)', style)
    if m:
        return f'h{min(int(m.group(1)), 6)}'
    if style == 'Title':
        return 'h1'

    # 2. Monospace → code line
    if meta['monospace']:
        return 'code'

    # 3. Font-size-based heading detection
    if sz is not None:
        if sz >= 22:
            return 'h1'
        if sz >= 16:
            return 'h2'
        if sz >= 13 and bold:
            return 'h3'
        if sz >= 11 and bold and len(text) < 90:
            return 'h4'

    # 4. All-bold short paragraph → h4
    if bold and len(text) < 100 and not text.endswith(('.', '!', '?', ':')):
        return 'h4'

    # 5. List bullet
    if 'List' in style:
        return 'list'

    return 'p'


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


_CSHARP_HINTS = re.compile(
    r'\b(public|private|protected|internal|class|interface|namespace|using|var|'
    r'async|await|new|return|void|string|int|bool|double|float|long|short|'
    r'IEnumerable|Task|List|Dictionary|HashSet|null|true|false|throw|try|catch|'
    r'finally|if|else|foreach|for|while|switch|case|default|static|readonly|'
    r'const|abstract|virtual|override|sealed|partial|record|struct|enum)\b'
)
_BOX_CHARS = set('┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬▶▼←↑↓→↔')


def _detect_code_language(lines: list[str]) -> str:
    """Heuristic: choose 'csharp', 'text' (ASCII art), or 'plain' for a code block."""
    text = '\n'.join(lines)
    box_count = sum(1 for c in text if c in _BOX_CHARS)
    if box_count > 8:
        return 'text'  # ASCII diagram
    cs_matches = len(_CSHARP_HINTS.findall(text))
    if cs_matches >= 3:
        return 'csharp'
    if '{' in text and '}' in text and (';' in text or '=>' in text or '⇒' in text):
        return 'csharp'
    return 'text'


def _normalize_code(text: str) -> str:
    """Undo Word's smart-replace mangling so the highlighter sees real C# tokens."""
    return (text
            .replace('⇒', '=>')
            .replace('≥', '>=')
            .replace('≤', '<=')
            .replace('≠', '!=')
            .replace('“', '"').replace('”', '"')
            .replace('‘', "'").replace('’', "'")
            .replace('–', '-').replace('—', '-'))


def extract_docx_md(path: Path) -> str:
    """Smart DOCX → Markdown extractor (handles font-size headings, monospace
    code blocks, and tables). Walks direct body children only — ignores body-
    level <w:sdt> blocks (typically auto-generated TOCs)."""
    try:
        import docx as docx_lib
    except ImportError:
        return ''
    try:
        doc = docx_lib.Document(str(path))
    except Exception as e:
        return f'[Error opening DOCX: {e}]'

    parts: list[str] = []
    code_buffer: list[str] = []
    list_buffer: list[str] = []
    seen_any_real_heading = False

    def flush_code():
        nonlocal code_buffer
        if code_buffer:
            lang = _detect_code_language(code_buffer)
            joined = '\n'.join(code_buffer)
            if lang == 'csharp':
                joined = _normalize_code(joined)
            parts.append(f'```{lang}\n{joined}\n```')
            code_buffer = []

    def flush_list():
        nonlocal list_buffer
        if list_buffer:
            parts.append('\n'.join(list_buffer))
            list_buffer = []

    for child in doc.element.body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'tbl':
            flush_code()
            flush_list()
            md = _docx_table_md(child, doc.part)
            if md:
                parts.append(md)
            continue

        if tag != 'p':
            continue

        meta = _para_metadata(child, doc.part)
        if not meta['text']:
            continue

        kind = _classify_paragraph(meta)

        if kind == 'code':
            flush_list()
            code_buffer.append(meta['text'])
            continue

        # Non-code: flush any open code block
        flush_code()

        if kind == 'list':
            list_buffer.append('- ' + meta['text'])
            continue
        flush_list()

        if kind.startswith('h'):
            level = int(kind[1:])
            # Skip an early TOC: paragraphs before the first real heading
            # that just look like a list of section names get suppressed.
            parts.append('#' * level + ' ' + meta['text'])
            seen_any_real_heading = True
        else:
            parts.append(meta['text'])

    flush_code()
    flush_list()

    return '\n\n'.join(parts)

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

BASE = Path(r'C:\Users\User\Desktop\AGILE\Learning')
OUT = BASE / '_Curated'

ANALYSES_PATH = OUT / '_analyses_merged.json'
MANIFEST_PATH = OUT / '_manifest.json'

# Top-level dirs we manage (everything else in OUT/ is preserved)
MANAGED_TOPLEVEL = {'CORE', 'APPLICATIONS', '00-Index.html',
                    '_Duplicates.md', '_Curated_Manifest.json'}


# ─── Family + domain descriptions ─────────────────────────────────────────────

FAMILY_DESCRIPTIONS: dict[str, dict] = {
    'language': {
        'name': 'C# Language',
        'tagline': 'Features of the language itself',
        'desc': 'C# language features that show up everywhere: generics, expression trees, named tuples, delegates, flag enums, and the runtime mechanics that make them work.',
        'icon': '⟨/⟩',
        'order': 1,
    },
    'patterns': {
        'name': 'Patterns & Architecture',
        'tagline': 'How to organise code that survives change',
        'desc': 'Design patterns and software architecture — clean architecture, SOLID, and the catalog of patterns (Strategy, Adapter, Decorator, Chain of Responsibility, Builder…) as they actually appear in production .NET code.',
        'icon': '◇',
        'order': 2,
    },
    'frontend': {
        'name': 'Blazor & Frontend',
        'tagline': 'Components, lifecycle, JS bridges',
        'desc': 'Blazor Server patterns and JS interop fundamentals: component lifecycle, parent-child communication, the static-events trap, prerendering gotchas, and bridging to jQuery / vanilla JS libraries.',
        'icon': '⊞',
        'order': 3,
    },
    'data': {
        'name': 'Data & Persistence',
        'tagline': 'EF Core, SQL, schemas',
        'desc': 'Persistence and querying — Entity Framework Core (configurations, migrations, change tracking, audit trails), raw SQL, multi-tenant designs, eager vs lazy loading.',
        'icon': '▤',
        'order': 4,
    },
    'concurrency': {
        'name': 'Concurrency & Performance',
        'tagline': 'Async, locks, caches',
        'desc': 'How to do multiple things without setting your code on fire — async/await, semaphores, concurrent collections, caching strategies (IMemoryCache, ConcurrentDictionary), and background services.',
        'icon': '⇄',
        'order': 5,
    },
    'realtime': {
        'name': 'Real-Time',
        'tagline': 'SignalR fundamentals',
        'desc': 'Real-time communication fundamentals — SignalR hubs, transports, groups, and the mental model of push-based messaging.',
        'icon': '⌁',
        'order': 6,
    },
    'security': {
        'name': 'Security',
        'tagline': 'Auth, hashing, identity',
        'desc': 'Authentication, authorization, password hashing — the foundations, not a specific project.',
        'icon': '⚿',
        'order': 7,
    },
    'testing': {
        'name': 'Testing',
        'tagline': 'Unit testing for .NET',
        'desc': 'Unit testing strategy and mechanics for .NET — what to test, what not to test, and the mechanics of xUnit / NUnit / MSTest.',
        'icon': '✓',
        'order': 8,
    },
    'web': {
        'name': 'Web Fundamentals',
        'tagline': 'HTTP, browsers, the platform',
        'desc': 'HTTP, browser plumbing, IMAP/SMTP, and the platform mechanics every web developer should know.',
        'icon': '⌬',
        'order': 9,
    },
    'ml': {
        'name': 'Machine Learning',
        'tagline': 'How neural networks actually learn',
        'desc': 'Machine learning education — backpropagation, neural networks, sigmoids, training loops, and the math behind credit assignment.',
        'icon': '∿',
        'order': 10,
    },
    'git': {
        'name': 'Git',
        'tagline': 'Version control plumbing',
        'desc': 'Git operations and branching strategies — repo separation, rebases, merges.',
        'icon': '⎇',
        'order': 11,
    },
    'tooling': {
        'name': 'Tooling',
        'tagline': 'Infrastructure helpers',
        'desc': 'Tools and infrastructure helpers.',
        'icon': '⚒',
        'order': 12,
    },
}

DOMAIN_DESCRIPTIONS: dict[str, dict] = {
    'factory-floor': {
        'name': 'Factory Floor System',
        'tagline': 'Production-line tracking for a real factory',
        'desc': 'A production-tracking system for a real manufacturing floor: jobs, equipment, employees, downtime, quality checks. Documented for engineers (formal spec) and managers (plain-language version), in both English and Portuguese.',
        'order': 1,
    },
    'stock-service': {
        'name': 'Stock Service (BioBraga)',
        'tagline': 'Decorator-cached real-time inventory',
        'desc': 'A real-time inventory service with decorator-pattern caching, raw SQL functions for temporal stock, graduated cache expiration, and 2000ms→1ms cached read times. Documented in ENG and PT.',
        'order': 2,
    },
    'identity-project': {
        'name': 'Identity Project',
        'tagline': 'Custom auth without ASP.NET Identity',
        'desc': "A custom authentication and authorization system (no ASP.NET Identity): roles, BCrypt hashing, session tokens, claims-based authorization, and the three-layer auth pattern.",
        'order': 3,
    },
    'scheduling': {
        'name': 'Scheduling Module',
        'tagline': 'Generic conflict detection',
        'desc': 'A scheduling module with agnostic conflict detection and a generic schedule grid that can render any time-based domain (jobs, equipment, employees, rooms…).',
        'order': 4,
    },
    'notification-system': {
        'name': 'Notification System',
        'tagline': 'Multi-channel push pipeline',
        'desc': 'A multi-channel notification system built on SignalR with a recipient-resolver pipeline (chain of responsibility) that fans out from groups, departments, sites, or roles.',
        'order': 5,
    },
    'chat-system': {
        'name': 'Chat System',
        'tagline': 'In-app real-time messaging',
        'desc': 'In-app real-time chat built on SignalR with persistence — hubs, groups, presence, and message storage in EF Core.',
        'order': 6,
    },
    'facial-recognition': {
        'name': 'Facial Recognition',
        'tagline': 'Attendance via face matching',
        'desc': 'A facial-recognition attendance system: face encoding, matching, threshold tuning, and presence verification.',
        'order': 7,
    },
    'geofencing': {
        'name': 'Geofencing',
        'tagline': 'Location-bound check-ins',
        'desc': 'Browser GPS + Haversine distance + chain-of-responsibility validators for location-bound check-ins.',
        'order': 8,
    },
    'audit-trail': {
        'name': 'Audit Trail',
        'tagline': 'Two-layer EF Core change tracking',
        'desc': 'A two-layer EF Core audit trail capturing all entity mutations with both row-level and field-level history.',
        'order': 9,
    },
    'feature-flags': {
        'name': 'Feature Flags',
        'tagline': 'Hierarchical runtime toggles',
        'desc': 'A hierarchical feature-flag system with dependency resolution between flags.',
        'order': 10,
    },
    'background-services': {
        'name': 'Background Services',
        'tagline': 'Smart hosted scheduling',
        'desc': 'Hosted background services with smart scheduling, scoped DI, and graceful shutdown.',
        'order': 11,
    },
    'migration-system': {
        'name': 'Migration & Seeding',
        'tagline': 'Database reset and bootstrap',
        'desc': 'EF Core database reset + migration + seeding mechanism with environment-aware bootstrap data.',
        'order': 12,
    },
    'caching-system': {
        'name': 'Caching System',
        'tagline': 'In-memory cache layer',
        'desc': 'IMemoryCache + ConcurrentDictionary-based caching infrastructure.',
        'order': 13,
    },
    'email-integration': {
        'name': 'Email Integration',
        'tagline': 'IMAP / SMTP plumbing',
        'desc': 'IMAP/SMTP integration for sending mail and consuming inbound messages.',
        'order': 14,
    },
    'ml-aggression-scorer': {
        'name': 'Aggression Scorer ML',
        'tagline': 'ML.NET text classifier',
        'desc': 'An aggression-score ML API project — text classification with ML.NET.',
        'order': 15,
    },
    'ml-laptop-pricing': {
        'name': 'Laptop Price Prediction ML',
        'tagline': 'Regression walkthrough',
        'desc': 'A laptop-price prediction ML walkthrough using ML.NET regression.',
        'order': 16,
    },
    'furnor-category-system': {
        'name': 'Furnor Categories',
        'tagline': 'Category CRUD walkthrough',
        'desc': 'A "new category" tutorial walkthrough for the Furnor application.',
        'order': 17,
    },
    'ui-demos': {
        'name': 'UI Demos',
        'tagline': 'Standalone HTML/CSS prototypes',
        'desc': 'Standalone UI/CSS/HTML demos and prototypes.',
        'order': 18,
    },
    'meta-index': {
        'name': 'Meta',
        'tagline': 'Library metadata',
        'desc': 'Meta documents that index or describe the library itself.',
        'order': 19,
    },
}


# ════════════════════════════════════════════════════════════════════════════
# CSS + JS — extended rich theme
# ════════════════════════════════════════════════════════════════════════════

CSS = r'''
:root {
  --bg: #07090f;
  --bg-1: #0c111c;
  --bg-2: #11182a;
  --bg-3: #1a2238;
  --bg-4: #232e4a;
  --border: #1e2840;
  --border-2: #2a3551;
  --border-3: #3a4870;
  --text: #e9eef8;
  --text-dim: #94a3bf;
  --text-mut: #5f6b86;
  --accent: #6aa6ff;
  --accent-strong: #3b82f6;
  --accent-2: #b86aff;
  --accent-3: #f472b6;
  --ok: #4ade80;
  --warn: #fbbf24;
  --bad: #f87171;
  --info: #38bdf8;
  --code-bg: #0a1020;
  --code-border: #1a2340;
  --shadow: 0 8px 32px rgba(0,0,0,0.55);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.35);
  --shadow-glow: 0 0 0 1px rgba(106,166,255,0.18), 0 12px 40px rgba(106,166,255,0.10);
}

/* Doc-type theming */
[data-doc-type="core-concept"] {
  --doc-accent: #6aa6ff;
  --doc-accent-rgb: 106,166,255;
  --doc-eyebrow: "Concept";
}
[data-doc-type="applied-implementation"] {
  --doc-accent: #b86aff;
  --doc-accent-rgb: 184,106,255;
  --doc-eyebrow: "Implementation";
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font: 16px/1.7 -apple-system, "Inter", \'Segoe UI\', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
::selection { background: rgba(106,166,255,0.30); }

/* ═══ Top bar ═══════════════════════════════════════════════════════ */
.topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(7,9,15,0.88);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
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
  font-size: 13px; padding: 6px 14px; border-radius: 8px;
  color: var(--text-dim); text-decoration: none;
  border: 1px solid transparent; transition: all .15s;
}
.topbar .action:hover {
  color: var(--text); background: var(--bg-2); border-color: var(--border);
  text-decoration: none;
}

/* ═══ Document layout ═══════════════════════════════════════════════ */
.layout {
  display: grid; grid-template-columns: 280px 1fr;
  max-width: 1380px; margin: 0 auto; align-items: start;
}
.layout.no-toc { grid-template-columns: 1fr; max-width: 940px; }

.toc-sidebar {
  position: sticky; top: 70px;
  align-self: start;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  padding: 40px 8px 40px 28px;
  border-right: 1px solid var(--border);
  scrollbar-width: thin; scrollbar-color: var(--border-2) transparent;
}
.toc-sidebar::-webkit-scrollbar { width: 6px; }
.toc-sidebar::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
.toc-sidebar h3 {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;
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
.toc-sidebar a:hover {
  color: var(--text); border-left-color: var(--border-2); text-decoration: none;
}
.toc-sidebar a.active {
  color: var(--doc-accent, var(--accent));
  border-left-color: var(--doc-accent, var(--accent));
  background: rgba(var(--doc-accent-rgb, 106,166,255),0.07);
}
.toc-sidebar .lvl-3 a { padding-left: 28px; font-size: 12.5px; }
.toc-sidebar .lvl-4 a, .toc-sidebar .lvl-5 a, .toc-sidebar .lvl-6 a {
  padding-left: 42px; font-size: 12px;
}

.content { padding: 40px 64px 120px; min-width: 0; }

/* ═══ Hero (per-doc) ════════════════════════════════════════════════ */
.doc-hero {
  position: relative;
  border-bottom: 1px solid var(--border);
  padding-bottom: 32px;
  margin-bottom: 36px;
}
.doc-hero::before {
  content: ''; position: absolute;
  top: -40px; left: -64px; right: -64px; height: 220px;
  background: radial-gradient(ellipse 60% 100% at 0% 0%, rgba(var(--doc-accent-rgb, 106,166,255),0.10), transparent 70%);
  pointer-events: none; z-index: 0;
}
.doc-hero > * { position: relative; z-index: 1; }
.doc-hero .eyebrow {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.6px;
  color: var(--doc-accent, var(--accent)); font-weight: 600;
  display: inline-flex; align-items: center; gap: 8px;
}
.doc-hero .eyebrow .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--doc-accent, var(--accent));
  box-shadow: 0 0 8px var(--doc-accent, var(--accent));
}
.doc-hero h1 {
  font-size: 40px; line-height: 1.1;
  margin: 12px 0 16px;
  font-weight: 700; letter-spacing: -0.025em;
  color: var(--text);
}
.doc-hero .one-liner {
  font-size: 18px; line-height: 1.55;
  color: var(--text-dim);
  margin: 0 0 20px;
  max-width: 70ch;
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
.meta-pill.complexity-beginner    { color: var(--ok); border-color: rgba(74,222,128,0.30); background: rgba(74,222,128,0.06); }
.meta-pill.complexity-intermediate { color: var(--info); border-color: rgba(56,189,248,0.30); background: rgba(56,189,248,0.06); }
.meta-pill.complexity-advanced     { color: #fb923c; border-color: rgba(251,146,60,0.30); background: rgba(251,146,60,0.06); }
.meta-pill.complexity-unknown      { color: var(--text-mut); }
.meta-pill.source code { background: transparent; padding: 0; border: 0; font-size: 11px; color: var(--text-dim); }

/* ═══ Curation panels ═══════════════════════════════════════════════ */

.curation {
  margin-bottom: 36px;
}

.intro-hook {
  font-size: 18px;
  line-height: 1.65;
  color: var(--text);
  border-left: 3px solid var(--doc-accent, var(--accent));
  padding: 8px 0 8px 20px;
  margin: 0 0 28px;
  font-style: italic;
  font-weight: 350;
}

.exec-summary {
  background: linear-gradient(135deg, rgba(var(--doc-accent-rgb, 106,166,255),0.07), rgba(var(--doc-accent-rgb, 106,166,255),0.02));
  border: 1px solid rgba(var(--doc-accent-rgb, 106,166,255),0.20);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 0 0 24px;
}
.exec-summary h3 {
  margin: 0 0 8px;
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--doc-accent, var(--accent));
  font-weight: 600;
}
.exec-summary p {
  margin: 0; font-size: 15px; line-height: 1.65; color: var(--text);
}

.metaphor-callout {
  display: flex; gap: 14px; align-items: flex-start;
  background: rgba(184,106,255,0.06);
  border: 1px solid rgba(184,106,255,0.25);
  border-radius: 12px;
  padding: 16px 20px;
  margin: 0 0 24px;
}
.metaphor-callout .icon {
  font-size: 22px;
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px rgba(184,106,255,0.4));
}
.metaphor-callout .body {
  flex: 1; font-size: 14.5px; line-height: 1.6;
  color: var(--text);
}
.metaphor-callout .body .label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--accent-2); font-weight: 700;
  display: block; margin-bottom: 4px;
}

.tutorial-structure {
  display: grid; grid-template-columns: 1fr; gap: 14px;
  margin: 0 0 28px;
}
.tutorial-section {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--doc-accent);
  border-radius: 0 10px 10px 0;
  padding: 16px 20px;
}
.tutorial-section h3 {
  margin: 0 0 8px;
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--doc-accent);
  font-weight: 600;
  display: flex; align-items: center; gap: 8px;
}
.tutorial-section h3 .num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--doc-accent); color: var(--bg);
  font-size: 10px; font-weight: 700;
}
.tutorial-section p {
  margin: 0; font-size: 14.5px; line-height: 1.65; color: var(--text);
}

.context-row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin: 0 0 28px;
}
.context-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.context-card h4 {
  margin: 0 0 8px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--text-mut);
  font-weight: 600;
}
.context-card ul {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-wrap: wrap; gap: 6px;
}
.context-card li {
  background: var(--bg-3);
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-dim);
  border: 1px solid var(--border-2);
}
.context-card.prereqs li { color: #fbbf24; border-color: rgba(251,191,36,0.30); background: rgba(251,191,36,0.05); }
.context-card.builds li { color: var(--ok); border-color: rgba(74,222,128,0.30); background: rgba(74,222,128,0.05); }
.context-card.concepts li { color: var(--info); border-color: rgba(56,189,248,0.30); background: rgba(56,189,248,0.05); }

.takeaways {
  background: linear-gradient(135deg, rgba(74,222,128,0.05), rgba(74,222,128,0.01));
  border: 1px solid rgba(74,222,128,0.20);
  border-radius: 12px;
  padding: 18px 22px;
  margin: 36px 0 0;
}
.takeaways h3 {
  margin: 0 0 10px;
  font-size: 12px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--ok); font-weight: 600;
  display: flex; align-items: center; gap: 8px;
}
.takeaways h3::before {
  content: '✓';
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  background: rgba(74,222,128,0.18);
  font-size: 12px; font-weight: 700;
}
.takeaways ul { margin: 0; padding-left: 22px; }
.takeaways li {
  font-size: 14.5px; line-height: 1.6; color: var(--text);
  margin: 6px 0;
}

/* ═══ Article body ══════════════════════════════════════════════════ */
article { font-size: 16px; line-height: 1.78; color: var(--text); max-width: 78ch; }
article > * + * { margin-top: 1.0em; }
article p { margin: 0; }
article h1, article h2, article h3, article h4 {
  font-weight: 650; letter-spacing: -0.01em; color: var(--text);
  scroll-margin-top: 90px; position: relative;
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
  border-left: 3px solid var(--doc-accent, var(--accent));
  background: rgba(var(--doc-accent-rgb, 106,166,255),0.05);
  padding: 14px 18px;
  margin: 22px 0;
  border-radius: 0 8px 8px 0;
  color: var(--text-dim);
}
article blockquote p { margin: 0; }

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

article pre .kw   { color: #c084fc; font-weight: 500; }
article pre .type { color: #67e8f9; }
article pre .str  { color: #fcd34d; }
article pre .num  { color: #fb923c; }
article pre .cmt  { color: #6b7d99; font-style: italic; }

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

article .img-ref {
  display: inline-block;
  background: var(--bg-2); color: var(--text-mut);
  padding: 1px 8px; border-radius: 4px;
  font-size: 11px; font-style: normal;
  border: 1px dashed var(--border-2);
}

/* ═══ Duplicate banners ═════════════════════════════════════════════ */
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
.dup-banner h4 { margin: 0 0 6px; font-size: 13px; font-weight: 600; color: var(--warn); text-transform: uppercase; letter-spacing: 1px; }
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
.banner-stack { display: flex; flex-direction: column; gap: 10px; margin-bottom: 28px; }

/* ═══ PDF page cards ════════════════════════════════════════════════ */
.pdf-page {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin: 24px 0;
  overflow: hidden;
  scroll-margin-top: 90px;
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

/* ═══ Cross-references + related ════════════════════════════════════ */
.cross-refs {
  margin-top: 56px;
  padding-top: 28px;
  border-top: 1px solid var(--border);
}
.cross-refs h2 {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;
  color: var(--text-mut); margin: 0 0 14px;
  border: 0; padding: 0; font-weight: 600;
}
.cross-ref-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.cross-ref-list a {
  display: block;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text-dim);
  text-decoration: none;
  transition: all .15s;
}
.cross-ref-list a:hover {
  color: var(--text);
  border-color: var(--doc-accent, var(--accent));
  background: var(--bg-3);
  text-decoration: none;
}
.cross-ref-list a .arrow { color: var(--doc-accent, var(--accent)); margin-right: 6px; }

.related {
  margin-top: 48px;
  padding-top: 28px;
  border-top: 1px solid var(--border);
}
.related h2 {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;
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
  border-color: var(--doc-accent, var(--accent));
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

/* ═══ Master index page ═════════════════════════════════════════════ */

.index-hero {
  text-align: center;
  padding: 80px 24px 56px;
  border-bottom: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.index-hero::before {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 50% at 30% 0%, rgba(106,166,255,0.13), transparent 70%),
    radial-gradient(ellipse 50% 40% at 70% 30%, rgba(184,106,255,0.10), transparent 70%);
  pointer-events: none;
}
.index-hero > * { position: relative; z-index: 1; }
.index-hero .eyebrow {
  color: var(--accent); font-size: 12px;
  text-transform: uppercase; letter-spacing: 1.8px; font-weight: 600;
}
.index-hero h1 {
  font-size: 56px; margin: 16px 0 12px;
  font-weight: 750; letter-spacing: -0.025em;
  background: linear-gradient(135deg, #6aa6ff 0%, #b86aff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.index-hero .tagline {
  color: var(--text-dim); font-size: 18px;
  max-width: 720px; margin: 14px auto 0; line-height: 1.6;
}
.search-row {
  display: flex; gap: 12px;
  max-width: 720px; margin: 36px auto 0;
}
.search-row input {
  flex: 1;
  background: var(--bg-2);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 15px;
  padding: 14px 22px;
  border-radius: 14px;
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
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  max-width: 1080px; margin: 36px auto 56px; padding: 0 24px;
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
  font-size: 32px; font-weight: 700; color: var(--accent);
  font-feature-settings: "tnum"; line-height: 1.1;
}
.stat-card .lbl {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--text-mut); margin-top: 6px;
}

.split-view {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  max-width: 1320px; margin: 0 auto; padding: 0 24px 60px;
}
@media (max-width: 980px) {
  .split-view { grid-template-columns: 1fr; }
}

.hub-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 32px 36px;
  position: relative;
  overflow: hidden;
  transition: all .2s;
}
.hub-card.core::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 0% 0%, rgba(106,166,255,0.08), transparent 60%);
  pointer-events: none;
}
.hub-card.applications::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 100% 0%, rgba(184,106,255,0.08), transparent 60%);
  pointer-events: none;
}
.hub-card > * { position: relative; z-index: 1; }
.hub-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
.hub-card .label {
  font-size: 11px; text-transform: uppercase; letter-spacing: 1.6px;
  font-weight: 700;
}
.hub-card.core .label { color: var(--accent); }
.hub-card.applications .label { color: var(--accent-2); }
.hub-card h2 {
  font-size: 32px; line-height: 1.15;
  margin: 8px 0 12px;
  font-weight: 700; letter-spacing: -0.02em;
  color: var(--text);
}
.hub-card .desc {
  font-size: 15px; line-height: 1.6; color: var(--text-dim);
  margin: 0 0 24px;
}
.hub-card .stats {
  display: flex; gap: 18px; margin-bottom: 24px;
  font-size: 13px; color: var(--text-mut);
}
.hub-card .stats .num { color: var(--text); font-weight: 600; }
.hub-card .cta {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 18px; border-radius: 10px;
  font-size: 13.5px; font-weight: 600;
  text-decoration: none;
}
.hub-card.core .cta {
  background: rgba(106,166,255,0.12);
  color: var(--accent);
  border: 1px solid rgba(106,166,255,0.30);
}
.hub-card.applications .cta {
  background: rgba(184,106,255,0.12);
  color: var(--accent-2);
  border: 1px solid rgba(184,106,255,0.30);
}
.hub-card .cta:hover { text-decoration: none; transform: translateX(2px); }
.hub-card .quick {
  margin-top: 24px; padding-top: 18px;
  border-top: 1px solid var(--border);
}
.hub-card .quick h4 {
  margin: 0 0 8px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 1.4px;
  color: var(--text-mut); font-weight: 600;
}
.hub-card .quick ul { list-style: none; margin: 0; padding: 0; }
.hub-card .quick li { padding: 4px 0; font-size: 13px; }
.hub-card .quick li a { color: var(--text-dim); text-decoration: none; }
.hub-card .quick li a:hover { color: var(--text); }

/* ═══ Hub page (CORE / APPLICATIONS landing) ════════════════════════ */

.hub-hero {
  padding: 64px 32px 36px;
  border-bottom: 1px solid var(--border);
  max-width: 1240px; margin: 0 auto;
}
.hub-hero .eyebrow {
  font-size: 12px; text-transform: uppercase; letter-spacing: 1.6px;
  font-weight: 600;
}
.hub-hero h1 {
  font-size: 48px; margin: 12px 0 14px;
  font-weight: 750; letter-spacing: -0.025em;
  color: var(--text);
}
.hub-hero p {
  color: var(--text-dim); font-size: 17px;
  max-width: 760px; margin: 0; line-height: 1.65;
}
.hub-hero .stats {
  display: flex; gap: 22px; margin-top: 24px;
  font-size: 13px; color: var(--text-mut);
}
.hub-hero .stats .num { color: var(--text); font-weight: 600; }

.cat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 18px;
  max-width: 1280px; margin: 28px auto; padding: 0 32px 80px;
}
.cat-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 24px;
  text-decoration: none;
  color: var(--text);
  transition: all .15s;
  display: flex; flex-direction: column; gap: 8px;
}
.cat-card:hover {
  border-color: var(--border-3);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  text-decoration: none;
}
.cat-card .head {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px;
}
.cat-card .head .icon {
  font-family: "JetBrains Mono", monospace;
  font-size: 18px;
  color: var(--accent);
  font-weight: 700;
  flex-shrink: 0;
}
.cat-card.app .head .icon { color: var(--accent-2); }
.cat-card .title {
  font-size: 18px; font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--text);
  flex: 1;
}
.cat-card .head .count {
  font-size: 12px; color: var(--text-mut);
  flex-shrink: 0;
}
.cat-card .tagline {
  font-size: 13px; color: var(--accent);
  font-weight: 500;
  margin: 0;
}
.cat-card.app .tagline { color: var(--accent-2); }
.cat-card .desc {
  font-size: 13.5px; color: var(--text-dim);
  line-height: 1.55;
  margin: 4px 0 0;
}

/* ═══ Category landing (per family/domain) ══════════════════════════ */

.cat-hero {
  padding: 56px 32px 32px;
  border-bottom: 1px solid var(--border);
  max-width: 1180px; margin: 0 auto;
}
.cat-hero .eyebrow {
  font-size: 12px; text-transform: uppercase; letter-spacing: 1.4px; font-weight: 600;
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
  display: flex; gap: 20px; margin-top: 22px;
  font-size: 13px; color: var(--text-mut);
}
.cat-hero .stats .num { color: var(--text); font-weight: 600; }
.cat-hero .search-row {
  max-width: 520px; margin: 24px 0 0;
}
.cat-hero .search-row input { padding: 12px 18px; font-size: 14px; }

.doc-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
  max-width: 1180px; margin: 36px auto 96px;
  padding: 0 32px;
}
.doc-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 22px;
  text-decoration: none;
  color: var(--text);
  transition: all .18s;
  display: flex; flex-direction: column; gap: 12px;
}
.doc-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
  box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
.doc-card.app:hover { border-color: var(--accent-2); }
.doc-card .head {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
}
.doc-card .title {
  font-size: 16px; font-weight: 650; line-height: 1.3;
  color: var(--text); flex: 1;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  letter-spacing: -0.01em;
}
.doc-card .badges { display: flex; gap: 4px; flex-shrink: 0; }
.doc-card .badge {
  font-size: 9px; padding: 2px 7px; border-radius: 3px;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px;
  background: var(--bg-3); color: var(--text-mut);
}
.doc-card .badge.dup { background: rgba(248,113,113,0.18); color: var(--bad); }
.doc-card .badge.fmt-md { background: rgba(106,166,255,0.18); color: #6aa6ff; }
.doc-card .badge.fmt-pdf { background: rgba(248,113,113,0.18); color: #f87171; }
.doc-card .badge.fmt-docx { background: rgba(56,189,248,0.18); color: #38bdf8; }
.doc-card .badge.fmt-html { background: rgba(251,191,36,0.18); color: #fbbf24; }
.doc-card .one-liner {
  font-size: 13.5px; color: var(--text-dim); line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  flex: 1;
}
.doc-card .meta {
  display: flex; gap: 14px; font-size: 11px; color: var(--text-mut);
  border-top: 1px solid var(--border); padding-top: 12px;
  margin-top: auto;
}
.doc-card .meta .num { color: var(--text-dim); font-weight: 600; font-feature-settings: "tnum"; }

/* ═══ Mobile ════════════════════════════════════════════════════════ */
@media (max-width: 980px) {
  .layout { grid-template-columns: 1fr; }
  .toc-sidebar { display: none; }
  .content { padding: 28px 24px 80px; }
  .doc-hero h1 { font-size: 30px; }
  .doc-hero .one-liner { font-size: 16px; }
  .topbar { padding: 10px 18px; }
  .index-hero h1 { font-size: 38px; }
  .index-hero { padding: 56px 20px 36px; }
  .hub-hero h1 { font-size: 34px; }
  .hub-hero { padding: 40px 20px 24px; }
  .cat-hero h1 { font-size: 32px; }
  .cat-hero { padding: 36px 20px 24px; }
  .doc-cards, .cat-grid { padding: 0 20px 60px; }
  .split-view { padding: 0 20px 40px; }
}
'''


JS = r'''
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
    entries.forEach(e => { if (e.isIntersecting) lastVisible = e.target.id; });
    setActive(lastVisible);
  }, { rootMargin: '-15% 0px -75% 0px', threshold: 0 });
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

// ─── Live filter (master + hub + category pages) ─────────────────
(function() {
  const search = document.getElementById('search-input');
  if (!search) return;
  const items = document.querySelectorAll('[data-search]');
  function apply() {
    const q = search.value.toLowerCase().trim();
    items.forEach(el => {
      const match = !q || el.dataset.search.includes(q);
      el.style.display = match ? '' : 'none';
    });
    document.querySelectorAll('[data-search-parent]').forEach(parent => {
      const visible = Array.from(parent.querySelectorAll('[data-search]'))
        .some(el => el.style.display !== 'none');
      parent.style.display = visible ? '' : 'none';
    });
  }
  search.addEventListener('input', apply);
})();
'''


# ════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════════════════════════════════════

def html_url(name: str) -> str:
    return urllib.parse.quote(name)


def esc(s) -> str:
    return html_module.escape(str(s) if s is not None else '')


def reading_minutes(words: int) -> int:
    return max(1, round(words / 200))


def _force_remove(func, p, exc_info):
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
    print(f'[render] WARN could not delete {p}; continuing.')


def wipe_managed_outputs() -> None:
    """Remove only the managed top-level entries (CORE/, APPLICATIONS/,
    00-Index.html, etc.). Preserve _analysis/, _extracted/, _manifest.json,
    _analyses_merged.json so we don't have to redo agent work."""
    if not OUT.exists():
        OUT.mkdir(parents=True)
        return
    for child in list(OUT.iterdir()):
        if child.name not in MANAGED_TOPLEVEL:
            continue
        for attempt in range(5):
            try:
                if child.is_dir():
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
                    print(f'[render] WARN could not delete {child}; continuing.')
                    break
                time.sleep(0.4 * (attempt + 1))


# ════════════════════════════════════════════════════════════════════════════
# BODY RENDERING
# ════════════════════════════════════════════════════════════════════════════

def render_body(rec: dict, manifest_entry: dict) -> tuple[str, list[tuple[int, str, str]], bool]:
    """Return (body_html, headings, is_full_html_doc).

    For full HTML docs we return the raw HTML and the caller copies them
    verbatim (with a curation strip injected after <body>).
    """
    src = Path(manifest_entry['src_abs'])
    ext = manifest_entry['src_ext']

    if ext == '.md':
        md = extract_md_text(src)
        return bw.md_to_html(md), extract_md_headings(md), False

    if ext == '.docx':
        md = extract_docx_md(src)
        return bw.md_to_html(md), extract_md_headings(md), False

    if ext == '.pdf':
        pages = extract_pdf_pages(src)
        if not pages:
            return (
                '<p class="empty-note">No extractable text — this is most '
                'likely a scanned/image-only PDF. Use OCR to recover text.</p>',
                [], False,
            )
        parts: list[str] = []
        headings: list[tuple[int, str, str]] = []
        for i, page in enumerate(pages, 1):
            parts.append(
                f'<div class="pdf-page" id="page-{i}">'
                f'<div class="page-head">Page {i}</div>'
                f'<div class="page-body"><pre>{esc(page.rstrip())}</pre></div>'
                f'</div>'
            )
            headings.append((2, f'Page {i}', f'page-{i}'))
        return '\n'.join(parts), headings, False

    if ext in ('.html', '.htm'):
        raw = src.read_text(encoding='utf-8', errors='replace')
        looks_full = bool(re.search(r'<html[\s>]', raw, re.IGNORECASE))
        if looks_full:
            return raw, extract_html_headings(raw), True
        return raw, extract_html_headings(raw), False

    return '<p class="empty-note">Unsupported source format.</p>', [], False


# ════════════════════════════════════════════════════════════════════════════
# DUPLICATE DETECTION (content + bytes + jaccard)
# ════════════════════════════════════════════════════════════════════════════

def detect_duplicates(records: list[dict]) -> dict:
    """Compute byte/content/near clusters across all records."""
    by_byte: dict[str, list[str]] = defaultdict(list)
    by_content: dict[str, list[str]] = defaultdict(list)
    shingles_map: dict[str, set] = {}

    for r in records:
        rel = r['src_rel']
        by_byte[r['_byte_md5']].append(rel)
        if r['_content_md5']:
            by_content[r['_content_md5']].append(rel)
        if r['_shingles']:
            shingles_map[rel] = r['_shingles']

    byte_clusters = {k: sorted(set(v)) for k, v in by_byte.items() if len(set(v)) >= 2}
    content_clusters = {k: sorted(set(v)) for k, v in by_content.items() if len(set(v)) >= 2}

    # Near clusters: greedy jaccard ≥ 0.65 (lower than organize_learning's 0.80
    # because the agent analyses give us secondary evidence to be confident)
    near_clusters: list[list[str]] = []
    assigned: set[str] = set()
    rels = list(shingles_map.keys())
    for i, ri in enumerate(rels):
        if ri in assigned:
            continue
        cluster = [ri]
        for rj in rels[i + 1:]:
            if rj in assigned:
                continue
            # Skip if already content-identical
            same_content = False
            for cms in content_clusters.values():
                if ri in cms and rj in cms:
                    same_content = True
                    break
            if same_content:
                continue
            sim = jaccard(shingles_map[ri], shingles_map[rj])
            if sim >= 0.65:
                cluster.append(rj)
        if len(cluster) >= 2:
            near_clusters.append(cluster)
            for x in cluster:
                assigned.add(x)

    return {
        'byte': byte_clusters,
        'content': content_clusters,
        'near': near_clusters,
    }


# ════════════════════════════════════════════════════════════════════════════
# CURATED PAGE RENDERING
# ════════════════════════════════════════════════════════════════════════════

def render_curated_doc_page(
    rec: dict,
    body_html: str,
    headings: list[tuple[int, str, str]],
    banner_html: str,
    cross_refs_html: str,
    related_html: str,
    crumbs_html: str,
    download_link: str,
) -> str:
    a = rec['_analysis']
    title = a.get('title') or rec['src_rel']
    one_liner = a.get('one_line_summary') or ''
    intro_hook = a.get('suggested_intro_hook') or ''
    exec_summary = a.get('executive_summary') or ''
    metaphor = a.get('suggested_metaphor') or ''
    key_concepts = a.get('key_concepts') or []
    prerequisites = a.get('prerequisites') or []
    builds_toward = a.get('builds_toward') or []
    key_takeaways = a.get('key_takeaways') or []
    tutorial = a.get('tutorial_structure')
    complexity = (a.get('complexity') or 'unknown').lower()
    doc_type = a.get('doc_type') or 'core-concept'
    domain = a.get('domain')
    family = a.get('topic_family')

    ext_label = rec['_ext'].lstrip('.').upper()
    fmt_class = 'fmt-' + rec['_ext'].lstrip('.').lower()

    # Eyebrow
    if doc_type == 'applied-implementation':
        dom_info = DOMAIN_DESCRIPTIONS.get(domain, {})
        eyebrow_text = f"Implementation · {dom_info.get('name', domain)}"
    else:
        fam_info = FAMILY_DESCRIPTIONS.get(family, {})
        eyebrow_text = f"Concept · {fam_info.get('name', family)}"

    # TOC
    toc_html = ''
    if headings:
        items: list[str] = []
        for lvl, text, anchor in headings:
            cls = f'lvl-{min(max(lvl, 2), 6)}'
            items.append(
                f'<li class="{cls}"><a href="#{esc(anchor)}">{esc(text)}</a></li>'
            )
        toc_html = (
            '<aside class="toc-sidebar">'
            '<h3>On this page</h3>'
            '<ol>' + ''.join(items) + '</ol>'
            '</aside>'
        )

    # Hero
    hero = f'''
<header class="doc-hero">
  <div class="eyebrow"><span class="dot"></span>{esc(eyebrow_text)}</div>
  <h1>{esc(title)}</h1>
  <p class="one-liner">{esc(one_liner)}</p>
  <div class="meta-row">
    <span class="meta-pill {fmt_class}">{esc(ext_label)}</span>
    <span class="meta-pill complexity-{esc(complexity)}">{esc(complexity.title())}</span>
    <span class="meta-pill"><span class="num">{rec["_word_count"]:,}</span> words</span>
    <span class="meta-pill"><span class="num">{reading_minutes(rec["_word_count"])}</span> min read</span>
    <span class="meta-pill source">Source: <code>{esc(rec["src_rel"])}</code></span>
  </div>
</header>'''

    # Curation panels
    curation_parts: list[str] = []

    if intro_hook:
        curation_parts.append(f'<p class="intro-hook">{esc(intro_hook)}</p>')

    if exec_summary:
        curation_parts.append(
            f'<div class="exec-summary">'
            f'<h3>Executive summary</h3>'
            f'<p>{esc(exec_summary)}</p>'
            f'</div>'
        )

    if metaphor:
        curation_parts.append(
            f'<div class="metaphor-callout">'
            f'<div class="icon">💡</div>'
            f'<div class="body">'
            f'<span class="label">Metaphor</span>{esc(metaphor)}'
            f'</div>'
            f'</div>'
        )

    # Tutorial structure (applied implementations)
    if tutorial and doc_type == 'applied-implementation':
        why = tutorial.get('why_it_exists') or ''
        what = tutorial.get('what_it_does') or ''
        how = tutorial.get('how_it_works') or ''
        ts_parts: list[str] = []
        if why:
            ts_parts.append(f'<div class="tutorial-section"><h3><span class="num">1</span>Why it exists</h3><p>{esc(why)}</p></div>')
        if what:
            ts_parts.append(f'<div class="tutorial-section"><h3><span class="num">2</span>What it does</h3><p>{esc(what)}</p></div>')
        if how:
            ts_parts.append(f'<div class="tutorial-section"><h3><span class="num">3</span>How it works</h3><p>{esc(how)}</p></div>')
        if ts_parts:
            curation_parts.append('<div class="tutorial-structure">' + ''.join(ts_parts) + '</div>')

    # Prerequisites / key concepts / builds-toward row
    ctx_cards: list[str] = []
    if prerequisites:
        lis = ''.join(f'<li>{esc(p)}</li>' for p in prerequisites)
        ctx_cards.append(f'<div class="context-card prereqs"><h4>You should know first</h4><ul>{lis}</ul></div>')
    if key_concepts:
        lis = ''.join(f'<li>{esc(c)}</li>' for c in key_concepts)
        ctx_cards.append(f'<div class="context-card concepts"><h4>Key concepts covered</h4><ul>{lis}</ul></div>')
    if builds_toward:
        lis = ''.join(f'<li>{esc(b)}</li>' for b in builds_toward)
        ctx_cards.append(f'<div class="context-card builds"><h4>Opens the door to</h4><ul>{lis}</ul></div>')
    if ctx_cards:
        curation_parts.append('<div class="context-row">' + ''.join(ctx_cards) + '</div>')

    curation_html = '<div class="curation">' + '\n'.join(curation_parts) + '</div>' if curation_parts else ''

    # Key takeaways (after body)
    takeaways_html = ''
    if key_takeaways:
        lis = ''.join(f'<li>{esc(t)}</li>' for t in key_takeaways)
        takeaways_html = (
            '<div class="takeaways">'
            '<h3>Key takeaways</h3>'
            f'<ul>{lis}</ul>'
            '</div>'
        )

    layout_class = 'layout' if headings else 'layout no-toc'

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style>
</head>
<body data-doc-type="{esc(doc_type)}">
<nav class="topbar">
<div class="crumbs">{crumbs_html}</div>
<div class="actions">{download_link}<a class="action" href="../../00-Index.html">All docs</a></div>
</nav>
<div class="{layout_class}">
{toc_html}
<main class="content">
{hero}
{banner_html}
{curation_html}
<article>
{body_html}
</article>
{takeaways_html}
{cross_refs_html}
{related_html}
</main>
</div>
<script>{JS}</script>
</body>
</html>
'''


# ════════════════════════════════════════════════════════════════════════════
# BANNER + RELATED + CROSS-REF BUILDERS
# ════════════════════════════════════════════════════════════════════════════

def build_banner(rec, all_records, clusters) -> str:
    rel = rec['src_rel']
    sections: list[str] = []

    # Byte-identical
    for h, members in clusters['byte'].items():
        if rel in members:
            others = [m for m in members if m != rel]
            if others:
                lis = ''.join(f'<li><code>{esc(m)}</code></li>' for m in sorted(others))
                sections.append(
                    '<div class="dup-banner exact"><div class="icon">⊜</div><div class="body">'
                    '<h4>Byte-identical duplicate</h4>'
                    '<p>This file is a literal copy of:</p>'
                    f'<ul>{lis}</ul>'
                    '</div></div>'
                )
            break

    # Content-identical (post-normalisation)
    for h, members in clusters['content'].items():
        if rel in members:
            byte_members = set()
            for bm in clusters['byte'].values():
                if rel in bm:
                    byte_members = set(bm)
                    break
            others = [m for m in members if m != rel and m not in byte_members]
            if others:
                lis = ''.join(f'<li><code>{esc(m)}</code></li>' for m in sorted(others))
                sections.append(
                    '<div class="dup-banner"><div class="icon">≡</div><div class="body">'
                    '<h4>Same text content, different format</h4>'
                    '<p>The extracted text matches (after normalisation) — likely a DOCX⇄PDF export pair:</p>'
                    f'<ul>{lis}</ul>'
                    '</div></div>'
                )
            break

    # Near (jaccard ≥ 0.65)
    for cluster in clusters['near']:
        if rel in cluster:
            others = [m for m in cluster if m != rel]
            if others:
                lis = ''.join(f'<li><code>{esc(m)}</code></li>' for m in sorted(others))
                sections.append(
                    '<div class="dup-banner near"><div class="icon">≈</div><div class="body">'
                    '<h4>Near-duplicate content</h4>'
                    '<p>Significant text overlap (Jaccard ≥ 0.65) with — likely audience variants (ENG/PT, ForDummies/Formal) of the same source:</p>'
                    f'<ul>{lis}</ul>'
                    '</div></div>'
                )
            break

    if not sections:
        return ''
    return '<div class="banner-stack">' + ''.join(sections) + '</div>'


def build_cross_refs(rec, all_records, slug_to_record) -> str:
    refs = (rec['_analysis'].get('cross_references') or [])
    if not refs:
        return ''
    items: list[str] = []
    for ref_slug in refs:
        target = slug_to_record.get(ref_slug)
        if target:
            href = relative_doc_link(rec, target)
            items.append(
                f'<a href="{esc(href)}"><span class="arrow">→</span>{esc(target["_analysis"].get("title", ref_slug))}</a>'
            )
        else:
            # Unresolved — show as plain pill
            items.append(
                f'<a href="javascript:void(0)" style="opacity:0.5;cursor:default;"><span class="arrow">→</span>{esc(ref_slug)}</a>'
            )
    if not items:
        return ''
    return (
        '<aside class="cross-refs">'
        '<h2>Cross-references</h2>'
        '<div class="cross-ref-list">' + ''.join(items) + '</div>'
        '</aside>'
    )


def build_related(rec, all_records) -> str:
    """Other docs in the same family (CORE) or domain (APPLICATIONS)."""
    a = rec['_analysis']
    same_group = []
    if a.get('doc_type') == 'core-concept':
        key_field, key_val = 'topic_family', a.get('topic_family')
    else:
        key_field, key_val = 'domain', a.get('domain')

    for other in all_records:
        if other['src_rel'] == rec['src_rel']:
            continue
        oa = other['_analysis']
        if oa.get(key_field) == key_val:
            same_group.append(other)

    if not same_group:
        return ''

    same_group.sort(key=lambda r: r['_analysis'].get('title', '').lower())
    cards: list[str] = []
    for s in same_group[:6]:
        href = relative_doc_link(rec, s)
        title = s['_analysis'].get('title', s['src_rel'])
        ext = s['_ext'].lstrip('.').upper()
        cards.append(
            f'<a class="related-card" href="{esc(href)}">'
            f'<div class="title">{esc(title)}</div>'
            f'<div class="meta"><span class="badge">{esc(ext)}</span>'
            f'<span>{s["_word_count"]:,} words</span></div>'
            f'</a>'
        )
    return (
        '<aside class="related">'
        '<h2>More in this category</h2>'
        '<div class="related-grid">' + ''.join(cards) + '</div>'
        '</aside>'
    )


def relative_doc_link(from_rec, to_rec) -> str:
    """Compute a relative href from one rendered doc to another."""
    return '../../' + to_rec['_path_in_curated']


# ════════════════════════════════════════════════════════════════════════════
# EMBED BANNER (for verbatim-copied HTML pages)
# ════════════════════════════════════════════════════════════════════════════

EMBED_STYLE_BASE = (
    'background:linear-gradient(135deg,#0a0e1a 0%,#11182a 100%);'
    'border:1px solid #1f2940;'
    'border-radius:14px;'
    'padding:24px 28px;'
    'margin:20px;'
    'font:15px/1.7 -apple-system,Inter,\'Segoe UI\',system-ui,sans-serif;'
    'color:#e9eef8;'
    'box-shadow:0 12px 40px rgba(0,0,0,0.35);'
)


def _build_embed_topbar(rec) -> str:
    """Inline-styled fixed topbar with breadcrumbs. Uses position:fixed +
    left/right:0 to escape the host page's centered layout container, plus
    a spacer div so the original content doesn't render underneath it."""
    a = rec['_analysis']
    title = a.get('title') or rec['src_rel']
    cat_kind = rec['_category_kind']
    cat_key = rec['_category_key']
    top_label = 'CORE' if cat_kind == 'core' else 'APPLICATIONS'
    cat_info = (FAMILY_DESCRIPTIONS if cat_kind == 'core' else DOMAIN_DESCRIPTIONS).get(
        cat_key, {'name': cat_key},
    )
    cat_name = cat_info.get('name', cat_key)

    bar = (
        'background:rgba(7,9,15,0.94);'
        'border-bottom:1px solid #1f2940;'
        'padding:12px 24px;'
        'font:13px/1.4 -apple-system,Inter,\'Segoe UI\',system-ui,sans-serif;'
        'position:fixed;top:0;left:0;right:0;z-index:99999;'
        '-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);'
        'display:flex;align-items:center;gap:10px;'
        'color:#94a3bf;'
        'box-sizing:border-box;'
        'min-height:48px;'
    )
    link = 'color:#94a3bf;text-decoration:none;'
    sep = '<span style="color:#5f6b86;">›</span>'
    current = (
        'color:#e9eef8;font-weight:500;'
        'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;'
    )
    action = (
        'color:#94a3bf;text-decoration:none;padding:6px 12px;border-radius:7px;'
        'border:1px solid #1f2940;background:#11182a;flex-shrink:0;font-size:12px;'
    )
    spacer = '<div style="height:48px;"></div>'
    return (
        f'<div style="{bar}">'
        f'<a href="../../00-Index.html" style="{link}">Learning</a>{sep}'
        f'<a href="../_Hub.html" style="{link}">{esc(top_label)}</a>{sep}'
        f'<a href="_Category.html" style="{link}">{esc(cat_name)}</a>{sep}'
        f'<span style="{current}">{esc(title)}</span>'
        f'<a href="{html_url(rec["_orig_filename"])}" download style="{action}">↓ Download</a>'
        f'<a href="../../00-Index.html" style="{action}">All docs</a>'
        f'</div>'
        f'{spacer}'
    )


def build_embed_curation_strip(rec, banner_html_inline) -> str:
    a = rec['_analysis']
    title = a.get('title') or rec['src_rel']
    eyebrow = ('Concept · ' + (a.get('topic_family') or '').title()
               if a.get('doc_type') == 'core-concept'
               else 'Implementation · ' + (a.get('domain') or '').replace('-', ' ').title())
    one_liner = a.get('one_line_summary') or ''
    intro_hook = a.get('suggested_intro_hook') or ''
    exec_summary = a.get('executive_summary') or ''
    metaphor = a.get('suggested_metaphor') or ''
    key_concepts = a.get('key_concepts') or []

    accent = '#6aa6ff' if a.get('doc_type') == 'core-concept' else '#b86aff'

    parts: list[str] = []
    # Sticky breadcrumb topbar — first thing at the top of <body>
    parts.append(_build_embed_topbar(rec))

    parts.append(f'<div style="{EMBED_STYLE_BASE}">')
    parts.append(
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:1.6px;color:{accent};font-weight:600;margin-bottom:8px;">▸ Curated · {esc(eyebrow)}</div>'
    )
    parts.append(
        f'<div style="font-size:24px;font-weight:700;color:#e9eef8;margin-bottom:10px;letter-spacing:-0.02em;line-height:1.2;">{esc(title)}</div>'
    )
    if one_liner:
        parts.append(f'<div style="font-size:16px;color:#94a3bf;margin-bottom:18px;line-height:1.5;">{esc(one_liner)}</div>')
    if intro_hook:
        parts.append(f'<div style="font-style:italic;border-left:3px solid {accent};padding:6px 0 6px 16px;margin:14px 0;color:#e9eef8;">{esc(intro_hook)}</div>')
    if exec_summary:
        parts.append(
            f'<div style="background:rgba(106,166,255,0.06);border:1px solid rgba(106,166,255,0.20);border-radius:10px;padding:14px 18px;margin:14px 0;">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:{accent};margin-bottom:6px;font-weight:600;">Executive summary</div>'
            f'<div style="font-size:14px;color:#e9eef8;line-height:1.6;">{esc(exec_summary)}</div>'
            f'</div>'
        )
    if metaphor:
        parts.append(
            f'<div style="background:rgba(184,106,255,0.06);border:1px solid rgba(184,106,255,0.25);border-radius:10px;padding:14px 18px;margin:14px 0;display:flex;gap:12px;">'
            f'<div style="font-size:20px;flex-shrink:0;">💡</div>'
            f'<div style="flex:1;font-size:14px;color:#e9eef8;line-height:1.6;">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:#b86aff;margin-bottom:4px;font-weight:700;">Metaphor</div>'
            f'{esc(metaphor)}'
            f'</div>'
            f'</div>'
        )
    if key_concepts:
        pills = ' '.join(
            f'<span style="display:inline-block;background:#1a2238;border:1px solid #2a3551;color:#38bdf8;padding:3px 10px;border-radius:12px;font-size:11px;margin:2px;">{esc(c)}</span>'
            for c in key_concepts
        )
        parts.append(
            f'<div style="margin-top:14px;">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:#5f6b86;margin-bottom:8px;font-weight:600;">Key concepts</div>'
            f'<div>{pills}</div>'
            f'</div>'
        )
    parts.append(
        f'<div style="margin-top:18px;padding-top:14px;border-top:1px solid #1f2940;font-size:11px;color:#5f6b86;">'
        f'↑ Curated overlay added by render_curated.py · the original document follows below'
        f'</div>'
    )
    parts.append('</div>')

    if banner_html_inline:
        parts.insert(0, banner_html_inline)

    return ''.join(parts)


def build_inline_dup_banner(rec, clusters) -> str:
    """Tiny inline-styled dup banner for use inside complete HTML files."""
    rel = rec['src_rel']
    sections: list[str] = []
    for h, members in clusters['byte'].items():
        if rel in members and len(members) > 1:
            others = [m for m in members if m != rel]
            sections.append(f'BYTE-IDENTICAL DUPLICATE: also as {", ".join(others)}')
            break
    for h, members in clusters['content'].items():
        if rel in members and len(members) > 1:
            others = [m for m in members if m != rel]
            sections.append(f'SAME CONTENT (other format): {", ".join(others)}')
            break
    for cluster in clusters['near']:
        if rel in cluster and len(cluster) > 1:
            others = [m for m in cluster if m != rel]
            sections.append(f'NEAR-DUPLICATE (Jaccard ≥ 0.65): {", ".join(others)}')
            break
    if not sections:
        return ''
    body = '<br>'.join(esc(s) for s in sections)
    return (
        f'<div style="background:linear-gradient(135deg,rgba(251,191,36,0.10),rgba(251,191,36,0.04));'
        f'border:1px solid rgba(251,191,36,0.40);border-radius:10px;padding:12px 16px;margin:20px;'
        f'font:13px/1.55 -apple-system,Inter,\'Segoe UI\',sans-serif;color:#fbbf24;">{body}</div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# CATEGORY / HUB / INDEX RENDERING
# ════════════════════════════════════════════════════════════════════════════

def render_category_page(category_kind: str, key: str, info: dict, docs: list[dict]) -> str:
    """category_kind = 'core' (family) or 'app' (domain)."""
    docs_sorted = sorted(docs, key=lambda r: r['_analysis'].get('title', '').lower())
    total_words = sum(d['_word_count'] for d in docs_sorted)
    total_minutes = sum(reading_minutes(d['_word_count']) for d in docs_sorted)

    cards: list[str] = []
    card_class = 'app' if category_kind == 'app' else ''
    for d in docs_sorted:
        a = d['_analysis']
        title = a.get('title') or d['src_rel']
        one_liner = a.get('one_line_summary') or ''
        ext = d['_ext'].lstrip('.').lower()
        ext_label = ext.upper()
        wc = d['_word_count']
        rm = reading_minutes(wc)
        href = html_url(d['_html_filename'])

        badges = [f'<span class="badge fmt-{ext}">{esc(ext_label)}</span>']
        if d.get('_is_dup'):
            badges.append('<span class="badge dup">DUP</span>')

        search_blob = f'{title} {ext_label} {a.get("topic_slug", "")}'.lower()

        cards.append(
            f'<a class="doc-card {card_class}" href="{href}" data-search="{esc(search_blob)}">'
            f'<div class="head"><div class="title">{esc(title)}</div>'
            f'<div class="badges">{"".join(badges)}</div></div>'
            f'<div class="one-liner">{esc(one_liner)}</div>'
            f'<div class="meta">'
            f'<span><span class="num">{wc:,}</span> words</span>'
            f'<span><span class="num">{rm}</span> min</span>'
            f'<span>{esc((a.get("complexity") or "?").title())}</span>'
            f'</div>'
            f'</a>'
        )

    eyebrow = 'Concept family' if category_kind == 'core' else 'Implementation domain'
    parent_label = 'CORE' if category_kind == 'core' else 'APPLICATIONS'
    parent_href = '../../00-Index.html'
    hub_href = '../_Hub.html'
    cat_name = info.get('name', key)
    desc = info.get('desc', '')

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(cat_name)} — Learning</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs">
<a href="{parent_href}">Learning</a>
<span class="sep">›</span>
<a href="{hub_href}">{esc(parent_label)}</a>
<span class="sep">›</span>
<span class="current">{esc(cat_name)}</span>
</div>
<div class="actions"><a class="action" href="{hub_href}">All {esc(parent_label.lower())}</a></div>
</nav>
<section class="cat-hero">
<div class="eyebrow" style="color:{'#6aa6ff' if category_kind == 'core' else '#b86aff'}">{esc(eyebrow)}</div>
<h1>{esc(cat_name)}</h1>
<p>{esc(desc)}</p>
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
<script>{JS}</script>
</body>
</html>
'''


def render_hub_page(kind: str, groups: dict, all_records: list[dict]) -> str:
    """Render CORE/_Hub.html or APPLICATIONS/_Hub.html"""
    if kind == 'core':
        title = 'Core Concepts'
        eyebrow_color = '#6aa6ff'
        intro = 'Pure programming theory that exists independently of any specific application. The reusable knowledge layer.'
        descriptions = FAMILY_DESCRIPTIONS
        card_class = ''
    else:
        title = 'Implementations'
        eyebrow_color = '#b86aff'
        intro = 'Real systems built and shipped — read these like full project tutorials with the why, what, and how.'
        descriptions = DOMAIN_DESCRIPTIONS
        card_class = 'app'

    total_docs = sum(len(g) for g in groups.values())
    total_words = sum(d['_word_count'] for g in groups.values() for d in g)

    # Order categories
    sorted_keys = sorted(groups.keys(), key=lambda k: (
        descriptions.get(k, {}).get('order', 999), k,
    ))

    cards: list[str] = []
    for key in sorted_keys:
        info = descriptions.get(key, {'name': key, 'tagline': '', 'desc': '', 'icon': '◆'})
        n_docs = len(groups[key])
        href = f'{key}/_Category.html'
        icon = info.get('icon', '◆')
        cards.append(
            f'<a class="cat-card {card_class}" href="{href}">'
            f'<div class="head"><span class="icon">{esc(icon)}</span>'
            f'<span class="title">{esc(info.get("name", key))}</span>'
            f'<span class="count">{n_docs} docs</span></div>'
            f'<p class="tagline">{esc(info.get("tagline", ""))}</p>'
            f'<p class="desc">{esc(info.get("desc", ""))}</p>'
            f'</a>'
        )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)} — Learning</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs">
<a href="../00-Index.html">Learning</a>
<span class="sep">›</span>
<span class="current">{esc(title)}</span>
</div>
<div class="actions"><a class="action" href="../00-Index.html">Master index</a></div>
</nav>
<section class="hub-hero">
<div class="eyebrow" style="color:{eyebrow_color}">{esc(title)}</div>
<h1>{esc(title)}</h1>
<p>{esc(intro)}</p>
<div class="stats">
<span><span class="num">{len(groups)}</span> categories</span>
<span><span class="num">{total_docs}</span> documents</span>
<span><span class="num">{total_words:,}</span> words</span>
</div>
</section>
<div class="cat-grid">
{"".join(cards)}
</div>
<script>{JS}</script>
</body>
</html>
'''


def render_master_index(records, core_groups, app_groups, clusters) -> str:
    total_docs = len(records)
    total_words = sum(r['_word_count'] for r in records)
    n_core = sum(len(g) for g in core_groups.values())
    n_app = sum(len(g) for g in app_groups.values())
    n_byte = len(clusters['byte'])
    n_content = len(clusters['content'])
    n_near = len(clusters['near'])
    n_dup = sum(1 for r in records if r.get('_is_dup'))

    # Quick links — top 5 docs in each side, alphabetised
    def quick_links(groups):
        all_docs = sorted(
            [d for g in groups.values() for d in g],
            key=lambda r: r['_analysis'].get('title', '').lower(),
        )[:6]
        return ''.join(
            f'<li><a href="{esc(d["_path_in_curated"])}">{esc(d["_analysis"].get("title", d["src_rel"]))}</a></li>'
            for d in all_docs
        )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Learning — Master Index</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<nav class="topbar">
<div class="crumbs"><span class="current">Learning</span></div>
<div class="actions">
<a class="action" href="_Duplicates.md">Duplicates report</a>
<a class="action" href="_Curated_Manifest.json">Manifest</a>
</div>
</nav>
<section class="index-hero">
<div class="eyebrow">Personal learning library</div>
<h1>Learning</h1>
<p class="tagline">A curated split between <strong style="color:#6aa6ff">core concepts</strong> you can reuse anywhere, and <strong style="color:#b86aff">real implementations</strong> documented like full project tutorials.</p>
<div class="search-row">
<input id="search-input" type="search" placeholder="Search documents and categories…" autocomplete="off">
</div>
</section>
<section class="summary-stats">
<div class="stat-card"><div class="num">{total_docs}</div><div class="lbl">Documents</div></div>
<div class="stat-card"><div class="num">{n_core}</div><div class="lbl">Core concepts</div></div>
<div class="stat-card"><div class="num">{n_app}</div><div class="lbl">Implementations</div></div>
<div class="stat-card"><div class="num">{total_words:,}</div><div class="lbl">Total words</div></div>
<div class="stat-card"><div class="num">{n_byte + n_content + n_near}</div><div class="lbl">Dup clusters</div></div>
<div class="stat-card"><div class="num">{n_dup}</div><div class="lbl">Files flagged</div></div>
</section>
<div class="split-view">
<div class="hub-card core">
<div class="label">▸ Concepts</div>
<h2>Core concepts</h2>
<p class="desc">Pure programming theory — generics, patterns, EF Core, SignalR, async, caching, ML fundamentals. The reusable knowledge layer that exists independently of any specific project.</p>
<div class="stats">
<span><span class="num">{len(core_groups)}</span> families</span>
<span><span class="num">{n_core}</span> documents</span>
</div>
<a class="cta" href="CORE/_Hub.html">Browse concepts →</a>
<div class="quick">
<h4>Recent additions</h4>
<ul>{quick_links(core_groups)}</ul>
</div>
</div>
<div class="hub-card applications">
<div class="label">▸ Implementations</div>
<h2>Real implementations</h2>
<p class="desc">Concrete systems built and shipped — Factory Floor production tracker, Stock Service, Identity Project, Scheduling, Facial Recognition. Each documented like a full tutorial: why, what, how.</p>
<div class="stats">
<span><span class="num">{len(app_groups)}</span> domains</span>
<span><span class="num">{n_app}</span> documents</span>
</div>
<a class="cta" href="APPLICATIONS/_Hub.html">Browse implementations →</a>
<div class="quick">
<h4>Recent additions</h4>
<ul>{quick_links(app_groups)}</ul>
</div>
</div>
</div>
<script>{JS}</script>
</body>
</html>
'''


# ════════════════════════════════════════════════════════════════════════════
# DUP REPORT
# ════════════════════════════════════════════════════════════════════════════

def render_dup_report(clusters) -> str:
    out: list[str] = []
    out.append('# Duplicates Report')
    out.append('')
    out.append('Generated by `render_curated.py`. Three precision levels:')
    out.append('')
    out.append('1. **Byte-identical** — same MD5 of raw bytes. Truly identical files.')
    out.append('2. **Content-identical** — same MD5 of *normalised text* (lowercased, alphanumerics only, code/URLs stripped). Catches `Foo.docx` and its `Foo.pdf` export when the prose matches even though the file bytes do not.')
    out.append('3. **Near-duplicate** — Jaccard similarity ≥ 0.65 on 5-word shingles. Catches reworded variants, ENG↔PT translations, ForDummies vs formal versions, etc.')
    out.append('')

    out.append('## 1. Byte-identical clusters')
    out.append('')
    if not clusters['byte']:
        out.append('_None found._')
    else:
        for h, members in sorted(clusters['byte'].items(), key=lambda x: -len(x[1])):
            out.append(f'### `{h}` — {len(members)} files')
            for m in sorted(members):
                out.append(f'- `{m}`')
            out.append('')

    out.append('## 2. Content-identical clusters')
    out.append('')
    if not clusters['content']:
        out.append('_None found._')
    else:
        for h, members in sorted(clusters['content'].items(), key=lambda x: -len(x[1])):
            out.append(f'### `{h}` — {len(members)} files')
            for m in sorted(members):
                out.append(f'- `{m}`')
            out.append('')

    out.append('## 3. Near-duplicate clusters (Jaccard ≥ 0.65)')
    out.append('')
    if not clusters['near']:
        out.append('_None found._')
    else:
        for i, members in enumerate(clusters['near'], 1):
            out.append(f'### Near-cluster {i} — {len(members)} files')
            for m in sorted(members):
                out.append(f'- `{m}`')
            out.append('')

    return '\n'.join(out)


# ════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print(f'[render] Loading analyses from {ANALYSES_PATH}')
    analyses = json.load(open(ANALYSES_PATH, encoding='utf-8'))
    print(f'[render] {len(analyses)} analyses loaded')

    manifest = json.load(open(MANIFEST_PATH, encoding='utf-8'))
    manifest_by_rel = {m['src_rel']: m for m in manifest}

    print('[render] Wiping managed outputs')
    wipe_managed_outputs()

    # ── Phase 1: build records (one per source file) ──────────────────────
    records: list[dict] = []
    for rel, a in analyses.items():
        m = manifest_by_rel.get(rel)
        if not m:
            print(f'[render] WARN no manifest entry for {rel}')
            continue
        src = Path(m['src_abs'])
        ext = m['src_ext']

        # Hashes & shingles for dup detection
        h_bytes = md5_bytes(src)
        text_path = m.get('text_abs')
        raw_text = ''
        if text_path and Path(text_path).exists():
            raw_text = Path(text_path).read_text(encoding='utf-8', errors='replace')
        elif ext in ('.html', '.htm'):
            raw_text = extract_html_visible_text(src.read_text(encoding='utf-8', errors='replace'))
        norm = normalize_for_compare(raw_text)
        c_md5 = content_md5_fn(norm) if norm else ''
        sh = shingles(norm) if norm else set()

        records.append({
            'src_rel': rel,
            '_src': src,
            '_ext': ext,
            '_byte_md5': h_bytes,
            '_content_md5': c_md5,
            '_shingles': sh,
            '_word_count': m.get('word_count') or 0,
            '_analysis': a,
        })

    # ── Phase 2: assign output paths ───────────────────────────────────────
    # Each record gets:
    #   _category_kind: 'core' | 'app'
    #   _category_key:  family slug (core) or domain slug (app)
    #   _html_filename: <slug>.html (collision-free within category)
    #   _orig_filename: <safe>.<ext> (collision-free within category)
    #   _path_in_curated: relative path inside _Curated/ (e.g. CORE/data/foo.html)
    used_html: dict[tuple[str, str], set[str]] = defaultdict(set)
    used_orig: dict[tuple[str, str], set[str]] = defaultdict(set)

    # Group records by output category for naming
    for r in records:
        a = r['_analysis']
        if a.get('doc_type') == 'applied-implementation':
            r['_category_kind'] = 'app'
            r['_category_key'] = a.get('domain') or 'unknown'
        else:
            r['_category_kind'] = 'core'
            r['_category_key'] = a.get('topic_family') or 'unknown'

        # Filename based on topic_slug
        slug = a.get('topic_slug') or slugify(Path(r['src_rel']).stem)
        cat_key = (r['_category_kind'], r['_category_key'])

        html_name = f'{slug}.html'
        n = 2
        while html_name.lower() in used_html[cat_key]:
            html_name = f'{slug}__{n}.html'
            n += 1
        used_html[cat_key].add(html_name.lower())
        r['_html_filename'] = html_name

        # Original copy filename
        ext = r['_ext']
        orig_base = safe_filename(slug + ext)
        orig_name = orig_base
        n = 2
        while orig_name.lower() in used_orig[cat_key]:
            stem, e = os.path.splitext(orig_base)
            orig_name = f'{stem}__{n}{e}'
            n += 1
        used_orig[cat_key].add(orig_name.lower())
        r['_orig_filename'] = orig_name

        top = 'CORE' if r['_category_kind'] == 'core' else 'APPLICATIONS'
        r['_path_in_curated'] = f'{top}/{r["_category_key"]}/{html_name}'

    # ── Phase 3: build slug → record map (for cross-references) ────────────
    slug_to_record: dict[str, dict] = {}
    for r in records:
        slug = r['_analysis'].get('topic_slug')
        if slug and slug not in slug_to_record:
            slug_to_record[slug] = r

    # ── Phase 4: detect duplicates ─────────────────────────────────────────
    clusters = detect_duplicates(records)
    flagged_set: set[str] = set()
    for k in ('byte', 'content'):
        for members in clusters[k].values():
            if len(members) >= 2:
                flagged_set.update(members)
    for cluster in clusters['near']:
        if len(cluster) >= 2:
            flagged_set.update(cluster)
    for r in records:
        r['_is_dup'] = r['src_rel'] in flagged_set

    # ── Phase 5: render every doc ──────────────────────────────────────────
    for r in records:
        a = r['_analysis']
        cat_kind = r['_category_kind']
        cat_key = r['_category_key']
        top = 'CORE' if cat_kind == 'core' else 'APPLICATIONS'
        cat_dir = OUT / top / cat_key
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Copy original
        try:
            shutil.copy2(r['_src'], cat_dir / r['_orig_filename'])
        except Exception as e:
            print(f'[render] WARN copy {r["src_rel"]}: {e}')
            continue

        # Build body
        try:
            body_html, headings, is_full_doc = render_body(r, manifest_by_rel[r['src_rel']])
        except Exception as e:
            print(f'[render] WARN render body {r["src_rel"]}: {e}')
            body_html = f'<p class="empty-note">Error rendering body: {esc(e)}</p>'
            headings = []
            is_full_doc = False

        # Build crumbs
        cat_info = (FAMILY_DESCRIPTIONS if cat_kind == 'core' else DOMAIN_DESCRIPTIONS).get(
            cat_key, {'name': cat_key},
        )
        crumbs_html = (
            f'<a href="../../00-Index.html">Learning</a>'
            f'<span class="sep">›</span>'
            f'<a href="../_Hub.html">{esc(top)}</a>'
            f'<span class="sep">›</span>'
            f'<a href="_Category.html">{esc(cat_info.get("name", cat_key))}</a>'
            f'<span class="sep">›</span>'
            f'<span class="current">{esc(a.get("title") or r["src_rel"])}</span>'
        )

        download_link = (
            f'<a class="action" href="{html_url(r["_orig_filename"])}" download>↓ Download</a>'
        )

        if is_full_doc:
            # Verbatim copy with curation strip + dup banner injected
            inline_dup = build_inline_dup_banner(r, clusters)
            curation_strip = build_embed_curation_strip(r, inline_dup)
            html_doc = re.sub(
                r'(<body[^>]*>)',
                r'\1\n' + curation_strip,
                body_html, count=1, flags=re.IGNORECASE,
            )
            (cat_dir / r['_html_filename']).write_text(html_doc, encoding='utf-8')
        else:
            # Wrap in rich shell
            banner_html = build_banner(r, records, clusters)
            cross_refs_html = build_cross_refs(r, records, slug_to_record)
            related_html = build_related(r, records)
            page = render_curated_doc_page(
                r, body_html, headings, banner_html, cross_refs_html, related_html,
                crumbs_html, download_link,
            )
            (cat_dir / r['_html_filename']).write_text(page, encoding='utf-8')

    # ── Phase 6: render category pages ─────────────────────────────────────
    core_groups: dict[str, list[dict]] = defaultdict(list)
    app_groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r['_category_kind'] == 'core':
            core_groups[r['_category_key']].append(r)
        else:
            app_groups[r['_category_key']].append(r)

    for fam, docs in core_groups.items():
        info = FAMILY_DESCRIPTIONS.get(fam, {'name': fam, 'desc': ''})
        page = render_category_page('core', fam, info, docs)
        (OUT / 'CORE' / fam / '_Category.html').write_text(page, encoding='utf-8')

    for dom, docs in app_groups.items():
        info = DOMAIN_DESCRIPTIONS.get(dom, {'name': dom, 'desc': ''})
        page = render_category_page('app', dom, info, docs)
        (OUT / 'APPLICATIONS' / dom / '_Category.html').write_text(page, encoding='utf-8')

    # ── Phase 7: hub pages ─────────────────────────────────────────────────
    (OUT / 'CORE').mkdir(parents=True, exist_ok=True)
    (OUT / 'APPLICATIONS').mkdir(parents=True, exist_ok=True)
    (OUT / 'CORE' / '_Hub.html').write_text(
        render_hub_page('core', core_groups, records), encoding='utf-8',
    )
    (OUT / 'APPLICATIONS' / '_Hub.html').write_text(
        render_hub_page('app', app_groups, records), encoding='utf-8',
    )

    # ── Phase 8: master index ──────────────────────────────────────────────
    (OUT / '00-Index.html').write_text(
        render_master_index(records, core_groups, app_groups, clusters),
        encoding='utf-8',
    )

    # ── Phase 9: dup report ────────────────────────────────────────────────
    (OUT / '_Duplicates.md').write_text(
        render_dup_report(clusters), encoding='utf-8',
    )

    # ── Phase 10: manifest ─────────────────────────────────────────────────
    manifest_out = {
        'total_docs': len(records),
        'core_categories': sorted(core_groups.keys()),
        'app_domains': sorted(app_groups.keys()),
        'cluster_counts': {
            'byte': len(clusters['byte']),
            'content': len(clusters['content']),
            'near': len(clusters['near']),
        },
        'docs': [
            {
                'src_rel': r['src_rel'],
                'title': r['_analysis'].get('title'),
                'doc_type': r['_analysis'].get('doc_type'),
                'topic_family': r['_analysis'].get('topic_family'),
                'domain': r['_analysis'].get('domain'),
                'topic_slug': r['_analysis'].get('topic_slug'),
                'complexity': r['_analysis'].get('complexity'),
                'word_count': r['_word_count'],
                'reading_min': reading_minutes(r['_word_count']),
                'rendered_path': r['_path_in_curated'],
                'is_dup': r['_is_dup'],
                'byte_md5': r['_byte_md5'],
                'content_md5': r['_content_md5'],
            }
            for r in records
        ],
    }
    (OUT / '_Curated_Manifest.json').write_text(
        json.dumps(manifest_out, indent=2, ensure_ascii=False), encoding='utf-8',
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    print(f'[render] Rendered {len(records)} curated documents')
    print(f'[render] CORE: {len(core_groups)} families, {sum(len(g) for g in core_groups.values())} docs')
    print(f'[render] APPLICATIONS: {len(app_groups)} domains, {sum(len(g) for g in app_groups.values())} docs')
    print(f'[render] Duplicate clusters: {len(clusters["byte"])} byte, {len(clusters["content"])} content, {len(clusters["near"])} near')
    print(f'[render] Files flagged as duplicate: {sum(1 for r in records if r["_is_dup"])}')
    print(f'[render] Open: {OUT / "00-Index.html"}')


if __name__ == '__main__':
    main()
