"""Grounding checker protocol — defines the interface for hallucination detectors.

Each checker examines generated text against source items and returns
a GroundingResult with issues found and a confidence score.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from brief.models import Item


@dataclass
class GroundingIssue:
    """A single hallucination or quality issue found by a grounding checker."""
    checker: str
    severity: str  # "error" | "warning" | "info"
    message: str
    span: str = ""  # the problematic text span


@dataclass
class GroundingResult:
    """Aggregated result from one or more grounding checkers."""
    passed: bool
    score: float  # 0.0 ~ 1.0
    issues: list[GroundingIssue] = field(default_factory=list)

    def merge(self, other: "GroundingResult") -> "GroundingResult":
        combined_issues = self.issues + other.issues
        combined_score = (self.score + other.score) / 2
        return GroundingResult(
            passed=self.passed and other.passed,
            score=combined_score,
            issues=combined_issues,
        )


class GroundingChecker(ABC):
    """Abstract base for all grounding/hallucination checkers."""
    name: str = "base"

    @abstractmethod
    def check(self, markdown: str, items: list[Item]) -> GroundingResult:
        """Check generated markdown against source items for hallucinations."""
        ...
