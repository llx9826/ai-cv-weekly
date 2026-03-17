"""Selection strategies: how to pick final items from scored candidates.

Protocol: SelectionStrategy
  - select(scored_items, max_items, **kwargs) -> list[ScoredItem]

Implementations:
  TopKStrategy — Simple top-k by score
  MMRStrategy  — Maximal Marginal Relevance for diversity-aware selection
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from brief.models import ScoredItem

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def _text_to_shingles(text: str, n: int = 2) -> set[str]:
    """Extract character n-gram shingles that work for CJK + Latin mixed text.

    For CJK characters: extract character bigrams directly.
    For Latin words: extract word-level tokens.
    Produces a unified set for Jaccard similarity.
    """
    text = text.lower()
    shingles: set[str] = set()

    for word in text.split():
        if _CJK_RE.search(word):
            chars = [c for c in word if not c.isspace()]
            for i in range(len(chars) - n + 1):
                shingles.add("".join(chars[i:i + n]))
            if len(chars) == 1:
                shingles.add(chars[0])
        else:
            shingles.add(word)

    cjk_only = "".join(_CJK_RE.findall(text))
    for i in range(len(cjk_only) - n + 1):
        shingles.add(cjk_only[i:i + n])

    return shingles


class SelectionStrategy(ABC):
    """Protocol for item selection strategies."""
    name: str = "base"

    @abstractmethod
    def select(self, items: list[ScoredItem], max_items: int) -> list[ScoredItem]:
        ...


class TopKStrategy(SelectionStrategy):
    """Simple top-k selection by composite score."""
    name = "topk"

    def select(self, items: list[ScoredItem], max_items: int) -> list[ScoredItem]:
        sorted_items = sorted(items, key=lambda x: x.score, reverse=True)
        return sorted_items[:max_items]


class MMRStrategy(SelectionStrategy):
    """Maximal Marginal Relevance: balances relevance and diversity.

    MMR = lambda * relevance - (1 - lambda) * max_similarity_to_selected

    Uses character-shingle Jaccard similarity as the diversity metric,
    which works correctly for both CJK and Latin text.
    """
    name = "mmr"

    def __init__(self, lambda_param: float = 0.7):
        self._lambda = lambda_param

    def select(self, items: list[ScoredItem], max_items: int) -> list[ScoredItem]:
        if not items:
            return []

        max_score = max(si.score for si in items) or 1.0

        item_shingles: list[set[str]] = []
        for si in items:
            text = f"{si.item.title} {si.item.raw_text}"
            item_shingles.append(_text_to_shingles(text))

        selected: list[int] = []
        remaining = set(range(len(items)))

        best_idx = max(remaining, key=lambda i: items[i].score)
        selected.append(best_idx)
        remaining.discard(best_idx)

        while len(selected) < max_items and remaining:
            best_mmr = -float("inf")
            best_r = -1

            for r in remaining:
                relevance = items[r].score / max_score

                max_sim = 0.0
                for s in selected:
                    intersection = len(item_shingles[r] & item_shingles[s])
                    union = len(item_shingles[r] | item_shingles[s])
                    sim = intersection / union if union else 0.0
                    max_sim = max(max_sim, sim)

                mmr = self._lambda * relevance - (1 - self._lambda) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_r = r

            if best_r < 0:
                break
            selected.append(best_r)
            remaining.discard(best_r)

        return [items[i] for i in selected]
