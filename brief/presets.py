"""LunaClaw Brief — Preset Definitions

Each preset is a complete configuration for a report type.
Add new presets here and they become instantly available via CLI / Skill.

Available presets:
  - ai_cv_weekly     : AI/CV tech deep-dive weekly
  - ai_daily         : AI tech daily brief
  - finance_weekly   : Investment-oriented market weekly
  - finance_daily    : Market flash daily
"""

from brief.models import PresetConfig

# ────────────────────────────────────────────
# Tech — AI / CV
# ────────────────────────────────────────────

AI_CV_WEEKLY = PresetConfig(
    name="ai_cv_weekly",
    display_name="AI/CV Weekly",
    cycle="weekly",
    editor_type="tech_weekly",
    sources=["github", "arxiv", "hackernews", "paperswithcode"],
    time_range_days=7,
    max_items=25,
    domain_keywords={
        "ocr": 5, "document ai": 5, "document understanding": 5,
        "layout analysis": 5, "text recognition": 5,
        "computer vision": 4, "cv": 4, "multimodal": 4,
        "vlm": 4, "vision-language": 4,
        "detection": 3, "segmentation": 3, "image": 3,
        "vision": 3, "medical imaging": 3,
    },
    source_weights={"arxiv": 2, "github": 1, "hackernews": 1, "paperswithcode": 2},
    low_value_keywords=[
        "crypto", "nft", "blockchain", "portfolio", "resume",
        "personal website", "job posting", "hiring", "awesome list",
    ],
    sections=[
        "core_conclusions", "events", "projects", "papers", "trends", "review",
    ],
    target_word_count=(4000, 5500),
    tone="sharp",
    min_sections=5,
    min_word_count=3500,
    dedup_window_days=30,
    template="weekly",
)

AI_DAILY = PresetConfig(
    name="ai_daily",
    display_name="AI Daily Brief",
    cycle="daily",
    editor_type="tech_daily",
    sources=["github", "arxiv", "hackernews"],
    time_range_days=1,
    max_items=10,
    domain_keywords={
        "llm": 3, "agent": 3, "multimodal": 3,
        "cv": 2, "ocr": 2, "vision": 2,
        "transformer": 2, "diffusion": 2,
    },
    source_weights={"hackernews": 2, "arxiv": 1, "github": 1},
    low_value_keywords=[
        "crypto", "nft", "blockchain", "portfolio", "resume",
    ],
    sections=["top_picks", "quick_takes"],
    target_word_count=(800, 1500),
    tone="sharp",
    min_sections=2,
    min_word_count=600,
    dedup_window_days=3,
    template="daily",
)

# ────────────────────────────────────────────
# Finance — Securities & Investment
# ────────────────────────────────────────────

FINANCE_WEEKLY = PresetConfig(
    name="finance_weekly",
    display_name="LunaClaw Finance Weekly",
    cycle="weekly",
    editor_type="finance_weekly",
    sources=["finnews", "hackernews"],
    time_range_days=7,
    max_items=20,
    domain_keywords={
        "earnings": 5, "revenue": 5, "ipo": 5, "fundraising": 5,
        "valuation": 4, "stock": 4, "market": 4, "fed": 4,
        "interest rate": 4, "gdp": 4,
        "fintech": 3, "payment": 3, "banking": 3,
        "venture capital": 3, "private equity": 3,
        "ai investment": 3, "semiconductor": 3,
    },
    source_weights={"finnews": 2, "hackernews": 1},
    low_value_keywords=[
        "meme", "shitcoin", "pump", "moon", "fomo",
    ],
    sections=[
        "core_judgment", "macro_policy", "sector_events",
        "tech_finance", "strategy", "risk",
    ],
    target_word_count=(4000, 5500),
    tone="sharp",
    min_sections=5,
    min_word_count=3500,
    dedup_window_days=14,
    template="finance",
)

FINANCE_DAILY = PresetConfig(
    name="finance_daily",
    display_name="LunaClaw Finance Daily",
    cycle="daily",
    editor_type="finance_daily",
    sources=["finnews", "hackernews"],
    time_range_days=1,
    max_items=10,
    domain_keywords={
        "earnings": 4, "stock": 4, "market": 4,
        "fed": 3, "interest rate": 3,
        "fintech": 2, "ipo": 2,
    },
    source_weights={"finnews": 2, "hackernews": 1},
    low_value_keywords=["meme", "shitcoin", "pump"],
    sections=["market_news", "signals"],
    target_word_count=(800, 1500),
    tone="sharp",
    min_sections=2,
    min_word_count=600,
    dedup_window_days=3,
    template="daily",
)

# ────────────────────────────────────────────
# Registry
# ────────────────────────────────────────────

PRESETS: dict[str, PresetConfig] = {
    "ai_cv_weekly": AI_CV_WEEKLY,
    "ai_daily": AI_DAILY,
    "finance_weekly": FINANCE_WEEKLY,
    "finance_daily": FINANCE_DAILY,
}


def get_preset(name: str) -> PresetConfig:
    """Look up a preset by name. Raises ValueError if not found."""
    if name not in PRESETS:
        raise ValueError(
            f"Unknown preset '{name}'. Available: {list(PRESETS.keys())}"
        )
    return PRESETS[name]
