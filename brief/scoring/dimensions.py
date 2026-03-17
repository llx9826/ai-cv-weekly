"""Pluggable scoring dimensions — each computes a partial score for an Item.

Protocol: ScoringDimension
  - name: str
  - score(item, preset) -> float  (raw, unnormalized)

Implementations:
  BM25Dimension       — TF-IDF keyword relevance with BM25 saturation
  RecencyDimension    — Hacker-News-style time decay
  EngagementDimension — Reddit-style logarithmic community signals
  SourceDimension     — Source trust weighting from PresetConfig
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from brief.models import Item, PresetConfig


class ScoringDimension(ABC):
    """Protocol for pluggable scoring dimensions."""
    name: str = "base"

    @abstractmethod
    def score(self, item: Item, preset: PresetConfig) -> float:
        """Return raw score for this dimension (will be normalized later)."""
        ...


class BM25Dimension(ScoringDimension):
    """BM25-inspired keyword relevance scoring.

    Uses term frequency saturation (k1) and document length normalization (b)
    to prevent long documents from dominating.
    """
    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75, avg_dl: float = 200.0):
        self._k1 = k1
        self._b = b
        self._avg_dl = avg_dl

    def score(self, item: Item, preset: PresetConfig) -> float:
        text = f"{item.title} {item.raw_text}".lower()
        dl = len(text.split())
        total = 0.0
        for keyword, weight in preset.domain_keywords.items():
            tf = text.count(keyword.lower())
            if tf == 0:
                continue
            norm_tf = (tf * (self._k1 + 1)) / (tf + self._k1 * (1 - self._b + self._b * dl / self._avg_dl))
            total += norm_tf * weight
        return total


class RecencyDimension(ScoringDimension):
    """Hacker-News-style time decay: score = 1 / (1 + (age_hours / half_life))^1.5

    Configurable half_life via preset.decay_half_life_hours.
    """
    name = "recency"

    def score(self, item: Item, preset: PresetConfig) -> float:
        if not item.published_at:
            return 0.5
        try:
            pub = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_hours = max((now - pub).total_seconds() / 3600, 0.1)
        except (ValueError, TypeError):
            return 0.5

        half_life = preset.decay_half_life_hours or 24.0
        return 1.0 / (1.0 + (age_hours / half_life) ** 1.5)


class EngagementDimension(ScoringDimension):
    """Reddit-style logarithmic community engagement scoring.

    Combines stars, points, and comments with diminishing returns:
    score = log2(1 + stars/100) + log2(1 + points/10) + log2(1 + comments/5)
    """
    name = "engagement"

    def score(self, item: Item, preset: PresetConfig) -> float:
        stars = item.meta.get("stars", 0)
        points = item.meta.get("points", 0)
        comments = item.meta.get("comments", 0)

        s = math.log2(1 + stars / 100) if stars else 0.0
        p = math.log2(1 + points / 10) if points else 0.0
        c = math.log2(1 + comments / 5) if comments else 0.0
        return s + p + c


class SourceDimension(ScoringDimension):
    """Direct source weighting from PresetConfig.source_weights."""
    name = "source"

    def score(self, item: Item, preset: PresetConfig) -> float:
        return float(preset.source_weights.get(item.source, 0))
