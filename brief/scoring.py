"""LunaClaw Brief — Content Scoring & Item Selection

Multi-dimensional scoring engine driven by PresetConfig.
Supports both tech and finance domains via configurable keyword weights.

Architecture:
  - Scorer: assigns composite scores + domain tags to each Item.
  - Selector: deduplicates and picks Top-K by score.

The same Scorer class handles all presets — behavior is entirely
determined by PresetConfig.domain_keywords / source_weights / low_value_keywords.
Tags are assigned by a unified rule set covering tech AND finance domains.
"""

from brief.models import Item, ScoredItem, PresetConfig


# Unified tag rules covering all supported domains.
# Each tag maps to a list of trigger keywords (matched case-insensitively).
TAG_RULES: dict[str, list[str]] = {
    # ── Tech ──
    "OCR": [
        "ocr", "document ai", "text recognition",
        "document understanding", "layout analysis",
    ],
    "CV": [
        "computer vision", "detection", "segmentation",
        "image classification", "object detection",
    ],
    "Multimodal": [
        "multimodal", "vlm", "vision-language", "text-to-image",
    ],
    "LLM": [
        "llm", "large language model", "gpt", "transformer",
        "language model", "chatbot",
    ],
    "Agent": ["agent", "tool use", "function calling", "mcp"],
    "Medical": ["medical", "healthcare", "clinical", "pathology"],

    # ── Finance ──
    "Macro": [
        "gdp", "inflation", "interest rate", "fed ", "federal reserve",
        "central bank", "cpi", "ppi", "monetary policy", "fiscal",
        "recession", "employment", "unemployment",
    ],
    "Equity": [
        "stock", "equity", "earnings", "ipo", "buyback", "dividend",
        "s&p 500", "nasdaq", "dow jones", "valuation", "pe ratio",
        "market cap", "share price",
    ],
    "Credit": [
        "bond", "yield", "spread", "high-yield", "credit rating",
        "treasury", "fixed income", "debt",
    ],
    "Fintech": [
        "fintech", "payment", "digital bank", "neobank", "neo-bank",
        "insurtech", "regtech", "open banking", "embedded finance",
    ],
    "Crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "defi",
        "stablecoin", "blockchain", "web3",
    ],
    "VC": [
        "venture capital", "fundraising", "series a", "series b",
        "private equity", "seed round", "unicorn",
    ],
    "Semiconductor": [
        "semiconductor", "chip", "nvidia", "tsmc", "intel",
        "foundry", "wafer", "gpu shortage",
    ],
    # ── Regional Stock Markets ──
    "A-Share": [
        "a股", "沪深", "上证", "深证", "创业板", "科创板", "北交所",
        "a-share", "shanghai", "shenzhen", "csi 300", "沪深300",
        "北向资金", "融资融券", "板块轮动",
    ],
    "HK-Stock": [
        "港股", "恒生", "恒指", "hkex", "hang seng",
        "南向资金", "港股通", "h-share",
        "alibaba", "tencent", "中概股",
    ],
    "US-Stock": [
        "s&p 500", "nasdaq", "dow jones", "nyse",
        "us stock", "wall street", "faang",
        "apple", "nvidia", "microsoft", "google",
        "tesla", "amazon", "meta",
    ],
}


class Scorer:
    """Assigns multi-dimensional scores and domain tags to items.

    Scoring factors (all configurable via PresetConfig):
      1. Domain keyword match  → preset.domain_keywords
      2. Source weight          → preset.source_weights
      3. Community signal       → stars, points, comments
      4. Low-value filter       → preset.low_value_keywords (zero-score)
    """

    def __init__(self, preset: PresetConfig):
        self.preset = preset

    def score(self, items: list[Item]) -> list[ScoredItem]:
        result: list[ScoredItem] = []
        for item in items:
            text = f"{item.title} {item.raw_text}".lower()

            if any(kw in text for kw in self.preset.low_value_keywords):
                continue

            score = 1.0

            for keyword, weight in self.preset.domain_keywords.items():
                if keyword in text:
                    score += weight

            score += self.preset.source_weights.get(item.source, 0)

            # Community signals: GitHub stars
            stars = item.meta.get("stars", 0)
            if stars >= 1000:
                score += 3
            elif stars >= 500:
                score += 2
            elif stars >= 100:
                score += 1

            # Community signals: HN / Reddit points
            points = item.meta.get("points", 0)
            if points >= 100:
                score += 2
            elif points >= 30:
                score += 1

            # Community signals: comment count
            comments = item.meta.get("comments", 0)
            if comments >= 50:
                score += 1

            tags = self._assign_tags(text)
            result.append(ScoredItem(item=item, score=score, tags=tags))

        return result

    @staticmethod
    def _assign_tags(text: str) -> list[str]:
        """Assign domain tags using the unified TAG_RULES."""
        tags: list[str] = []
        for tag, keywords in TAG_RULES.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags or ["General"]


class Selector:
    """Deduplicates and selects Top-K scored items.

    Dedup order: URL → title prefix → sort by score → take Top-K.
    """

    def __init__(self, preset: PresetConfig):
        self.max_items = preset.max_items

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

        deduped.sort(key=lambda x: x.score, reverse=True)
        selected = deduped[: self.max_items]

        result: list[Item] = []
        for si in selected:
            si.item.meta["score"] = si.score
            si.item.meta["domain_tags"] = si.tags
            result.append(si.item)
        return result
