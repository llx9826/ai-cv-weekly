# 🦞 LunaClaw Brief

> **Plugin-based intelligent report engine — AI-powered, extensible daily/weekly briefing system.**  
> 插件化智能简报引擎 — 由 AI 驱动，可扩展的日/周报生成系统。

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0.0-orange.svg)](skill.yaml)

---

## Features

- 🔌 **Plugin Architecture** — Add sources, editors, and presets without modifying core code
- 📊 **Smart Curation** — Multi-dimensional scoring, deduplication, and quality gates
- 🤖 **LLM-Powered Editing** — Sharp or neutral editorial tone with auto-retry
- 📧 **Email Delivery** — HTML body + optional PDF attachment via SMTP
- 🎨 **Customizable Templates** — Jinja2 + Design System CSS for professional output

## Architecture

```
┌──────┐   ┌───────┐   ┌───────┐   ┌──────┐   ┌──────────┐   ┌─────────┐   ┌───────┐   ┌───────┐
│Fetch │ → │ Score │ → │Select │ → │Dedup │ → │Edit(LLM) │ → │ Quality │ → │Render │ → │ Email │
└──────┘   └───────┘   └───────┘   └──────┘   └──────────┘   └─────────┘   └───────┘   └───────┘
```

| Stage | Description |
|-------|-------------|
| **Fetch** | Aggregate items from GitHub, arXiv, Hacker News, Papers with Code, FinNews |
| **Score** | Multi-dimensional relevance scoring (domain keywords, source weights) |
| **Select** | Top-K selection by composite score |
| **Dedup** | Filter items already covered in recent issues |
| **Edit (LLM)** | Generate report draft with LLM (exponential backoff retry) |
| **Quality** | Validate sections and word count; retry if below threshold |
| **Render** | Jinja2 HTML + optional WeasyPrint PDF |
| **Email** | Send via SMTP (optional) |

## Design Patterns

| Pattern | Usage |
|---------|-------|
| **Adapter** | `BaseSource` provides a unified interface for disparate data sources |
| **Strategy** | `BaseEditor` implements different prompt strategies per preset |
| **Pipeline** | `ReportPipeline` orchestrates 8 sequential stages |
| **Observer/Middleware** | `MiddlewareChain` for timing, metrics, and custom hooks |
| **Registry** | Decorator-based `SourceRegistry`, `EditorRegistry` for plugin discovery |
| **Factory** | `create_sources()`, `create_editor()` resolve by name |
| **Dataclass** | `Item`, `ScoredItem`, `PresetConfig` for type-safe data flow |

---

## Installation

```bash
git clone <repo-url>
cd ai-cv-weekly
pip install -r requirements.txt
```

Create `config.local.yaml` for secrets (API keys, tokens, email credentials):

```yaml
llm:
  api_key: "your-llm-api-key"
github:
  token: "your-github-token"
email:
  sender_email: "your@email.com"
  password: "app-password"
  to_emails: ["subscriber@example.com"]
```

---

## Quick Start

```bash
# Default: AI/CV Weekly report
python run.py

# AI Daily brief
python run.py --preset ai_daily

# Finance Weekly
python run.py --preset finance_weekly

# Finance Daily
python run.py --preset finance_daily

# Generate and send email
python run.py --preset ai_cv_weekly --email

# With custom hint for the LLM
python run.py --hint "Focus on OCR and document understanding this week"
```

## Available Presets

| Preset | Description |
|--------|-------------|
| `ai_cv_weekly` | Deep-dive AI/CV tech weekly (GitHub, arXiv, HN, PwC) |
| `ai_daily` | Quick AI tech daily brief |
| `finance_weekly` | Investment-oriented market weekly (FinNews, HN) |
| `finance_daily` | Market flash daily |

---

## Project Structure

```
ai-cv-weekly/
├── run.py                 # CLI entry point
├── config.yaml            # Base config (non-sensitive)
├── config.local.yaml      # Secrets (gitignored)
├── skill.yaml             # OpenClaw skill manifest
├── requirements.txt
├── brief/
│   ├── pipeline.py        # 8-stage ReportPipeline
│   ├── presets.py         # PresetConfig definitions
│   ├── models.py          # Item, ScoredItem, PresetConfig, etc.
│   ├── registry.py        # SourceRegistry, EditorRegistry
│   ├── sources/           # Data source adapters
│   │   ├── github.py
│   │   ├── arxiv.py
│   │   ├── hackernews.py
│   │   ├── paperswithcode.py
│   │   └── finnews.py
│   ├── editors/           # LLM editor strategies
│   │   ├── weekly.py
│   │   ├── daily.py
│   │   └── finance.py
│   ├── scoring.py
│   ├── dedup.py
│   ├── quality.py
│   ├── middleware.py
│   └── renderer/
├── templates/             # Jinja2 HTML
│   ├── base.html
│   ├── weekly.html
│   ├── daily.html
│   └── finance.html
├── static/                # CSS, assets
├── data/                  # used_items.json, issue_counter.json
└── output/                # Generated reports
```

---

## How to Extend

### Add a Source

1. Create `brief/sources/your_source.py`, inherit `BaseSource`
2. Implement `async def fetch(since, until) -> list[Item]`
3. Use `@register_source("your_source")` and add import in `brief/sources/__init__.py`

### Add an Editor

1. Create `brief/editors/your_editor.py`, inherit `BaseEditor`
2. Implement `_build_system_prompt()` and `_build_user_prompt()`
3. Use `@register_editor("your_editor")` and add import in `brief/editors/__init__.py`

### Add a Preset

1. Define `PresetConfig` in `brief/presets.py`
2. Add to `PRESETS` dict

### Add a Template

1. Create `templates/your_template.html` (extend `base.html`)
2. Set `template="your_template"` in the preset

---

## Contributing

Contributions are welcome. Please open an issue or submit a PR.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built with ❤️ by llx & Luna 🐱
