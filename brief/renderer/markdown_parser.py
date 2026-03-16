"""LunaClaw Brief — Markdown → Structured Section Parser

Converts raw Markdown (from LLM) into a list of section dicts that
Jinja2 templates can render with icons, CSS classes, and HTML content.

Supports both tech and finance report section keywords.
"""

import re


# Section style map: Chinese keyword → visual properties
SECTION_STYLES = {
    # Tech sections
    "核心结论": {"css_class": "section-core", "icon": "💡", "gradient": "from-amber-400 to-orange-500"},
    "重点事件": {"css_class": "section-events", "icon": "🔥", "gradient": "from-blue-400 to-indigo-500"},
    "开源项目": {"css_class": "section-projects", "icon": "🚀", "gradient": "from-green-400 to-emerald-500"},
    "论文推荐": {"css_class": "section-papers", "icon": "📄", "gradient": "from-cyan-400 to-blue-500"},
    "论文": {"css_class": "section-papers", "icon": "📄", "gradient": "from-cyan-400 to-blue-500"},
    "趋势分析": {"css_class": "section-trends", "icon": "📈", "gradient": "from-purple-400 to-pink-500"},
    "趋势": {"css_class": "section-trends", "icon": "📈", "gradient": "from-purple-400 to-pink-500"},
    "复盘": {"css_class": "section-review", "icon": "🦞", "gradient": "from-orange-400 to-red-500"},
    "Claw 复盘": {"css_class": "section-review", "icon": "🦞", "gradient": "from-orange-400 to-red-500"},
    "今日必看": {"css_class": "section-core", "icon": "⚡", "gradient": "from-amber-400 to-orange-500"},
    "快评": {"css_class": "section-review", "icon": "🦞", "gradient": "from-orange-400 to-red-500"},
    # Finance sections
    "核心判断": {"css_class": "section-core", "icon": "🎯", "gradient": "from-amber-400 to-orange-500"},
    "市场核心判断": {"css_class": "section-core", "icon": "🎯", "gradient": "from-amber-400 to-orange-500"},
    "宏观": {"css_class": "section-finance-macro", "icon": "🏛️", "gradient": "from-blue-400 to-indigo-500"},
    "政策": {"css_class": "section-finance-macro", "icon": "🏛️", "gradient": "from-blue-400 to-indigo-500"},
    "行业热点": {"css_class": "section-events", "icon": "🔥", "gradient": "from-orange-400 to-red-500"},
    "公司事件": {"css_class": "section-events", "icon": "🏢", "gradient": "from-orange-400 to-red-500"},
    "科技": {"css_class": "section-projects", "icon": "💻", "gradient": "from-cyan-400 to-blue-500"},
    "金融交叉": {"css_class": "section-projects", "icon": "💻", "gradient": "from-cyan-400 to-blue-500"},
    "投资策略": {"css_class": "section-finance-strategy", "icon": "📊", "gradient": "from-green-400 to-emerald-500"},
    "策略建议": {"css_class": "section-finance-strategy", "icon": "📊", "gradient": "from-green-400 to-emerald-500"},
    "风险提示": {"css_class": "section-finance-risk", "icon": "⚠️", "gradient": "from-red-400 to-rose-500"},
    "Claw 风险": {"css_class": "section-finance-risk", "icon": "🦞", "gradient": "from-red-400 to-rose-500"},
    "市场要闻": {"css_class": "section-core", "icon": "📰", "gradient": "from-amber-400 to-orange-500"},
    "投资信号": {"css_class": "section-finance-strategy", "icon": "📡", "gradient": "from-green-400 to-emerald-500"},
}

DEFAULT_STYLE = {"css_class": "section-default", "icon": "📝", "gradient": "from-gray-400 to-gray-500"}


def parse_sections(markdown: str) -> list[dict]:
    """把 Markdown 按 ## 标题拆成 section 列表"""
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
    for keyword, style in SECTION_STYLES.items():
        if keyword in clean:
            return style
    return DEFAULT_STYLE


def _render_content(content: str) -> str:
    """把 Markdown 内容块转成 HTML"""
    content = re.sub(r"\n+---+\n*", "\n\n", content)

    if "### " in content:
        blocks = re.split(r"\n+(?=### )", content.strip())
        return "\n".join(_render_block(b.strip()) for b in blocks if b.strip())
    return _render_block(content.strip())


def _render_block(content: str) -> str:
    lines = content.split("\n")
    html: list[str] = []
    in_claw = False
    claw_lines: list[str] = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("### "):
            html.append(f'<div class="item-block"><h3>{stripped[4:]}</h3>')
            i += 1
            continue

        if stripped.startswith("#### "):
            html.append(f"<h4>{stripped[5:]}</h4>")
            i += 1
            continue

        # 锐评开始
        if re.match(r"\*\*🦞 Claw 锐评\*\*[:：]", stripped):
            in_claw = True
            claw_lines = []
            match = re.match(r"\*\*🦞 Claw 锐评\*\*[:：](.+)", stripped)
            if match:
                claw_lines.append(match.group(1))
            i += 1
            continue

        if in_claw:
            if not stripped or stripped.startswith("### ") or stripped.startswith("#### ") or re.match(r"\*\*🦞", stripped):
                if claw_lines:
                    text = _inline((" ".join(claw_lines)))
                    html.append(
                        f'<div class="claw-card"><div class="claw-label">🦞 Claw 锐评</div><p>{text}</p></div>'
                    )
                in_claw = False
                claw_lines = []
                continue
            claw_lines.append(stripped)
            i += 1
            continue

        # 列表
        if stripped.startswith("- ") and not stripped.startswith("---"):
            list_items = [stripped[2:]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("- "):
                list_items.append(lines[i].strip()[2:])
                i += 1
            html.append("<ul>" + "".join(f"<li>{_inline(li)}</li>" for li in list_items) + "</ul>")
            continue

        if stripped:
            html.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    # 关闭最后锐评
    if in_claw and claw_lines:
        text = _inline(" ".join(claw_lines))
        html.append(f'<div class="claw-card"><div class="claw-label">🦞 Claw 锐评</div><p>{text}</p></div>')

    if html:
        html.append("</div>")

    return "\n".join(html)


def _inline(text: str) -> str:
    """行内格式化：bold / italic / link"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text
