<p align="center">
  <img src="static/luna_logo_wordmark.png" alt="ClawCat Brief" width="420">
</p>

<p align="center">
  <strong>Pluggable AI-Powered Report Engine</strong> | 插件化 AI 智能简报引擎
</p>

<p align="center">
  Built with ❤️ by <strong>llx</strong> & <strong>Luna</strong> 🐱 (a brown tabby Maine Coon)
</p>

---

## What is ClawCat Brief?

ClawCat Brief is a fully-configurable, protocol-driven report generation engine. It fetches content from multiple sources in parallel, scores items with a pluggable multi-dimensional algorithm (BM25 + time decay + engagement + source trust), selects via MMR diversity reranking, generates opinionated reports via LLM with grounding checks, and renders into production-grade HTML/PDF with multi-channel delivery.

ClawCat Brief 是一个全配置化、协议驱动的报告生成引擎。并行抓取多数据源，通过可插拔多维评分（BM25 + 时间衰减 + 社区信号 + 来源信任度），MMR 多样性重排选材，LLM 生成有观点的深度报告并进行幻觉检测，渲染为产品级 HTML/PDF 并支持多渠道推送。

## Architecture / 架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          ReportPipeline                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Fetch   │→│ Score v2 │→│  Select  │→│  Memory  │            │
│  │ (async   │  │ (BM25+   │  │ (MMR/   │  │  Dedup   │            │
│  │  gather) │  │  Recency+ │  │  Top-K)  │  │ (3-level)│            │
│  └──────────┘  │  Engage+  │  └──────────┘  └──────────┘            │
│                │  Source)   │                     ↕                   │
│                └──────────┘           ┌─────────────────────────┐    │
│                               │     MemoryManager            │    │
│       ↓                       │  L1 ItemStore   (item dedup) │    │
│  ┌──────────┐                 │  L2 TopicStore  (theme div)  │    │
│  │Edit(LLM) │                 │  L3 ContentStore(claim neg)  │    │
│  │ stream/  │                 └─────────────────────────────┘    │
│  │  sync    │                                                     │
│  └──────────┘                                                     │
│       ↓                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Token    │→│ Grounding│→│   Quality    │→│Render(Jinja2 │  │
│  │ Budget   │  │ Pipeline │  │   Checker   │  │ +WeasyPrint) │  │
│  │(MapReduce│  │(4 checks)│  │  (+retry)   │  │              │  │
│  └──────────┘  └──────────┘  └──────────────┘  └──────────────┘  │
│                                                      ↓            │
│                                               ┌──────────────┐    │
│                                               │Email/Webhook │    │
│                                               │  Delivery    │    │
│                                               └──────────────┘    │
├──────────────────────────────────────────────────────────────────────┤
│  MiddlewareChain: Timing · Metrics · Custom Hooks                    │
│  Multi-Model Router: task-based LLM model selection                  │
│  BriefLogger: Structured logging with phase context                  │
│  Scheduler: Cron-based auto-generation + multi-channel push          │
└──────────────────────────────────────────────────────────────────────┘
```

## Design Patterns / 设计模式

| Pattern | Application | 应用 |
|---------|-------------|------|
| **Protocol** | `ScoringDimension` / `SelectionStrategy` / `GroundingChecker` / `MemoryStore` | 四层协议抽象 |
| **Adapter** | `BaseSource` → GitHub / arXiv / HN / PwC / FinNews / Yahoo / Eastmoney / Xueqiu | 8 个数据源统一接口 |
| **Strategy** | `BaseEditor` → Weekly / Daily / Finance / Stock / Generic | 9 种 LLM prompt 策略 |
| **Pipeline** | `ReportPipeline` — 9-stage flow (sync + streaming) | 9 阶段管线 |
| **Registry** | `@register_source` / `@register_editor` decorators | 装饰器零配置注册 |
| **Observer** | `MiddlewareChain` + `PipelineMiddleware` | 管线钩子系统 |
| **Factory** | `create_sources()` / `create_editor()` / `GroundingPipeline.create_default()` | 工厂模式 |
| **Facade** | `MemoryManager` / `GroundingPipeline` | 门面模式 |
| **Router** | `LLMClient._resolve_model()` task-based model routing | 多模型路由 |
| **Cache** | `FileCache` with TTL | 文件级 TTL 缓存 |

## Presets / 预设报告类型

| Preset | Description | Sources | Editor |
|--------|-------------|---------|--------|
| `ai_cv_weekly` | AI/CV tech deep-dive weekly | GitHub, arXiv, HN, PwC | tech_weekly |
| `ai_daily` | AI tech daily brief | GitHub, arXiv, HN | tech_daily |
| `finance_weekly` | Investment market weekly | FinNews, HN, Yahoo Finance | finance_weekly |
| `finance_daily` | Market flash daily | FinNews, HN, Yahoo Finance | finance_daily |
| `stock_a_daily` | A-share market daily (A股日报) | Eastmoney, Xueqiu, FinNews | stock_a |
| `stock_hk_daily` | HK stock market daily (港股日报) | FinNews, Yahoo Finance, Xueqiu | stock_hk |
| `stock_us_daily` | US stock market daily (美股日报) | Yahoo Finance, FinNews | stock_us |

**Auto-derivation**: `derive_preset()` automatically creates weekly/daily variants from any existing preset.

**Custom presets**: `python run.py --create-preset "我是新能源基金经理"` — LLM generates full config including scoring weights and target audience.

## Quick Start / 快速开始

```bash
pip install -r requirements.txt

# Configure LLM key (create config.local.yaml, gitignored)
cat > config.local.yaml << 'EOF'
llm:
  api_key: "your-api-key-here"
EOF

# Generate AI/CV Weekly (default)
python run.py

# Auto-route from natural language
python run.py --hint "今天A股怎么样"         # → stock_a_daily
python run.py --hint "生成A股周报"           # → auto-derive stock_a_weekly
python run.py --hint "帮我看看腾讯和阿里"    # → LLM auto-route

# Explicit preset
python run.py --preset stock_us_daily

# Generate and send via email
python run.py --preset ai_cv_weekly --email

# Create custom preset
python run.py --create-preset "我是半导体行业分析师，关注芯片设计和晶圆代工"

# Run scheduler (cron-based)
python -m brief.scheduler
```

## Key Features / 核心特性

### Scoring v2 — Pluggable Multi-Dimensional Scoring

Protocol-based scoring with 4 pluggable dimensions and configurable weights:

| Dimension | Algorithm | 算法 |
|-----------|-----------|------|
| `BM25Dimension` | TF-IDF with term frequency saturation (k1=1.5, b=0.75) | BM25 关键词相关性 |
| `RecencyDimension` | Hacker-News-style decay: `1/(1+(age/half_life)^1.5)` | 时间衰减 |
| `EngagementDimension` | Reddit-style: `log2(1+stars/100) + log2(1+points/10)` | 社区信号 |
| `SourceDimension` | Configurable source trust weights | 来源信任度 |

Selection via **MMR** (Maximal Marginal Relevance) for diversity-aware reranking, or simple **TopK**.

### Grounding System — Modular Hallucination Detection

4 pluggable checkers composed by `GroundingPipeline`:

| Checker | Detects | 检测内容 |
|---------|---------|----------|
| `TemporalGrounder` | Future dates, invalid timestamps | 时间幻觉 |
| `EntityGrounder` | Entities not in source items | 实体幻觉 |
| `NumericGrounder` | Ungrounded numeric claims | 数据幻觉 |
| `StructureGrounder` | Missing sections, insufficient Claw reviews | 结构缺陷 |

### Token Budget Manager

- Accurate token counting via `tiktoken`
- Map-Reduce batching for over-budget inputs (no truncation)
- Sentence-boundary-aware output length enforcement
- Configurable via `PresetConfig.max_word_count`

### Multi-Model Router

`LLMClient` routes tasks to different models based on type:

```yaml
llm:
  model: gpt-4o-mini
  model_routes:
    classify: gpt-4o-mini    # lightweight for intent parsing
    summarize: gpt-4o-mini   # cost-effective for summaries
    default: gpt-4o-mini     # full generation
```

### Three-Level Memory System

| Level | Store | Granularity | Effect |
|-------|-------|-------------|--------|
| L1 | `ItemStore` | item_id (SHA-256) | Same article won't be reused |
| L2 | `TopicStore` | keyword fingerprint (Jaccard) | Same theme won't repeat |
| L3 | `ContentStore` | LLM-extracted claims | Same viewpoint won't appear |

### Async Parallel Fetch

All data sources are fetched concurrently via `asyncio.gather` for maximum throughput.

### Content Engagement Engineering

LLM prompts include engagement rules: hook-first openings, contrast anchoring, data highlighting, suspenseful endings, audience-targeted language.

### Configurable Brand

Single-point brand configuration in `config.yaml` — changes propagate to all templates:

```yaml
brand:
  name: "ClawCat"
  full_name: "ClawCat Brief"
  tagline: "AI-Powered Report Engine"
  author: "by llx & Luna"
```

## Project Structure / 项目结构

```
lunaclaw-brief/
├── brief/
│   ├── models.py                   # Data models (Item, ScoredItem, PresetConfig...)
│   ├── presets.py                  # 7 built-in presets + derive_preset() + custom loader
│   ├── pipeline.py                 # 9-stage ReportPipeline (async fetch + grounding)
│   ├── registry.py                 # Plugin Registry (@register_source/editor)
│   ├── intent.py                   # Hybrid intent parser (regex + LLM)
│   ├── middleware.py               # Pipeline hooks (Timing, Metrics, Custom)
│   ├── log.py                      # Structured logging
│   ├── cache.py                    # File-based TTL cache
│   ├── quality.py                  # Quality checker
│   ├── llm.py                      # LLM client (multi-model router + streaming)
│   ├── token_budget.py             # Token budget manager (Map-Reduce)
│   ├── sender.py                   # Email + Webhook delivery
│   ├── scheduler.py                # Cron-based scheduler
│   ├── custom_preset.py            # LLM-based custom preset generator
│   ├── scoring/                    # Scoring v2 subpackage
│   │   ├── dimensions.py           #   ScoringDimension protocol + 4 implementations
│   │   ├── strategies.py           #   SelectionStrategy protocol (TopK + MMR)
│   │   └── scorer.py               #   Scorer + Selector composition
│   ├── grounding/                  # Grounding system subpackage
│   │   ├── protocol.py             #   GroundingChecker protocol + result types
│   │   ├── checkers.py             #   4 built-in checkers
│   │   └── pipeline.py             #   GroundingPipeline aggregator
│   ├── memory/                     # Three-level pluggable memory
│   │   ├── protocol.py             #   MemoryStore protocol
│   │   ├── item_store.py           #   L1: item-id dedup
│   │   ├── topic_store.py          #   L2: topic fingerprint diversity
│   │   ├── content_store.py        #   L3: claim extraction
│   │   └── manager.py              #   MemoryManager facade
│   ├── sources/                    # 8 data source adapters
│   ├── editors/                    # 9 editor strategies
│   └── renderer/                   # Jinja2 + WeasyPrint + Markdown parser
├── templates/                      # Jinja2 templates
├── static/                         # CSS design system + logo
├── run.py                          # CLI + OpenClaw Skill entry
├── config.yaml                     # Global config (brand, llm, schedule)
└── SKILL.md                        # Skill documentation
```

## Tech Stack / 技术栈

- **Python 3.10+** — async/await, dataclasses, type hints, Protocol
- **asyncio** — parallel data fetching (`asyncio.gather`)
- **tiktoken** — accurate LLM token counting
- **Jinja2** — template rendering
- **WeasyPrint** — HTML → PDF (optional)
- **OpenAI-compatible API** — LLM generation (auto-detects OpenClaw)

## License

MIT

---

*ClawCat Brief — where Luna holds the claws, and the claws hold the truth.* 🦞🐱
