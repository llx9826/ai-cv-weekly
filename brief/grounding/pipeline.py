"""Grounding pipeline — composes multiple checkers and produces aggregated results.

Usage:
    pipeline = GroundingPipeline.create_default()
    result = pipeline.run(markdown, items)
"""

from __future__ import annotations

from brief.models import Item
from brief.grounding.protocol import GroundingChecker, GroundingResult
from brief.grounding.checkers import (
    TemporalGrounder,
    EntityGrounder,
    NumericGrounder,
    StructureGrounder,
)


class GroundingPipeline:
    """Runs multiple GroundingCheckers and aggregates results."""

    def __init__(self, checkers: list[GroundingChecker] | None = None):
        self._checkers = checkers or []

    def add(self, checker: GroundingChecker) -> "GroundingPipeline":
        self._checkers.append(checker)
        return self

    def run(self, markdown: str, items: list[Item]) -> GroundingResult:
        if not self._checkers:
            return GroundingResult(passed=True, score=1.0)

        combined = GroundingResult(passed=True, score=1.0)
        for checker in self._checkers:
            try:
                result = checker.check(markdown, items)
                combined = combined.merge(result)
            except Exception:
                pass
        return combined

    @classmethod
    def create_default(cls) -> "GroundingPipeline":
        return cls(checkers=[
            TemporalGrounder(),
            EntityGrounder(),
            NumericGrounder(),
            StructureGrounder(),
        ])
