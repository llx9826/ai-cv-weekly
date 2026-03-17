"""Selection strategies: how to pick final items from scored candidates.

Protocol: SelectionStrategy
  - select(scored_items, max_items, **kwargs) -> list[ScoredItem]

Implementations:
  TopKStrategy — Simple top-k by score
  MMRStrategy  — Maximal Marginal Relevance for diversity-aware selection
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from brief.models import ScoredItem


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

    Uses keyword-overlap Jaccard similarity as the diversity metric.
    """
    name = "mmr"

    def __init__(self, lambda_param: float = 0.7):
        self._lambda = lambda_param

    def select(self, items: list[ScoredItem], max_items: int) -> list[ScoredItem]:
        if not items:
            return []

        max_score = max(si.score for si in items) or 1.0

        item_keywords: list[set[str]] = []
        for si in items:
            text = f"{si.item.title} {si.item.raw_text}".lower()
            kw = set(text.split())
            item_keywords.append(kw)

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
                    intersection = len(item_keywords[r] & item_keywords[s])
                    union = len(item_keywords[r] | item_keywords[s])
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
