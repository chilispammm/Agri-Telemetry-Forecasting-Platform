import os
import re
import sys
import argparse
from pathlib import Path

# Canonical CA-ENG Editorial Stylesheet with Math & Mermaid Support
CSS_STYLES = """
:root {
    --bg: #f4f1ea;
    --surface: #faf8f3;
    --ink: #151515;
    --muted: #62605a;
    --border: #d3cec0;
    --dark: #151515;
    --dark-border: #333;
    --blue: #2563eb;
    --amber: #b7791f;
    --grey: #777;
    --green: #34785a;
    --red: #991b1b;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 2rem; }
body {
    margin: 0;
    color: var(--ink);
    background: var(--bg);
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.65;
}

/* Sidebar */
.sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 270px;
    height: 100vh;
    padding: 2.5rem 1.75rem;
    border-right: 1px solid var(--border);
    background: var(--bg);
    overflow-y: auto;
    z-index: 10;
}

.brand {
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--ink);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}

.sidebar-meta {
    margin-bottom: 2.5rem;
    color: var(--muted);
    font-size: 10px;
    line-height: 1.7;
    text-transform: uppercase;
    letter-spacing: .7px;
}

.nav-item {
    display: block;
    margin-bottom: .9rem;
    color: var(--muted);
    text-decoration: none;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .45px;
    text-transform: uppercase;
    transition: color .2s ease;
}

.nav-item:hover { color: var(--ink); }

/* Main Content Area */
.main {
    width: calc(100% - 270px);
    max-width: 1200px;
    margin-left: 270px;
    padding: 4rem 5rem 7rem;
}

.top-meta {
    display: flex;
    justify-content: space-between;
    gap: 2rem;
    padding-bottom: 1rem;
    margin-bottom: 4rem;
    border-bottom: 1px solid var(--border);
    color: var(--muted);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.hero { max-width: 900px; margin-bottom: 5rem; }

.eyebrow {
    margin-bottom: 1rem;
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

h1 {
    max-width: 900px;
    margin: 0 0 1.5rem;
    font-size: clamp(2.2rem, 4.5vw, 3.8rem);
    line-height: 1.05;
    letter-spacing: -.045em;
    font-weight: 600;
}

.hero-description {
    max-width: 780px;
    color: var(--muted);
    font-size: 16px;
    line-height: 1.6;
}

/* Principle / Highlight Callout */
.principle {
    padding: 2rem 2.25rem;
    margin: 2rem 0 3rem;
    background: var(--dark);
    color: white;
}

.principle-label {
    margin-bottom: .75rem;
    color: #999;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}

.principle strong {
    display: block;
    margin-bottom: 1.25rem;
    font-size: 18px;
    font-weight: 500;
}

.workflow {
    color: #ddd;
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    letter-spacing: .2px;
    line-height: 2;
    overflow-wrap: anywhere;
}

/* Content Sections */
.section {
    margin-top: 5rem;
    scroll-margin-top: 2rem;
}

.section-header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    padding-top: 1rem;
    margin-bottom: 2rem;
    border-top: 1px solid var(--ink);
}

.section-number {
    min-width: 30px;
    font-size: 11px;
    font-weight: 700;
}

h2 {
    margin: 0;
    font-size: 1.65rem;
    line-height: 1.2;
    letter-spacing: -.025em;
    font-weight: 600;
}

h3 {
    margin: 2.5rem 0 1rem;
    font-size: 1.05rem;
    font-weight: 600;
}

h4 {
    margin: 1.75rem 0 .75rem;
    font-size: .9rem;
    font-weight: 700;
}

p {
    max-width: 850px;
    font-size: 14px;
}

/* Lists */
ul, ol {
    max-width: 850px;
    padding-left: 1.4rem;
    font-size: 13.5px;
}

li {
    margin-bottom: .6rem;
}

/* Tables */
.table-wrap {
    width: 100%;
    overflow-x: auto;
    margin: 1.5rem 0 2rem;
}

table {
    width: 100%;
    border-collapse: collapse;
    border-top: 1px solid var(--ink);
    font-size: 13px;
}

th, td {
    padding: 1.1rem .9rem;
    border-bottom: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
}

th {
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .7px;
    text-transform: uppercase;
}

.key {
    width: 28%;
    border-right: 1px solid var(--border);
    font-weight: 600;
}

/* Callouts & Requirements */
.callout {
    padding: 1.5rem 1.75rem;
    margin: 2rem 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--ink);
    font-size: 13px;
}
.callout.warning { border-left-color: var(--amber); }
.callout.dark { background: var(--dark); color: white; border-left-color: var(--ink); }

/* Monospace Code & ASCII Blocks */
code {
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    background: #eae5d9;
    padding: 2px 6px;
}

pre {
    background: var(--dark);
    color: #eee;
    padding: 1.5rem;
    overflow-x: auto;
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    line-height: 1.6;
    margin: 1.5rem 0;
}

pre code {
    background: transparent;
    padding: 0;
    color: inherit;
}

/* Mermaid Flowcharts */
.mermaid {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--ink);
    padding: 2rem 1.5rem;
    margin: 2rem 0;
    text-align: center;
    overflow-x: auto;
}

/* LaTeX Block Math */
.math-block {
    margin: 1.5rem 0;
    padding: 1.25rem 1.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--blue);
    overflow-x: auto;
    font-size: 1.05rem;
}

mjx-container[jax="CHTML"][display="true"] {
    margin: 0.5rem 0 !important;
}

/* Restrained Status Badges */
.badge {
    display: inline-block;
    padding: 2px 7px;
    border: 1px solid currentColor;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: .6px;
    text-transform: uppercase;
    white-space: nowrap;
    background: transparent;
}
.badge-decided, .decided, .badge-validated, .validated, .badge-tested, .tested, .defined {
    color: var(--green);
    border-color: var(--green);
}
.badge-researching, .researching {
    color: var(--blue);
    border-color: var(--blue);
}
.badge-assumption, .assumption {
    color: var(--amber);
    border-color: var(--amber);
}
.badge-configurable, .configurable, .badge-open, .open, .not-started {
    color: var(--grey);
    border-color: var(--grey);
}
.badge-implemented, .implemented {
    color: var(--blue);
    border-color: var(--blue);
}
.badge-rejected, .rejected {
    color: var(--red);
    border-color: var(--red);
}

a { color: var(--ink); text-decoration: underline; font-weight: 600; }
a:hover { opacity: 0.8; }

/* Footer */
.footer {
    padding-top: 3rem;
    margin-top: 7rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 10px;
    letter-spacing: .5px;
    text-transform: uppercase;
    line-height: 2;
}

/* Responsive & Print */
@media (max-width: 1100px) {
    .main { padding: 3rem 3rem 6rem; }
}

@media (max-width: 900px) {
    .sidebar {
        position: static;
        width: 100%;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--border);
        padding: 1.5rem;
    }
    .sidebar-meta { margin-bottom: 1.5rem; }
    .sidebar nav {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .5rem 1rem;
    }
    .nav-item { margin-bottom: .4rem; }
    .main { width: 100%; margin-left: 0; padding: 3rem 1.5rem 5rem; }
    .top-meta { flex-direction: column; gap: .5rem; }
}

@media (max-width: 520px) {
    .sidebar nav { grid-template-columns: 1fr; }
    .section-header { gap: .65rem; }
    h2 { font-size: 1.35rem; }
}

@media print {
    @page { size: A4; margin: 18mm; }
    body { background: white; color: black; font-size: 10pt; }
    .sidebar { display: none; }
    .main { width: 100%; max-width: none; margin: 0; padding: 0; }
    .top-meta { margin-bottom: 2rem; }
    .section { margin-top: 3rem; }
    .section-header { break-after: avoid; }
    .table-wrap, table, pre, .callout, .principle, .mermaid, .math-block { break-inside: avoid; }
    a { color: inherit; text-decoration: none; }
    .footer { margin-top: 3rem; }
}
"""

MATHJAX_MERMAID_SCRIPTS = """
    <!-- MathJax for LaTeX mathematical formula rendering -->
    <script>
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true,
        processEnvironments: true
      },
      options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      }
    };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

    <!-- Mermaid for Flowcharts and Diagrams -->
    <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({
        startOnLoad: true,
        theme: 'neutral',
        themeVariables: {
            fontFamily: 'Inter, -apple-system, sans-serif',
            primaryColor: '#faf8f3',
            primaryBorderColor: '#151515',
            primaryTextColor: '#151515',
            lineColor: '#151515',
            secondaryColor: '#f4f1ea',
            tertiaryColor: '#faf8f3',
            edgeLabelBackground: '#ffffff'
        }
    });
    </script>
"""

def get_badge_html(status_text: str) -> str:
    st = status_text.upper().strip()
    if "DECIDED" in st or "DEFINED" in st:
        cls = "badge-decided"
    elif "RESEARCHING" in st:
        cls = "badge-researching"
    elif "ASSUMPTION" in st:
        cls = "badge-assumption"
    elif "CONFIGURABLE" in st:
        cls = "badge-configurable"
    elif "IMPLEMENTED" in st:
        cls = "badge-implemented"
    elif "TESTED" in st or "VALIDATED" in st:
        cls = "badge-validated"
    elif "REJECTED" in st:
        cls = "badge-rejected"
    else:
        cls = "badge-open"
    return f'<span class="badge {cls}">{status_text}</span>'

def format_inline(text: str) -> str:
    """Format markdown bold, code, math, badges, and links."""
    # Escape HTML special chars inside inline code first
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1).replace('<', '&lt;').replace('>', '&gt;')}</code>", text)
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    for status in ["DECIDED", "RESEARCHING", "ASSUMPTION", "CONFIGURABLE", "IMPLEMENTED", "TESTED", "VALIDATED", "REJECTED", "OPEN"]:
        badge_html = get_badge_html(status)
        text = text.replace(f"[{status}]", badge_html)
    return text

def render_table(lines: list[str]) -> str:
    """Converts markdown table lines to HTML with table-wrap."""
    if len(lines) < 2:
        return ""
    
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for l in lines[2:]:
        if not l.strip():
            continue
        cols = [c.strip() for c in l.strip("|").split("|")]
        rows.append(cols)

    th_html = "".join(f"<th>{format_inline(h)}</th>" for h in headers)
    tr_html_list = []
    for row in rows:
        td_html = "".join(f"<td>{format_inline(c)}</td>" for c in row)
        tr_html_list.append(f"<tr>{td_html}</tr>")
    
    tbody_html = "\n".join(tr_html_list)
    return f"""<div class="table-wrap">
<table>
    <thead>
        <tr>{th_html}</tr>
    </thead>
    <tbody>
{tbody_html}
    </tbody>
</table>
</div>"""

def render_markdown_to_ca_eng(md_text: str, doc_number: str, doc_title: str, doc_category: str) -> str:
    """Parses canonical markdown text and wraps it in CA-ENG layout with LaTeX & Mermaid support."""
    lines = md_text.splitlines()
    
    # Extract status and metadata
    status_match = re.search(r"\*\*Status:\*\*\s*(.+)", md_text)
    doc_status = status_match.group(1).strip() if status_match else "DECIDED"
    
    date_match = re.search(r"\*\*Last (?:Updated|Edited):\*\*\s*(.+)", md_text)
    doc_date = date_match.group(1).strip() if date_match else "September 30, 2026"

    # Identify major section headings for sidebar
    sections = []
    section_counter = 1
    
    for line in lines:
        m = re.match(r"^##\s+(\d+[\.\s]+)?(.+)", line)
        if m:
            sec_name = m.group(2).strip()
            anchor = re.sub(r"[^a-zA-Z0-9]+", "-", sec_name.lower()).strip("-")
            sections.append((f"{section_counter:02d}", sec_name, anchor))
            section_counter += 1

    # Sidebar Navigation HTML
    nav_links_html = []
    for num, name, anchor in sections:
        nav_links_html.append(f'<a href="#{anchor}" class="nav-item">{num}. {name}</a>')
    
    sidebar_nav = "\n            ".join(nav_links_html)

    # Process body content
    body_html_parts = []
    in_code_block = False
    is_mermaid_block = False
    code_block_lines = []
    
    in_math_block = False
    math_block_lines = []
    
    in_table = False
    table_lines = []
    in_ul = False
    ul_items = []
    in_ol = False
    ol_items = []
    current_sec_num = 0

    def flush_list():
        nonlocal in_ul, ul_items, in_ol, ol_items
        if in_ul and ul_items:
            items_html = "".join(f"<li>{item}</li>" for item in ul_items)
            body_html_parts.append(f"<ul>{items_html}</ul>")
            ul_items = []
            in_ul = False
        if in_ol and ol_items:
            items_html = "".join(f"<li>{item}</li>" for item in ol_items)
            body_html_parts.append(f"<ol>{items_html}</ol>")
            ol_items = []
            in_ol = False

    def flush_table():
        nonlocal in_table, table_lines
        if in_table and table_lines:
            body_html_parts.append(render_table(table_lines))
            table_lines = []
            in_table = False

    for line in lines:
        # Multi-line Math block ($$ ... $$)
        if line.strip() == "$$":
            flush_list()
            flush_table()
            if in_math_block:
                math_content = "\n".join(math_block_lines)
                body_html_parts.append(f'<div class="math-block">$$\n{math_content}\n$$</div>')
                math_block_lines = []
                in_math_block = False
            else:
                in_math_block = True
            continue
        
        if in_math_block:
            math_block_lines.append(line)
            continue

        # Single-line Math block ($$...$$)
        if line.strip().startswith("$$") and line.strip().endswith("$$") and len(line.strip()) > 4:
            flush_list()
            flush_table()
            body_html_parts.append(f'<div class="math-block">{line.strip()}</div>')
            continue

        # Code & Mermaid block handling
        if line.startswith("```"):
            flush_list()
            flush_table()
            if in_code_block:
                if is_mermaid_block:
                    mermaid_content = "\n".join(code_block_lines)
                    body_html_parts.append(f'<div class="mermaid">\n{mermaid_content}\n</div>')
                else:
                    code_content = "\n".join(code_block_lines)
                    body_html_parts.append(f"<pre><code>{code_content}</code></pre>")
                code_block_lines = []
                in_code_block = False
                is_mermaid_block = False
            else:
                in_code_block = True
                is_mermaid_block = "mermaid" in line.lower()
            continue
        
        if in_code_block:
            if is_mermaid_block:
                code_block_lines.append(line)
            else:
                code_block_lines.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Table handling
        if line.strip().startswith("|") and line.strip().endswith("|"):
            flush_list()
            in_table = True
            table_lines.append(line)
            continue
        else:
            flush_table()

        # Headings
        if line.startswith("## "):
            flush_list()
            if current_sec_num > 0:
                body_html_parts.append("</section>")
            sec_title = line[3:].strip()
            clean_title = re.sub(r"^\d+[\.\s]+", "", sec_title)
            current_sec_num += 1
            anchor = re.sub(r"[^a-zA-Z0-9]+", "-", clean_title.lower()).strip("-")
            body_html_parts.append(f"""
        <section id="{anchor}" class="section">
            <div class="section-header">
                <div class="section-number">{current_sec_num:02d}</div>
                <h2>{clean_title}</h2>
            </div>""")
            continue
        
        if line.startswith("### "):
            flush_list()
            body_html_parts.append(f"<h3>{format_inline(line[4:].strip())}</h3>")
            continue
        
        if line.startswith("#### "):
            flush_list()
            body_html_parts.append(f"<h4>{format_inline(line[5:].strip())}</h4>")
            continue

        # Blockquote / Principle
        if line.startswith("> "):
            flush_list()
            quote_text = line[2:].strip()
            body_html_parts.append(f'<div class="principle"><strong>{format_inline(quote_text)}</strong></div>')
            continue

        # Unordered Lists
        clean_line = line.strip()
        if clean_line.startswith("- ") or clean_line.startswith("* "):
            if in_ol:
                flush_list()
            in_ul = True
            item_text = clean_line[2:].strip()
            ul_items.append(format_inline(item_text))
            continue
        
        # Ordered Lists
        if re.match(r"^\d+\.\s+", clean_line):
            if in_ul:
                flush_list()
            in_ol = True
            item_text = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            ol_items.append(format_inline(item_text))
            continue

        # Non-list line
        flush_list()

        # Paragraphs
        if clean_line and not clean_line.startswith("#") and not clean_line.startswith("---"):
            p_text = format_inline(clean_line)
            body_html_parts.append(f"<p>{p_text}</p>")

    flush_list()
    flush_table()

    if current_sec_num > 0:
        body_html_parts.append("</section>")

    main_content = "\n".join(body_html_parts)
    status_badge_html = get_badge_html(doc_status)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agri Telemetry &amp; Forecasting — {doc_title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
{CSS_STYLES}
    </style>
{MATHJAX_MERMAID_SCRIPTS}
</head>
<body>

    <aside class="sidebar">
        <div class="brand">CA-ENG // Master Record</div>
        <div class="sidebar-meta">
            Agri Telemetry &amp; Forecasting<br>
            {doc_number} / {doc_category}<br>
            Status: {status_badge_html}
        </div>
        <nav aria-label="Document navigation">
            {sidebar_nav}
        </nav>
    </aside>

    <main class="main">
        <div class="top-meta">
            <span>Agri Telemetry &amp; Forecasting Platform</span>
            <span>Last Edited: {doc_date} &nbsp; / &nbsp; Status: {doc_status}</span>
        </div>

        <header class="hero">
            <div class="eyebrow">{doc_number} / {doc_category}</div>
            <h1>{doc_title}</h1>
            <p class="hero-description">Canonical engineering document for the Agri Telemetry &amp; Forecasting Platform.</p>
        </header>

{main_content}

        <footer class="footer">
            CA-ENG // Agri Telemetry &amp; Forecasting Platform<br>
            {doc_title} &nbsp;&bull;&nbsp; Last Edited: {doc_date} &nbsp;&bull;&nbsp; Status: {doc_status}
        </footer>
    </main>
</body>
</html>
"""
    return html_doc

def build_adr_register(folder_path: Path) -> str:
    """Builds a consolidated Master Architecture Decision Register from ADR_INDEX.md + all individual ADRs."""
    index_md_path = folder_path / "ADR_INDEX.md"
    if not index_md_path.exists():
        return ""
    
    with open(index_md_path, "r", encoding="utf-8") as f:
        index_content = f.read()

    # Read all individual ADRs in numerical order
    adr_files = sorted(folder_path.glob("ADR-*.md"))
    consolidated_parts = [index_content, "\n\n---\n\n## 3. Decision Records\n\n"]
    
    for adr_f in adr_files:
        with open(adr_f, "r", encoding="utf-8") as f:
            adr_text = f.read()
        
        # Demote headings so they fit inside section 3
        demoted = re.sub(r"^#\s+", "### ", adr_text, flags=re.MULTILINE)
        demoted = re.sub(r"^##\s+", "#### ", demoted, flags=re.MULTILINE)
        
        consolidated_parts.append(f"\n\n---\n\n{demoted}\n\n")

    full_md = "".join(consolidated_parts)
    return full_md

def run():
    parser = argparse.ArgumentParser(description="Agri Telemetry HTML Generator")
    parser.add_argument("--all", action="store_true", help="Force regeneration across all folders (overwriting bespoke early HTML)")
    args = parser.parse_args()

    base_dir = Path(__file__).parent.resolve()
    print(f"[generate_html] Scanning workspace at {base_dir} (mode: {'ALL' if args.all else 'NEW DOCS ONLY, BESPOKE PROTECTED'})...")
    
    doc_registry = [
        ("01", "Project Charter", "Project Charter", "Charter", True),
        ("02", "Research Feasibility", "Research Feasibility", "Research", True),
        ("03", "Product Requirements Doc", "Product Requirements Document", "Product", True),
        ("04", "Data & Scientific Spec", "Data & Scientific Specification", "Scientific Spec", True),
        ("05", "Data Forecast Design", "Data & Forecast Design", "Forecasting", True),
        ("06", "Technical Spec", "System Architecture & Technical Specification", "Architecture", False),
        ("07", "ADRs", "Architecture Decision Records", "Decisions", False),
        ("08", "Event & Telemetry Contract", "Event & Telemetry Interface Contract", "Contracts", False),
        ("09", "Implementation Plan", "Implementation Plan", "Implementation", False),
        ("10", "Evidence & Validation", "Evidence & Validation Framework", "Evidence", False),
    ]

    generated_count = 0
    for doc_num, folder_name, doc_title, doc_category, is_bespoke in doc_registry:
        folder_path = base_dir / folder_name
        if not folder_path.exists():
            continue

        if is_bespoke and not args.all:
            print(f"[PROTECTED] Preserving existing bespoke HTML in: {folder_name}")
            continue

        # Special handling for ADR folder
        if folder_name == "ADRs":
            print(f"[RENDER] {folder_name}/ADR_INDEX.md (+ ADR-001..005) -> ADR_INDEX.html")
            full_adr_md = build_adr_register(folder_path)
            html_output = render_markdown_to_ca_eng(full_adr_md, doc_num, doc_title, doc_category)
            html_path = folder_path / "ADR_INDEX.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_output)
            generated_count += 1
            continue

        md_files = list(folder_path.glob("*.md"))
        if not md_files:
            print(f"[SKIP] No .md found in {folder_name}")
            continue

        primary_md = md_files[0]
        for f in md_files:
            if "INDEX" in f.name.upper() or folder_name.lower() in f.name.lower():
                primary_md = f
                break

        html_name = primary_md.stem + ".html"
        html_path = folder_path / html_name

        print(f"[RENDER] {folder_name}/{primary_md.name} -> {html_name}")
        with open(primary_md, "r", encoding="utf-8") as f:
            md_content = f.read()

        html_output = render_markdown_to_ca_eng(md_content, doc_num, doc_title, doc_category)
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_output)
        
        generated_count += 1

    print(f"\n[DONE] Generation pass complete. Processed {generated_count} documents.")

if __name__ == "__main__":
    run()
