# 🦞 LunaClaw Brief

**Plugin-Based Intelligent Report Engine**  
**插件化智能简报引擎**

---

## Core Capabilities | 核心能力

| English | 中文 |
|---------|------|
| **Multi-Preset Support**: AI/CV weekly, AI daily, Finance weekly/daily — extendable to OCR, fintech, etc. | **多 Preset 支持**：AI/CV 周报、AI 日报、金融周/日报，可扩展至 OCR、金融科技等 |
| **Plugin Data Sources**: GitHub, arXiv, Hacker News, Papers with Code, FinNews — extend via `BaseSource` | **插件化数据源**：GitHub、arXiv、Hacker News、Papers with Code、FinNews，实现 `BaseSource` 即可扩展 |
| **Smart Scoring & Dedup**: Multi-dimensional scoring model + historical dedup, ensures no duplicate content | **智能打分 & 去重**：多维评分模型 + 历史去重，确保每期内容不重复 |
| **LLM Editor**: Sharp or neutral tone, in-depth editorial with commentary | **LLM 主编**：支持 sharp/neutral 两种风格，带锐评的深度内容 |
| **Quality Control**: Auto-check sections, word count, structure; retry on failure | **质量控制**：自动检查章节、字数、结构，不达标自动重试 |
| **Elegant Rendering**: Jinja2 templates + Design System CSS, HTML/PDF output | **精美渲染**：Jinja2 模板 + Design System CSS，支持 HTML/PDF 输出 |
| **Email Delivery**: HTML body + optional PDF attachment | **邮件推送**：HTML 正文 + PDF 附件 |

---

## Architecture | 架构

8-stage pipeline with middleware hooks:

```
┌──────┐   ┌───────┐   ┌───────┐   ┌──────┐   ┌──────────┐   ┌─────────┐   ┌───────┐   ┌───────┐
│Fetch │ → │ Score │ → │Select │ → │Dedup │ → │Edit(LLM) │ → │ Quality │ → │Render │ → │ Email │
└──────┘   └───────┘   └───────┘   └──────┘   └──────────┘   └─────────┘   └───────┘   └───────┘
```

1. **Fetch** — Aggregate items from all configured sources (async)
2. **Score** — Multi-dimensional relevance scoring (domain keywords, source weights)
3. **Select** — Top-K selection by score
4. **Dedup** — Filter out items seen in recent issues
5. **Edit (LLM)** — Generate report draft with LLM (retry on failure)
6. **Quality** — Validate sections, word count; retry if needed
7. **Render** — Jinja2 HTML (+ optional WeasyPrint PDF)
8. **Email** — Send via SMTP (optional)

---

## Design Patterns | 设计模式

| Pattern | 模式 | Application | 应用 |
|---------|------|--------------|------|
| **Adapter** | 适配器 | `BaseSource` → unified interface for GitHub, arXiv, HN, etc. | 各数据源统一接口 |
| **Strategy** | 策略 | `BaseEditor` → different prompt strategies (weekly vs daily) | 周报/日报不同 prompt 策略 |
| **Pipeline** | 管线 | `ReportPipeline` — 8 stages in sequence | 8 阶段串联 |
| **Observer / Middleware** | 观察者/中间件 | `MiddlewareChain` — timing, metrics, custom hooks | 计时、指标、自定义钩子 |
| **Registry** | 注册表 | `SourceRegistry`, `EditorRegistry` — decorator-based discovery | `@register_source` / `@register_editor` |
| **Factory** | 工厂 | `create_sources()`, `create_editor()` | 按名称创建实例 |
| **Dataclass** | 数据类 | `Item`, `ScoredItem`, `PresetConfig`, `ReportDraft` | 类型安全、不可变友好 |

---

## Quick Start | 快速开始

```bash
# AI/CV Weekly (default) — 生成 AI/CV 周报
python run.py

# AI Daily — 生成 AI 日报
python run.py --preset ai_daily

# Finance Weekly — 生成金融周报
python run.py --preset finance_weekly

# Finance Daily — 生成金融日报
python run.py --preset finance_daily

# With email delivery — 生成后发送邮件
python run.py --preset ai_cv_weekly --email

# With custom hint for LLM — 给 LLM 的额外提示
python run.py --hint "本期重点关注 OCR 和文档理解方向"
```

---

## Extension Guide | 扩展指南

### Add a new Source | 添加新数据源

1. Create `brief/sources/your_source.py`
2. Inherit `BaseSource`, implement `fetch(since, until) -> list[Item]`
3. Register: `@register_source("your_source")` (from `brief.registry`)
4. Add `import brief.sources.your_source` in `brief/sources/__init__.py`

### Add a new Editor | 添加新编辑器

1. Create `brief/editors/your_editor.py`
2. Inherit `BaseEditor`, implement `_build_system_prompt()` and `_build_user_prompt()`
3. Register: `@register_editor("your_editor")`
4. Add import in `brief/editors/__init__.py`

### Add a new Preset | 添加新 Preset

1. In `brief/presets.py`, define `PresetConfig(name=..., sources=..., editor_type=..., ...)`
2. Add to `PRESETS` dict: `PRESETS["your_preset"] = YourPreset`

### Add a new Template | 添加新模板

1. Create `templates/your_template.html` (extend `base.html`)
2. Set `template="your_template"` in the Preset

---

## Tech Stack | 技术栈

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **Async I/O** | `aiohttp`, `asyncio` |
| **LLM** | OpenAI-compatible API (Kimi, DashScope) |
| **Template** | Jinja2 |
| **Config** | YAML (`config.yaml` + `config.local.yaml`) |
| **PDF** | WeasyPrint (optional) |
| **Email** | SMTP (smtplib) |
| **Deps** | `requests`, `pyyaml`, `jinja2`, `aiohttp` |

---

Built with ❤️ by llx & Luna 🐱
