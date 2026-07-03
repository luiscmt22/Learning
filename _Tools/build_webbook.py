#!/usr/bin/env python3
"""
Learning Webbook v2 Generator
Builds a single self-contained HTML file from all Learning resources.
100% self-contained — zero external dependencies, no iframes, no PDF links.
"""

import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
import html as html_module
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Learning root (this script lives in _Tools/)
OUTPUT = os.path.join(BASE, 'learning-webbook.html')

# ═══════════════════════════════════════════════════════════════════════════════
# DOCX EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def _docx_para_text(para, ns):
    """Extract text from a single <w:p> element."""
    texts = []
    for run in para.iter(f'{{{ns}}}r'):
        for text_el in run.iter(f'{{{ns}}}t'):
            if text_el.text:
                texts.append(text_el.text)
    return ''.join(texts)

def extract_docx_text(filepath):
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            if 'word/document.xml' not in z.namelist():
                return ''
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

            # Build ordered list of top-level body children (paragraphs + tables)
            body = tree.find(f'{{{ns}}}body')
            if body is None:
                return ''

            result_parts = []
            for child in body:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag == 'tbl':
                    # Extract table as markdown pipe table
                    rows = []
                    for tr in child.iter(f'{{{ns}}}tr'):
                        cells = []
                        for tc in tr.iter(f'{{{ns}}}tc'):
                            # A cell may contain multiple paragraphs; join with space
                            cell_texts = []
                            for p in tc.iter(f'{{{ns}}}p'):
                                t = _docx_para_text(p, ns)
                                if t:
                                    cell_texts.append(t)
                            cells.append(' '.join(cell_texts))
                        if cells:
                            rows.append(cells)
                    if rows:
                        # Normalize column count
                        max_cols = max(len(r) for r in rows)
                        for r in rows:
                            while len(r) < max_cols:
                                r.append('')
                        # Build pipe table
                        lines = []
                        for i, row in enumerate(rows):
                            lines.append('| ' + ' | '.join(row) + ' |')
                            if i == 0:
                                lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
                        result_parts.append('\n'.join(lines))
                elif tag == 'p':
                    text = _docx_para_text(child, ns)
                    if text:
                        result_parts.append(text)

            return '\n\n'.join(result_parts)
    except Exception as e:
        return f'[Error extracting {os.path.basename(filepath)}: {e}]'

def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f'[Error reading {filepath}: {e}]'

# ═══════════════════════════════════════════════════════════════════════════════
# C# SYNTAX HIGHLIGHTER
# ═══════════════════════════════════════════════════════════════════════════════

CS_KEYWORDS = {
    'abstract','as','async','await','base','bool','break','byte','case','catch',
    'char','checked','class','const','continue','decimal','default','delegate',
    'do','double','else','enum','event','explicit','extern','false','finally',
    'fixed','float','for','foreach','goto','if','implicit','in','int','interface',
    'internal','is','lock','long','namespace','new','null','object','operator',
    'out','override','params','private','protected','public','readonly','ref',
    'return','sbyte','sealed','short','sizeof','stackalloc','static','string',
    'struct','switch','this','throw','true','try','typeof','uint','ulong',
    'unchecked','unsafe','ushort','using','var','virtual','void','volatile',
    'where','while','yield','record','init','required','get','set','value',
    'partial','when','and','or','not','with','global'
}

CS_TYPES = {
    'Task','List','Dictionary','IEnumerable','IQueryable','IList','ICollection',
    'IReadOnlyList','IReadOnlyCollection','HashSet','Queue','Stack','Action',
    'Func','Predicate','EventHandler','IDisposable','IAsyncDisposable',
    'IObservable','IObserver','DbContext','DbSet','ILogger','IServiceProvider',
    'IHostBuilder','WebApplication','WebApplicationBuilder','IConfiguration',
    'HttpContext','HttpClient','CancellationToken','StringBuilder','Exception',
    'ArgumentException','InvalidOperationException','NotImplementedException',
    'IOptions','IServiceCollection','ServiceResult','INotificationService',
    'IRepository','IUnitOfWork','ClaimsPrincipal','SignInManager','UserManager',
    'IdentityUser','IdentityRole','AuthenticationState','ComponentBase',
    'EventCallback','RenderFragment','MarkupString','IJSRuntime',
    'NavigationManager','HubConnection','Hub','IHubContext',
    'String','Int32','Int64','Boolean','DateTime','DateTimeOffset','TimeSpan',
    'Guid','Nullable','ValueTask','IResult','Results','Ok','BadRequest',
    'NotFound','Unauthorized'
}

_CS_TOKEN_RE = re.compile(
    r'(//[^\n]*'                     # single-line comment
    r'|/\*[\s\S]*?\*/'              # multi-line comment
    r'|&quot;(?:(?!&quot;).)*?&quot;' # HTML-escaped string
    r'|"(?:\\.|[^"\\])*"'           # regular string
    r'|\b\d[\d.]*[fFdDmMlLuU]?\b'  # numbers
    r'|[A-Za-z_@]\w*'               # identifiers
    r'|&\w+;'                        # HTML entities
    r'|.)', re.DOTALL)

def highlight_csharp(code):
    """Syntax-highlight C# code with span classes — regex-based for speed."""
    escaped = html_module.escape(code)
    parts = []
    for m in _CS_TOKEN_RE.finditer(escaped):
        tok = m.group(0)
        if not tok:
            continue
        if tok.startswith('//') or tok.startswith('/*'):
            parts.append(f'<span class="cmt">{tok}</span>')
        elif tok.startswith('&quot;') or tok.startswith('"'):
            parts.append(f'<span class="str">{tok}</span>')
        elif tok[0].isdigit():
            parts.append(f'<span class="num">{tok}</span>')
        elif tok[0].isalpha() or tok[0] in '_@':
            bare = tok.lstrip('@')
            if bare in CS_KEYWORDS:
                parts.append(f'<span class="kw">{tok}</span>')
            elif bare in CS_TYPES:
                parts.append(f'<span class="type">{tok}</span>')
            elif bare and bare[0].isupper() and len(bare) > 1:
                parts.append(f'<span class="type">{tok}</span>')
            else:
                parts.append(tok)
        else:
            parts.append(tok)
    return ''.join(parts)

def highlight_code(code, lang=''):
    """Highlight code based on language."""
    lang = lang.lower().strip()
    if lang in ('csharp', 'cs', 'c#', 'razor'):
        return highlight_csharp(code)
    return html_module.escape(code)

# ═══════════════════════════════════════════════════════════════════════════════
# MARKDOWN TO HTML CONVERTER (ENHANCED)
# ═══════════════════════════════════════════════════════════════════════════════

def md_to_html(md_text):
    if not md_text:
        return ''
    lines = md_text.split('\n')
    html_parts = []
    in_code = False
    code_lang = ''
    code_lines = []
    in_list = False
    list_type = None
    in_table = False
    table_rows = []
    in_blockquote = False
    bq_lines = []
    para_lines = []  # accumulate consecutive paragraph lines

    def inline(text):
        text = html_module.escape(text)
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code class="il">\1</code>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<span class="img-ref">[\1]</span>', text)
        return text

    def close_para():
        nonlocal para_lines
        if para_lines:
            html_parts.append(f'<p>{" ".join(para_lines)}</p>')
            para_lines = []

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            html_parts.append(f'</{list_type}>')
            in_list = False
            list_type = None

    def close_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            html_parts.append('<div class="tbl-wrap"><table>')
            for idx, row in enumerate(table_rows):
                cells = [c.strip() for c in row.strip('|').split('|')]
                if idx == 0:
                    html_parts.append('<thead><tr>')
                    for cell in cells:
                        html_parts.append(f'<th>{inline(cell)}</th>')
                    html_parts.append('</tr></thead><tbody>')
                elif all(re.match(r'^[-:]+$', c.strip()) for c in cells):
                    continue
                else:
                    html_parts.append('<tr>')
                    for cell in cells:
                        html_parts.append(f'<td>{inline(cell)}</td>')
                    html_parts.append('</tr>')
            html_parts.append('</tbody></table></div>')
            table_rows = []
            in_table = False

    def close_bq():
        nonlocal in_blockquote, bq_lines
        if in_blockquote and bq_lines:
            html_parts.append(f'<blockquote>{"<br>".join(bq_lines)}</blockquote>')
            bq_lines = []
            in_blockquote = False

    def close_all():
        close_para(); close_list(); close_table(); close_bq()

    i = 0
    while i < len(lines):
        line = lines[i]
        # Code blocks (fenced)
        if line.strip().startswith('```'):
            if in_code:
                raw = '\n'.join(code_lines)
                # Detect ASCII art / diagrams and render in styled container
                _box_chars = set('┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬')
                box_count = sum(1 for c in raw if c in _box_chars)
                tree_chars = raw.count('├') + raw.count('└') + raw.count('│')
                escaped = html_module.escape(raw)
                if code_lang == 'text' and (box_count > 8 or tree_chars > 3):
                    html_parts.append(f'<div class="diagram-box"><pre>{escaped}</pre></div>')
                else:
                    highlighted = highlight_code(raw, code_lang)
                    html_parts.append(f'<pre><code class="lang-{code_lang}">{highlighted}</code></pre>')
                code_lines = []
                in_code = False
                code_lang = ''
            else:
                close_all()
                in_code = True
                code_lang = line.strip().lstrip('`').strip() or 'text'
            i += 1; continue
        if in_code:
            code_lines.append(line)
            i += 1; continue

        # Table
        if '|' in line and line.strip().startswith('|'):
            close_para(); close_list(); close_bq()
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(line)
            i += 1; continue
        else:
            close_table()

        # Empty line — ends paragraph
        if not line.strip():
            close_all()
            i += 1; continue

        # Headers
        hm = re.match(r'^(#{1,6})\s+(.+?)(?:\s*\{#[\w-]+\})?\s*$', line)
        if hm:
            close_all()
            lvl = len(hm.group(1))
            txt = hm.group(2)
            anchor = re.sub(r'[^a-z0-9]+', '-', txt.lower()).strip('-')
            html_parts.append(f'<h{lvl} id="{anchor}">{inline(txt)}</h{lvl}>')
            i += 1; continue

        # HR
        if re.match(r'^(---|\*\*\*|___)\s*$', line.strip()):
            close_all()
            html_parts.append('<hr>')
            i += 1; continue

        # Blockquote
        if line.strip().startswith('>'):
            close_para(); close_list()
            in_blockquote = True
            bq_lines.append(inline(line.strip().lstrip('>').strip()))
            i += 1; continue
        else:
            close_bq()

        # Unordered list
        ul = re.match(r'^(\s*)[*\-+]\s+(.+)$', line)
        if ul:
            close_para()
            if not in_list or list_type != 'ul':
                close_list()
                html_parts.append('<ul>')
                in_list = True
                list_type = 'ul'
            html_parts.append(f'<li>{inline(ul.group(2))}</li>')
            i += 1; continue

        # Ordered list
        ol = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ol:
            close_para()
            if not in_list or list_type != 'ol':
                close_list()
                html_parts.append('<ol>')
                in_list = True
                list_type = 'ol'
            html_parts.append(f'<li>{inline(ol.group(2))}</li>')
            i += 1; continue

        # Paragraph — accumulate consecutive text lines
        close_list()
        para_lines.append(inline(line))
        i += 1

    close_all()
    if in_code:
        raw = '\n'.join(code_lines)
        _box_chars = set('┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬')
        box_count = sum(1 for c in raw if c in _box_chars)
        tree_chars = raw.count('├') + raw.count('└') + raw.count('│')
        escaped = html_module.escape(raw)
        if code_lang == 'text' and (box_count > 8 or tree_chars > 3):
            html_parts.append(f'<div class="diagram-box"><pre>{escaped}</pre></div>')
        else:
            html_parts.append(f'<pre><code class="lang-{code_lang}">{highlight_code(raw, code_lang)}</code></pre>')
    return '\n'.join(html_parts)

# ═══════════════════════════════════════════════════════════════════════════════
# DOCX TO HTML CONVERTER (ENHANCED)
# ═══════════════════════════════════════════════════════════════════════════════

def _docx_inline(text):
    """Apply inline markdown formatting to DOCX text."""
    text = html_module.escape(text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code class="il">\1</code>', text)
    return text

def docx_to_html(raw):
    if not raw or len(raw) < 30:
        return '<p><em>Content available in source file.</em></p>'

    # If the content looks like full markdown (has # headings and ``` blocks), route to md_to_html
    if re.search(r'^#{1,3}\s+', raw, re.MULTILINE) and '```' in raw:
        return md_to_html(raw)

    lines = raw.split('\n')
    result = []
    code_buf = []
    code_starts = ('{','}','//', 'using ', 'public ', 'private ', 'var ', 'dotnet ', 'cd ',
        'namespace ', 'class ', '[', 'async ', 'await ', 'return ', 'protected ',
        'internal ', 'static ', 'void ', 'if (', 'if(', 'else', 'for ', 'foreach',
        'try', 'catch', 'throw ', 'new ', 'builder.', 'services.', 'app.', 'options.',
        # GDScript / Python patterns (for Godot-related DOCX)
        'signal ', 'emit_signal', 'func ', 'extends ', 'queue_free', 'call_deferred',
        # More C# patterns
        'player.', 'service.', 'Console.', 'Assert.',
        '@implements', '@code', '@inject',
        )

    def looks_like_code(line):
        s = line.strip()
        if not s:
            return None  # blank — ambiguous
        if s.startswith(code_starts) or s in ('{', '}', '};', ');', '});', ')'):
            return True
        # Indented by 4+ spaces = code
        if line.startswith('    ') or line.startswith('\t'):
            return True
        # C# method calls/assignments (e.g. "player.OnHealthChanged += ...")
        if re.match(r'^\w+\.\w+', s) and ('(' in s or '+=' in s or '-=' in s or '=' in s):
            return True
        # Lines with C# operators that are clearly code
        if '=>' in s or '?.Invoke' in s or '+=' in s or '-=' in s:
            return True
        return False

    def flush_code():
        nonlocal code_buf
        if code_buf:
            while code_buf and not code_buf[-1].strip():
                code_buf.pop()
            if code_buf:
                raw_code = '\n'.join(code_buf)
                result.append(f'<pre><code class="lang-csharp">{highlight_csharp(raw_code)}</code></pre>')
            code_buf = []

    text_buf = []
    def flush_text():
        nonlocal text_buf
        if text_buf:
            joined = ' '.join(text_buf)
            result.append(f'<p>{_docx_inline(joined)}</p>')
            text_buf = []

    in_code = False
    blank_run = 0
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            result.append('<div class="tbl-wrap"><table>')
            for idx, row in enumerate(table_rows):
                cells = [c.strip() for c in row.strip('|').split('|')]
                if idx == 0:
                    result.append('<thead><tr>')
                    for cell in cells:
                        result.append(f'<th>{_docx_inline(cell)}</th>')
                    result.append('</tr></thead><tbody>')
                elif all(re.match(r'^[-:]+$', c.strip()) for c in cells):
                    continue
                else:
                    result.append('<tr>')
                    for cell in cells:
                        result.append(f'<td>{_docx_inline(cell)}</td>')
                    result.append('</tr>')
            result.append('</tbody></table></div>')
            table_rows = []
            in_table = False

    for line in lines:
        s = line.strip()

        # Markdown table
        if '|' in s and s.startswith('|'):
            flush_text()
            if in_code:
                flush_code(); in_code = False
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(s)
            blank_run = 0
            continue
        else:
            flush_table()

        # Heading (# or ## or ### syntax from DOCX)
        # But skip if we're already in a code block — GDScript uses # for comments
        hm = re.match(r'^(#{1,4})\s+(.+)$', s)
        if hm and not in_code:
            # Heuristic: if a single-# line looks like a code comment rather than
            # a real heading, treat it as code instead of a heading.
            is_code_comment = False
            if len(hm.group(1)) == 1:
                txt_lower = hm.group(2).lower()
                # Code-comment indicators: starts with a verb/keyword common in comments
                comment_words = ('define', 'emit', 'connect', 'create', 'set', 'get',
                                 'call', 'check', 'add', 'remove', 'update', 'initialize',
                                 'similar', 'optional', 'note', 'todo', 'fixme', 'hack',
                                 'godot', 'gdscript', 'example', 'usage', 'called',
                                 'this ', 'the ')
                if any(txt_lower.startswith(w) for w in comment_words):
                    is_code_comment = True
                # If previous lines were code, a single # is likely a comment
                if code_buf:
                    is_code_comment = True
                # File names with extensions are code comments, not headings
                if re.search(r'\.\w{1,4}\b', hm.group(2)):
                    is_code_comment = True
                # Lines with parentheses/brackets are likely code
                if '(' in hm.group(2) or '[' in hm.group(2):
                    is_code_comment = True
            if not is_code_comment:
                flush_text()
                lvl = len(hm.group(1))
                txt = hm.group(2)
                anchor = re.sub(r'[^a-z0-9]+', '-', txt.lower()).strip('-')
                result.append(f'<h{lvl} id="{anchor}">{_docx_inline(txt)}</h{lvl}>')
                blank_run = 0
                continue

        # Blockquote (> prefix from DOCX)
        if s.startswith('>'):
            flush_text()
            if in_code:
                flush_code(); in_code = False
            bq_text = s.lstrip('>').strip()
            result.append(f'<blockquote>{_docx_inline(bq_text)}</blockquote>')
            blank_run = 0
            continue

        # List items
        li = re.match(r'^[-*+]\s+(.+)$', s)
        if li:
            flush_text()
            if in_code:
                flush_code(); in_code = False
            result.append(f'<ul><li>{_docx_inline(li.group(1))}</li></ul>')
            blank_run = 0
            continue

        check = looks_like_code(line)
        if check is True:
            flush_text()
            if not in_code:
                in_code = True
            for _ in range(blank_run):
                code_buf.append('')
            blank_run = 0
            code_buf.append(line)
        elif check is None:  # blank line
            blank_run += 1
            if not in_code and text_buf:
                flush_text()
                blank_run = 0
        else:
            if in_code:
                flush_code()
                in_code = False
            blank_run = 0
            text_buf.append(s)

    flush_code()
    flush_text()
    flush_table()
    return '\n'.join(result)

# ═══════════════════════════════════════════════════════════════════════════════
# CSS SCOPING FOR EMBEDDED HTML FILES
# ═══════════════════════════════════════════════════════════════════════════════

def scope_css(css_text, prefix):
    """Prefix all CSS selectors with a scoping class."""
    result = []
    in_media = False
    media_depth = 0
    i = 0
    rules = re.split(r'(?<=\})', css_text)
    for rule in rules:
        rule = rule.strip()
        if not rule:
            continue
        # Handle @keyframes - pass through unchanged
        if '@keyframes' in rule or '@-webkit-keyframes' in rule:
            result.append(rule)
            continue
        # Handle @media queries
        media_match = re.match(r'(@media[^{]+\{)(.*)', rule, re.DOTALL)
        if media_match:
            result.append(media_match.group(1))
            inner = media_match.group(2)
            if inner:
                inner = scope_css_rule(inner, prefix)
                result.append(inner)
            continue
        result.append(scope_css_rule(rule, prefix))
    return '\n'.join(result)

def scope_css_rule(rule, prefix):
    """Scope a single CSS rule."""
    # Split selector from body
    brace = rule.find('{')
    if brace == -1:
        return rule
    selector = rule[:brace].strip()
    body = rule[brace:]
    # Skip @rules
    if selector.startswith('@'):
        return rule
    # Replace body, :root, html, * selectors
    parts = [s.strip() for s in selector.split(',')]
    new_parts = []
    for part in parts:
        if part in ('body', ':root', 'html'):
            new_parts.append(f'.{prefix}')
        elif part == '*':
            new_parts.append(f'.{prefix} *')
        else:
            new_parts.append(f'.{prefix} {part}')
    return ', '.join(new_parts) + ' ' + body

def embed_html_file(filepath, embed_id):
    """Extract and scope an HTML file for inline embedding."""
    try:
        raw = read_file(filepath)
    except:
        return f'<p><em>Could not load {os.path.basename(filepath)}</em></p>'

    # Extract style content
    styles = re.findall(r'<style[^>]*>(.*?)</style>', raw, re.DOTALL)
    css_text = '\n'.join(styles)
    scoped_css = scope_css(css_text, embed_id)

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', raw, re.DOTALL)
    if body_match:
        body_content = body_match.group(1)
    else:
        # Try to get content after </head> or after last </style>
        head_end = raw.rfind('</style>')
        if head_end != -1:
            body_content = raw[head_end + 8:]
            body_content = re.sub(r'</head>|<body[^>]*>|</body>|</html>', '', body_content)
        else:
            body_content = raw

    # Clean up body content - remove script tags, we'll handle them separately
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', body_content, re.DOTALL)
    body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL)

    # Also extract scripts from outside body
    all_scripts = re.findall(r'<script[^>]*>(.*?)</script>', raw, re.DOTALL)
    script_text = '\n'.join(all_scripts)

    # Build the embedded section
    return f'''<div class="embedded-demo">
<div class="embed-toggle-bar">
    <button class="embed-toggle-btn" onclick="toggleEmbed('{embed_id}')">
        <span class="embed-icon">&#9654;</span> Interactive Demo: {os.path.basename(filepath).replace('.html','')}
    </button>
</div>
<div class="embed-wrapper" id="wrap-{embed_id}" style="display:none;">
    <style>{scoped_css}</style>
    <div class="{embed_id}">
        {body_content}
    </div>
    <script>(function(){{
        var wrapper = document.querySelector('.{embed_id}');
        if(!wrapper) return;
        {script_text.replace(chr(92) + "'", chr(92) + chr(92) + "'")}
    }})();</script>
</div>
</div>'''

# ═══════════════════════════════════════════════════════════════════════════════
# SVG DIAGRAM GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def svg(content, w=700, h=300):
    return f'<div class="svg-diagram"><svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{w}px;font-family:Segoe UI,sans-serif">{content}</svg></div>'

def svg_rect(x, y, w, h, label, color='var(--accent)', fill='var(--surface)'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{color}" stroke-width="2"/><text x="{x+w//2}" y="{y+h//2+5}" text-anchor="middle" fill="var(--text)" font-size="13">{label}</text>'

def svg_arrow(x1, y1, x2, y2, color='var(--accent)'):
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1
    length = (dx*dx + dy*dy) ** 0.5
    if length == 0:
        return ''
    ux, uy = dx/length, dy/length
    ax = x2 - ux*10 - uy*6
    ay = y2 - uy*10 + ux*6
    bx = x2 - ux*10 + uy*6
    by = y2 - uy*10 - ux*6
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"/><polygon points="{x2},{y2} {ax},{ay} {bx},{by}" fill="{color}"/>'

def svg_arrow_right(x1, y, x2, color='var(--accent)'):
    return svg_arrow(x1, y, x2, y, color)

def svg_arrow_down(x, y1, y2, color='var(--accent)'):
    return svg_arrow(x, y1, x, y2, color)

def svg_middleware_pipeline():
    """ASP.NET Middleware Pipeline diagram"""
    items = ['Request', 'Auth\nMiddleware', 'Routing\nMiddleware', 'CORS\nMiddleware', 'Endpoint\nMiddleware', 'Response']
    parts = []
    for i, label in enumerate(items):
        x = 10 + i * 115
        lines = label.split('\n')
        fill = 'var(--accent-bg)' if i in (0, 5) else 'var(--surface)'
        stroke = 'var(--success)' if i in (0, 5) else 'var(--accent)'
        parts.append(f'<rect x="{x}" y="30" width="100" height="55" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        for li, line in enumerate(lines):
            parts.append(f'<text x="{x+50}" y="{55 + li*16}" text-anchor="middle" fill="var(--text)" font-size="12">{line}</text>')
        if i < len(items) - 1:
            parts.append(svg_arrow_right(x + 100, 57, x + 115, 'var(--accent)'))
    # Return path
    parts.append(f'<path d="M 585 85 L 585 110 L 60 110 L 60 85" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-dasharray="5,5"/>')
    parts.append(f'<text x="320" y="125" text-anchor="middle" fill="var(--text-muted)" font-size="11">Response flows back through pipeline</text>')
    return svg('\n'.join(parts), 700, 140)

def svg_clean_architecture():
    """Clean Architecture concentric layers"""
    cx, cy = 250, 150
    layers = [(200, 'var(--accent-bg)', 'UI Layer', 'var(--accent)'),
              (150, 'var(--surface)', 'Service Layer', 'var(--warning)'),
              (90, 'var(--code-bg)', 'Domain / Data', 'var(--success)')]
    parts = []
    for r, fill, label, stroke in layers:
        parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r*0.6}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(f'<text x="{cx}" y="{cy - r*0.6 + 25}" text-anchor="middle" fill="{stroke}" font-size="13" font-weight="600">{label}</text>')
    parts.append(f'<text x="{cx}" y="{cy + 145}" text-anchor="middle" fill="var(--text-muted)" font-size="11">Dependencies point inward →</text>')
    return svg('\n'.join(parts), 500, 310)

def svg_type_constraints():
    """C# Generic type constraint hierarchy"""
    parts = []
    parts.append(svg_rect(250, 10, 200, 40, 'where T : ...'))
    constraints = [('class', 50, 'var(--accent)'), ('struct', 200, 'var(--warning)'),
                   ('new()', 350, 'var(--success)'), ('IInterface', 500, 'var(--info)')]
    for label, x, color in constraints:
        parts.append(f'<rect x="{x}" y="80" width="120" height="35" rx="6" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+60}" y="102" text-anchor="middle" fill="{color}" font-size="12" font-weight="600">{label}</text>')
        parts.append(svg_arrow_down(x + 60, 50, 80, color))
    return svg('\n'.join(parts), 680, 130)

def svg_bitfield():
    """Flags enum bitfield visualization"""
    parts = []
    bits = [('Read', '0001', 'var(--success)'), ('Write', '0010', 'var(--warning)'),
            ('Execute', '0100', 'var(--accent)'), ('Delete', '1000', 'var(--info)')]
    for i, (label, binary, color) in enumerate(bits):
        x = 10 + i * 165
        parts.append(f'<rect x="{x}" y="10" width="150" height="70" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+75}" y="35" text-anchor="middle" fill="{color}" font-size="14" font-weight="600">{label}</text>')
        parts.append(f'<text x="{x+75}" y="60" text-anchor="middle" fill="var(--text-muted)" font-size="18" font-family="monospace">{binary}</text>')
    # Combined example
    parts.append(f'<rect x="90" y="100" width="480" height="40" rx="6" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="330" y="125" text-anchor="middle" fill="var(--accent)" font-size="13">Read | Write | Execute = 0111 (7)</text>')
    return svg('\n'.join(parts), 670, 155)

def svg_async_flow():
    """Async/await flow diagram"""
    parts = []
    steps = [('Caller', 0), ('async Method', 140), ('await Task', 280), ('Thread Released', 420), ('Task Complete', 420), ('Resume', 560)]
    parts.append(f'<rect x="10" y="20" width="120" height="40" rx="8" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="70" y="45" text-anchor="middle" fill="var(--text)" font-size="12">Caller</text>')
    parts.append(svg_arrow_right(130, 40, 150, 'var(--accent)'))
    parts.append(f'<rect x="150" y="20" width="120" height="40" rx="8" fill="var(--surface)" stroke="var(--warning)" stroke-width="2"/>')
    parts.append(f'<text x="210" y="45" text-anchor="middle" fill="var(--text)" font-size="12">async Method</text>')
    parts.append(svg_arrow_right(270, 40, 290, 'var(--warning)'))
    parts.append(f'<rect x="290" y="20" width="120" height="40" rx="8" fill="var(--accent-bg)" stroke="var(--success)" stroke-width="2"/>')
    parts.append(f'<text x="350" y="45" text-anchor="middle" fill="var(--text)" font-size="12">await Task</text>')
    # Thread released line
    parts.append(f'<line x1="350" y1="60" x2="350" y2="85" stroke="var(--text-muted)" stroke-width="1.5" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="350" y="100" text-anchor="middle" fill="var(--success)" font-size="11">Thread released to pool</text>')
    # Resume
    parts.append(f'<path d="M 350 110 Q 350 130 470 130 L 470 40 L 490 40" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="4,4"/>')
    parts.append(f'<rect x="490" y="20" width="120" height="40" rx="8" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="550" y="45" text-anchor="middle" fill="var(--text)" font-size="12">Resume</text>')
    return svg('\n'.join(parts), 630, 145)

def svg_blazor_server():
    """Blazor Server architecture"""
    parts = []
    # Browser
    parts.append(f'<rect x="10" y="30" width="200" height="120" rx="10" fill="var(--surface)" stroke="var(--info)" stroke-width="2"/>')
    parts.append(f'<text x="110" y="55" text-anchor="middle" fill="var(--info)" font-size="14" font-weight="600">Browser</text>')
    parts.append(f'<text x="110" y="80" text-anchor="middle" fill="var(--text-muted)" font-size="11">Thin client</text>')
    parts.append(f'<text x="110" y="100" text-anchor="middle" fill="var(--text-muted)" font-size="11">DOM diffs via SignalR</text>')
    parts.append(f'<text x="110" y="120" text-anchor="middle" fill="var(--text-muted)" font-size="11">UI events sent to server</text>')
    # SignalR connection
    parts.append(f'<line x1="210" y1="70" x2="310" y2="70" stroke="var(--warning)" stroke-width="2.5"/>')
    parts.append(f'<line x1="210" y1="110" x2="310" y2="110" stroke="var(--warning)" stroke-width="2.5"/>')
    parts.append(f'<text x="260" y="62" text-anchor="middle" fill="var(--warning)" font-size="10">Events →</text>')
    parts.append(f'<text x="260" y="128" text-anchor="middle" fill="var(--warning)" font-size="10">← UI Diffs</text>')
    parts.append(f'<text x="260" y="155" text-anchor="middle" fill="var(--warning)" font-size="10" font-weight="600">SignalR</text>')
    # Server
    parts.append(f'<rect x="310" y="10" width="280" height="160" rx="10" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="450" y="35" text-anchor="middle" fill="var(--accent)" font-size="14" font-weight="600">Server</text>')
    # Circuit inside server
    parts.append(f'<rect x="325" y="45" width="250" height="50" rx="6" fill="var(--code-bg)" stroke="var(--success)" stroke-width="1.5"/>')
    parts.append(f'<text x="450" y="65" text-anchor="middle" fill="var(--success)" font-size="11" font-weight="600">Circuit (per user)</text>')
    parts.append(f'<text x="450" y="82" text-anchor="middle" fill="var(--text-muted)" font-size="10">Component tree + state in memory</text>')
    # Services
    parts.append(f'<rect x="325" y="105" width="120" height="35" rx="6" fill="var(--code-bg)" stroke="var(--text-muted)" stroke-width="1"/>')
    parts.append(f'<text x="385" y="127" text-anchor="middle" fill="var(--text-muted)" font-size="10">DI Services</text>')
    parts.append(f'<rect x="455" y="105" width="120" height="35" rx="6" fill="var(--code-bg)" stroke="var(--text-muted)" stroke-width="1"/>')
    parts.append(f'<text x="515" y="127" text-anchor="middle" fill="var(--text-muted)" font-size="10">EF Core / DB</text>')
    return svg('\n'.join(parts), 600, 180)

def svg_cookie_flow():
    """Cookie authentication flow"""
    parts = []
    steps = [('Login Form', 10, 'var(--info)'), ('Server Validates', 175, 'var(--warning)'),
             ('Set-Cookie', 340, 'var(--success)'), ('Browser Stores', 505, 'var(--accent)')]
    for label, x, color in steps:
        parts.append(f'<rect x="{x}" y="20" width="150" height="45" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+75}" y="48" text-anchor="middle" fill="{color}" font-size="12" font-weight="600">{label}</text>')
        if x < 505:
            parts.append(svg_arrow_right(x + 150, 42, x + 175, color))
    parts.append(f'<text x="330" y="90" text-anchor="middle" fill="var(--text-muted)" font-size="11">Subsequent requests include cookie automatically</text>')
    return svg('\n'.join(parts), 670, 105)

def svg_broadcast_vs_mailbox():
    """Static event broadcast vs scoped mailbox"""
    parts = []
    # Broadcast side
    parts.append(f'<text x="140" y="20" text-anchor="middle" fill="var(--accent)" font-size="13" font-weight="600">Static Event (Broadcast)</text>')
    parts.append(f'<rect x="90" y="30" width="100" height="35" rx="6" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="140" y="52" text-anchor="middle" fill="var(--text)" font-size="11">Event Source</text>')
    for i, label in enumerate(['User A', 'User B', 'User C']):
        y = 90 + i * 35
        parts.append(svg_arrow_down(140, 65 if i == 0 else y - 10, y, 'var(--accent)'))
        parts.append(f'<rect x="90" y="{y}" width="100" height="25" rx="4" fill="var(--surface)" stroke="var(--accent)" stroke-width="1"/>')
        parts.append(f'<text x="140" y="{y+16}" text-anchor="middle" fill="var(--text)" font-size="10">{label} hears ALL</text>')
    # Mailbox side
    parts.append(f'<text x="430" y="20" text-anchor="middle" fill="var(--success)" font-size="13" font-weight="600">Scoped Service (Mailbox)</text>')
    for i, label in enumerate(['User A', 'User B', 'User C']):
        y = 35 + i * 50
        parts.append(f'<rect x="350" y="{y}" width="70" height="30" rx="4" fill="var(--surface)" stroke="var(--success)" stroke-width="2"/>')
        parts.append(f'<text x="385" y="{y+19}" text-anchor="middle" fill="var(--text)" font-size="10">Source</text>')
        parts.append(svg_arrow_right(420, y + 15, 440, 'var(--success)'))
        parts.append(f'<rect x="440" y="{y}" width="80" height="30" rx="4" fill="var(--surface)" stroke="var(--success)" stroke-width="1"/>')
        parts.append(f'<text x="480" y="{y+19}" text-anchor="middle" fill="var(--text)" font-size="10">{label} only</text>')
    return svg('\n'.join(parts), 560, 195)

def svg_eager_vs_lazy():
    """Eager vs Lazy loading comparison"""
    parts = []
    # Eager side
    parts.append(f'<text x="150" y="20" text-anchor="middle" fill="var(--success)" font-size="13" font-weight="600">Eager Loading (.Include)</text>')
    parts.append(f'<rect x="50" y="30" width="200" height="40" rx="6" fill="var(--surface)" stroke="var(--success)" stroke-width="2"/>')
    parts.append(f'<text x="150" y="55" text-anchor="middle" fill="var(--text)" font-size="12">1 SQL Query (JOIN)</text>')
    parts.append(f'<rect x="50" y="80" width="200" height="30" rx="6" fill="var(--success)" stroke="var(--success)" stroke-width="1" opacity="0.2"/>')
    parts.append(f'<text x="150" y="100" text-anchor="middle" fill="var(--success)" font-size="11">All data loaded upfront</text>')
    # Lazy side
    parts.append(f'<text x="450" y="20" text-anchor="middle" fill="var(--warning)" font-size="13" font-weight="600">Lazy Loading (virtual)</text>')
    parts.append(f'<rect x="350" y="30" width="200" height="40" rx="6" fill="var(--surface)" stroke="var(--warning)" stroke-width="2"/>')
    parts.append(f'<text x="450" y="55" text-anchor="middle" fill="var(--text)" font-size="12">N+1 SQL Queries</text>')
    for i in range(3):
        y = 80 + i * 22
        parts.append(f'<rect x="{370 + i*15}" y="{y}" width="160" height="18" rx="4" fill="var(--warning)" stroke="var(--warning)" stroke-width="1" opacity="{0.15 + i*0.1}"/>')
        parts.append(f'<text x="{450 + i*7}" y="{y+13}" text-anchor="middle" fill="var(--warning)" font-size="9">Query on access #{i+1}</text>')
    return svg('\n'.join(parts), 600, 150)

def svg_solid_relationships():
    """SOLID principles relationship diagram"""
    parts = []
    principles = [('S', 'Single Resp.', 'var(--accent)'), ('O', 'Open/Closed', 'var(--warning)'),
                  ('L', 'Liskov Sub.', 'var(--success)'), ('I', 'Interface Seg.', 'var(--info)'),
                  ('D', 'Dependency Inv.', 'var(--accent2, #533483)')]
    for i, (letter, name, color) in enumerate(principles):
        x = 10 + i * 130
        parts.append(f'<rect x="{x}" y="10" width="120" height="65" rx="10" fill="var(--surface)" stroke="{color}" stroke-width="2.5"/>')
        parts.append(f'<text x="{x+60}" y="38" text-anchor="middle" fill="{color}" font-size="24" font-weight="700">{letter}</text>')
        parts.append(f'<text x="{x+60}" y="58" text-anchor="middle" fill="var(--text-muted)" font-size="10">{name}</text>')
    # Connection line
    parts.append(f'<line x1="70" y1="75" x2="590" y2="75" stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="330" y="95" text-anchor="middle" fill="var(--text-muted)" font-size="11">Together: maintainable, extensible, testable code</text>')
    return svg('\n'.join(parts), 660, 110)

def svg_strategy_pattern():
    """Strategy pattern class diagram"""
    parts = []
    parts.append(svg_rect(200, 10, 200, 50, 'IConflictDetector<T>'))
    parts.append(f'<text x="300" y="80" text-anchor="middle" fill="var(--text-muted)" font-size="10" font-style="italic">interface</text>')
    for i, impl in enumerate(['EmployeeDetector', 'EquipmentDetector', 'VehicleDetector']):
        x = 30 + i * 220
        parts.append(svg_rect(x, 100, 190, 40, impl))
        parts.append(svg_arrow(x + 95, 100, 300, 60, 'var(--accent)'))
    return svg('\n'.join(parts), 650, 155)

def svg_observer_pubsub():
    """Observer / pub-sub pattern"""
    parts = []
    parts.append(svg_rect(220, 10, 160, 50, 'Event Publisher'))
    for i, sub in enumerate(['Subscriber A', 'Subscriber B', 'Subscriber C']):
        x = 50 + i * 200
        parts.append(svg_rect(x, 100, 150, 40, sub))
        parts.append(svg_arrow(300, 60, x + 75, 100, 'var(--accent)'))
    parts.append(f'<text x="300" y="160" text-anchor="middle" fill="var(--text-muted)" font-size="11">One-to-many notification</text>')
    return svg('\n'.join(parts), 600, 175)

def svg_adapter():
    """Adapter pattern bridge diagram"""
    parts = []
    parts.append(svg_rect(10, 40, 140, 50, 'Client Code'))
    parts.append(svg_arrow_right(150, 65, 180, 'var(--accent)'))
    parts.append(svg_rect(180, 40, 140, 50, 'IEmailService'))
    parts.append(svg_arrow_right(320, 65, 350, 'var(--warning)'))
    parts.append(svg_rect(350, 10, 160, 45, 'SendGridAdapter'))
    parts.append(svg_rect(350, 65, 160, 45, 'MailGunAdapter'))
    parts.append(svg_arrow_right(510, 32, 540, 'var(--success)'))
    parts.append(svg_arrow_right(510, 87, 540, 'var(--success)'))
    parts.append(svg_rect(540, 10, 120, 45, 'SendGrid SDK'))
    parts.append(svg_rect(540, 65, 120, 45, 'MailGun SDK'))
    return svg('\n'.join(parts), 680, 120)

def svg_facade():
    """Facade wrapping subsystems"""
    parts = []
    # Facade
    parts.append(f'<rect x="200" y="10" width="200" height="50" rx="10" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<text x="300" y="40" text-anchor="middle" fill="var(--accent)" font-size="14" font-weight="600">Facade</text>')
    # Subsystems
    for i, name in enumerate(['Auth Service', 'Email Service', 'Logging', 'Database']):
        x = 30 + i * 160
        parts.append(svg_arrow_down(x + 60, 60, 80, 'var(--accent)'))
        parts.append(svg_rect(x, 80, 130, 40, name))
    return svg('\n'.join(parts), 670, 130)

def svg_builder_steps():
    """Fluent builder step-by-step construction"""
    parts = []
    steps = ['new Builder()', '.WithName(...)', '.WithEmail(...)', '.WithRole(...)', '.Build()']
    for i, step in enumerate(steps):
        x = 10 + i * 130
        color = 'var(--success)' if i == len(steps)-1 else 'var(--accent)'
        parts.append(f'<rect x="{x}" y="15" width="120" height="40" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+60}" y="40" text-anchor="middle" fill="{color}" font-size="10" font-weight="600">{step}</text>')
        if i < len(steps)-1:
            parts.append(svg_arrow_right(x + 120, 35, x + 130, 'var(--accent)'))
    return svg('\n'.join(parts), 670, 70)

def svg_repository_layer():
    """Repository pattern layer diagram"""
    parts = []
    layers = [('Controller / UI', 10, 'var(--info)'), ('Service Layer', 80, 'var(--warning)'),
              ('IRepository<T>', 150, 'var(--accent)'), ('EF Core DbContext', 220, 'var(--success)'),
              ('Database', 290, 'var(--text-muted)')]
    for label, y, color in layers:
        parts.append(f'<rect x="100" y="{y}" width="300" height="50" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="250" y="{y+30}" text-anchor="middle" fill="{color}" font-size="13" font-weight="600">{label}</text>')
        if y < 290:
            parts.append(svg_arrow_down(250, y + 50, y + 70, color))
    return svg('\n'.join(parts), 500, 350)

def svg_factory_creation():
    """Factory pattern creation flow"""
    parts = []
    parts.append(svg_rect(10, 50, 150, 45, 'Client Code'))
    parts.append(svg_arrow_right(160, 72, 190, 'var(--accent)'))
    parts.append(f'<rect x="190" y="30" width="160" height="85" rx="10" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<text x="270" y="55" text-anchor="middle" fill="var(--accent)" font-size="13" font-weight="600">Factory</text>')
    parts.append(f'<text x="270" y="75" text-anchor="middle" fill="var(--text-muted)" font-size="10">Create(type)</text>')
    parts.append(f'<text x="270" y="100" text-anchor="middle" fill="var(--text-muted)" font-size="10">Decides which class</text>')
    for i, product in enumerate(['Product A', 'Product B', 'Product C']):
        y = 20 + i * 45
        parts.append(svg_arrow_right(350, 72, 390, 'var(--success)'))
        parts.append(svg_rect(390, y, 130, 35, product))
    return svg('\n'.join(parts), 540, 160)

def svg_decorator_nesting():
    """Decorator pattern nesting"""
    parts = []
    layers = [('LoggingDecorator', 240, 'var(--info)', 0),
              ('CachingDecorator', 200, 'var(--warning)', 1),
              ('RetryDecorator', 160, 'var(--accent)', 2),
              ('Actual Service', 120, 'var(--success)', 3)]
    for label, w, color, depth in layers:
        x = 200 - w//2
        y = 10 + depth * 20
        h = 140 - depth * 35
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="200" y="{y + 18}" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{label}</text>')
    return svg('\n'.join(parts), 400, 155)

def svg_pipeline_chain():
    """Pipeline / Chain of Responsibility"""
    parts = []
    handlers = [('Validator', 'var(--info)'), ('Enricher', 'var(--warning)'),
                ('Resolver', 'var(--accent)'), ('Sender', 'var(--success)')]
    for i, (name, color) in enumerate(handlers):
        x = 10 + i * 160
        parts.append(f'<rect x="{x}" y="20" width="140" height="50" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+70}" y="50" text-anchor="middle" fill="{color}" font-size="12" font-weight="600">{name}</text>')
        if i < len(handlers) - 1:
            parts.append(svg_arrow_right(x + 140, 45, x + 160, color))
    parts.append(f'<text x="330" y="90" text-anchor="middle" fill="var(--text-muted)" font-size="11">Request flows through each handler in sequence</text>')
    return svg('\n'.join(parts), 660, 105)

def svg_export_matrix():
    """Two-dimensional strategy matrix"""
    parts = []
    # Headers
    formats = ['PDF', 'Excel', 'CSV']
    reports = ['Employee', 'Schedule', 'Financial']
    parts.append(f'<rect x="10" y="10" width="100" height="35" rx="4" fill="var(--code-bg)" stroke="var(--border)" stroke-width="1"/>')
    parts.append(f'<text x="60" y="32" text-anchor="middle" fill="var(--text-muted)" font-size="11">Report \\ Format</text>')
    for i, fmt in enumerate(formats):
        x = 120 + i * 120
        parts.append(f'<rect x="{x}" y="10" width="110" height="35" rx="4" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="1.5"/>')
        parts.append(f'<text x="{x+55}" y="32" text-anchor="middle" fill="var(--accent)" font-size="12" font-weight="600">{fmt}</text>')
    for j, report in enumerate(reports):
        y = 55 + j * 40
        parts.append(f'<rect x="10" y="{y}" width="100" height="30" rx="4" fill="var(--accent-bg)" stroke="var(--warning)" stroke-width="1.5"/>')
        parts.append(f'<text x="60" y="{y+20}" text-anchor="middle" fill="var(--warning)" font-size="11" font-weight="600">{report}</text>')
        for i in range(3):
            x = 120 + i * 120
            parts.append(f'<rect x="{x}" y="{y}" width="110" height="30" rx="4" fill="var(--surface)" stroke="var(--border)" stroke-width="1"/>')
            parts.append(f'<text x="{x+55}" y="{y+20}" text-anchor="middle" fill="var(--text-muted)" font-size="10">Strategy</text>')
    return svg('\n'.join(parts), 490, 180)

def svg_schedule_grid():
    """Generic schedule grid data provider architecture"""
    parts = []
    parts.append(svg_rect(180, 5, 220, 45, 'ScheduleGrid<T>'))
    parts.append(svg_arrow_down(290, 50, 70, 'var(--accent)'))
    parts.append(svg_rect(160, 70, 260, 40, 'IScheduleDataProvider<T>'))
    for i, impl in enumerate(['EmployeeProvider', 'EquipmentProvider', 'RoomProvider']):
        x = 20 + i * 210
        parts.append(svg_arrow_down(x + 95, 110, 125, 'var(--success)'))
        parts.append(svg_rect(x, 125, 190, 35, impl))
    return svg('\n'.join(parts), 650, 170)

def svg_role_hierarchy():
    """Role-based auth hierarchy"""
    parts = []
    roles = [('Admin', 'var(--accent)'), ('Manager', 'var(--warning)'), ('User', 'var(--success)')]
    for i, (role, color) in enumerate(roles):
        x = 150
        y = 10 + i * 60
        w = 200 - i * 30
        parts.append(f'<rect x="{x - w//2 + 100}" y="{y}" width="{w}" height="40" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="250" y="{y+25}" text-anchor="middle" fill="{color}" font-size="13" font-weight="600">{role}</text>')
        if i < 2:
            parts.append(svg_arrow_down(250, y + 40, y + 60, 'var(--text-muted)'))
    parts.append(f'<text x="400" y="45" fill="var(--text-muted)" font-size="10">Full access</text>')
    parts.append(f'<text x="400" y="105" fill="var(--text-muted)" font-size="10">Team access</text>')
    parts.append(f'<text x="400" y="165" fill="var(--text-muted)" font-size="10">Own data only</text>')
    return svg('\n'.join(parts), 500, 195)

def svg_three_layer_auth():
    """Three-tier authorization"""
    parts = []
    layers_data = [('Page Level', 'AuthorizeView / @attribute', 'var(--info)'),
               ('Component Level', 'CascadingAuthState', 'var(--warning)'),
               ('Service Level', 'ClaimsPrincipal checks', 'var(--accent)')]
    for i, (name, detail, color) in enumerate(layers_data):
        y = 10 + i * 65
        parts.append(f'<rect x="50" y="{y}" width="400" height="50" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="250" y="{y+22}" text-anchor="middle" fill="{color}" font-size="13" font-weight="600">{name}</text>')
        parts.append(f'<text x="250" y="{y+40}" text-anchor="middle" fill="var(--text-muted)" font-size="10">{detail}</text>')
        if i < 2:
            parts.append(svg_arrow_down(250, y + 50, y + 65, color))
    return svg('\n'.join(parts), 500, 210)

def svg_identity_architecture():
    """ASP.NET Identity architecture"""
    parts = []
    parts.append(svg_rect(170, 5, 200, 40, 'ASP.NET Identity'))
    # Sub-components
    comps = [('UserManager', 20, 'var(--accent)'), ('SignInManager', 175, 'var(--warning)'),
             ('RoleManager', 340, 'var(--success)'), ('UserStore', 500, 'var(--info)')]
    for name, x, color in comps:
        parts.append(svg_arrow_down(x + 65, 45, 65, color))
        parts.append(f'<rect x="{x}" y="65" width="130" height="40" rx="6" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+65}" y="90" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{name}</text>')
    # Database
    parts.append(f'<line x1="85" y1="105" x2="565" y2="105" stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="3,3"/>')
    parts.append(svg_arrow_down(270, 105, 125, 'var(--text-muted)'))
    parts.append(svg_rect(170, 125, 200, 35, 'Identity Database'))
    return svg('\n'.join(parts), 650, 170)

def svg_signalr_hub():
    """SignalR hub/group/connection diagram"""
    parts = []
    parts.append(f'<rect x="200" y="5" width="160" height="50" rx="10" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<text x="280" y="35" text-anchor="middle" fill="var(--accent)" font-size="14" font-weight="600">SignalR Hub</text>')
    # Groups
    groups = [('Group A', 80, 'var(--success)'), ('Group B', 360, 'var(--warning)')]
    for gname, gx, gcolor in groups:
        parts.append(f'<rect x="{gx}" y="80" width="160" height="85" rx="8" fill="var(--surface)" stroke="{gcolor}" stroke-width="2"/>')
        parts.append(f'<text x="{gx+80}" y="100" text-anchor="middle" fill="{gcolor}" font-size="12" font-weight="600">{gname}</text>')
        parts.append(svg_arrow(280, 55, gx + 80, 80, gcolor))
        for j in range(3):
            parts.append(f'<rect x="{gx+10+j*48}" y="110" width="44" height="22" rx="4" fill="var(--code-bg)" stroke="var(--text-muted)" stroke-width="1"/>')
            parts.append(f'<text x="{gx+32+j*48}" y="125" text-anchor="middle" fill="var(--text-muted)" font-size="8">Client</text>')
    return svg('\n'.join(parts), 560, 175)

def svg_notification_flow():
    """Notification system flow"""
    parts = []
    steps = [('Event Raised', 'var(--info)'), ('Resolve Recipients', 'var(--warning)'),
             ('Build Notification', 'var(--accent)'), ('Send via Hub', 'var(--success)')]
    for i, (name, color) in enumerate(steps):
        x = 10 + i * 155
        parts.append(f'<rect x="{x}" y="15" width="140" height="45" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+70}" y="43" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{name}</text>')
        if i < 3:
            parts.append(svg_arrow_right(x + 140, 37, x + 155, color))
    return svg('\n'.join(parts), 640, 75)

def svg_face_detection():
    """Facial recognition flow"""
    parts = []
    steps = [('Camera Feed', 'var(--info)'), ('JS face-api.js', 'var(--warning)'),
             ('Detect Faces', 'var(--accent)'), ('Match Identity', 'var(--success)'),
             ('Clock In/Out', 'var(--accent2, #533483)')]
    for i, (name, color) in enumerate(steps):
        x = 5 + i * 132
        parts.append(f'<rect x="{x}" y="15" width="122" height="45" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+61}" y="43" text-anchor="middle" fill="{color}" font-size="10" font-weight="600">{name}</text>')
        if i < 4:
            parts.append(svg_arrow_right(x + 122, 37, x + 132, color))
    return svg('\n'.join(parts), 670, 75)

def svg_production_system():
    """Factory floor production system"""
    parts = []
    components = [('Work Orders', 10, 'var(--info)'), ('Production Lines', 175, 'var(--accent)'),
                  ('Quality Control', 340, 'var(--warning)'), ('Inventory', 505, 'var(--success)')]
    for name, x, color in components:
        parts.append(f'<rect x="{x}" y="15" width="150" height="50" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+75}" y="45" text-anchor="middle" fill="{color}" font-size="12" font-weight="600">{name}</text>')
        if x < 505:
            parts.append(svg_arrow_right(x + 150, 40, x + 175, color))
    return svg('\n'.join(parts), 670, 80)

def svg_stock_system():
    """Stock service system"""
    parts = []
    parts.append(svg_rect(200, 5, 200, 45, 'Stock Service'))
    subs = [('Warehouses', 20, 'var(--info)'), ('Products', 175, 'var(--warning)'),
            ('Movements', 340, 'var(--accent)'), ('Alerts', 500, 'var(--success)')]
    for name, x, color in subs:
        parts.append(svg_arrow_down(x + 60, 50, 70, color))
        parts.append(f'<rect x="{x}" y="70" width="120" height="35" rx="6" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+60}" y="92" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{name}</text>')
    return svg('\n'.join(parts), 640, 115)

def svg_neural_network():
    """Neural network layers"""
    parts = []
    layer_sizes = [4, 6, 6, 3]
    layer_names = ['Input', 'Hidden 1', 'Hidden 2', 'Output']
    colors = ['var(--info)', 'var(--warning)', 'var(--accent)', 'var(--success)']
    for l, (size, name, color) in enumerate(zip(layer_sizes, layer_names, colors)):
        x = 50 + l * 150
        parts.append(f'<text x="{x}" y="15" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{name}</text>')
        for n in range(size):
            y = 30 + n * 30 + (6 - size) * 15
            parts.append(f'<circle cx="{x}" cy="{y}" r="10" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
            # Connections to next layer
            if l < len(layer_sizes) - 1:
                next_size = layer_sizes[l + 1]
                nx = 50 + (l + 1) * 150
                for nn in range(next_size):
                    ny = 30 + nn * 30 + (6 - next_size) * 15
                    parts.append(f'<line x1="{x+10}" y1="{y}" x2="{nx-10}" y2="{ny}" stroke="var(--border)" stroke-width="0.5" opacity="0.4"/>')
    return svg('\n'.join(parts), 550, 210)

def svg_sigmoid():
    """Sigmoid function plot"""
    parts = []
    # Axes
    parts.append(f'<line x1="50" y1="150" x2="450" y2="150" stroke="var(--text-muted)" stroke-width="1.5"/>')
    parts.append(f'<line x1="250" y1="10" x2="250" y2="190" stroke="var(--text-muted)" stroke-width="1.5"/>')
    # Labels
    parts.append(f'<text x="460" y="155" fill="var(--text-muted)" font-size="12">x</text>')
    parts.append(f'<text x="255" y="12" fill="var(--text-muted)" font-size="12">σ(x)</text>')
    parts.append(f'<text x="42" y="155" fill="var(--text-muted)" font-size="10">-6</text>')
    parts.append(f'<text x="448" y="155" fill="var(--text-muted)" font-size="10">6</text>')
    parts.append(f'<text x="236" y="30" fill="var(--text-muted)" font-size="10">1</text>')
    parts.append(f'<text x="236" y="150" fill="var(--text-muted)" font-size="10">0</text>')
    # Sigmoid curve approximation using path
    import math
    points = []
    for i in range(100):
        x_val = -6 + i * 12 / 99
        y_val = 1 / (1 + math.exp(-x_val))
        px = 50 + (x_val + 6) / 12 * 400
        py = 150 - y_val * 140
        points.append(f'{px:.1f},{py:.1f}')
    parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>')
    # 0.5 line
    parts.append(f'<line x1="50" y1="80" x2="450" y2="80" stroke="var(--warning)" stroke-width="1" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="460" y="83" fill="var(--warning)" font-size="10">0.5</text>')
    return svg('\n'.join(parts), 490, 200)

def svg_training_flow():
    """ML training flow"""
    parts = []
    steps = [('Training Data', 'var(--info)'), ('Forward Pass', 'var(--warning)'),
             ('Loss Calculation', 'var(--accent)'), ('Backpropagation', 'var(--success)'),
             ('Weight Update', 'var(--accent2, #533483)')]
    for i, (name, color) in enumerate(steps):
        x = 5 + i * 130
        parts.append(f'<rect x="{x}" y="15" width="120" height="45" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+60}" y="43" text-anchor="middle" fill="{color}" font-size="10" font-weight="600">{name}</text>')
        if i < 4:
            parts.append(svg_arrow_right(x + 120, 37, x + 130, color))
    # Loop back arrow
    parts.append(f'<path d="M 645 60 C 645 90 10 90 10 60" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="330" y="100" text-anchor="middle" fill="var(--text-muted)" font-size="10">Repeat for many epochs</text>')
    return svg('\n'.join(parts), 660, 115)

def svg_git_branching():
    """Git branching / merge flow"""
    parts = []
    # main branch line
    parts.append(f'<line x1="30" y1="40" x2="620" y2="40" stroke="var(--success)" stroke-width="3"/>')
    parts.append(f'<text x="15" y="20" fill="var(--success)" font-size="12" font-weight="700">main</text>')
    # Commits on main
    for cx in [60, 160, 400, 530, 600]:
        parts.append(f'<circle cx="{cx}" cy="40" r="8" fill="var(--success)" stroke="var(--bg)" stroke-width="2"/>')
    # feature branch
    parts.append(f'<line x1="160" y1="40" x2="200" y2="100" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<line x1="200" y1="100" x2="400" y2="100" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<line x1="400" y1="100" x2="400" y2="40" stroke="var(--accent)" stroke-width="2.5" stroke-dasharray="6,3"/>')
    parts.append(f'<text x="185" y="80" fill="var(--accent)" font-size="11" font-weight="600">feature/xyz</text>')
    for cx in [230, 300, 370]:
        parts.append(f'<circle cx="{cx}" cy="100" r="6" fill="var(--accent)" stroke="var(--bg)" stroke-width="2"/>')
    # merge arrow
    parts.append(f'<text x="410" y="70" fill="var(--warning)" font-size="10" font-weight="600">merge</text>')
    # hotfix branch
    parts.append(f'<line x1="530" y1="40" x2="550" y2="100" stroke="var(--warning)" stroke-width="2"/>')
    parts.append(f'<line x1="550" y1="100" x2="590" y2="100" stroke="var(--warning)" stroke-width="2"/>')
    parts.append(f'<line x1="590" y1="100" x2="600" y2="40" stroke="var(--warning)" stroke-width="2" stroke-dasharray="6,3"/>')
    parts.append(f'<text x="545" y="120" fill="var(--warning)" font-size="10">hotfix</text>')
    parts.append(f'<circle cx="570" cy="100" r="5" fill="var(--warning)" stroke="var(--bg)" stroke-width="2"/>')
    return svg('\n'.join(parts), 640, 135)

def svg_git_rebase():
    """Git rebase before/after"""
    parts = []
    # BEFORE label
    parts.append(f'<text x="10" y="18" fill="var(--text-muted)" font-size="12" font-weight="700">BEFORE rebase:</text>')
    # main
    parts.append(f'<line x1="30" y1="45" x2="300" y2="45" stroke="var(--success)" stroke-width="2.5"/>')
    for cx in [50, 120, 200, 280]:
        parts.append(f'<circle cx="{cx}" cy="45" r="6" fill="var(--success)" stroke="var(--bg)" stroke-width="2"/>')
    parts.append(f'<text x="310" y="49" fill="var(--success)" font-size="10">main</text>')
    # feature diverges
    parts.append(f'<line x1="120" y1="45" x2="145" y2="85" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<line x1="145" y1="85" x2="250" y2="85" stroke="var(--accent)" stroke-width="2"/>')
    for cx in [165, 210]:
        parts.append(f'<circle cx="{cx}" cy="85" r="5" fill="var(--accent)" stroke="var(--bg)" stroke-width="2"/>')
    parts.append(f'<text x="260" y="89" fill="var(--accent)" font-size="10">feature</text>')
    # Arrow
    parts.append(f'<text x="350" y="65" fill="var(--warning)" font-size="22">→</text>')
    # AFTER label
    parts.append(f'<text x="390" y="18" fill="var(--text-muted)" font-size="12" font-weight="700">AFTER rebase:</text>')
    # main + rebased feature on top
    parts.append(f'<line x1="410" y1="45" x2="660" y2="45" stroke="var(--success)" stroke-width="2.5"/>')
    for cx in [430, 490, 555, 620]:
        parts.append(f'<circle cx="{cx}" cy="45" r="6" fill="var(--success)" stroke="var(--bg)" stroke-width="2"/>')
    # Feature commits replayed on top
    parts.append(f'<line x1="620" y1="45" x2="700" y2="45" stroke="var(--accent)" stroke-width="2.5"/>')
    for cx in [650, 690]:
        parts.append(f'<circle cx="{cx}" cy="45" r="6" fill="var(--accent)" stroke="var(--bg)" stroke-width="2"/>')
    parts.append(f'<text x="660" y="30" fill="var(--accent)" font-size="10">feature (rebased)</text>')
    parts.append(f'<text x="490" y="70" fill="var(--success)" font-size="10">main</text>')
    return svg('\n'.join(parts), 720, 100)

def svg_git_remotes():
    """Git remote / clone / push / pull flow"""
    parts = []
    # Remote
    parts.append(f'<rect x="220" y="5" width="200" height="50" rx="10" fill="var(--accent-bg)" stroke="var(--accent)" stroke-width="2.5"/>')
    parts.append(f'<text x="320" y="25" text-anchor="middle" fill="var(--accent)" font-size="12" font-weight="700">Remote (origin)</text>')
    parts.append(f'<text x="320" y="42" text-anchor="middle" fill="var(--text-muted)" font-size="10">github.com/org/repo</text>')
    # Local
    parts.append(f'<rect x="50" y="100" width="180" height="50" rx="10" fill="var(--surface)" stroke="var(--success)" stroke-width="2"/>')
    parts.append(f'<text x="140" y="120" text-anchor="middle" fill="var(--success)" font-size="12" font-weight="600">Local Repo</text>')
    parts.append(f'<text x="140" y="138" text-anchor="middle" fill="var(--text-muted)" font-size="10">Working copy</text>')
    # Another dev
    parts.append(f'<rect x="410" y="100" width="180" height="50" rx="10" fill="var(--surface)" stroke="var(--warning)" stroke-width="2"/>')
    parts.append(f'<text x="500" y="120" text-anchor="middle" fill="var(--warning)" font-size="12" font-weight="600">Colleague</text>')
    parts.append(f'<text x="500" y="138" text-anchor="middle" fill="var(--text-muted)" font-size="10">Their clone</text>')
    # Arrows
    parts.append(f'<text x="100" y="85" fill="var(--success)" font-size="10" font-weight="600">push ↑  pull ↓</text>')
    parts.append(svg_arrow(140, 100, 280, 55, 'var(--success)'))
    parts.append(svg_arrow(300, 55, 140, 100, 'var(--text-muted)'))
    parts.append(svg_arrow(500, 100, 360, 55, 'var(--warning)'))
    parts.append(svg_arrow(340, 55, 500, 100, 'var(--text-muted)'))
    parts.append(f'<text x="460" y="85" fill="var(--warning)" font-size="10" font-weight="600">push ↑  pull ↓</text>')
    return svg('\n'.join(parts), 640, 165)

def svg_git_repo_separation():
    """Repository separation flow"""
    parts = []
    # Shared repo
    parts.append(f'<rect x="200" y="5" width="200" height="45" rx="8" fill="var(--surface)" stroke="var(--warning)" stroke-width="2.5"/>')
    parts.append(f'<text x="300" y="32" text-anchor="middle" fill="var(--warning)" font-size="12" font-weight="700">Shared Repo (A + B)</text>')
    # Arrow down splits
    parts.append(svg_arrow(250, 50, 130, 80, 'var(--success)'))
    parts.append(svg_arrow(350, 50, 470, 80, 'var(--accent)'))
    # Repo A
    parts.append(f'<rect x="50" y="80" width="160" height="45" rx="8" fill="var(--surface)" stroke="var(--success)" stroke-width="2"/>')
    parts.append(f'<text x="130" y="107" text-anchor="middle" fill="var(--success)" font-size="12" font-weight="600">Repo A (clean)</text>')
    # Repo B
    parts.append(f'<rect x="390" y="80" width="160" height="45" rx="8" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/>')
    parts.append(f'<text x="470" y="107" text-anchor="middle" fill="var(--accent)" font-size="12" font-weight="600">Repo B (clean)</text>')
    parts.append(f'<text x="300" y="148" text-anchor="middle" fill="var(--text-muted)" font-size="10">Full history preserved in both — independent versioning</text>')
    return svg('\n'.join(parts), 600, 160)

def svg_git_workflow():
    """Git daily workflow: edit → stage → commit → push"""
    parts = []
    steps = [('Working Dir', 'var(--info)'), ('Staging Area', 'var(--warning)'),
             ('Local Repo', 'var(--success)'), ('Remote Repo', 'var(--accent)')]
    cmds = ['git add', 'git commit', 'git push']
    for i, (name, color) in enumerate(steps):
        x = 10 + i * 160
        parts.append(f'<rect x="{x}" y="25" width="140" height="45" rx="8" fill="var(--surface)" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x+70}" y="53" text-anchor="middle" fill="{color}" font-size="11" font-weight="600">{name}</text>')
        if i < 3:
            parts.append(svg_arrow_right(x + 140, 47, x + 160, color))
            parts.append(f'<text x="{x+150}" y="22" text-anchor="middle" fill="var(--text-muted)" font-size="9" font-family="monospace">{cmds[i]}</text>')
    # git pull back arrow
    parts.append(f'<path d="M 490 70 C 490 100 170 100 170 70" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="330" y="110" text-anchor="middle" fill="var(--text-muted)" font-size="9" font-family="monospace">git pull (fetch + merge)</text>')
    return svg('\n'.join(parts), 660, 120)


# ═══════════════════════════════════════════════════════════════════════════════
# CALLOUT BOX HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def callout(type_name, title, content):
    """Generate a styled callout box. Types: analogy, insight, smell, rule, tldr"""
    icons = {'analogy': '&#x1f3ad;', 'insight': '&#x1f4a1;', 'smell': '&#x26a0;&#xfe0f;',
             'rule': '&#x2705;', 'tldr': '&#x1f4dd;'}
    return f'<div class="callout callout-{type_name}"><div class="callout-title">{icons.get(type_name, "")} {title}</div><div class="callout-body">{content}</div></div>'

def fordummies_panel(content_html):
    """Wrap content in a ForDummies-styled panel."""
    return content_html

# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORED CONTENT — NEW TOPICS
# ═══════════════════════════════════════════════════════════════════════════════

def content_blazor_fundamentals():
    return f'''
<h2>What is Blazor?</h2>
<p>Blazor is a framework for building interactive web UIs using C# instead of JavaScript. It runs on .NET and lets you share code between server and client.</p>

{callout('insight', 'Key Insight', 'Blazor lets C# developers build full-stack web apps without writing JavaScript. Components are <code class="il">.razor</code> files that mix HTML markup with C# code.')}

<h3>Server vs WebAssembly</h3>
<div class="tbl-wrap"><table>
<thead><tr><th>Feature</th><th>Blazor Server</th><th>Blazor WASM</th></tr></thead>
<tbody>
<tr><td>Execution</td><td>Server-side, DOM diffs via SignalR</td><td>Client-side, runs in browser</td></tr>
<tr><td>Initial Load</td><td>Fast (small download)</td><td>Slower (download .NET runtime)</td></tr>
<tr><td>Offline</td><td>No (requires connection)</td><td>Yes (after cached)</td></tr>
<tr><td>Server Resources</td><td>Memory per user (circuit)</td><td>Minimal server load</td></tr>
<tr><td>Latency</td><td>Every UI event → server round-trip</td><td>Instant (local execution)</td></tr>
</tbody></table></div>

{svg_blazor_server()}

<h3>Component Lifecycle</h3>
<pre><code class="lang-csharp">{highlight_csharp("""@page "/counter"

<h3>Count: @count</h3>
<button @onclick="Increment">Click me</button>

@code {
    private int count = 0;

    // Called when component is first initialized
    protected override async Task OnInitializedAsync()
    {
        // Load data from services
        await LoadData();
    }

    // Called after each render
    protected override void OnAfterRender(bool firstRender)
    {
        if (firstRender)
        {
            // JS interop calls go here
        }
    }

    private void Increment() => count++;
}""")}</code></pre>

{callout('rule', 'Golden Rule', '<strong>OnInitializedAsync</strong> runs once when the component loads. <strong>OnParametersSetAsync</strong> runs when parent passes new parameters. <strong>OnAfterRender</strong> runs after the DOM updates — use it for JS interop.')}

<h3>Key Concepts</h3>
<ul>
<li><strong>Parameters</strong> — Data passed from parent to child via <code class="il">[Parameter]</code> attributes</li>
<li><strong>EventCallback</strong> — Child-to-parent communication (like events in WPF)</li>
<li><strong>Cascading Values</strong> — Data that flows down the component tree without explicit passing</li>
<li><strong>RenderFragment</strong> — Allows components to accept child content (like slots in Vue)</li>
<li><strong>Dependency Injection</strong> — Services injected via <code class="il">@inject</code> directive</li>
</ul>
'''

def content_blazor_architecture():
    return f'''
<h2>Blazor Server Internals</h2>

<h3>Circuits</h3>
<p>Each user connection creates a <strong>circuit</strong> — a server-side unit that holds the component tree, state, and service instances. When a user interacts with the page, UI events travel over SignalR to the server, which processes them and sends back DOM diffs.</p>

{callout('insight', 'Key Insight', 'A circuit is essentially a "virtual browser tab" on the server. All your C# component code, event handlers, and DI-scoped services live in this circuit. If the SignalR connection drops, the circuit stays alive briefly (configurable) waiting for reconnection.')}

<h3>SignalR Transport</h3>
<p>Blazor Server uses SignalR WebSockets as its primary transport. The connection is persistent — every button click, text input, and dropdown selection sends a message to the server. The server processes the event, re-renders affected components, and sends a minimal diff back.</p>

<h3>Prerendering</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// In _Host.cshtml
<component type="typeof(App)" render-mode="ServerPrerendered" />

// ServerPrerendered = HTML rendered on server first (SEO friendly),
// then Blazor takes over when SignalR connects.
// Warning: OnInitializedAsync runs TWICE with prerendering!""")}</code></pre>

{callout('smell', 'Common Pitfall', 'With <code class="il">ServerPrerendered</code>, lifecycle methods run twice — once during prerender (no JS interop available!) and once when the circuit connects. Guard JS interop calls with <code class="il">firstRender</code> checks in <code class="il">OnAfterRender</code>.')}

<h3>Security Model</h3>
<ul>
<li><strong>Authentication State</strong> — Provided via <code class="il">AuthenticationStateProvider</code>, cascaded down the tree</li>
<li><strong>AuthorizeView</strong> — Component that conditionally renders based on auth state</li>
<li><strong>Circuit isolation</strong> — Each user&apos;s circuit is separate; no cross-circuit data leaks</li>
<li><strong>Anti-forgery</strong> — SignalR messages are inherently protected (no CSRF on WebSocket)</li>
</ul>

{callout('rule', 'Golden Rule', 'Never trust the client. Even though Blazor Server runs C# on the server, always validate at the service layer. The UI is just a presentation layer — authorization checks belong in your services.')}
'''

def content_solid_deep_dive():
    return f'''
<h2>SOLID Principles Deep Dive</h2>
{svg_solid_relationships()}

<h3>S — Single Responsibility Principle</h3>
<p><em>A class should have only one reason to change.</em></p>

{callout('smell', 'Violation', 'A class that validates, saves, AND sends email notifications — three reasons to change.')}

<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Multiple responsibilities
public class EmployeeService
{
    public void Save(Employee emp)
    {
        Validate(emp);           // Validation logic
        _dbContext.Save(emp);    // Persistence logic
        SendEmail(emp);          // Notification logic
    }
}

// GOOD: Single responsibility each
public class EmployeeValidator { public bool Validate(Employee emp) { ... } }
public class EmployeeRepository { public void Save(Employee emp) { ... } }
public class EmployeeNotifier { public void NotifyCreated(Employee emp) { ... } }

public class EmployeeService
{
    public void Save(Employee emp)
    {
        _validator.Validate(emp);
        _repository.Save(emp);
        _notifier.NotifyCreated(emp);
    }
}""")}</code></pre>

<h3>O — Open/Closed Principle</h3>
<p><em>Open for extension, closed for modification.</em></p>

{callout('insight', 'Key Insight', 'You should be able to add new behavior without changing existing code. This is achieved through interfaces, abstract classes, and polymorphism.')}

<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Must modify this switch every time
public decimal CalculateDiscount(string customerType, decimal amount)
{
    switch (customerType)
    {
        case "Regular": return amount * 0.05m;
        case "Premium": return amount * 0.10m;
        case "VIP":     return amount * 0.15m;  // Added later - modification!
    }
}

// GOOD: Add new types without changing existing code
public interface IDiscountStrategy
{
    decimal Calculate(decimal amount);
}

public class RegularDiscount : IDiscountStrategy
{
    public decimal Calculate(decimal amount) => amount * 0.05m;
}

// Adding VIP? Just add a new class - no existing code changes
public class VipDiscount : IDiscountStrategy
{
    public decimal Calculate(decimal amount) => amount * 0.15m;
}""")}</code></pre>

<h3>L — Liskov Substitution Principle</h3>
<p><em>Subtypes must be substitutable for their base types without altering correctness.</em></p>

<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Square violates Rectangle's contract
public class Rectangle
{
    public virtual int Width { get; set; }
    public virtual int Height { get; set; }
    public int Area => Width * Height;
}

public class Square : Rectangle
{
    public override int Width
    {
        set { base.Width = value; base.Height = value; } // Surprise!
    }
}

// Code expecting Rectangle behavior breaks:
Rectangle r = new Square();
r.Width = 5;
r.Height = 10;
// r.Area is 100, not 50! Contract violated.""")}</code></pre>

<h3>I — Interface Segregation Principle</h3>
<p><em>Clients should not be forced to depend on interfaces they don&apos;t use.</em></p>

<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Fat interface
public interface IWorker
{
    void Work();
    void Eat();       // Robots don't eat!
    void Sleep();     // Robots don't sleep!
}

// GOOD: Segregated interfaces
public interface IWorkable { void Work(); }
public interface IFeedable { void Eat(); }
public interface ISleepable { void Sleep(); }

public class HumanWorker : IWorkable, IFeedable, ISleepable { ... }
public class RobotWorker : IWorkable { ... }  // Only implements what it needs""")}</code></pre>

<h3>D — Dependency Inversion Principle</h3>
<p><em>High-level modules should not depend on low-level modules. Both should depend on abstractions.</em></p>

<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Direct dependency on concrete class
public class NotificationService
{
    private readonly SmtpEmailSender _sender = new SmtpEmailSender();
    public void Notify(string message) => _sender.Send(message);
}

// GOOD: Depend on abstraction
public class NotificationService
{
    private readonly IMessageSender _sender;
    public NotificationService(IMessageSender sender) => _sender = sender;
    public void Notify(string message) => _sender.Send(message);
}

// Now you can inject SmtpSender, SmsSender, PushNotificationSender, etc.
// And easily mock for testing!""")}</code></pre>
'''

def content_solid_fordummies():
    return f'''
{callout('analogy', 'SOLID Kitchen Analogy', """Think of SOLID like the rules of a well-organized kitchen:
<ul>
<li><strong>S</strong>ingle Responsibility = each cook has one station (grill cook grills, pastry chef bakes)</li>
<li><strong>O</strong>pen/Closed = you can add new menu items without rebuilding the kitchen</li>
<li><strong>L</strong>iskov = any substitute chef can work any station and produce the same quality</li>
<li><strong>I</strong>nterface Segregation = the grill cook&apos;s job description doesn&apos;t include washing dishes</li>
<li><strong>D</strong>ependency Inversion = recipes refer to "protein" not "chicken" — so you can swap ingredients</li>
</ul>""")}

{callout('tldr', 'TL;DR', 'SOLID makes your code easier to change, test, and understand. Each principle tackles a different kind of "code smell" — together, they prevent spaghetti code.')}
'''

def content_observer():
    return f'''
<h2>Observer Pattern — Event-Driven Communication</h2>
{svg_observer_pubsub()}

<p>The Observer pattern defines a one-to-many dependency between objects. When one object (the <strong>subject/publisher</strong>) changes state, all its dependents (the <strong>observers/subscribers</strong>) are notified automatically.</p>

{callout('insight', 'Key Insight', 'C# has the Observer pattern built into the language via <code class="il">event</code> and <code class="il">delegate</code>. Every time you write <code class="il">button.OnClick += handler</code>, you&apos;re using Observer.')}

<h3>C# Events as Native Observer</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// Publisher (Subject)
public class ScheduleService
{
    public event EventHandler<ScheduleChangedEventArgs> ScheduleChanged;

    public void UpdateSchedule(Schedule schedule)
    {
        // ... update logic ...
        ScheduleChanged?.Invoke(this, new ScheduleChangedEventArgs(schedule));
    }
}

// Subscriber (Observer)
public class NotificationListener
{
    public NotificationListener(ScheduleService service)
    {
        service.ScheduleChanged += OnScheduleChanged;
    }

    private void OnScheduleChanged(object sender, ScheduleChangedEventArgs e)
    {
        // React to the change
        SendNotification(e.Schedule);
    }
}""")}</code></pre>

<h3>When to Use</h3>
<ul>
<li>When changes in one object require updating others, and you don&apos;t know how many objects need updating</li>
<li>When an object should notify other objects without knowing who they are (loose coupling)</li>
<li>Event systems, notification systems, UI data binding, message buses</li>
</ul>

{callout('smell', 'Common Mistake', 'Forgetting to unsubscribe! In Blazor, always unsubscribe in <code class="il">Dispose()</code> to prevent memory leaks. A disposed component that&apos;s still subscribed to events will cause exceptions.')}
'''

def content_observer_fordummies():
    return callout('analogy', 'Newsletter Analogy', """Think of Observer like a newsletter subscription:
<ul>
<li>The <strong>magazine publisher</strong> (Subject) doesn&apos;t know who reads each issue</li>
<li><strong>Subscribers</strong> (Observers) sign up and get notified when a new issue comes out</li>
<li>Subscribers can <strong>unsubscribe</strong> anytime without the publisher caring</li>
<li>New subscribers can join without changing the publishing process</li>
</ul>
In code: the publisher raises an <code class="il">event</code>, and all subscribed methods get called.""")

def content_adapter_deep():
    return f'''
<h2>Adapter Pattern — Bridging Incompatible Interfaces</h2>
{svg_adapter()}

<p>The Adapter pattern lets classes with incompatible interfaces work together by wrapping one class&apos;s interface with another that clients expect.</p>

<h3>Real-World Example: Email Provider Swap</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// Your application's interface
public interface IEmailService
{
    Task SendAsync(string to, string subject, string body);
}

// Third-party SDK with incompatible interface
public class SendGridClient
{
    public Task SendEmailAsync(SendGridMessage message) { ... }
}

// Adapter bridges the gap
public class SendGridAdapter : IEmailService
{
    private readonly SendGridClient _client;

    public SendGridAdapter(SendGridClient client) => _client = client;

    public async Task SendAsync(string to, string subject, string body)
    {
        var message = new SendGridMessage
        {
            To = to, Subject = subject, HtmlContent = body
        };
        await _client.SendEmailAsync(message);
    }
}

// DI registration - swap providers by changing one line
services.AddScoped<IEmailService, SendGridAdapter>();
// Later: services.AddScoped<IEmailService, MailGunAdapter>();""")}</code></pre>
'''

def content_adapter_fordummies():
    return callout('analogy', 'Travel Adapter Analogy', 'Think of a power adapter when traveling abroad. Your laptop has a US plug, but the wall socket is European. The adapter doesn&apos;t change your laptop or the wall — it just translates between them. In code, an Adapter wraps a third-party library so your code can use it through your own interface.')

def content_facade():
    return f'''
<h2>Facade Pattern — Simplifying Complex Subsystems</h2>
{svg_facade()}

<p>A Facade provides a unified, simplified interface to a complex subsystem. It doesn&apos;t add new functionality — it just makes existing functionality easier to use.</p>

<pre><code class="lang-csharp">{highlight_csharp("""// Complex subsystem classes
public class AuthService { public bool ValidateUser(string token) { ... } }
public class InventoryService { public bool CheckStock(int productId) { ... } }
public class PaymentService { public bool ProcessPayment(decimal amount) { ... } }
public class ShippingService { public string CreateShipment(Order order) { ... } }

// Facade simplifies the workflow
public class OrderFacade
{
    private readonly AuthService _auth;
    private readonly InventoryService _inventory;
    private readonly PaymentService _payment;
    private readonly ShippingService _shipping;

    public OrderResult PlaceOrder(string token, Order order)
    {
        if (!_auth.ValidateUser(token))
            return OrderResult.Unauthorized();

        if (!_inventory.CheckStock(order.ProductId))
            return OrderResult.OutOfStock();

        if (!_payment.ProcessPayment(order.Total))
            return OrderResult.PaymentFailed();

        var trackingId = _shipping.CreateShipment(order);
        return OrderResult.Success(trackingId);
    }
}

// Client code is simple:
var result = _orderFacade.PlaceOrder(userToken, myOrder);""")}</code></pre>

{callout('insight', 'Key Insight', 'ASP.NET&apos;s <code class="il">WebApplicationBuilder</code> is a Facade — it hides the complexity of configuring Kestrel, DI, logging, configuration, and middleware behind a simple fluent API.')}
'''

def content_facade_fordummies():
    return callout('analogy', 'Hotel Concierge Analogy', 'A Facade is like a hotel concierge. Instead of calling the restaurant, taxi company, and theater box office yourself, you tell the concierge "I want dinner and a show tonight." The concierge handles all the complex coordination — you get a simple, unified interface to multiple services.')

def content_builder():
    return f'''
<h2>Builder Pattern — Step-by-Step Object Construction</h2>
{svg_builder_steps()}

<h3>The Problem: Telescoping Constructors</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// BAD: Constructor with too many parameters
var user = new User("John", "Doe", "john@email.com", "Admin",
                    true, false, DateTime.Now, null, "EN");
// What does 'true' mean? What's 'false'? Which null?""")}</code></pre>

<h3>The Solution: Fluent Builder</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public class UserBuilder
{
    private string _firstName, _lastName, _email, _role = "User";
    private bool _isActive = true;

    public UserBuilder WithName(string first, string last)
    {
        _firstName = first; _lastName = last;
        return this;
    }

    public UserBuilder WithEmail(string email)
    {
        _email = email;
        return this;
    }

    public UserBuilder WithRole(string role)
    {
        _role = role;
        return this;
    }

    public UserBuilder AsInactive()
    {
        _isActive = false;
        return this;
    }

    public User Build()
    {
        if (string.IsNullOrEmpty(_email))
            throw new InvalidOperationException("Email is required");
        return new User(_firstName, _lastName, _email, _role, _isActive);
    }
}

// Usage - self-documenting, readable
var admin = new UserBuilder()
    .WithName("John", "Doe")
    .WithEmail("john@company.com")
    .WithRole("Admin")
    .Build();""")}</code></pre>

<h3>Real .NET Builders</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// WebApplicationBuilder
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddRazorPages();
builder.Services.AddSignalR();
var app = builder.Build();

// DbContextOptionsBuilder
services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString)
           .EnableSensitiveDataLogging()
           .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));

// IHostBuilder
Host.CreateDefaultBuilder(args)
    .ConfigureWebHostDefaults(web => web.UseStartup<Startup>())
    .ConfigureLogging(log => log.AddConsole())
    .Build();""")}</code></pre>

{callout('smell', 'Common Mistakes', '<ul><li>Mutable products — once <code class="il">Build()</code> is called, the result should be immutable</li><li>No validation in <code class="il">Build()</code> — always validate required fields before constructing</li><li>Returning the product instead of the builder from setter methods (breaks chaining)</li></ul>')}
'''

def content_builder_fordummies():
    return callout('analogy', 'Custom Burger Analogy', """Imagine ordering a custom burger: "I&apos;ll have the brioche bun, double patty, extra cheese, no onions, BBQ sauce."
<ul>
<li>Each topping choice is a <code class="il">.With...()</code> call</li>
<li>You can add toppings in any order</li>
<li>At the end, <code class="il">.Build()</code> hands you your completed burger</li>
<li>You can&apos;t get a burger without at least a bun and patty (validation)</li>
</ul>
That&apos;s a fluent builder — step-by-step construction with a clear, readable API.""")

def content_repository():
    return f'''
<h2>Repository Pattern — Abstracting Data Access</h2>
{svg_repository_layer()}

<p>The Repository pattern mediates between the domain/service layer and the data mapping layer (EF Core), acting like an in-memory collection of domain objects.</p>

<h3>Generic Repository</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public interface IRepository<T> where T : class
{
    Task<T?> GetByIdAsync(int id);
    Task<IEnumerable<T>> GetAllAsync();
    Task<IEnumerable<T>> FindAsync(Expression<Func<T, bool>> predicate);
    Task AddAsync(T entity);
    void Update(T entity);
    void Remove(T entity);
}

public class Repository<T> : IRepository<T> where T : class
{
    protected readonly DbContext _context;
    protected readonly DbSet<T> _dbSet;

    public Repository(DbContext context)
    {
        _context = context;
        _dbSet = context.Set<T>();
    }

    public async Task<T?> GetByIdAsync(int id)
        => await _dbSet.FindAsync(id);

    public async Task<IEnumerable<T>> GetAllAsync()
        => await _dbSet.ToListAsync();

    public async Task<IEnumerable<T>> FindAsync(Expression<Func<T, bool>> predicate)
        => await _dbSet.Where(predicate).ToListAsync();

    public async Task AddAsync(T entity) => await _dbSet.AddAsync(entity);
    public void Update(T entity) => _dbSet.Update(entity);
    public void Remove(T entity) => _dbSet.Remove(entity);
}""")}</code></pre>

<h3>Unit of Work</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public interface IUnitOfWork : IDisposable
{
    IRepository<Employee> Employees { get; }
    IRepository<Schedule> Schedules { get; }
    Task<int> SaveChangesAsync();
}

// Usage in service:
public async Task TransferEmployee(int empId, int newDeptId)
{
    var emp = await _unitOfWork.Employees.GetByIdAsync(empId);
    emp.DepartmentId = newDeptId;
    _unitOfWork.Employees.Update(emp);
    await _unitOfWork.SaveChangesAsync();  // Single transaction
}""")}</code></pre>

{callout('smell', 'Anti-Pattern Warning', 'Don&apos;t create a generic repository that just wraps DbContext 1:1. If your repository methods are just <code class="il">GetAll()</code>, <code class="il">GetById()</code>, <code class="il">Add()</code>, <code class="il">Delete()</code> — you&apos;re adding a layer without value. Add domain-specific methods like <code class="il">GetActiveEmployeesByDepartment()</code>.')}
'''

def content_repository_fordummies():
    return callout('analogy', 'Library Analogy', 'A Repository is like a librarian. You don&apos;t go into the stacks yourself — you tell the librarian "I need all books by Author X published after 2020." The librarian knows <em>where</em> and <em>how</em> to find them. If the library switches from Dewey Decimal to a digital system, your request stays the same — only the librarian&apos;s internal process changes.')

def content_factory():
    return f'''
<h2>Factory Pattern — Encapsulating Object Creation</h2>
{svg_factory_creation()}

<h3>Level 1: Simple Factory</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public static class NotificationFactory
{
    public static INotification Create(string type) => type switch
    {
        "email" => new EmailNotification(),
        "sms"   => new SmsNotification(),
        "push"  => new PushNotification(),
        _ => throw new ArgumentException($"Unknown type: {type}")
    };
}""")}</code></pre>

<h3>Level 2: Factory Method</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public abstract class ReportGenerator
{
    // Factory method - subclasses decide which report to create
    protected abstract IReport CreateReport();

    public void Generate(ReportData data)
    {
        var report = CreateReport();
        report.Build(data);
        report.Export();
    }
}

public class PdfReportGenerator : ReportGenerator
{
    protected override IReport CreateReport() => new PdfReport();
}

public class ExcelReportGenerator : ReportGenerator
{
    protected override IReport CreateReport() => new ExcelReport();
}""")}</code></pre>

<h3>Level 3: Abstract Factory</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public interface IUIFactory
{
    IButton CreateButton();
    ITextBox CreateTextBox();
    IDropdown CreateDropdown();
}

public class MaterialUIFactory : IUIFactory
{
    public IButton CreateButton() => new MaterialButton();
    public ITextBox CreateTextBox() => new MaterialTextBox();
    public IDropdown CreateDropdown() => new MaterialDropdown();
}

public class BootstrapUIFactory : IUIFactory
{
    public IButton CreateButton() => new BootstrapButton();
    public ITextBox CreateTextBox() => new BootstrapTextBox();
    public IDropdown CreateDropdown() => new BootstrapDropdown();
}

// Usage - entire UI family created consistently
public class FormBuilder
{
    public Form Build(IUIFactory factory)
    {
        var form = new Form();
        form.Add(factory.CreateTextBox());  // Always consistent family
        form.Add(factory.CreateButton());
        return form;
    }
}""")}</code></pre>

{callout('tldr', 'Progression', '<strong>Simple Factory</strong>: one method, switch/match. <strong>Factory Method</strong>: subclass decides. <strong>Abstract Factory</strong>: family of related objects. Choose the simplest level that fits your needs.')}
'''

def content_factory_fordummies():
    return callout('analogy', 'Pizza Shop Analogy', """<ul>
<li><strong>Simple Factory</strong> = ordering at a counter: "One Margherita please." The kitchen knows how to make it.</li>
<li><strong>Factory Method</strong> = franchise model: each city&apos;s kitchen makes pizza their own way, but all follow the same menu.</li>
<li><strong>Abstract Factory</strong> = themed restaurant chain: Italian branch makes Italian pizzas AND Italian desserts; Japanese branch makes Japanese pizzas AND Japanese desserts — everything in a family is consistent.</li>
</ul>""")

def content_decorator():
    return f'''
<h2>Decorator Pattern — Wrapping Behavior Dynamically</h2>
{svg_decorator_nesting()}

<p>The Decorator pattern attaches additional responsibilities to an object dynamically. It provides a flexible alternative to subclassing for extending functionality.</p>

<h3>Classic Example: Logging + Caching + Retry</h3>
<pre><code class="lang-csharp">{highlight_csharp("""public interface IUserService
{
    Task<User> GetByIdAsync(int id);
}

// Core implementation
public class UserService : IUserService
{
    public async Task<User> GetByIdAsync(int id)
        => await _dbContext.Users.FindAsync(id);
}

// Logging decorator
public class LoggingUserService : IUserService
{
    private readonly IUserService _inner;
    private readonly ILogger _logger;

    public LoggingUserService(IUserService inner, ILogger logger)
    {
        _inner = inner; _logger = logger;
    }

    public async Task<User> GetByIdAsync(int id)
    {
        _logger.LogInformation("Getting user {Id}", id);
        var result = await _inner.GetByIdAsync(id);
        _logger.LogInformation("Found user {Name}", result?.Name);
        return result;
    }
}

// Caching decorator
public class CachingUserService : IUserService
{
    private readonly IUserService _inner;
    private readonly IMemoryCache _cache;

    public async Task<User> GetByIdAsync(int id)
    {
        return await _cache.GetOrCreateAsync($"user-{id}",
            entry => { entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
                       return _inner.GetByIdAsync(id); });
    }
}

// DI composition - decorators wrap like Russian dolls
services.AddScoped<UserService>();
services.AddScoped<IUserService>(sp =>
    new LoggingUserService(
        new CachingUserService(
            sp.GetRequiredService<UserService>(),
            sp.GetRequiredService<IMemoryCache>()),
        sp.GetRequiredService<ILogger<LoggingUserService>>()));""")}</code></pre>

{callout('insight', 'Key Insight', 'ASP.NET middleware IS the Decorator pattern. Each middleware wraps the next, adding behavior (auth, logging, CORS) around the core request handler. The <code class="il">next()</code> call invokes the inner decorator.')}
'''

def content_decorator_fordummies():
    return callout('analogy', 'Gift Wrapping Analogy', 'Think of decorators like wrapping a gift. You start with the present (core service), wrap it in tissue paper (caching), then a box (logging), then gift wrap (retry logic). Each layer adds something without changing what&apos;s inside. You can add or remove layers independently.')

def content_identity_expansion():
    return f'''
<h2>ASP.NET Identity System</h2>
{svg_identity_architecture()}

<h3>Core Components</h3>
<div class="tbl-wrap"><table>
<thead><tr><th>Component</th><th>Role</th><th>Key Methods</th></tr></thead>
<tbody>
<tr><td><strong>UserManager&lt;T&gt;</strong></td><td>CRUD operations on users</td><td>CreateAsync, FindByEmailAsync, AddToRoleAsync</td></tr>
<tr><td><strong>SignInManager&lt;T&gt;</strong></td><td>Authentication workflows</td><td>PasswordSignInAsync, SignOutAsync</td></tr>
<tr><td><strong>RoleManager&lt;T&gt;</strong></td><td>Role management</td><td>CreateAsync, RoleExistsAsync</td></tr>
<tr><td><strong>UserStore</strong></td><td>Persistence (EF Core)</td><td>Implements IUserStore interfaces</td></tr>
</tbody></table></div>

<h3>Configuration</h3>
<pre><code class="lang-csharp">{highlight_csharp("""builder.Services.AddIdentity<ApplicationUser, IdentityRole>(options =>
{
    options.Password.RequiredLength = 8;
    options.Password.RequireDigit = true;
    options.Password.RequireUppercase = true;
    options.Lockout.MaxFailedAccessAttempts = 5;
    options.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(15);
    options.User.RequireUniqueEmail = true;
})
.AddEntityFrameworkStores<AppDbContext>()
.AddDefaultTokenProviders();""")}</code></pre>

{callout('rule', 'Golden Rule', 'Never implement your own password hashing, token generation, or session management. Identity handles all of this securely. Focus on configuring it correctly for your business rules.')}
'''

def content_testing_consolidated():
    return f'''
<h2>Unit Testing in .NET — Complete Guide</h2>

<h3>Project Setup</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// 1. Create test project
// dotnet new xunit -n MyApp.Tests
// dotnet add reference ../MyApp/MyApp.csproj
// dotnet add package Moq
// dotnet add package FluentAssertions

// 2. Naming convention: MethodName_Scenario_ExpectedResult
[Fact]
public async Task GetById_ExistingUser_ReturnsUser()
{
    // Arrange
    var mockRepo = new Mock<IUserRepository>();
    mockRepo.Setup(r => r.GetByIdAsync(1))
            .ReturnsAsync(new User { Id = 1, Name = "John" });
    var service = new UserService(mockRepo.Object);

    // Act
    var result = await service.GetByIdAsync(1);

    // Assert
    result.Should().NotBeNull();
    result.Name.Should().Be("John");
}""")}</code></pre>

<h3>AAA Pattern (Arrange-Act-Assert)</h3>
<ul>
<li><strong>Arrange</strong> — Set up test data, mocks, and the system under test</li>
<li><strong>Act</strong> — Call the method being tested</li>
<li><strong>Assert</strong> — Verify the result matches expectations</li>
</ul>

<h3>Mocking with Moq</h3>
<pre><code class="lang-csharp">{highlight_csharp("""// Mock setup
var mockService = new Mock<IEmailService>();
mockService.Setup(s => s.SendAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<string>()))
           .ReturnsAsync(true);

// Verify interaction
mockService.Verify(s => s.SendAsync("admin@test.com", It.IsAny<string>(), It.IsAny<string>()),
    Times.Once);

// Mock with callback
mockService.Setup(s => s.SendAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<string>()))
           .Callback<string, string, string>((to, subj, body) =>
           {
               // Inspect arguments
               Assert.Contains("Welcome", subj);
           })
           .ReturnsAsync(true);""")}</code></pre>

<h3>Theory Tests (Parameterized)</h3>
<pre><code class="lang-csharp">{highlight_csharp("""[Theory]
[InlineData("", false)]           // Empty email = invalid
[InlineData("notanemail", false)] // No @ = invalid
[InlineData("user@test.com", true)] // Valid
public void IsValidEmail_VariousInputs_ReturnsExpected(string email, bool expected)
{
    var result = EmailValidator.IsValid(email);
    result.Should().Be(expected);
}""")}</code></pre>

{callout('rule', 'Testing Best Practices', '<ul><li>Test behavior, not implementation details</li><li>One assertion per test (or one logical assertion)</li><li>Don&apos;t test framework code (EF Core, ASP.NET internals)</li><li>Use in-memory database for integration tests, mocks for unit tests</li><li>Name tests clearly: <code class="il">MethodName_Scenario_ExpectedResult</code></li></ul>')}
'''

# ═══════════════════════════════════════════════════════════════════════════════
# GIT CONTENT — AUTHORED
# ═══════════════════════════════════════════════════════════════════════════════

def content_git_fundamentals():
    return f'''
<h3>What is Git?</h3>
<p>Git is a <strong>distributed version control system</strong>. Every developer has a full copy of the repository, including its entire history. There is no single point of failure — if the server goes down, any clone can restore the project.</p>

{callout('analogy', 'Think of It Like This', 'Imagine a shared Google Doc, but instead of everyone editing the same document simultaneously, each person has their own complete copy. They work independently, then periodically merge their changes together. The "merge" step is where Git shines — it tracks exactly what changed, when, and by whom.')}

<h3>The Three Areas</h3>
<p>Git manages your code through three conceptual areas:</p>

{svg_git_workflow()}

<table class="comparison-table">
<thead><tr><th>Area</th><th>What It Is</th><th>Analogy</th></tr></thead>
<tbody>
<tr><td><strong>Working Directory</strong></td><td>Your actual files on disk — what you see in your editor</td><td>Your desk with papers spread out</td></tr>
<tr><td><strong>Staging Area (Index)</strong></td><td>A snapshot of what will go into the next commit</td><td>An envelope where you place the papers you want to mail</td></tr>
<tr><td><strong>Repository (.git)</strong></td><td>The full history of all committed snapshots</td><td>The filing cabinet that stores every envelope ever mailed</td></tr>
</tbody></table>

<h3>Essential Commands</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Check what's changed
git status                    # Overview of modified/staged/untracked files
git diff                      # See unstaged changes (line-by-line)
git diff --staged             # See what's staged for commit

# Stage changes
git add MyFile.cs             # Stage a specific file
git add src/Services/         # Stage all changes in a directory
git add -p                    # Interactively stage hunks (partial file staging)

# Commit
git commit -m "Add user validation to login service"
git commit --amend            # Modify the last commit (message or files)

# View history
git log --oneline -20         # Last 20 commits, compact
git log --graph --all         # Visual branch graph
git log --author="Luis"       # Filter by author
git show abc1234              # Full details of a specific commit""")}</code></pre>

{callout('rule', 'Commit Messages Matter', '<strong>Bad:</strong> <code class="il">fix stuff</code>, <code class="il">updates</code>, <code class="il">WIP</code><br><strong>Good:</strong> <code class="il">Fix null reference in ScheduleService when employee has no shifts</code><br><br>A good commit message tells you <em>what changed</em> and <em>why</em> — not just that something changed. Your future self will thank you.')}

<h3>Configuration</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Identity (required for commits)
git config --global user.name "Your Name"
git config --global user.email "your.email@company.com"

# Useful defaults
git config --global init.defaultBranch main        # Use 'main' not 'master'
git config --global pull.rebase true               # Rebase on pull (cleaner history)
git config --global push.autoSetupRemote true       # Auto-track new branches
git config --global core.autocrlf true              # Line endings (Windows)

# Aliases (shortcuts)
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br "branch -a"
git config --global alias.lg "log --oneline --graph --all -20"
git config --global alias.last "log -1 HEAD --stat"

# Check your config
git config --global --list""")}</code></pre>

{callout('insight', 'Config Levels', '<code class="il">--global</code> applies to all repos for your user account (stored in <code class="il">~/.gitconfig</code>).<br><code class="il">--local</code> (default) applies only to the current repo (stored in <code class="il">.git/config</code>).<br>Local settings override global settings.')}

<h3>.gitignore — What NOT to Track</h3>
<pre><code class="lang-bash">{highlight_csharp("""# .gitignore for .NET projects
bin/
obj/
*.user
*.suo
.vs/
*.db
appsettings.Development.json
wwwroot/lib/

# Common additions
node_modules/
.env
*.log
*.bak""")}</code></pre>

{callout('smell', 'Never Commit These', 'Secrets (<code class="il">appsettings.json</code> with connection strings, <code class="il">.env</code> files), build outputs (<code class="il">bin/</code>, <code class="il">obj/</code>), IDE folders (<code class="il">.vs/</code>), or massive binary files. If you accidentally commit a secret, <strong>rotating the secret is mandatory</strong> — removing it from history isn&apos;t enough because it lives in git reflog and any existing clone.')}
'''


def content_git_fundamentals_fordummies():
    return f'''
{callout('analogy', 'Git in 30 Seconds', 'Git is like a time machine for your code. Every time you <strong>commit</strong>, you take a snapshot. You can always go back to any snapshot. You can create parallel timelines (<strong>branches</strong>) to try new things without risking the main timeline.')}
<p><strong>The daily workflow is just 4 steps:</strong></p>
<ol>
<li><strong>Edit</strong> your files normally in your editor</li>
<li><code class="il">git add</code> — put your changes in an envelope</li>
<li><code class="il">git commit</code> — seal the envelope with a label</li>
<li><code class="il">git push</code> — mail the envelope to the shared repository</li>
</ol>
<p>That&apos;s it. Everything else (branches, merges, rebases) builds on this.</p>
'''


def content_git_branching():
    return f'''
<h3>Why Branches?</h3>
<p>Branches let you work on features, fixes, and experiments <strong>without affecting the main codebase</strong>. They&apos;re lightweight (just a pointer to a commit) and fast to create.</p>

{svg_git_branching()}

<h3>Branch Operations</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Create and switch
git branch feature/add-leave-calendar     # Create branch
git checkout feature/add-leave-calendar   # Switch to it
git checkout -b feature/add-leave-calendar # Both in one command (shorthand)
git switch -c feature/add-leave-calendar   # Modern alternative (Git 2.23+)

# List branches
git branch            # Local branches
git branch -a         # All branches (including remote-tracking)
git branch -v         # With last commit info
git branch --merged   # Branches already merged into current

# Delete branches
git branch -d feature/old-feature        # Safe delete (only if merged)
git branch -D feature/old-feature        # Force delete (even if unmerged)
git push origin --delete feature/old     # Delete remote branch""")}</code></pre>

<h3>Merging</h3>
<p>Merging combines the work from one branch into another.</p>

<pre><code class="lang-bash">{highlight_csharp("""# Merge feature into main
git checkout main
git merge feature/add-leave-calendar

# If there are conflicts:
# 1. Git marks conflicted files
# 2. Open them — look for <<<<<<< ======= >>>>>>> markers
# 3. Edit to resolve (keep what you want)
# 4. Stage resolved files: git add ConflictedFile.cs
# 5. Complete the merge: git commit""")}</code></pre>

<h4>Merge Strategies</h4>
<table class="comparison-table">
<thead><tr><th>Strategy</th><th>When It Happens</th><th>Result</th></tr></thead>
<tbody>
<tr><td><strong>Fast-forward</strong></td><td>Target branch has no new commits since branching</td><td>Branch pointer simply moves forward — no merge commit</td></tr>
<tr><td><strong>Three-way merge</strong></td><td>Both branches have new commits</td><td>Creates a merge commit with two parents</td></tr>
<tr><td><strong>Squash merge</strong></td><td><code class="il">git merge --squash</code></td><td>Combines all branch commits into one — cleaner history, loses individual commits</td></tr>
</tbody></table>

{callout('insight', 'Fast-Forward vs Merge Commit', 'Some teams always use <code class="il">--no-ff</code> (no fast-forward) to preserve the fact that a feature was developed on a separate branch. This creates a merge commit even when fast-forward is possible, making the history more informative.')}

<h3>Branching Strategies</h3>
<h4>Git Flow (Traditional)</h4>
<pre><code class="lang-bash">{highlight_csharp("""main          ─── stable, production-ready
  └─ develop   ─── integration branch
       ├─ feature/X  ─── new features branch from develop
       ├─ release/1.2 ─── stabilization before release
       └─ hotfix/Y   ─── urgent fixes from main""")}</code></pre>

<h4>GitHub Flow (Simpler)</h4>
<pre><code class="lang-bash">{highlight_csharp("""main          ─── always deployable
  ├─ feature/X  ─── branch from main, PR back to main
  └─ fix/Y      ─── branch from main, PR back to main""")}</code></pre>

{callout('rule', 'Branch Naming Convention', 'Use prefixes: <code class="il">feature/</code>, <code class="il">fix/</code>, <code class="il">hotfix/</code>, <code class="il">refactor/</code>, <code class="il">chore/</code>. Include ticket numbers when applicable: <code class="il">feature/JIRA-1234-add-leave-calendar</code>. Keep names lowercase with hyphens.')}
'''


def content_git_branching_fordummies():
    return f'''
{callout('analogy', 'Branches Are Parallel Universes', 'Imagine you&apos;re writing a book. Instead of editing your only copy, you photocopy the whole manuscript. Now you can experiment freely — rewrite Chapter 3, add a new character, try a different ending. If it works out, you merge it back into the original. If not, you throw the copy away. Nothing was lost.')}
<p><strong>The 3 commands you&apos;ll use 90% of the time:</strong></p>
<ol>
<li><code class="il">git checkout -b my-feature</code> — create a branch and switch to it</li>
<li><em>...do your work, commit normally...</em></li>
<li><code class="il">git checkout main && git merge my-feature</code> — merge back when done</li>
</ol>
'''


def content_git_rebasing():
    return f'''
<h3>What is Rebasing?</h3>
<p>Rebasing <strong>replays your commits on top of another branch</strong>. Instead of creating a merge commit, it rewrites history to make it look like you branched from the latest point.</p>

{svg_git_rebase()}

<h3>Basic Rebase</h3>
<pre><code class="lang-bash">{highlight_csharp("""# You're on feature/calendar, main has moved ahead
git checkout feature/calendar
git rebase main

# What happens:
# 1. Git finds the common ancestor of feature/calendar and main
# 2. Saves your feature commits aside (as patches)
# 3. Resets feature/calendar to point at main's latest
# 4. Replays your commits one by one on top

# After rebase, merge into main is a clean fast-forward:
git checkout main
git merge feature/calendar  # Fast-forward! Clean linear history""")}</code></pre>

<h3>Interactive Rebase — Rewriting History</h3>
<p>Interactive rebase (<code class="il">git rebase -i</code>) lets you edit, squash, reorder, or drop commits before pushing.</p>

<pre><code class="lang-bash">{highlight_csharp("""# Rebase last 4 commits interactively
git rebase -i HEAD~4

# This opens your editor with something like:
# pick a1b2c3d Add leave calendar component
# pick e4f5g6h Fix typo in calendar header
# pick i7j8k9l Add date validation
# pick m0n1o2p Fix validation edge case

# Change 'pick' to:
#   squash (s) — combine with previous commit
#   reword (r) — change commit message
#   edit (e)   — pause to amend the commit
#   drop (d)   — remove the commit entirely

# Example: squash the typo fix into the first commit:
# pick a1b2c3d Add leave calendar component
# squash e4f5g6h Fix typo in calendar header
# pick i7j8k9l Add date validation
# squash m0n1o2p Fix validation edge case""")}</code></pre>

{callout('insight', 'When to Rebase vs Merge', '<strong>Rebase</strong> when: cleaning up local commits before pushing, keeping feature branch up-to-date with main.<br><strong>Merge</strong> when: integrating a completed feature into main, preserving the full history of how work was done.<br><br><strong>Rule of thumb:</strong> Rebase your own unpublished work. Merge shared/published branches.')}

<h3>Handling Rebase Conflicts</h3>
<pre><code class="lang-bash">{highlight_csharp("""# During rebase, if a conflict occurs:
# 1. Git pauses and tells you which files conflict
# 2. Resolve the conflicts in your editor
# 3. Stage the resolved files:
git add ResolvedFile.cs

# 4. Continue the rebase:
git rebase --continue

# If you want to abort and go back to before the rebase:
git rebase --abort

# If you want to skip this specific commit:
git rebase --skip""")}</code></pre>

{callout('smell', 'The Golden Rule of Rebasing', '<strong>NEVER rebase commits that have been pushed to a shared branch.</strong><br><br>Rebasing rewrites commit hashes. If someone else has based work on the original commits, their history diverges from yours. This creates a mess that&apos;s hard to untangle.<br><br><strong>Safe:</strong> Rebase your local feature branch before pushing.<br><strong>Dangerous:</strong> Rebase <code class="il">main</code> or any branch others are working on.')}

<h3>Other History Rewriting Tools</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Amend the last commit (message or content)
git commit --amend -m "Better commit message"

# Cherry-pick: copy a specific commit to current branch
git cherry-pick abc1234

# Revert: create a NEW commit that undoes a previous one (safe for shared branches)
git revert abc1234

# Reset: move branch pointer (DANGEROUS — can lose commits)
git reset --soft HEAD~1    # Undo commit, keep changes staged
git reset --mixed HEAD~1   # Undo commit, keep changes unstaged (default)
git reset --hard HEAD~1    # Undo commit, DISCARD changes permanently""")}</code></pre>

<table class="comparison-table">
<thead><tr><th>Tool</th><th>Rewrites History?</th><th>Safe for Shared Branches?</th><th>Use Case</th></tr></thead>
<tbody>
<tr><td><code class="il">rebase</code></td><td>Yes</td><td>No</td><td>Clean up local history before pushing</td></tr>
<tr><td><code class="il">amend</code></td><td>Yes</td><td>No</td><td>Fix the last commit</td></tr>
<tr><td><code class="il">cherry-pick</code></td><td>No (copies)</td><td>Yes</td><td>Pull a specific fix into another branch</td></tr>
<tr><td><code class="il">revert</code></td><td>No (adds)</td><td>Yes</td><td>Undo a commit publicly</td></tr>
<tr><td><code class="il">reset</code></td><td>Yes</td><td>No</td><td>Undo local commits</td></tr>
</tbody></table>
'''


def content_git_rebasing_fordummies():
    return f'''
{callout('analogy', 'Rebasing is Like Rewriting a Draft', 'Imagine you wrote 3 chapters of a book based on an outline. Meanwhile, the outline was updated with new requirements. <strong>Merge</strong> would add a note saying "the following chapters were written before the outline changed." <strong>Rebase</strong> rewrites your chapters so they read as if you always had the updated outline. Cleaner to read, but you&apos;re rewriting history.')}
<p><strong>Simple rule:</strong> If you haven&apos;t pushed yet, rebase freely. If you have pushed, use merge instead.</p>
'''


def content_git_remotes():
    return f'''
<h3>Working with Remotes</h3>
<p>A <strong>remote</strong> is a reference to a repository hosted elsewhere (GitHub, Azure DevOps, GitLab, etc.). Most projects have one remote called <code class="il">origin</code>.</p>

{svg_git_remotes()}

<pre><code class="lang-bash">{highlight_csharp("""# View remotes
git remote -v                    # Show fetch and push URLs
git remote show origin           # Detailed info about a remote

# Add / rename / remove remotes
git remote add upstream https://github.com/original/repo.git
git remote rename origin github
git remote remove upstream

# Clone — your starting point for existing repos
git clone https://github.com/company/project.git
git clone https://github.com/company/project.git my-folder  # Custom folder name

# Fetch — download remote changes WITHOUT merging
git fetch origin                 # Get all branches
git fetch origin main            # Get just main

# Pull — fetch + merge (or fetch + rebase if configured)
git pull                         # Pull current tracking branch
git pull origin main             # Pull specific branch
git pull --rebase                # Rebase instead of merge

# Push — upload your commits
git push                         # Push current branch
git push -u origin feature/X    # Push new branch + set up tracking
git push origin --tags           # Push all tags""")}</code></pre>

{callout('insight', 'Fetch vs Pull', '<code class="il">git fetch</code> downloads commits from the remote but doesn&apos;t touch your working files. You can inspect the changes with <code class="il">git log origin/main</code> before deciding what to do.<br><br><code class="il">git pull</code> = <code class="il">git fetch</code> + <code class="il">git merge</code> (or rebase). It&apos;s a convenience command that fetches AND integrates in one step.')}

<h3>Tracking Branches</h3>
<pre><code class="lang-bash">{highlight_csharp("""# See which local branches track which remote branches
git branch -vv

# Set up tracking for an existing branch
git branch --set-upstream-to=origin/main main

# Check out a remote branch (creates local tracking branch)
git checkout feature/X           # Auto-tracks origin/feature/X if it exists
git checkout -b local-name origin/feature/X  # Custom local name""")}</code></pre>

<h3>Forking Workflow (Open Source / Cross-Team)</h3>
<pre><code class="lang-bash">{highlight_csharp("""# 1. Fork the repo on GitHub (creates your copy)
# 2. Clone YOUR fork
git clone https://github.com/YOUR-USER/project.git

# 3. Add the original as 'upstream'
git remote add upstream https://github.com/ORIGINAL-OWNER/project.git

# 4. Keep your fork up to date
git fetch upstream
git checkout main
git merge upstream/main
git push origin main           # Push to YOUR fork

# 5. Create a PR from your fork to the original""")}</code></pre>

{callout('rule', 'Keep main Clean', 'Never commit directly to <code class="il">main</code>. Always branch off, work, then merge back via pull request. This ensures code review happens before changes reach the main branch, and makes <code class="il">main</code> always deployable.')}
'''


def content_git_repo_separation():
    return f'''
<h3>When Two Projects Share One Repo</h3>
<p>Sometimes projects grow intertwined in the same repository. When they need independent versioning, deployments, or teams — it&apos;s time to separate.</p>

{svg_git_repo_separation()}

<h3>The Separation Process</h3>
<h4>Step 1: Clone the shared repo to the new location</h4>
<pre><code class="lang-bash">{highlight_csharp("""# Clone keeps ALL history
git clone https://github.com/company/SharedRepo.git NewProject
cd NewProject""")}</code></pre>

<h4>Step 2: Repoint to a new remote</h4>
<pre><code class="lang-bash">{highlight_csharp("""# Create new empty repo on GitHub/Azure DevOps first, then:
git remote set-url origin https://github.com/company/NewProject.git
git push -u origin master""")}</code></pre>
<p>The new repo now has the complete commit history.</p>

<h4>Step 3: Clean up the old repo</h4>
<pre><code class="lang-bash">{highlight_csharp("""# Add the old repo as a temporary remote
git remote add oldrepo https://github.com/company/SharedRepo.git
git fetch oldrepo

# Find the last commit BEFORE the new-project-specific commits
git log oldrepo/master --oneline -10

# Push that commit to the old repo's branch, removing new-project commits
git push oldrepo <commit-sha>:master --force""")}</code></pre>

{callout('insight', 'The Power Move', 'The command <code class="il">git push remote commit-sha:branch --force</code> is extremely powerful. It tells the remote: "set this branch to exactly this commit." No checkout needed, no branch switching, your working tree is untouched. You&apos;re manipulating the remote directly.')}

<h4>Step 4: Clean up remotes</h4>
<pre><code class="lang-bash">{highlight_csharp("""git remote remove oldrepo
git remote -v  # Verify only the new origin remains""")}</code></pre>

<h3>Alternative: Splitting with filter-branch</h3>
<p>If you want to extract a <em>subdirectory</em> into its own repo (keeping only its history):</p>
<pre><code class="lang-bash">{highlight_csharp("""# Create a new branch with ONLY the history of src/NewProject/
git subtree split -P src/NewProject/ -b split-branch

# Create a new repo from that branch
mkdir ../NewProjectRepo && cd ../NewProjectRepo
git init
git pull ../SharedRepo split-branch

# Set up remote and push
git remote add origin https://github.com/company/NewProject.git
git push -u origin main""")}</code></pre>

{callout('rule', 'After Separation Checklist', '<ul><li>Update CI/CD pipelines in both repos</li><li>Update any cross-references or NuGet package sources</li><li>Verify both repos build independently</li><li>Inform the team and update documentation</li><li>Consider adding the separated project as a NuGet package or git submodule if it&apos;s a shared library</li></ul>')}
'''


def content_git_advanced():
    return f'''
<h3>Stashing — Save Work Without Committing</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Stash your current changes (quick save)
git stash                        # Stash tracked changes
git stash -u                     # Include untracked files
git stash save "WIP: calendar validation"  # Named stash

# View stashes
git stash list                   # Show all stashes

# Restore stashed changes
git stash pop                    # Apply most recent stash + remove it
git stash apply stash@{{0}}       # Apply without removing
git stash drop stash@{{0}}        # Delete a specific stash
git stash clear                  # Delete ALL stashes""")}</code></pre>

{callout('insight', 'When to Stash', 'Stash when you need to switch branches but aren&apos;t ready to commit. Example: you&apos;re halfway through a feature, and a critical bug comes in on <code class="il">main</code>. Stash → switch to main → fix bug → switch back → pop stash.')}

<h3>Tags — Marking Releases</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Lightweight tag (just a name)
git tag v1.0.0

# Annotated tag (recommended — includes author, date, message)
git tag -a v1.0.0 -m "Release 1.0.0 — initial production deploy"

# Tag a specific past commit
git tag -a v0.9.0 abc1234 -m "Beta release"

# List tags
git tag -l "v1.*"                # Filter by pattern

# Push tags
git push origin v1.0.0           # Push specific tag
git push origin --tags           # Push all tags

# Delete a tag
git tag -d v1.0.0                # Delete locally
git push origin --delete v1.0.0  # Delete on remote""")}</code></pre>

<h3>Bisect — Find the Bug-Introducing Commit</h3>
<pre><code class="lang-bash">{highlight_csharp("""# Start bisecting
git bisect start

# Mark the current state as bad
git bisect bad

# Mark a known good commit
git bisect good v1.2.0

# Git checks out a commit halfway between. Test it, then:
git bisect good    # if this commit is fine
git bisect bad     # if this commit has the bug

# Git narrows down until it finds the exact culprit commit
# When done:
git bisect reset""")}</code></pre>

{callout('analogy', 'Bisect is Binary Search', 'If you have 1000 commits between "it worked" and "it&apos;s broken", bisect finds the culprit in ~10 steps instead of checking all 1000. It splits the range in half each time.')}

<h3>Reflog — Your Safety Net</h3>
<pre><code class="lang-bash">{highlight_csharp("""# View the reflog (records every HEAD movement)
git reflog

# Example output:
# abc1234 HEAD@{0}: commit: Add calendar component
# def5678 HEAD@{1}: checkout: moving from main to feature/calendar
# ghi9012 HEAD@{2}: commit: Fix authentication bug

# Recover a "lost" commit after a hard reset
git reset --hard HEAD@{{2}}       # Go back to that point

# Recover a deleted branch
git checkout -b recovered-branch abc1234""")}</code></pre>

{callout('rule', 'Reflog Saves Lives', 'Almost nothing is truly lost in Git. The reflog keeps a record of every position HEAD has been at for the last 90 days. Even after <code class="il">reset --hard</code> or deleting a branch, you can usually recover using the reflog.')}

<h3>Useful Git Tricks</h3>
<pre><code class="lang-bash">{highlight_csharp("""# See who changed each line of a file
git blame src/Services/AuthService.cs

# Find all commits that changed a specific file
git log --follow -- src/Services/AuthService.cs

# Find a commit by message content
git log --grep="calendar" --oneline

# Find a commit that introduced/removed a string
git log -S "ConnectionString" --oneline

# Show files changed in a commit
git show --stat abc1234

# Create a patch file
git diff > my-changes.patch
git apply my-changes.patch

# Clean untracked files (careful!)
git clean -n     # Dry run — shows what would be deleted
git clean -fd    # Delete untracked files and directories""")}</code></pre>
'''


def content_git_advanced_fordummies():
    return f'''
{callout('analogy', 'Git Power Tools', '<strong>Stash</strong> = a drawer where you temporarily put aside unfinished work.<br><strong>Tags</strong> = Post-it notes on important commits saying "v1.0 was HERE."<br><strong>Bisect</strong> = a detective that finds which commit broke things using binary search.<br><strong>Reflog</strong> = a security camera that records everything — even things you tried to delete.')}
<p>You don&apos;t need these daily, but when you do, they&apos;re lifesavers.</p>
'''


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT COLLECTION
# ═══════════════════════════════════════════════════════════════════════════════

def collect_content():
    content = {}
    edu = os.path.join(BASE, 'Education')

    # Education MD files (01-15)
    for num in ['01','02','03','04','05','06','07','08','09','10','11','12','13','14','15']:
        for f in os.listdir(edu):
            if f.startswith(num + '-') and f.endswith('.md'):
                content[f'edu_{num}'] = read_file(os.path.join(edu, f))
                break

    # Basics
    basics = os.path.join(edu, 'Basics')
    if os.path.isdir(basics):
        for f in os.listdir(basics):
            if f.endswith('.md'):
                content[f'basics_{f}'] = read_file(os.path.join(basics, f))

    # ForDummies
    fd = os.path.join(edu, 'ForDummies')
    if os.path.isdir(fd):
        for f in os.listdir(fd):
            if f.endswith('.md'):
                key = re.match(r'(\d+)', f)
                if key:
                    content[f'fd_{key.group(1)}'] = read_file(os.path.join(fd, f))

    # ML
    ml_dir = os.path.join(edu, 'Educational_ML')
    if os.path.isdir(ml_dir):
        for f in os.listdir(ml_dir):
            if f.endswith('.md'):
                content[f'ml_{f}'] = read_file(os.path.join(ml_dir, f))

    # DOCX files
    docx_map = {
        'actions_events': os.path.join(BASE, 'Actions&Events.docx'),
        'cookie_handling': os.path.join(BASE, 'CookieHandlingBlazorServerApplications.docx'),
        'async_pattern': os.path.join(BASE, 'Microsoft_Fullstack', 'ASyncPattern.docx'),
        'how_to_unit_test': os.path.join(BASE, 'Microsoft_Fullstack', 'HowToCreateUnitTesting.docx'),
        'complete_unit_testing': os.path.join(BASE, 'Microsoft_Fullstack', 'The Complete Guide to Unit Testing.docx'),
        'identity': os.path.join(BASE, 'Identity', 'IdentityProjectKnowledgeEditable.docx'),
        'factory_floor': os.path.join(BASE, 'Education', 'FactoryFloor', 'ENG', 'FactoryFloorProductionSystemFormalDocumentation.docx'),
        'factory_floor_infographic': os.path.join(BASE, 'Education', 'FactoryFloor', 'ENG', 'FactoryFloorProductionSystemInfoGraphic.docx'),
        'stock_service': os.path.join(BASE, 'Education', 'Stock', 'ENG', 'StockServiceSystemFormalDocumentation.docx'),
        'stock_service_infographic': os.path.join(BASE, 'Education', 'Stock', 'ENG', 'StockServiceSystemInfoGraphic.docx'),
    }
    # Find Loadings file (has emoji in name)
    for f in os.listdir(BASE):
        if 'Loadings' in f and f.endswith('.docx'):
            docx_map['loadings_includes'] = os.path.join(BASE, f)

    for key, path in docx_map.items():
        if os.path.exists(path):
            content[f'docx_{key}'] = extract_docx_text(path)

    # Embedded HTML files
    html_files = {
        'delegates': os.path.join(edu, 'delegates-lambdas-expression-bodies.html'),
        'generics': os.path.join(edu, 'generics-builders-deep-dive.html'),
        'backprop': os.path.join(edu, 'Educational_ML', 'backprop-visualization.html'),
        'nn_journey': os.path.join(edu, 'Educational_ML', 'neural-network-journeyV2.html'),
        'sigmoid': os.path.join(edu, 'Educational_ML', 'sigmoid-derivative.html'),
        'training': os.path.join(edu, 'Educational_ML', 'training-flow-visualization.html'),
    }
    for key, path in html_files.items():
        if os.path.exists(path):
            content[f'html_{key}'] = path  # Store path, will embed later

    # Git content
    git_dir = os.path.join(BASE, 'Git')
    if os.path.isdir(git_dir):
        for f in os.listdir(git_dir):
            if f.endswith('.md'):
                content[f'git_{f}'] = read_file(os.path.join(git_dir, f))

    return content

# ═══════════════════════════════════════════════════════════════════════════════
# TOPIC SECTION BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_topic(topic_id, title, phase, level, content_html,
                fordummies_html=None, next_topic=None, prereqs=''):
    level_badge = {
        'beginner': '<span class="lvl lvl-b">Beginner</span>',
        'intermediate': '<span class="lvl lvl-i">Intermediate</span>',
        'advanced': '<span class="lvl lvl-a">Advanced</span>',
    }.get(level, '')

    prereqs_html = f'<div class="prereqs"><strong>Prerequisites:</strong> {prereqs}</div>' if prereqs else ''

    fd_section = ''
    if fordummies_html:
        fd_section = f'''
        <div class="fd-toggle">
            <button class="fd-btn" onclick="toggleFD('{topic_id}')">
                &#x1f4a1; Show Simple Explanation
            </button>
            <div class="fd-content" id="fd-{topic_id}" style="display:none;">
                <div class="fd-header">&#x1f393; Simple Explanation</div>
                {fordummies_html}
            </div>
        </div>'''

    next_html = ''
    if next_topic:
        next_html = f'<div class="next-up"><a href="#{next_topic[0]}">Next: {next_topic[1]} &rarr;</a></div>'

    return f'''
    <section class="topic-section" id="{topic_id}" data-phase="{phase}">
        <div class="topic-header" onclick="toggleTopic(this)">
            <div>
                <h3>{title}</h3>
                {prereqs_html}
            </div>
            <div class="topic-meta">{level_badge}<span class="expand-icon">&#x25BC;</span></div>
        </div>
        {fd_section}
        <div class="topic-body">
            {content_html}
        </div>
        {next_html}
    </section>'''

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BUILD FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Learning Webbook v2 Generator")
    print("=" * 60)

    print("\nCollecting content from source files...")
    content = collect_content()
    print(f"  Collected {len(content)} content items")

    def get_md(key):
        return md_to_html(content.get(key, ''))

    def get_docx(key):
        return docx_to_html(content.get(f'docx_{key}', ''))

    def get_embed(key):
        path = content.get(f'html_{key}', '')
        if path and os.path.exists(path):
            return embed_html_file(path, f'embed-{key}')
        return '<p><em>Interactive file not available.</em></p>'

    print("Building topic sections...", flush=True)

    # ═══ PHASE 1: The Ground Floor (7 topics) ═══
    phase1 = []
    phase1.append(build_topic('t01-web-fundamentals', 'Web Fundamentals', 1, 'beginner',
        svg_middleware_pipeline() + get_md('edu_10'),
        next_topic=('t02-csharp-generics', 'C# Generics Complete Guide')))

    phase1.append(build_topic('t02-csharp-generics', 'C# Generics — Complete Guide', 1, 'beginner',
        svg_type_constraints() + get_md('basics_CSharp_Generics_Guide.md'),
        prereqs='Basic C# knowledge',
        next_topic=('t03-delegates-lambdas', 'Delegates, Lambdas & Expression Bodies')))

    phase1.append(build_topic('t03-delegates-lambdas', 'Delegates, Lambdas & Expression Bodies', 1, 'intermediate',
        get_embed('delegates'),
        prereqs='C# Generics',
        next_topic=('t04-generics-builders', 'Generics & Builders Deep Dive')))

    phase1.append(build_topic('t04-generics-builders', 'Generics & Builders Deep Dive', 1, 'intermediate',
        get_embed('generics'),
        prereqs='C# Generics, Delegates',
        next_topic=('t05-flags-enum', 'Flags Enum')))

    phase1.append(build_topic('t05-flags-enum', 'C# Flags Enum', 1, 'beginner',
        svg_bitfield() + get_md('edu_12'),
        prereqs='Basic C# knowledge',
        next_topic=('t06-actions-events', 'Actions & Events')))

    phase1.append(build_topic('t06-actions-events', 'Actions & Events', 1, 'intermediate',
        get_docx('actions_events'),
        prereqs='C# basics, Delegates',
        next_topic=('t07-async-patterns', 'Async Patterns')))

    phase1.append(build_topic('t07-async-patterns', 'Async Patterns', 1, 'intermediate',
        svg_async_flow() + get_docx('async_pattern') + f'''
        {callout('insight', 'Key Insight', '<code class="il">async/await</code> doesn&apos;t create new threads — it releases the current thread back to the pool while waiting for I/O. This is crucial for server scalability.')}
        {callout('rule', 'Golden Rules', '<ul><li>Always use <code class="il">async Task</code>, never <code class="il">async void</code> (except event handlers)</li><li>Don&apos;t use <code class="il">.Result</code> or <code class="il">.Wait()</code> — they cause deadlocks in ASP.NET</li><li>Use <code class="il">ConfigureAwait(false)</code> in library code</li><li>Always pass <code class="il">CancellationToken</code> through async chains</li></ul>')}''',
        prereqs='C# basics, Actions & Events',
        next_topic=('t08-blazor-fundamentals', 'Blazor Fundamentals')))

    # ═══ PHASE 2: Building with Blazor (5 topics) ═══
    phase2 = []
    phase2.append(build_topic('t08-blazor-fundamentals', 'Blazor Fundamentals', 2, 'beginner',
        content_blazor_fundamentals(),
        prereqs='Web Fundamentals, C# basics',
        next_topic=('t09-blazor-architecture', 'Blazor Architecture & Security')))

    phase2.append(build_topic('t09-blazor-architecture', 'Blazor Architecture & Security', 2, 'intermediate',
        content_blazor_architecture(),
        prereqs='Blazor Fundamentals',
        next_topic=('t10-cookie-handling', 'Cookie Handling in Blazor')))

    phase2.append(build_topic('t10-cookie-handling', 'Cookie Handling in Blazor Server', 2, 'intermediate',
        svg_cookie_flow() + get_docx('cookie_handling'),
        prereqs='Blazor Architecture',
        next_topic=('t11-js-interop', 'JS Interop & Static Events')))

    phase2.append(build_topic('t11-js-interop', 'JS Interop & Static Events', 2, 'intermediate',
        svg_broadcast_vs_mailbox() + get_md('edu_06'),
        fordummies_html=get_md('fd_06'),
        prereqs='Blazor basics, JavaScript',
        next_topic=('t12-ef-core', 'EF Core: Loadings, Includes & Virtuals')))

    phase2.append(build_topic('t12-ef-core', 'EF Core: Loadings, Includes & Virtuals', 2, 'intermediate',
        svg_eager_vs_lazy() + get_docx('loadings_includes') + f'''
        {callout('insight', 'Eager vs Lazy Loading', '<strong>Eager</strong> (<code class="il">.Include()</code>): loads related data in one query. Use when you know you&apos;ll need the data.<br><strong>Lazy</strong> (<code class="il">virtual</code> properties): loads on first access. Beware N+1 queries!<br><strong>Explicit</strong> (<code class="il">.Entry().Collection().Load()</code>): you control exactly when to load.')}''',
        prereqs='C# basics, Database concepts',
        next_topic=('t13-clean-architecture', 'Clean Architecture')))

    # ═══ PHASE 3: Thinking in Layers (3 topics) ═══

    phase3 = []
    phase3.append(build_topic('t13-clean-architecture', 'Clean Architecture', 3, 'intermediate',
        svg_clean_architecture() + get_md('edu_01'),
        prereqs='Blazor basics, C# fundamentals',
        next_topic=('t14-polite-code', 'Polite Code Style')))

    phase3.append(build_topic('t14-polite-code', 'Polite Code Style', 3, 'beginner',
        get_md('edu_05'),
        prereqs='Clean Architecture',
        next_topic=('t15-adapter-intro', 'Adapter Pattern')))

    phase3.append(build_topic('t15-adapter-intro', 'Adapter Pattern', 3, 'intermediate',
        get_md('edu_03'),
        prereqs='Clean Architecture, SOLID basics',
        next_topic=('t16-solid', 'SOLID Principles Deep Dive')))

    # ═══ PHASE 4: Design Patterns Masterclass (12 topics) ═══

    phase4 = []
    phase4.append(build_topic('t16-solid', 'SOLID Principles Deep Dive', 4, 'intermediate',
        content_solid_deep_dive(),
        fordummies_html=content_solid_fordummies(),
        prereqs='Clean Architecture, Adapter Pattern',
        next_topic=('t17-strategy', 'Strategy Pattern')))

    phase4.append(build_topic('t17-strategy', 'Strategy Pattern', 4, 'intermediate',
        svg_strategy_pattern() + get_md('edu_08'),
        fordummies_html=get_md('fd_08'),
        prereqs='SOLID, Interfaces',
        next_topic=('t18-observer', 'Observer Pattern')))

    phase4.append(build_topic('t18-observer', 'Observer Pattern', 4, 'intermediate',
        content_observer(),
        fordummies_html=content_observer_fordummies(),
        prereqs='Delegates, Events',
        next_topic=('t19-adapter-deep', 'Adapter Pattern Deep Dive')))

    phase4.append(build_topic('t19-adapter-deep', 'Adapter Pattern — Deep Dive', 4, 'intermediate',
        content_adapter_deep(),
        fordummies_html=content_adapter_fordummies(),
        prereqs='Clean Architecture, SOLID',
        next_topic=('t20-facade', 'Facade Pattern')))

    phase4.append(build_topic('t20-facade', 'Facade Pattern', 4, 'intermediate',
        content_facade(),
        fordummies_html=content_facade_fordummies(),
        prereqs='Clean Architecture',
        next_topic=('t21-builder', 'Builder Pattern')))

    phase4.append(build_topic('t21-builder', 'Builder Pattern', 4, 'intermediate',
        content_builder(),
        fordummies_html=content_builder_fordummies(),
        prereqs='C# Generics, OOP',
        next_topic=('t22-repository', 'Repository Pattern')))

    phase4.append(build_topic('t22-repository', 'Repository Pattern', 4, 'intermediate',
        content_repository(),
        fordummies_html=content_repository_fordummies(),
        prereqs='EF Core, Clean Architecture',
        next_topic=('t23-factory', 'Factory Pattern')))

    phase4.append(build_topic('t23-factory', 'Factory Pattern', 4, 'intermediate',
        content_factory(),
        fordummies_html=content_factory_fordummies(),
        prereqs='SOLID, Interfaces',
        next_topic=('t24-decorator', 'Decorator Pattern')))

    phase4.append(build_topic('t24-decorator', 'Decorator Pattern', 4, 'advanced',
        content_decorator(),
        fordummies_html=content_decorator_fordummies(),
        prereqs='SOLID, Interfaces, DI',
        next_topic=('t25-pipeline', 'Pipeline / Chain of Responsibility')))

    phase4.append(build_topic('t25-pipeline', 'Pipeline / Chain of Responsibility', 4, 'advanced',
        svg_pipeline_chain() + get_md('edu_15'),
        fordummies_html=get_md('fd_15'),
        prereqs='Decorator, Strategy',
        next_topic=('t26-export-strategy', 'Two-Dimensional Strategy')))

    phase4.append(build_topic('t26-export-strategy', 'Two-Dimensional Strategy (Export Service)', 4, 'advanced',
        svg_export_matrix() + get_md('edu_13'),
        prereqs='Strategy Pattern',
        next_topic=('t27-schedule-grid', 'Generic Schedule Grid')))

    phase4.append(build_topic('t27-schedule-grid', 'Generic Schedule Grid', 4, 'advanced',
        svg_schedule_grid() + get_md('edu_09'),
        fordummies_html=get_md('fd_09'),
        prereqs='C# Generics, Design Patterns',
        next_topic=('t28-role-auth', 'Role-Based Authorization')))

    # ═══ PHASE 5: Who Can Do What (3 topics) ═══

    phase5 = []
    phase5.append(build_topic('t28-role-auth', 'Role-Based Authorization', 5, 'intermediate',
        svg_role_hierarchy() + get_md('edu_02'),
        prereqs='Clean Architecture, EF Core',
        next_topic=('t29-auth-architecture', 'Authorization Architecture')))

    phase5.append(build_topic('t29-auth-architecture', 'Authorization Architecture', 5, 'advanced',
        svg_three_layer_auth() + get_md('edu_04'),
        prereqs='Role-Based Authorization',
        next_topic=('t30-identity', 'Identity System')))

    phase5.append(build_topic('t30-identity', 'Identity System', 5, 'advanced',
        content_identity_expansion() + get_docx('identity'),
        prereqs='Authorization Architecture',
        next_topic=('t31-signalr', 'SignalR Real-Time Communication')))

    # ═══ PHASE 6: Real-Time Everything (3 topics) ═══

    phase6 = []
    phase6.append(build_topic('t31-signalr', 'SignalR Real-Time Communication', 6, 'intermediate',
        svg_signalr_hub() + get_md('edu_11'),
        fordummies_html=get_md('fd_11'),
        prereqs='Blazor, Clean Architecture',
        next_topic=('t32-notifications', 'Notification System')))

    phase6.append(build_topic('t32-notifications', 'Notification System', 6, 'advanced',
        svg_notification_flow() + get_md('edu_14'),
        fordummies_html=get_md('fd_14'),
        prereqs='SignalR, Clean Architecture',
        next_topic=('t33-recipient-resolver', 'Recipient Resolver Pipeline')))

    phase6.append(build_topic('t33-recipient-resolver', 'Recipient Resolver Pipeline', 6, 'advanced',
        get_md('edu_15'),
        fordummies_html=get_md('fd_15'),
        prereqs='Notification System, OCP',
        next_topic=('t34-facial-recognition', 'Facial Recognition')))

    # ═══ PHASE 7: Domain Deep Dives (3 topics) ═══

    phase7 = []
    phase7.append(build_topic('t34-facial-recognition', 'Facial Recognition Architecture', 7, 'advanced',
        svg_face_detection() + get_md('edu_07'),
        fordummies_html=get_md('fd_07'),
        prereqs='Blazor, JS Interop',
        next_topic=('t35-factory-floor', 'Factory Floor Production')))

    phase7.append(build_topic('t35-factory-floor', 'Factory Floor Production System', 7, 'advanced',
        svg_production_system() + get_docx('factory_floor') + get_docx('factory_floor_infographic'),
        prereqs='Clean Architecture, Design Patterns',
        next_topic=('t36-stock-service', 'Stock Service System')))

    phase7.append(build_topic('t36-stock-service', 'Stock Service System', 7, 'advanced',
        svg_stock_system() + get_docx('stock_service') + get_docx('stock_service_infographic'),
        prereqs='Clean Architecture, Design Patterns',
        next_topic=('t37-testing', 'Unit Testing in .NET')))

    # ═══ PHASE 8: Quality & Testing (1 topic) ═══

    phase8 = []
    phase8.append(build_topic('t37-testing', 'Unit Testing in .NET — Complete Guide', 8, 'intermediate',
        content_testing_consolidated() + get_docx('how_to_unit_test') + get_docx('complete_unit_testing'),
        prereqs='C# basics, Clean Architecture',
        next_topic=('t38-git-fundamentals', 'Git Fundamentals & Configuration')))

    # ═══ PHASE 9: Git Mastery (5 topics) ═══

    phase9 = []
    phase9.append(build_topic('t38-git-fundamentals', 'Git Fundamentals & Configuration', 9, 'beginner',
        content_git_fundamentals(),
        fordummies_html=content_git_fundamentals_fordummies(),
        next_topic=('t39-git-branching', 'Branching & Merging')))

    phase9.append(build_topic('t39-git-branching', 'Branching & Merging', 9, 'beginner',
        content_git_branching(),
        fordummies_html=content_git_branching_fordummies(),
        prereqs='Git Fundamentals',
        next_topic=('t40-git-rebasing', 'Rebasing & History Rewriting')))

    phase9.append(build_topic('t40-git-rebasing', 'Rebasing & History Rewriting', 9, 'intermediate',
        content_git_rebasing(),
        fordummies_html=content_git_rebasing_fordummies(),
        prereqs='Branching & Merging',
        next_topic=('t41-git-remotes', 'Remotes, Cloning & Collaboration')))

    phase9.append(build_topic('t41-git-remotes', 'Remotes, Cloning & Collaboration', 9, 'intermediate',
        content_git_remotes(),
        prereqs='Git Fundamentals',
        next_topic=('t42-git-repo-separation', 'Repository Separation')))

    phase9.append(build_topic('t42-git-repo-separation', 'Repository Separation', 9, 'advanced',
        content_git_repo_separation() + get_md('git_separating-repos.md'),
        prereqs='Remotes, Rebasing',
        next_topic=('t43-git-advanced', 'Advanced Git Techniques')))

    phase9.append(build_topic('t43-git-advanced', 'Advanced Git Techniques', 9, 'intermediate',
        content_git_advanced(),
        fordummies_html=content_git_advanced_fordummies(),
        prereqs='Branching, Rebasing, Remotes',
        next_topic=('t44-backpropagation', 'Backpropagation')))

    # ═══ PHASE 10: Understanding ML (4 topics) ═══

    phase10 = []
    phase10.append(build_topic('t44-backpropagation', 'Backpropagation — How Neural Networks Learn', 10, 'advanced',
        svg_neural_network() + get_md('ml_Backpropagation.md') + get_embed('backprop'),
        prereqs='Basic math (derivatives, chain rule)',
        next_topic=('t45-nn-journey', 'Neural Network Journey')))

    phase10.append(build_topic('t45-nn-journey', 'Neural Network Journey', 10, 'advanced',
        get_embed('nn_journey'),
        prereqs='Backpropagation basics',
        next_topic=('t46-sigmoid', 'Sigmoid & Derivatives')))

    phase10.append(build_topic('t46-sigmoid', 'Sigmoid & Derivatives', 10, 'advanced',
        svg_sigmoid() + get_embed('sigmoid'),
        prereqs='Basic calculus',
        next_topic=('t47-training-flow', 'Training Flow')))

    phase10.append(build_topic('t47-training-flow', 'Training Flow Visualization', 10, 'advanced',
        svg_training_flow() + get_embed('training'),
        prereqs='Neural Networks, Backpropagation'))

    # ═══ ASSEMBLE PHASES ═══
    phases = {
        1: ('The Ground Floor', 'C# & Web Foundations', 'Build the baseline — from HTTP to advanced C# patterns.', phase1),
        2: ('Building with Blazor', 'Framework Essentials', 'Server-side Blazor, cookies, JS interop, and data loading.', phase2),
        3: ('Thinking in Layers', 'Architecture & Code Quality', 'Why code is structured the way it is.', phase3),
        4: ('The Design Patterns Masterclass', 'SOLID + GoF Patterns', 'Deep patterns with dual ForDummies/Technical modes.', phase4),
        5: ('Who Can Do What', 'Authorization & Identity', 'Role-based auth, three-tier authorization, ASP.NET Identity.', phase5),
        6: ('Real-Time Everything', 'SignalR & Notifications', 'Hubs, groups, notifications, and recipient resolution.', phase6),
        7: ('Domain Deep Dives', 'Complex Systems', 'All patterns come together in real features.', phase7),
        8: ('Quality & Testing', 'Making It Reliable', 'Testing strategies and best practices for .NET.', phase8),
        9: ('Git Mastery', 'Version Control Deep Dive', 'From clone to rebase — everything you need to manage code history like a pro.', phase9),
        10: ('Understanding ML', 'Machine Learning Concepts', 'Neural networks, backpropagation, and training visualization.', phase10),
    }

    # ═══ BUILD NAV ITEMS ═══
    nav_data = {}
    all_topics_ordered = []
    for pnum in sorted(phases.keys()):
        pname, psub, pdesc, ptopics = phases[pnum]
        nav_data[pnum] = {'name': pname, 'sub': psub, 'topics': []}
        for t in ptopics:
            tid = re.search(r'id="([^"]+)"', t).group(1)
            tname = re.search(r'<h3>([^<]+)</h3>', t).group(1)
            nav_data[pnum]['topics'].append((tid, tname))
            all_topics_ordered.append(tid)
    total_topics = len(all_topics_ordered)

    # ═══ BUILD SIDEBAR NAV HTML ═══
    nav_html = ''
    for pkey in sorted(nav_data.keys()):
        p = nav_data[pkey]
        label = f'Phase {pkey}: {p["name"]}'
        items = ''.join(f'<a href="#{tid}" class="nav-item" data-topic="{tid}">{tname}</a>' for tid, tname in p['topics'])
        nav_html += f'''<div class="phase-group">
            <div class="phase-header" onclick="togglePhase(this)"><span class="arrow">&#9660;</span><span>{label}</span></div>
            <div class="phase-items">{items}</div></div>'''

    # ═══ BUILD MAIN CONTENT HTML ═══
    main_html = ''
    for pnum in sorted(phases.keys()):
        pname, psub, pdesc, ptopics = phases[pnum]
        main_html += f'''<div class="phase-card" id="phase-{pnum}">
            <h2>Phase {pnum}: &ldquo;{pname}&rdquo;</h2>
            <div class="phase-sub">{psub}</div>
            <div class="phase-desc">{pdesc}</div></div>\n'''
        main_html += '\n'.join(ptopics)

    print("Assembling final HTML...")

    # ═══ GENERATE FINAL HTML ═══
    final_html = generate_html_template(nav_html, main_html, total_topics)

    # Write output
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(final_html)

    file_size = os.path.getsize(OUTPUT)
    print(f"\nWebbook written to: {OUTPUT}")
    print(f"File size: {file_size:,} bytes ({file_size/1024:.0f} KB)")
    print(f"Topics: {total_topics}")
    print("Done!")


# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_html_template(nav_html, main_html, total_topics):
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Learning Webbook v2 — A Curated Developer Journey</title>
<style>
/* ═══ THEMES ═══ */
:root, [data-theme="dark"] {{
    --bg: #1a1a2e; --bg2: #16213e; --surface: #1e2a4a; --surface-hover: #253560;
    --border: #2a3a5c; --text: #e8e8f0; --text-muted: #8890a8; --text-h: #fff;
    --accent: #e94560; --accent-hover: #ff6b81; --accent-bg: rgba(233,69,96,0.1);
    --accent2: #533483; --code-bg: #0d1117; --code-border: #30363d;
    --success: #4ecca3; --warning: #f0a500; --info: #3b82f6;
    --shadow: rgba(0,0,0,0.3); --sidebar-bg: #111827; --sidebar-hover: #1f2937;
    --sidebar-active: rgba(233,69,96,0.15);
}}
[data-theme="light"] {{
    --bg: #f8fafc; --bg2: #fff; --surface: #fff; --surface-hover: #f1f5f9;
    --border: #e2e8f0; --text: #334155; --text-muted: #64748b; --text-h: #0f172a;
    --accent: #2563eb; --accent-hover: #3b82f6; --accent-bg: rgba(37,99,235,0.06);
    --accent2: #7c3aed; --code-bg: #f8f9fa; --code-border: #e2e8f0;
    --success: #059669; --warning: #d97706; --info: #2563eb;
    --shadow: rgba(0,0,0,0.08); --sidebar-bg: #fff; --sidebar-hover: #f1f5f9;
    --sidebar-active: rgba(37,99,235,0.08);
}}
[data-theme="warm"] {{
    --bg: #1c1017; --bg2: #2a1520; --surface: #351c28; --surface-hover: #452535;
    --border: #5a3545; --text: #f0e0e5; --text-muted: #b89aa8; --text-h: #fff;
    --accent: #df2e26; --accent-hover: #f04038; --accent-bg: rgba(223,46,38,0.12);
    --accent2: #f26d28; --code-bg: #150a10; --code-border: #4a2535;
    --success: #2ecc71; --warning: #f39c12; --info: #e74c3c;
    --shadow: rgba(0,0,0,0.4); --sidebar-bg: #150a10; --sidebar-hover: #2a1520;
    --sidebar-active: rgba(223,46,38,0.15);
}}

/* ═══ RESET ═══ */
*,*::before,*::after {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scroll-behavior:smooth; font-size:16px; }}
body {{ font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif; background:var(--bg); color:var(--text); line-height:1.7; transition:background .3s,color .3s; overflow-x:hidden; }}
::-webkit-scrollbar {{ width:8px; }}
::-webkit-scrollbar-track {{ background:var(--bg); }}
::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:4px; }}
::-webkit-scrollbar-thumb:hover {{ background:var(--accent); }}

/* ═══ LAYOUT ═══ */
.layout {{ display:flex; min-height:100vh; }}
.sidebar {{ width:300px; min-width:300px; background:var(--sidebar-bg); border-right:1px solid var(--border); display:flex; flex-direction:column; position:fixed; top:0; left:0; height:100vh; z-index:100; transition:transform .3s; }}
.sidebar-header {{ padding:1.5rem; border-bottom:1px solid var(--border); }}
.sidebar-title {{ font-size:1.2rem; font-weight:700; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.sidebar-sub {{ font-size:.72rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:.1em; }}
.theme-sw {{ display:flex; gap:.5rem; padding:.75rem 1.5rem; border-bottom:1px solid var(--border); }}
.theme-btn {{ flex:1; padding:.4rem; border:1px solid var(--border); border-radius:6px; background:transparent; color:var(--text-muted); cursor:pointer; font-size:.8rem; transition:all .2s; }}
.theme-btn:hover,.theme-btn.active {{ background:var(--accent-bg); border-color:var(--accent); color:var(--accent); }}
.search-box {{ padding:.75rem 1.5rem; border-bottom:1px solid var(--border); }}
.search-input {{ width:100%; padding:.5rem .75rem; border:1px solid var(--border); border-radius:6px; background:var(--bg); color:var(--text); font-size:.85rem; outline:none; transition:border-color .2s; }}
.search-input:focus {{ border-color:var(--accent); }}
.search-input::placeholder {{ color:var(--text-muted); }}
.nav-tree {{ flex:1; overflow-y:auto; padding:.75rem 0; }}
.phase-group {{ margin-bottom:.25rem; }}
.phase-header {{ display:flex; align-items:center; gap:.5rem; padding:.5rem 1.5rem; cursor:pointer; color:var(--text-muted); font-size:.75rem; font-weight:600; text-transform:uppercase; letter-spacing:.05em; transition:color .2s; user-select:none; }}
.phase-header:hover {{ color:var(--text); }}
.phase-header .arrow {{ font-size:.6rem; transition:transform .2s; }}
.phase-header.collapsed .arrow {{ transform:rotate(-90deg); }}
.phase-items {{ overflow:hidden; transition:max-height .3s ease; }}
.phase-header.collapsed + .phase-items {{ max-height:0 !important; }}
.nav-item {{ display:block; padding:.35rem 1.5rem .35rem 2.5rem; color:var(--text-muted); text-decoration:none; font-size:.82rem; transition:all .15s; border-left:2px solid transparent; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.nav-item:hover {{ color:var(--text); background:var(--sidebar-hover); }}
.nav-item.active {{ color:var(--accent); background:var(--sidebar-active); border-left-color:var(--accent); }}
.nav-item.completed::before {{ content:"\\2713 "; color:var(--success); }}
.progress-section {{ padding:1rem 1.5rem; border-top:1px solid var(--border); }}
.progress-label {{ font-size:.75rem; color:var(--text-muted); margin-bottom:.4rem; display:flex; justify-content:space-between; }}
.progress-bar {{ height:4px; background:var(--border); border-radius:2px; overflow:hidden; }}
.progress-fill {{ height:100%; background:linear-gradient(90deg,var(--accent),var(--success)); border-radius:2px; transition:width .5s; width:0%; }}
.main-content {{ flex:1; margin-left:300px; padding:2rem 3rem; max-width:1200px; }}
.sidebar-toggle {{ display:none; position:fixed; top:1rem; left:1rem; z-index:200; background:var(--accent); color:#fff; border:none; border-radius:8px; width:40px; height:40px; font-size:1.2rem; cursor:pointer; }}

/* ═══ WELCOME ═══ */
.welcome {{ text-align:center; padding:3rem 0 2rem; margin-bottom:2rem; border-bottom:1px solid var(--border); }}
.welcome h1 {{ font-size:2.5rem; font-weight:800; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:.5rem; text-shadow:none; }}
.welcome p {{ color:var(--text-muted); font-size:1.1rem; max-width:600px; margin:0 auto; }}
.stats {{ display:flex; justify-content:center; gap:2rem; margin-top:1.5rem; }}
.stat-num {{ font-size:1.8rem; font-weight:700; color:var(--accent); }}
.stat-lbl {{ font-size:.75rem; color:var(--text-muted); text-transform:uppercase; }}

/* ═══ PHASE CARDS ═══ */
.phase-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.5rem; margin:2rem 0 1.5rem; }}
.phase-card h2 {{ font-size:1.4rem; color:var(--text-h); margin-bottom:.25rem; background:linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; text-shadow:0 0 30px rgba(233,69,96,0.15); }}
.phase-sub {{ color:var(--accent); font-size:.9rem; font-weight:600; margin-bottom:.5rem; }}
.phase-desc {{ color:var(--text-muted); font-size:.9rem; }}

/* ═══ TOPIC SECTIONS ═══ */
.topic-section {{ background:var(--bg2); border:1px solid var(--border); border-radius:10px; margin-bottom:1.5rem; overflow:hidden; transition:border-color .2s; }}
.topic-section:hover {{ border-color:color-mix(in srgb,var(--accent) 50%,transparent); }}
.topic-section:target {{ border-color:var(--accent); box-shadow:0 0 0 2px var(--accent-bg); }}
.topic-header {{ padding:1.25rem 1.5rem; cursor:pointer; display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }}
.topic-header h3 {{ font-size:1.15rem; color:var(--text-h); font-weight:600; }}
.topic-meta {{ display:flex; align-items:center; gap:.5rem; flex-shrink:0; }}
.expand-icon {{ font-size:.7rem; color:var(--text-muted); transition:transform .2s; }}
.topic-section.expanded .expand-icon {{ transform:rotate(180deg); }}
.lvl {{ font-size:.7rem; padding:.15rem .5rem; border-radius:10px; font-weight:600; text-transform:uppercase; }}
.lvl-b {{ background:rgba(78,204,163,0.15); color:var(--success); }}
.lvl-i {{ background:rgba(240,165,0,0.15); color:var(--warning); }}
.lvl-a {{ background:rgba(233,69,96,0.15); color:var(--accent); }}
.prereqs {{ font-size:.78rem; color:var(--text-muted); margin-top:.3rem; }}
.topic-body {{ padding:1.5rem; display:none; }}
.topic-section.expanded .topic-body {{ display:block; }}

/* ═══ CONTENT TYPOGRAPHY ═══ */
.topic-body h1,.topic-body h2,.topic-body h3,.topic-body h4 {{ color:var(--text-h); margin:1.5rem 0 .75rem; font-weight:600; }}
.topic-body h1 {{ font-size:1.5rem; }}
.topic-body h2 {{ font-size:1.3rem; border-bottom:1px solid var(--border); padding-bottom:.4rem; }}
.topic-body h3 {{ font-size:1.15rem; color:var(--success); }}
.topic-body h4 {{ font-size:1rem; color:var(--warning); }}
.topic-body p {{ margin-bottom:.75rem; line-height:1.8; }}
.topic-body ul,.topic-body ol {{ margin:.75rem 0; padding-left:1.5rem; }}
.topic-body li {{ margin-bottom:.3rem; }}
.topic-body blockquote {{ border-left:3px solid var(--accent); padding:.75rem 1rem; margin:1rem 0; background:var(--accent-bg); border-radius:0 6px 6px 0; color:var(--text-muted); }}
.topic-body hr {{ border:none; border-top:1px solid var(--border); margin:1.5rem 0; }}
.topic-body a {{ color:var(--accent); text-decoration:none; }}
.topic-body a:hover {{ text-decoration:underline; }}
.topic-body strong {{ color:var(--text-h); }}

/* ═══ DIAGRAM BOXES (styled ASCII art / architecture diagrams) ═══ */
.diagram-box {{ margin:1.25rem 0; border-radius:10px; border:1px solid var(--border); background:linear-gradient(135deg, var(--code-bg), color-mix(in srgb, var(--surface) 60%, var(--code-bg))); overflow-x:auto; position:relative; }}
.diagram-box::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg, var(--accent), var(--accent2), var(--success)); border-radius:10px 10px 0 0; }}
.diagram-box pre {{ font-family:'Cascadia Code','Fira Code','JetBrains Mono','Consolas',monospace; font-size:.82rem; line-height:1.6; padding:1.25rem 1.5rem; margin:0; color:var(--text); white-space:pre; background:transparent; border:none; }}
[data-theme="light"] .diagram-box {{ background:#1e293b; border-color:#334155; }}
[data-theme="light"] .diagram-box pre {{ color:#e2e8f0; }}

/* ═══ CODE BLOCKS ═══ */
.topic-body pre {{ background:var(--code-bg); border:1px solid var(--code-border); border-radius:8px; padding:1rem; margin:1rem 0; overflow-x:auto; font-size:.85rem; line-height:1.5; }}
.topic-body pre code {{ font-family:'Cascadia Code','Fira Code','JetBrains Mono','Consolas',monospace; color:var(--text); }}
.kw {{ color:#569cd6; }} .type {{ color:#4ec9b0; }} .str {{ color:#ce9178; }}
.cmt {{ color:#6a9955; }} .fn {{ color:#dcdcaa; }} .num {{ color:#b5cea8; }}
.il {{ background:var(--code-bg); border:1px solid var(--code-border); padding:.1rem .4rem; border-radius:4px; font-family:'Cascadia Code','Consolas',monospace; font-size:.88em; }}
[data-theme="light"] .kw {{ color:#0000ff; }}
[data-theme="light"] .type {{ color:#267f99; }}
[data-theme="light"] .str {{ color:#a31515; }}
[data-theme="light"] .cmt {{ color:#008000; }}
[data-theme="light"] .fn {{ color:#795e26; }}
[data-theme="light"] .num {{ color:#098658; }}

/* ═══ TABLES ═══ */
.tbl-wrap {{ overflow-x:auto; margin:1rem 0; }}
.topic-body table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
.topic-body th {{ background:var(--surface); padding:.6rem .75rem; text-align:left; font-weight:600; color:var(--text-h); border-bottom:2px solid var(--border); }}
.topic-body td {{ padding:.5rem .75rem; border-bottom:1px solid var(--border); }}
.topic-body tr:hover td {{ background:var(--surface-hover); }}
.comparison-table {{ width:100%; border-collapse:collapse; font-size:.88rem; margin:1rem 0; }}
.comparison-table th {{ background:var(--surface); padding:.6rem .75rem; text-align:left; font-weight:600; color:var(--text-h); border-bottom:2px solid var(--border); }}
.comparison-table td {{ padding:.5rem .75rem; border-bottom:1px solid var(--border); }}
.comparison-table tr:hover td {{ background:var(--surface-hover); }}

/* ═══ CALLOUT BOXES ═══ */
.callout {{ border-radius:8px; padding:1rem 1.25rem; margin:1rem 0; border-left:4px solid; }}
.callout-title {{ font-weight:700; margin-bottom:.5rem; font-size:.95rem; }}
.callout-body {{ font-size:.9rem; line-height:1.7; }}
.callout-body ul {{ margin:.5rem 0; padding-left:1.2rem; }}
.callout-analogy {{ background:rgba(83,52,131,0.1); border-color:var(--accent2); }}
.callout-analogy .callout-title {{ color:var(--accent2); }}
.callout-insight {{ background:var(--accent-bg); border-color:var(--accent); }}
.callout-insight .callout-title {{ color:var(--accent); }}
.callout-smell {{ background:rgba(240,165,0,0.08); border-color:var(--warning); }}
.callout-smell .callout-title {{ color:var(--warning); }}
.callout-rule {{ background:rgba(78,204,163,0.08); border-color:var(--success); }}
.callout-rule .callout-title {{ color:var(--success); }}
.callout-tldr {{ background:rgba(59,130,246,0.08); border-color:var(--info); }}
.callout-tldr .callout-title {{ color:var(--info); }}

/* ═══ FOR DUMMIES TOGGLE ═══ */
.fd-toggle {{ padding:0 1.5rem; display:none; }}
.topic-section.expanded .fd-toggle {{ display:block; }}
.fd-btn {{ display:inline-flex; align-items:center; gap:.4rem; padding:.5rem 1rem; background:var(--accent-bg); border:1px solid var(--accent); border-radius:8px; color:var(--accent); cursor:pointer; font-size:.85rem; font-weight:500; transition:all .2s; margin-top:.75rem; }}
.fd-btn:hover {{ background:var(--accent); color:#fff; }}
.fd-content {{ margin:1rem 0; padding:1.25rem; background:var(--accent-bg); border:1px solid var(--accent); border-radius:8px; }}
.fd-header {{ font-weight:700; color:var(--accent); margin-bottom:.75rem; font-size:1rem; }}
.fd-content p {{ margin-bottom:.75rem; }}
.fd-content ul,.fd-content ol {{ margin:.75rem 0; padding-left:1.5rem; }}

/* ═══ SVG DIAGRAMS ═══ */
.svg-diagram {{ margin:1.5rem 0; text-align:center; overflow-x:auto; }}
.svg-diagram svg {{ display:inline-block; }}

/* ═══ EMBEDDED DEMOS ═══ */
.embedded-demo {{ margin:1rem 0; border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
.embed-toggle-bar {{ background:var(--surface); padding:.5rem 1rem; border-bottom:1px solid var(--border); }}
.embed-toggle-btn {{ background:none; border:1px solid var(--accent); color:var(--accent); padding:.4rem 1rem; border-radius:6px; cursor:pointer; font-size:.85rem; font-weight:600; transition:all .2s; }}
.embed-toggle-btn:hover {{ background:var(--accent); color:#fff; }}
.embed-icon {{ display:inline-block; transition:transform .2s; }}
.embed-wrapper {{ overflow-y:auto; padding:1.5rem; background:var(--code-bg); border-radius:0 0 8px 8px; }}

/* ═══ NEXT UP ═══ */
.next-up {{ padding:1rem 1.5rem; border-top:1px solid var(--border); display:none; }}
.topic-section.expanded .next-up {{ display:block; }}
.next-up a {{ color:var(--accent); text-decoration:none; font-weight:600; font-size:.9rem; }}
.next-up a:hover {{ text-decoration:underline; }}

/* ═══ RESPONSIVE ═══ */
@media(max-width:768px) {{
    .sidebar {{ transform:translateX(-100%); }}
    .sidebar.open {{ transform:translateX(0); }}
    .sidebar-toggle {{ display:flex; align-items:center; justify-content:center; }}
    .main-content {{ margin-left:0; padding:1rem; padding-top:4rem; }}
    .welcome h1 {{ font-size:1.8rem; }}
    .stats {{ gap:1rem; }}
}}

/* ═══ PRINT ═══ */
@media print {{
    .sidebar,.sidebar-toggle,.theme-sw,.search-box,.progress-section,.fd-btn,.embedded-demo,.next-up {{ display:none !important; }}
    .main-content {{ margin-left:0; padding:0; max-width:100%; }}
    .topic-section {{ break-inside:avoid; border:1px solid #ddd; }}
    .topic-body {{ display:block !important; }}
    body {{ background:#fff; color:#333; }}
    .topic-header h3,.phase-card h2 {{ color:#111; -webkit-text-fill-color:#111; }}
}}
</style>
</head>
<body>
<button class="sidebar-toggle" onclick="toggleSidebar()" aria-label="Toggle navigation">&#9776;</button>
<div class="layout">
<nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <div class="sidebar-title">Learning Webbook</div>
        <div class="sidebar-sub">A Curated Developer Journey &mdash; v2</div>
    </div>
    <div class="theme-sw">
        <button class="theme-btn active" onclick="setTheme('dark')">Dark</button>
        <button class="theme-btn" onclick="setTheme('light')">Light</button>
        <button class="theme-btn" onclick="setTheme('warm')">Warm</button>
    </div>
    <div class="search-box">
        <input type="text" class="search-input" id="searchInput" placeholder="Search topics... (Ctrl+K)" autocomplete="off">
    </div>
    <div class="nav-tree" id="navTree">{nav_html}</div>
    <div class="progress-section">
        <div class="progress-label"><span>Journey Progress</span><span id="progressText">0 / {total_topics}</span></div>
        <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    </div>
</nav>
<main class="main-content" id="mainContent">
    <div class="welcome">
        <h1>Learning Webbook</h1>
        <p>A curated developer journey &mdash; from web fundamentals to multi-database notification pipelines. 100% self-contained.</p>
        <div class="stats">
            <div><div class="stat-num">8+</div><div class="stat-lbl">Phases</div></div>
            <div><div class="stat-num">{total_topics}</div><div class="stat-lbl">Topics</div></div>
            <div><div class="stat-num">6</div><div class="stat-lbl">Interactive Demos</div></div>
            <div><div class="stat-num">30+</div><div class="stat-lbl">SVG Diagrams</div></div>
        </div>
    </div>
    {main_html}
</main>
</div>

<script>
/* ═══ THEME ═══ */
function setTheme(t){{document.documentElement.setAttribute('data-theme',t);localStorage.setItem('wb-theme',t);document.querySelectorAll('.theme-btn').forEach(b=>b.classList.toggle('active',b.textContent.trim().toLowerCase()===t))}}
setTheme(localStorage.getItem('wb-theme')||'dark');

/* ═══ SIDEBAR ═══ */
function toggleSidebar(){{document.getElementById('sidebar').classList.toggle('open')}}
function togglePhase(h){{h.classList.toggle('collapsed');var items=h.nextElementSibling;items.style.maxHeight=h.classList.contains('collapsed')?'0':items.scrollHeight+'px'}}
document.querySelectorAll('.phase-items').forEach(el=>el.style.maxHeight=el.scrollHeight+'px');
document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('click',function(e){{e.preventDefault();var tid=this.getAttribute('data-topic'),sec=document.getElementById(tid);if(sec){{sec.classList.add('expanded');sec.scrollIntoView({{behavior:'smooth',block:'start'}});setActiveNav(tid);document.getElementById('sidebar').classList.remove('open')}}}}));
function setActiveNav(tid){{document.querySelectorAll('.nav-item').forEach(i=>i.classList.toggle('active',i.getAttribute('data-topic')===tid))}}

/* ═══ TOPIC TOGGLE ═══ */
function toggleTopic(header){{var sec=header.closest('.topic-section'),was=sec.classList.contains('expanded');sec.classList.toggle('expanded');if(!was){{markRead(sec.id);setActiveNav(sec.id)}}}}

/* ═══ PROGRESS ═══ */
var TOTAL={total_topics};
function getRead(){{var s=localStorage.getItem('wb-progress');return s?JSON.parse(s):[]}}
function markRead(tid){{var r=getRead();if(!r.includes(tid)){{r.push(tid);localStorage.setItem('wb-progress',JSON.stringify(r))}}updateProgress()}}
function updateProgress(){{var r=getRead(),c=r.length,pct=Math.round(c/TOTAL*100);document.getElementById('progressText').textContent=c+' / '+TOTAL;document.getElementById('progressFill').style.width=pct+'%';document.querySelectorAll('.nav-item').forEach(i=>i.classList.toggle('completed',r.includes(i.getAttribute('data-topic'))))}}
updateProgress();

/* ═══ SEARCH ═══ */
document.getElementById('searchInput').addEventListener('input',function(){{var q=this.value.toLowerCase().trim();if(!q){{document.querySelectorAll('.topic-section').forEach(s=>s.style.display='');document.querySelectorAll('.phase-card').forEach(c=>c.style.display='');document.querySelectorAll('.nav-item').forEach(i=>i.style.display='');document.querySelectorAll('.phase-group').forEach(g=>g.style.display='');return}}document.querySelectorAll('.topic-section').forEach(s=>{{s.style.display=s.textContent.toLowerCase().includes(q)?'':'none'}});document.querySelectorAll('.nav-item').forEach(i=>{{var tid=i.getAttribute('data-topic'),sec=document.getElementById(tid);i.style.display=sec&&sec.style.display!=='none'?'':'none'}});document.querySelectorAll('.phase-group').forEach(g=>{{g.style.display=g.querySelectorAll('.nav-item:not([style*="display: none"])').length>0?'':'none'}});}});

/* ═══ FOR DUMMIES ═══ */
function toggleFD(tid){{var el=document.getElementById('fd-'+tid),btn=el.parentElement.querySelector('.fd-btn');if(el.style.display==='none'){{el.style.display='block';btn.innerHTML='&#x1f4a1; Hide Simple Explanation'}}else{{el.style.display='none';btn.innerHTML='&#x1f4a1; Show Simple Explanation'}}}}

/* ═══ EMBEDDED DEMOS ═══ */
function toggleEmbed(id){{var w=document.getElementById('wrap-'+id),icon=w.previousElementSibling.querySelector('.embed-icon');if(w.style.display==='none'){{w.style.display='block';icon.style.transform='rotate(90deg)'}}else{{w.style.display='none';icon.style.transform='rotate(0deg)'}}}}

/* ═══ KEYBOARD SHORTCUTS ═══ */
document.addEventListener('keydown',function(e){{if((e.ctrlKey||e.metaKey)&&e.key==='k'){{e.preventDefault();document.getElementById('searchInput').focus()}}if(e.key==='Escape'){{var si=document.getElementById('searchInput');if(document.activeElement===si){{si.value='';si.dispatchEvent(new Event('input'));si.blur()}}document.getElementById('sidebar').classList.remove('open')}}}});

/* ═══ SCROLL SPY ═══ */
var scrollTO;window.addEventListener('scroll',function(){{clearTimeout(scrollTO);scrollTO=setTimeout(function(){{var secs=document.querySelectorAll('.topic-section'),cur='';secs.forEach(s=>{{if(s.getBoundingClientRect().top<=150)cur=s.id}});if(cur)setActiveNav(cur)}},100)}});

/* ═══ HASH ON LOAD ═══ */
if(window.location.hash){{var hid=window.location.hash.slice(1),hsec=document.getElementById(hid);if(hsec&&hsec.classList.contains('topic-section'))setTimeout(()=>{{hsec.classList.add('expanded');hsec.scrollIntoView({{behavior:'smooth'}});setActiveNav(hid);markRead(hid)}},100)}}
</script>
</body>
</html>'''


def export_json():
    """Export all topic content as structured JSON for the MAUI Blazor Hybrid app."""
    print("=" * 60)
    print("Learning Webbook — JSON Export")
    print("=" * 60)

    print("\nCollecting content from source files...")
    content = collect_content()
    print(f"  Collected {len(content)} content items")

    def get_md(key):
        return md_to_html(content.get(key, ''))

    def get_docx(key):
        return docx_to_html(content.get(f'docx_{key}', ''))

    def get_embed(key):
        path = content.get(f'html_{key}', '')
        if path and os.path.exists(path):
            return embed_html_file(path, f'embed-{key}')
        return '<p><em>Interactive file not available.</em></p>'

    print("Building topic data...", flush=True)

    # Collect topics as structured data (same order as main())
    def topic(tid, title, phase, level, content_html,
              fordummies_html=None, next_topic=None, prereqs=''):
        return {
            'id': tid,
            'title': title,
            'phase': phase,
            'level': level,
            'prereqs': prereqs,
            'contentHtml': content_html,
            'forDummiesHtml': fordummies_html,
            'nextTopicId': next_topic[0] if next_topic else None,
            'nextTopicTitle': next_topic[1] if next_topic else None,
        }

    # ═══ PHASE 1 ═══
    p1_topics = [
        topic('t01-web-fundamentals', 'Web Fundamentals', 1, 'beginner',
              svg_middleware_pipeline() + get_md('edu_10'),
              next_topic=('t02-csharp-generics', 'C# Generics Complete Guide')),
        topic('t02-csharp-generics', 'C# Generics — Complete Guide', 1, 'beginner',
              svg_type_constraints() + get_md('basics_CSharp_Generics_Guide.md'),
              prereqs='Basic C# knowledge',
              next_topic=('t03-delegates-lambdas', 'Delegates, Lambdas & Expression Bodies')),
        topic('t03-delegates-lambdas', 'Delegates, Lambdas & Expression Bodies', 1, 'intermediate',
              get_embed('delegates'),
              prereqs='C# Generics',
              next_topic=('t04-generics-builders', 'Generics & Builders Deep Dive')),
        topic('t04-generics-builders', 'Generics & Builders Deep Dive', 1, 'intermediate',
              get_embed('generics'),
              prereqs='C# Generics, Delegates',
              next_topic=('t05-flags-enum', 'Flags Enum')),
        topic('t05-flags-enum', 'C# Flags Enum', 1, 'beginner',
              svg_bitfield() + get_md('edu_12'),
              prereqs='Basic C# knowledge',
              next_topic=('t06-actions-events', 'Actions & Events')),
        topic('t06-actions-events', 'Actions & Events', 1, 'intermediate',
              get_docx('actions_events'),
              prereqs='C# basics, Delegates',
              next_topic=('t07-async-patterns', 'Async Patterns')),
        topic('t07-async-patterns', 'Async Patterns', 1, 'intermediate',
              svg_async_flow() + get_docx('async_pattern') +
              callout('insight', 'Key Insight', '<code class="il">async/await</code> doesn\'t create new threads — it releases the current thread back to the pool while waiting for I/O. This is crucial for server scalability.') +
              callout('rule', 'Golden Rules', '<ul><li>Always use <code class="il">async Task</code>, never <code class="il">async void</code> (except event handlers)</li><li>Don\'t use <code class="il">.Result</code> or <code class="il">.Wait()</code> — they cause deadlocks in ASP.NET</li><li>Use <code class="il">ConfigureAwait(false)</code> in library code</li><li>Always pass <code class="il">CancellationToken</code> through async chains</li></ul>'),
              prereqs='C# basics, Actions & Events',
              next_topic=('t08-blazor-fundamentals', 'Blazor Fundamentals')),
    ]

    # ═══ PHASE 2 ═══
    p2_topics = [
        topic('t08-blazor-fundamentals', 'Blazor Fundamentals', 2, 'beginner',
              content_blazor_fundamentals(),
              prereqs='Web Fundamentals, C# basics',
              next_topic=('t09-blazor-architecture', 'Blazor Architecture & Security')),
        topic('t09-blazor-architecture', 'Blazor Architecture & Security', 2, 'intermediate',
              content_blazor_architecture(),
              prereqs='Blazor Fundamentals',
              next_topic=('t10-cookie-handling', 'Cookie Handling in Blazor')),
        topic('t10-cookie-handling', 'Cookie Handling in Blazor Server', 2, 'intermediate',
              svg_cookie_flow() + get_docx('cookie_handling'),
              prereqs='Blazor Architecture',
              next_topic=('t11-js-interop', 'JS Interop & Static Events')),
        topic('t11-js-interop', 'JS Interop & Static Events', 2, 'intermediate',
              svg_broadcast_vs_mailbox() + get_md('edu_06'),
              fordummies_html=get_md('fd_06'),
              prereqs='Blazor basics, JavaScript',
              next_topic=('t12-ef-core', 'EF Core: Loadings, Includes & Virtuals')),
        topic('t12-ef-core', 'EF Core: Loadings, Includes & Virtuals', 2, 'intermediate',
              svg_eager_vs_lazy() + get_docx('loadings_includes') +
              callout('insight', 'Eager vs Lazy Loading', '<strong>Eager</strong> (<code class="il">.Include()</code>): loads related data in one query. Use when you know you\'ll need the data.<br><strong>Lazy</strong> (<code class="il">virtual</code> properties): loads on first access. Beware N+1 queries!<br><strong>Explicit</strong> (<code class="il">.Entry().Collection().Load()</code>): you control exactly when to load.'),
              prereqs='C# basics, Database concepts',
              next_topic=('t13-clean-architecture', 'Clean Architecture')),
    ]

    # ═══ PHASE 3 ═══
    p3_topics = [
        topic('t13-clean-architecture', 'Clean Architecture', 3, 'intermediate',
              svg_clean_architecture() + get_md('edu_01'),
              prereqs='Blazor basics, C# fundamentals',
              next_topic=('t14-polite-code', 'Polite Code Style')),
        topic('t14-polite-code', 'Polite Code Style', 3, 'beginner',
              get_md('edu_05'),
              prereqs='Clean Architecture',
              next_topic=('t15-adapter-intro', 'Adapter Pattern')),
        topic('t15-adapter-intro', 'Adapter Pattern', 3, 'intermediate',
              get_md('edu_03'),
              prereqs='Clean Architecture, SOLID basics',
              next_topic=('t16-solid', 'SOLID Principles Deep Dive')),
    ]

    # ═══ PHASE 4 ═══
    p4_topics = [
        topic('t16-solid', 'SOLID Principles Deep Dive', 4, 'intermediate',
              content_solid_deep_dive(),
              fordummies_html=content_solid_fordummies(),
              prereqs='Clean Architecture, Adapter Pattern',
              next_topic=('t17-strategy', 'Strategy Pattern')),
        topic('t17-strategy', 'Strategy Pattern', 4, 'intermediate',
              svg_strategy_pattern() + get_md('edu_08'),
              fordummies_html=get_md('fd_08'),
              prereqs='SOLID, Interfaces',
              next_topic=('t18-observer', 'Observer Pattern')),
        topic('t18-observer', 'Observer Pattern', 4, 'intermediate',
              content_observer(),
              fordummies_html=content_observer_fordummies(),
              prereqs='Delegates, Events',
              next_topic=('t19-adapter-deep', 'Adapter Pattern Deep Dive')),
        topic('t19-adapter-deep', 'Adapter Pattern — Deep Dive', 4, 'intermediate',
              content_adapter_deep(),
              fordummies_html=content_adapter_fordummies(),
              prereqs='Clean Architecture, SOLID',
              next_topic=('t20-facade', 'Facade Pattern')),
        topic('t20-facade', 'Facade Pattern', 4, 'intermediate',
              content_facade(),
              fordummies_html=content_facade_fordummies(),
              prereqs='Clean Architecture',
              next_topic=('t21-builder', 'Builder Pattern')),
        topic('t21-builder', 'Builder Pattern', 4, 'intermediate',
              content_builder(),
              fordummies_html=content_builder_fordummies(),
              prereqs='C# Generics, OOP',
              next_topic=('t22-repository', 'Repository Pattern')),
        topic('t22-repository', 'Repository Pattern', 4, 'intermediate',
              content_repository(),
              fordummies_html=content_repository_fordummies(),
              prereqs='EF Core, Clean Architecture',
              next_topic=('t23-factory', 'Factory Pattern')),
        topic('t23-factory', 'Factory Pattern', 4, 'intermediate',
              content_factory(),
              fordummies_html=content_factory_fordummies(),
              prereqs='SOLID, Interfaces',
              next_topic=('t24-decorator', 'Decorator Pattern')),
        topic('t24-decorator', 'Decorator Pattern', 4, 'advanced',
              content_decorator(),
              fordummies_html=content_decorator_fordummies(),
              prereqs='SOLID, Interfaces, DI',
              next_topic=('t25-pipeline', 'Pipeline / Chain of Responsibility')),
        topic('t25-pipeline', 'Pipeline / Chain of Responsibility', 4, 'advanced',
              svg_pipeline_chain() + get_md('edu_15'),
              fordummies_html=get_md('fd_15'),
              prereqs='Decorator, Strategy',
              next_topic=('t26-export-strategy', 'Two-Dimensional Strategy')),
        topic('t26-export-strategy', 'Two-Dimensional Strategy (Export Service)', 4, 'advanced',
              svg_export_matrix() + get_md('edu_13'),
              prereqs='Strategy Pattern',
              next_topic=('t27-schedule-grid', 'Generic Schedule Grid')),
        topic('t27-schedule-grid', 'Generic Schedule Grid', 4, 'advanced',
              svg_schedule_grid() + get_md('edu_09'),
              fordummies_html=get_md('fd_09'),
              prereqs='C# Generics, Design Patterns',
              next_topic=('t28-role-auth', 'Role-Based Authorization')),
    ]

    # ═══ PHASE 5 ═══
    p5_topics = [
        topic('t28-role-auth', 'Role-Based Authorization', 5, 'intermediate',
              svg_role_hierarchy() + get_md('edu_02'),
              prereqs='Clean Architecture, EF Core',
              next_topic=('t29-auth-architecture', 'Authorization Architecture')),
        topic('t29-auth-architecture', 'Authorization Architecture', 5, 'advanced',
              svg_three_layer_auth() + get_md('edu_04'),
              prereqs='Role-Based Authorization',
              next_topic=('t30-identity', 'Identity System')),
        topic('t30-identity', 'Identity System', 5, 'advanced',
              content_identity_expansion() + get_docx('identity'),
              prereqs='Authorization Architecture',
              next_topic=('t31-signalr', 'SignalR Real-Time Communication')),
    ]

    # ═══ PHASE 6 ═══
    p6_topics = [
        topic('t31-signalr', 'SignalR Real-Time Communication', 6, 'intermediate',
              svg_signalr_hub() + get_md('edu_11'),
              fordummies_html=get_md('fd_11'),
              prereqs='Blazor, Clean Architecture',
              next_topic=('t32-notifications', 'Notification System')),
        topic('t32-notifications', 'Notification System', 6, 'advanced',
              svg_notification_flow() + get_md('edu_14'),
              fordummies_html=get_md('fd_14'),
              prereqs='SignalR, Clean Architecture',
              next_topic=('t33-recipient-resolver', 'Recipient Resolver Pipeline')),
        topic('t33-recipient-resolver', 'Recipient Resolver Pipeline', 6, 'advanced',
              get_md('edu_15'),
              fordummies_html=get_md('fd_15'),
              prereqs='Notification System, OCP',
              next_topic=('t34-facial-recognition', 'Facial Recognition')),
    ]

    # ═══ PHASE 7 ═══
    p7_topics = [
        topic('t34-facial-recognition', 'Facial Recognition Architecture', 7, 'advanced',
              svg_face_detection() + get_md('edu_07'),
              fordummies_html=get_md('fd_07'),
              prereqs='Blazor, JS Interop',
              next_topic=('t35-factory-floor', 'Factory Floor Production')),
        topic('t35-factory-floor', 'Factory Floor Production System', 7, 'advanced',
              svg_production_system() + get_docx('factory_floor') + get_docx('factory_floor_infographic'),
              prereqs='Clean Architecture, Design Patterns',
              next_topic=('t36-stock-service', 'Stock Service System')),
        topic('t36-stock-service', 'Stock Service System', 7, 'advanced',
              svg_stock_system() + get_docx('stock_service') + get_docx('stock_service_infographic'),
              prereqs='Clean Architecture, Design Patterns',
              next_topic=('t37-testing', 'Unit Testing in .NET')),
    ]

    # ═══ PHASE 8 ═══
    p8_topics = [
        topic('t37-testing', 'Unit Testing in .NET — Complete Guide', 8, 'intermediate',
              content_testing_consolidated() + get_docx('how_to_unit_test') + get_docx('complete_unit_testing'),
              prereqs='C# basics, Clean Architecture',
              next_topic=('t38-git-fundamentals', 'Git Fundamentals & Configuration')),
    ]

    # ═══ PHASE 9 ═══
    p9_topics = [
        topic('t38-git-fundamentals', 'Git Fundamentals & Configuration', 9, 'beginner',
              content_git_fundamentals(),
              fordummies_html=content_git_fundamentals_fordummies(),
              next_topic=('t39-git-branching', 'Branching & Merging')),
        topic('t39-git-branching', 'Branching & Merging', 9, 'beginner',
              content_git_branching(),
              fordummies_html=content_git_branching_fordummies(),
              prereqs='Git Fundamentals',
              next_topic=('t40-git-rebasing', 'Rebasing & History Rewriting')),
        topic('t40-git-rebasing', 'Rebasing & History Rewriting', 9, 'intermediate',
              content_git_rebasing(),
              fordummies_html=content_git_rebasing_fordummies(),
              prereqs='Branching & Merging',
              next_topic=('t41-git-remotes', 'Remotes, Cloning & Collaboration')),
        topic('t41-git-remotes', 'Remotes, Cloning & Collaboration', 9, 'intermediate',
              content_git_remotes(),
              prereqs='Git Fundamentals',
              next_topic=('t42-git-repo-separation', 'Repository Separation')),
        topic('t42-git-repo-separation', 'Repository Separation', 9, 'advanced',
              content_git_repo_separation() + get_md('git_separating-repos.md'),
              prereqs='Remotes, Rebasing',
              next_topic=('t43-git-advanced', 'Advanced Git Techniques')),
        topic('t43-git-advanced', 'Advanced Git Techniques', 9, 'intermediate',
              content_git_advanced(),
              fordummies_html=content_git_advanced_fordummies(),
              prereqs='Branching, Rebasing, Remotes',
              next_topic=('t44-backpropagation', 'Backpropagation')),
    ]

    # ═══ PHASE 10 ═══
    p10_topics = [
        topic('t44-backpropagation', 'Backpropagation — How Neural Networks Learn', 10, 'advanced',
              svg_neural_network() + get_md('ml_Backpropagation.md') + get_embed('backprop'),
              prereqs='Basic math (derivatives, chain rule)',
              next_topic=('t45-nn-journey', 'Neural Network Journey')),
        topic('t45-nn-journey', 'Neural Network Journey', 10, 'advanced',
              get_embed('nn_journey'),
              prereqs='Backpropagation basics',
              next_topic=('t46-sigmoid', 'Sigmoid & Derivatives')),
        topic('t46-sigmoid', 'Sigmoid & Derivatives', 10, 'advanced',
              svg_sigmoid() + get_embed('sigmoid'),
              prereqs='Basic calculus',
              next_topic=('t47-training-flow', 'Training Flow')),
        topic('t47-training-flow', 'Training Flow Visualization', 10, 'advanced',
              svg_training_flow() + get_embed('training'),
              prereqs='Neural Networks, Backpropagation'),
    ]

    phases_data = [
        {'number': 1, 'name': 'The Ground Floor', 'subtitle': 'C# & Web Foundations',
         'description': 'Build the baseline — from HTTP to advanced C# patterns.', 'topics': p1_topics},
        {'number': 2, 'name': 'Building with Blazor', 'subtitle': 'Framework Essentials',
         'description': 'Server-side Blazor, cookies, JS interop, and data loading.', 'topics': p2_topics},
        {'number': 3, 'name': 'Thinking in Layers', 'subtitle': 'Architecture & Code Quality',
         'description': 'Why code is structured the way it is.', 'topics': p3_topics},
        {'number': 4, 'name': 'The Design Patterns Masterclass', 'subtitle': 'SOLID + GoF Patterns',
         'description': 'Deep patterns with dual ForDummies/Technical modes.', 'topics': p4_topics},
        {'number': 5, 'name': 'Who Can Do What', 'subtitle': 'Authorization & Identity',
         'description': 'Role-based auth, three-tier authorization, ASP.NET Identity.', 'topics': p5_topics},
        {'number': 6, 'name': 'Real-Time Everything', 'subtitle': 'SignalR & Notifications',
         'description': 'Hubs, groups, notifications, and recipient resolution.', 'topics': p6_topics},
        {'number': 7, 'name': 'Domain Deep Dives', 'subtitle': 'Complex Systems',
         'description': 'All patterns come together in real features.', 'topics': p7_topics},
        {'number': 8, 'name': 'Quality & Testing', 'subtitle': 'Making It Reliable',
         'description': 'Testing strategies and best practices for .NET.', 'topics': p8_topics},
        {'number': 9, 'name': 'Git Mastery', 'subtitle': 'Version Control Deep Dive',
         'description': 'From clone to rebase — everything you need to manage code history like a pro.', 'topics': p9_topics},
        {'number': 10, 'name': 'Understanding ML', 'subtitle': 'Machine Learning Concepts',
         'description': 'Neural networks, backpropagation, and training visualization.', 'topics': p10_topics},
    ]

    total_topics = sum(len(p['topics']) for p in phases_data)

    output_data = {
        'title': 'Learning Webbook',
        'subtitle': 'A Curated Developer Journey',
        'totalTopics': total_topics,
        'totalPhases': len(phases_data),
        'phases': phases_data,
    }

    output_path = os.path.join(BASE, 'LearningWebbook.Maui', 'Content', 'topics.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)

    file_size = os.path.getsize(output_path)
    print(f"\nJSON written to: {output_path}")
    print(f"File size: {file_size:,} bytes ({file_size/1024:.0f} KB)")
    print(f"Topics: {total_topics}")
    print(f"Phases: {len(phases_data)}")
    print("Done!")


if __name__ == '__main__':
    if '--json' in sys.argv:
        export_json()
    else:
        main()

