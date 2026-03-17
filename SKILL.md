# 🦞 ClawCat Brief — OpenClaw Skill

**Pluggable AI-Powered Report Engine** | 插件化 AI 智能简报引擎

## Overview / 概述

ClawCat Brief is an OpenClaw Skill that generates intelligent reports across multiple domains. It features a protocol-driven plugin architecture with:

- **9-stage pipeline** with async parallel fetch, grounding checks, and token budget management
- **8 data sources** with pluggable adapter protocol
- **9 editor strategies** (tech/finance/stock/generic)
- **Scoring v2**: 4 pluggable dimensions (BM25/Recency/Engagement/Source) + MMR diversity reranking
- **Grounding system**: 4 modular hallucination detectors
- **Three-level memory**: item dedup → topic diversity → claim extraction
- **Multi-model LLM router**: task-based model selection
- **Token budget manager**: Map-Reduce batching, no truncation
- Hybrid intent routing, streaming output, multi-channel delivery

## Presets / 预设

| Preset | Type | Description |
|--------|------|-------------|
| `ai_cv_weekly` | Tech | AI/CV/多模态技术深度周报 |
| `ai_daily` | Tech | AI 技术日报 |
| `finance_weekly` | Finance | 金融投资周报 |
| `finance_daily` | Finance | 金融快报日刊 |
| `stock_a_daily` | Stock | A 股日报（大盘/板块/北向资金/IPO/异动） |
| `stock_hk_daily` | Stock | 港股日报（恒生/南向资金/中概股/IPO） |
| `stock_us_daily` | Stock | 美股日报（S&P/NASDAQ/科技巨头/IPO） |
| Custom | Any | via `--create-preset` or `derive_preset()` |

**Auto-derive**: Weekly/daily variants auto-generated from any existing preset.

## Usage / 使用方式

### Via CLI

```bash
python run.py                                    # AI/CV Weekly (default)
python run.py --preset stock_a_daily             # A-share daily
python run.py --hint "今天A股怎么样"               # Auto-route → stock_a_daily
python run.py --hint "生成A股周报"                 # Auto-derive → stock_a_weekly
python run.py --hint "帮我做一份教育日报"           # LLM auto-create preset
python run.py --create-preset "我是新能源基金经理"  # Create custom preset
python -m brief.scheduler                        # Run scheduled jobs
```

### Via OpenClaw Skill API

```python
from run import generate_report

result = generate_report({
    "preset": "stock_hk_daily",
    "hint": "重点关注腾讯和美团",
    "send_email": True,
})
```

## Key Capabilities / 核心能力

- **Scoring v2**: Pluggable `ScoringDimension` protocol — BM25 relevance, HN-style time decay, Reddit-style engagement, source trust weighting. Configurable weights per preset.
- **MMR Selection**: Maximal Marginal Relevance balances relevance and diversity to avoid redundant content.
- **Grounding Pipeline**: 4 modular `GroundingChecker` implementations — temporal, entity, numeric, structure validation. Composable via `GroundingPipeline`.
- **Token Budget**: `tiktoken`-based counting + Map-Reduce batching for long inputs + sentence-boundary output trimming.
- **Multi-Model Router**: `LLMClient` routes `chat`/`classify`/`summarize` to different models for cost optimization.
- **Async Parallel Fetch**: `asyncio.gather` for concurrent data source fetching.
- **Content Engagement**: Prompt engineering with hook-first, contrast anchoring, data highlighting, audience targeting.
- **Three-Level Memory**: Pluggable `MemoryStore` protocol — item dedup, topic diversity, claim extraction.
- **Hybrid Intent Router**: Regex (instant) + LLM classification (fallback) for preset routing.
- **Streaming Output**: `pipeline.run_stream()` yields progress events + content chunks.
- **Multi-Channel Delivery**: Email (SMTP), Webhook (Slack/DingTalk/Feishu/custom).
- **Configurable Brand**: Single-point brand config propagates to all templates.

## Architecture / 架构

| Pattern | Where |
|---------|-------|
| Protocol | `ScoringDimension` / `SelectionStrategy` / `GroundingChecker` / `MemoryStore` |
| Adapter | `BaseSource` → 8 source adapters |
| Strategy | `BaseEditor` → 9 editor strategies |
| Pipeline | 9-stage `ReportPipeline` (async + stream) |
| Registry | `@register_source` / `@register_editor` decorators |
| Observer | `MiddlewareChain` for timing, metrics, custom hooks |
| Router | `LLMClient._resolve_model()` for task-based model selection |
| Factory | `create_sources()` / `create_editor()` / `GroundingPipeline.create_default()` |
| Facade | `MemoryManager` / `GroundingPipeline` |
| Cache | `FileCache` with TTL |

## Configuration / 配置

```yaml
# config.yaml
brand:
  name: "ClawCat"
  full_name: "ClawCat Brief"
  tagline: "AI-Powered Report Engine"
  author: "by llx & Luna"

llm:
  model: gpt-4o-mini
  model_routes:
    classify: gpt-4o-mini
    summarize: gpt-4o-mini
  context_window: 128000
  output_reserve: 8000
```

Secrets in `config.local.yaml` (gitignored). Auto-detects OpenClaw environment.

## Output / 输出

- **HTML**: Self-contained dark-theme report (financial terminal aesthetic)
- **PDF**: Dark-theme preserved via WeasyPrint
- **Markdown**: Raw LLM output
- **Email**: HTML body + PDF attachment
- **Webhook**: Slack/DingTalk/Feishu/custom HTTP POST

---

*Built by llx & Luna 🐱 — where the claw meets the code.* 🦞
