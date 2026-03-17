"""LunaClaw Brief — Markdown → Structured Section Parser

Converts raw Markdown (from LLM) into a list of section dicts that
Jinja2 templates can render with icons, CSS classes, and HTML content.

HTML output uses Tailwind CSS + DaisyUI classes exclusively.

Supports the unified Markdown Schema:
  ## Section Title  →  section boundary
  ### N. Item Title →  numbered item card (DaisyUI card)
  **Label**：text   →  key-value row (flex layout)
  **🦞 Claw 锐评**  →  claw review card (border-l + warning)
  > quote           →  blockquote (hero summary)
  - item            →  bullet list
  everything else   →  paragraph
"""

import re


SECTION_STYLES = {
    # Hero section — top-level summary
    "📌 核心判断": {"css_class": "section-hero", "icon": "📌"},
    "核心判断": {"css_class": "section-hero", "icon": "📌"},
    # Tech sections
    "核心结论": {"css_class": "section-core", "icon": "💡"},
    "重点事件": {"css_class": "section-events", "icon": "🔥"},
    "开源项目": {"css_class": "section-projects", "icon": "🚀"},
    "论文推荐": {"css_class": "section-papers", "icon": "📄"},
    "论文": {"css_class": "section-papers", "icon": "📄"},
    "趋势分析": {"css_class": "section-trends", "icon": "📈"},
    "趋势": {"css_class": "section-trends", "icon": "📈"},
    "趋势策略": {"css_class": "section-strategy", "icon": "🧭"},
    "技术趋势策略": {"css_class": "section-strategy", "icon": "🧭"},
    "技术动向策略": {"css_class": "section-strategy", "icon": "🧭"},
    "复盘": {"css_class": "section-review", "icon": "🦞"},
    "Claw 复盘": {"css_class": "section-review", "icon": "🦞"},
    "今日必看": {"css_class": "section-core", "icon": "⚡"},
    "快评": {"css_class": "section-review", "icon": "🦞"},
    # Finance sections
    "市场核心判断": {"css_class": "section-core", "icon": "🎯"},
    "市场核心结论": {"css_class": "section-core", "icon": "🎯"},
    "宏观": {"css_class": "section-finance-macro", "icon": "🏛️"},
    "政策": {"css_class": "section-finance-macro", "icon": "🏛️"},
    "行业热点": {"css_class": "section-events", "icon": "🔥"},
    "公司事件": {"css_class": "section-events", "icon": "🏢"},
    "科技": {"css_class": "section-projects", "icon": "💻"},
    "金融交叉": {"css_class": "section-projects", "icon": "💻"},
    "投资策略": {"css_class": "section-strategy", "icon": "📊"},
    "策略建议": {"css_class": "section-strategy", "icon": "📊"},
    "投资信号与策略": {"css_class": "section-strategy", "icon": "📡"},
    "风险提示": {"css_class": "section-finance-risk", "icon": "⚠️"},
    "Claw 风险": {"css_class": "section-finance-risk", "icon": "🦞"},
    "市场要闻": {"css_class": "section-core", "icon": "📰"},
    "投资信号": {"css_class": "section-strategy", "icon": "📡"},
    # Stock market sections
    "A 股": {"css_class": "section-core", "icon": "🇨🇳"},
    "A股": {"css_class": "section-core", "icon": "🇨🇳"},
    "大盘走势": {"css_class": "section-core", "icon": "📈"},
    "港股": {"css_class": "section-core", "icon": "🇭🇰"},
    "美股": {"css_class": "section-core", "icon": "🇺🇸"},
    "板块": {"css_class": "section-events", "icon": "🔥"},
    "个股": {"css_class": "section-events", "icon": "📈"},
    "热门": {"css_class": "section-events", "icon": "🔥"},
    "资金面": {"css_class": "section-finance-macro", "icon": "💰"},
    "资金流": {"css_class": "section-finance-macro", "icon": "💰"},
    "情绪": {"css_class": "section-finance-macro", "icon": "🌡️"},
    "跨市场": {"css_class": "section-projects", "icon": "🔄"},
    "联动": {"css_class": "section-projects", "icon": "🔄"},
    "科技巨头": {"css_class": "section-events", "icon": "💻"},
    "热点个股": {"css_class": "section-events", "icon": "🔥"},
    "新股": {"css_class": "section-events", "icon": "🆕"},
    "异动": {"css_class": "section-finance-risk", "icon": "⚡"},
    "IPO": {"css_class": "section-events", "icon": "🆕"},
    "Claw 策略": {"css_class": "section-finance-risk", "icon": "🦞"},
    "深度解读": {"css_class": "section-events", "icon": "🔍"},
    "Claw 快评": {"css_class": "section-review", "icon": "🦞"},
}

DEFAULT_STYLE = {"css_class": "section-default", "icon": "📝"}

_KV_PATTERN = re.compile(r"^\*\*(.+?)\*\*\s*[:：]\s*(.+)")
_CLAW_START = re.compile(r"\*\*🦞\s*Claw\s*(锐评|风险)")
_CLAW_FULL = re.compile(r"\*\*🦞\s*Claw\s*(?:锐评|风险提示?)\*\*\s*[:：]?\s*(.*)")
_NUM_HEADING = re.compile(r"^(\d+)\.\s*(.*)")


def parse_sections(markdown: str) -> list[dict]:
    """Split Markdown on ## headings into section list."""
    sections: list[dict] = []
    lines = markdown.split("\n")
    current_title = None
    content_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title:
                sections.append(_make_section(current_title, content_lines))
            raw_title = line[3:].strip()
            raw_title = re.sub(r"\*\*", "", raw_title)
            raw_title = re.sub(r"🦞\s*", "", raw_title)
            current_title = raw_title.strip()
            content_lines = []
        elif line.strip() or content_lines:
            content_lines.append(line)

    if current_title:
        sections.append(_make_section(current_title, content_lines))

    return sections


def _make_section(title: str, content_lines: list[str]) -> dict:
    style = _match_style(title)
    content_html = _render_content("\n".join(content_lines))
    return {"title": title, "content": content_html, **style}


def _match_style(title: str) -> dict:
    clean = title.strip()
    best_keyword = ""
    best_style = DEFAULT_STYLE
    for keyword, style in SECTION_STYLES.items():
        if keyword in clean and len(keyword) > len(best_keyword):
            best_keyword = keyword
            best_style = style
    return best_style


def _render_content(content: str) -> str:
    """Convert Markdown content block to HTML."""
    content = re.sub(r"(?:^|\n+)---+\s*(?:\n|$)", "\n\n", content)

    if "### " in content:
        blocks = re.split(r"\n+(?=### )", content.strip())
        parts = []
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            parts.append(_render_block(b))
        return "\n".join(parts)
    return _render_block(content.strip())


def _render_block(content: str) -> str:
    lines = content.split("\n")
    html: list[str] = []
    in_claw = False
    claw_lines: list[str] = []
    in_item_block = False
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        clean = _strip_list_marker(stripped)

        # ### heading → DaisyUI card
        if stripped.startswith("### "):
            if in_claw:
                _flush_claw(html, claw_lines)
                in_claw = False
                claw_lines = []
            if in_item_block:
                html.append("</div></div>")
            h3_text = stripped[4:]
            num_html = ""
            m_num = _NUM_HEADING.match(h3_text)
            if m_num:
                num_html = (
                    f'<span class="absolute top-3 right-4 text-3xl font-black'
                    f' opacity-[0.04] font-mono select-none">'
                    f'{int(m_num.group(1)):02d}</span>'
                )
                h3_text = m_num.group(2)
            html.append(
                f'<div class="card bg-base-100 border border-base-300 mt-3 relative">'
                f'{num_html}'
                f'<div class="card-body p-4 gap-1">'
                f'<h3 class="font-semibold text-sm pr-8">{_inline(h3_text)}</h3>'
            )
            in_item_block = True
            i += 1
            continue

        # #### sub-heading
        if stripped.startswith("#### "):
            html.append(
                f'<h4 class="text-xs font-semibold uppercase tracking-wide'
                f' opacity-60 mt-3 mb-1">{stripped[5:]}</h4>'
            )
            i += 1
            continue

        # > blockquote
        if stripped.startswith("> "):
            quote_text = stripped[2:]
            html.append(f'<p class="my-1">{_inline(quote_text)}</p>')
            i += 1
            continue

        # Claw review start
        if _CLAW_START.match(clean):
            if in_claw:
                _flush_claw(html, claw_lines)
            in_claw = True
            claw_lines = []
            m = _CLAW_FULL.match(clean)
            if m and m.group(1).strip():
                claw_lines.append(m.group(1).strip())
            i += 1
            continue

        # Inside claw review — keep collecting until a structural break
        if in_claw:
            if stripped.startswith("### ") or stripped.startswith("## "):
                _flush_claw(html, claw_lines)
                in_claw = False
                claw_lines = []
                continue

            if not stripped:
                next_idx = i + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines):
                    next_line = lines[next_idx].strip()
                    next_clean = _strip_list_marker(next_line)
                    is_structural = (
                        next_line.startswith("### ")
                        or next_line.startswith("## ")
                        or _KV_PATTERN.match(next_clean)
                        or _CLAW_START.match(next_clean)
                        or (next_line.startswith("| ") and "|" in next_line[1:])
                    )
                    if is_structural:
                        _flush_claw(html, claw_lines)
                        in_claw = False
                        claw_lines = []
                        i += 1
                        continue
                i += 1
                continue

            if clean:
                claw_lines.append(clean)
            i += 1
            continue

        # **Label**：text → key-value row
        kv_match = _KV_PATTERN.match(clean)
        if kv_match:
            label = kv_match.group(1)
            value = kv_match.group(2).strip()
            if "🦞" not in label:
                html.append(
                    f'<div class="flex gap-2 py-1 text-sm border-b border-base-200">'
                    f'<span class="font-bold text-primary shrink-0 text-xs min-w-[72px]">'
                    f'{_inline(label)}</span>'
                    f'<span class="opacity-80 flex-1">{_inline(value)}</span>'
                    f'</div>'
                )
                i += 1
                continue

        # Markdown table
        if stripped.startswith("|") and "|" in stripped[1:]:
            table_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            html.append(_render_table(table_lines))
            continue

        # Dash-style list items
        if stripped.startswith("- ") and not stripped.startswith("---"):
            list_items = [stripped[2:]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("- "):
                list_items.append(lines[i].strip()[2:])
                i += 1
            html.append(
                '<ul class="list-disc pl-5 space-y-1 text-sm opacity-80">'
                + "".join(f"<li>{_inline(li)}</li>" for li in list_items)
                + "</ul>"
            )
            continue

        # Regular content
        display = clean if clean != stripped else stripped
        if display:
            html.append(f'<p class="text-sm opacity-80 mb-2">{_inline(display)}</p>')
        i += 1

    if in_claw and claw_lines:
        _flush_claw(html, claw_lines)

    if in_item_block:
        html.append("</div></div>")

    return "\n".join(html)


def _strip_list_marker(s: str) -> str:
    """Strip leading markdown list markers (* or numbered) and indentation."""
    return re.sub(r"^\s*(?:[\*\-]\s+|\d+\.\s+)", "", s).strip()


def _flush_claw(html: list[str], claw_lines: list[str]):
    """Render collected Claw review lines into a DaisyUI-styled card."""
    if not claw_lines:
        return
    items_html = "".join(
        f'<p class="text-sm leading-relaxed">{_inline(cl)}</p>'
        for cl in claw_lines
    )
    html.append(
        f'<div class="mt-3 rounded-lg border-l-4 border-warning bg-base-200 p-3">'
        f'<span class="badge badge-warning badge-sm gap-1 mb-2">🦞 Claw 锐评</span>'
        f'{items_html}'
        f'</div>'
    )


def _render_table(table_lines: list[str]) -> str:
    """Convert markdown table lines to DaisyUI table."""
    rows: list[list[str]] = []
    separator_idx = -1
    for idx, line in enumerate(table_lines):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^[-:]+$", c) for c in cells if c):
            separator_idx = idx
            continue
        rows.append(cells)

    if not rows:
        return ""

    html_parts = ['<div class="overflow-x-auto mt-2"><table class="table table-xs">']

    if separator_idx == 1 and len(rows) >= 1:
        header = rows[0]
        html_parts.append("<thead><tr>")
        for cell in header:
            html_parts.append(f"<th>{_inline(cell)}</th>")
        html_parts.append("</tr></thead>")
        body_rows = rows[1:]
    else:
        body_rows = rows

    html_parts.append("<tbody>")
    for row in body_rows:
        html_parts.append("<tr>")
        for cell in row:
            html_parts.append(f"<td>{_inline(cell)}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table></div>")

    return "".join(html_parts)


def _inline(text: str) -> str:
    """Inline formatting: bold / italic / link."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2" class="link link-primary">\1</a>', text)
    return text
