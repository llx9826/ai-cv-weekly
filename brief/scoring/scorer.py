"""Scorer v2 — Composes ScoringDimensions + SelectionStrategy.

Drop-in replacement for the legacy brief/scoring.py Scorer & Selector.
Behavior is driven entirely by PresetConfig fields:
  - scoring_weights: dict of dimension_name -> weight (default all equal)
  - selection_strategy: "topk" | "mmr"
  - mmr_lambda: float (for MMR)
"""

from __future__ import annotations

from brief.models import Item, ScoredItem, PresetConfig
from brief.scoring.dimensions import (
    ScoringDimension,
    BM25Dimension,
    RecencyDimension,
    EngagementDimension,
    SourceDimension,
)
from brief.scoring.strategies import (
    SelectionStrategy,
    TopKStrategy,
    MMRStrategy,
)

TAG_RULES: dict[str, list[str]] = {
    "OCR": ["ocr", "document ai", "text recognition", "document understanding", "layout analysis"],
    "CV": ["computer vision", "detection", "segmentation", "image classification", "object detection"],
    "Multimodal": ["multimodal", "vlm", "vision-language", "text-to-image"],
    "LLM": ["llm", "large language model", "gpt", "transformer", "language model", "chatbot"],
    "Agent": ["agent", "tool use", "function calling", "mcp"],
    "Medical": ["medical", "healthcare", "clinical", "pathology"],
    "Macro": ["gdp", "inflation", "interest rate", "fed ", "federal reserve", "central bank", "cpi", "ppi", "monetary policy", "fiscal", "recession", "employment", "unemployment"],
    "Equity": ["stock", "equity", "earnings", "ipo", "buyback", "dividend", "s&p 500", "nasdaq", "dow jones", "valuation", "pe ratio", "market cap", "share price"],
    "Credit": ["bond", "yield", "spread", "high-yield", "credit rating", "treasury", "fixed income", "debt"],
    "Fintech": ["fintech", "payment", "digital bank", "neobank", "neo-bank", "insurtech", "regtech", "open banking", "embedded finance"],
    "Crypto": ["bitcoin", "ethereum", "cryptocurrency", "defi", "stablecoin", "blockchain", "web3"],
    "VC": ["venture capital", "fundraising", "series a", "series b", "private equity", "seed round", "unicorn"],
    "Semiconductor": ["semiconductor", "chip", "nvidia", "tsmc", "intel", "foundry", "wafer", "gpu shortage"],
    "A-Share": ["a股", "沪深", "上证", "深证", "创业板", "科创板", "北交所", "a-share", "shanghai", "shenzhen", "csi 300", "沪深300", "北向资金", "融资融券", "板块轮动"],
    "HK-Stock": ["港股", "恒生", "恒指", "hkex", "hang seng", "南向资金", "港股通", "h-share", "alibaba", "tencent", "中概股"],
    "US-Stock": ["s&p 500", "nasdaq", "dow jones", "nyse", "us stock", "wall street", "faang", "apple", "nvidia", "microsoft", "google", "tesla", "amazon", "meta"],
}

_DEFAULT_WEIGHTS = {"bm25": 0.35, "recency": 0.25, "engagement": 0.25, "source": 0.15}

_ALL_DIMENSIONS: list[ScoringDimension] = [
    BM25Dimension(),
    RecencyDimension(),
    EngagementDimension(),
    SourceDimension(),
]

_STRATEGIES: dict[str, type[SelectionStrategy]] = {
    "topk": TopKStrategy,
    "mmr": MMRStrategy,
}


class Scorer:
    """Multi-dimensional scorer with pluggable dimensions and min-max normalization."""

    def __init__(self, preset: PresetConfig):
        self.preset = preset
        self._weights = preset.scoring_weights or dict(_DEFAULT_WEIGHTS)
        self._dimensions = [d for d in _ALL_DIMENSIONS if d.name in self._weights]

    def score(self, items: list[Item]) -> list[ScoredItem]:
        if not items:
            return []

        filtered = []
        for item in items:
            text = f"{item.title} {item.raw_text}".lower()
            if any(kw in text for kw in self.preset.low_value_keywords):
                continue
            filtered.append(item)

        if not filtered:
            return []

        raw_scores: dict[str, list[float]] = {d.name: [] for d in self._dimensions}
        for item in filtered:
            for dim in self._dimensions:
                raw_scores[dim.name].append(dim.score(item, self.preset))

        norm_scores: dict[str, list[float]] = {}
        for name, scores in raw_scores.items():
            lo, hi = min(scores), max(scores)
            span = hi - lo if hi > lo else 1.0
            norm_scores[name] = [(s - lo) / span for s in scores]

        result: list[ScoredItem] = []
        for i, item in enumerate(filtered):
            breakdown: dict[str, float] = {}
            composite = 0.0
            for d in self._dimensions:
                w = self._weights.get(d.name, 0)
                ns = norm_scores[d.name][i]
                breakdown[d.name] = round(ns, 4)
                composite += w * ns

            text = f"{item.title} {item.raw_text}".lower()
            tags = self._assign_tags(text)
            si = ScoredItem(item=item, score=round(composite, 4), tags=tags)
            si.item.meta["score_breakdown"] = breakdown
            result.append(si)

        return result

    @staticmethod
    def _assign_tags(text: str) -> list[str]:
        tags: list[str] = []
        for tag, keywords in TAG_RULES.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags or ["General"]


class Selector:
    """Selects items using a configurable strategy (TopK or MMR)."""

    def __init__(self, preset: PresetConfig):
        self.max_items = preset.max_items
        strategy_name = preset.selection_strategy or "mmr"
        strategy_cls = _STRATEGIES.get(strategy_name, MMRStrategy)

        if strategy_name == "mmr":
            self._strategy = strategy_cls(lambda_param=preset.mmr_lambda or 0.7)
        else:
            self._strategy = strategy_cls()

    def select(self, scored_items: list[ScoredItem]) -> list[Item]:
        seen_urls: set[str] = set()
        unique: list[ScoredItem] = []
        for si in scored_items:
            if si.item.url not in seen_urls:
                seen_urls.add(si.item.url)
                unique.append(si)

        seen_titles: set[str] = set()
        deduped: list[ScoredItem] = []
        for si in unique:
            key = si.item.title.lower()[:50]
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(si)

        selected = self._strategy.select(deduped, self.max_items)

        result: list[Item] = []
        for si in selected:
            si.item.meta["score"] = si.score
            si.item.meta["domain_tags"] = si.tags
            result.append(si.item)
        return result
