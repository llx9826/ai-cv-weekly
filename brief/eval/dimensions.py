"""Evaluation dimensions — pluggable metrics for report quality assessment.

Each dimension implements a score() method returning an EvalMetric.
All dimensions are stateless and preset-aware.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter

from brief.models import Item, PresetConfig, Citation, EvalMetric


class EvalDimension(ABC):
    """Base class for evaluation dimensions."""
    name: str = "base"
    weight: float = 1.0

    @abstractmethod
    def score(
        self,
        markdown: str,
        preset: PresetConfig,
        items: list[Item] | None = None,
        fact_table=None,
        citations: list[Citation] | None = None,
    ) -> EvalMetric:
        ...


class FactAccuracyDim(EvalDimension):
    """Measures what percentage of numeric claims are traceable to sources."""
    name = "fact_accuracy"
    weight = 2.0

    def score(self, markdown, preset, items=None, fact_table=None, citations=None, **kw):
        if not citations:
            return EvalMetric(name=self.name, score=1.0, detail="No claims to verify")

        total = len(citations)
        grounded = sum(1 for c in citations if c.confidence > 0)
        ratio = grounded / total if total else 1.0

        return EvalMetric(
            name=self.name,
            score=round(ratio, 3),
            max_score=1.0,
            detail=f"{grounded}/{total} claims grounded ({ratio:.0%})",
        )


class StructureCompletenessDim(EvalDimension):
    """Checks whether all required sections and formatting rules are met."""
    name = "structure_completeness"
    weight = 1.5

    def score(self, markdown, preset, **kw):
        checks = 0
        passed = 0

        h2_count = len(re.findall(r"^## ", markdown, re.MULTILINE))
        checks += 1
        if h2_count >= preset.min_sections:
            passed += 1
        section_detail = f"sections={h2_count}/{preset.min_sections}"

        h3_count = len(re.findall(r"^### \d+\.", markdown, re.MULTILINE))
        checks += 1
        if h3_count >= 2:
            passed += 1

        checks += 1
        claw_count = markdown.count("🦞 Claw 锐评")
        if preset.tone == "sharp" and claw_count >= 1:
            passed += 1
        elif preset.tone != "sharp":
            passed += 1

        checks += 1
        if not markdown.strip().startswith("```"):
            passed += 1

        ratio = passed / checks if checks else 1.0
        return EvalMetric(
            name=self.name,
            score=round(ratio, 3),
            max_score=1.0,
            detail=f"{passed}/{checks} checks passed ({section_detail})",
        )


class WordCountHitDim(EvalDimension):
    """Measures how close the output is to the target word count range."""
    name = "word_count_hit"
    weight = 1.0

    def score(self, markdown, preset, **kw):
        char_count = len(markdown)
        lo, hi = preset.target_word_count
        max_wc = preset.max_word_count or hi

        if lo <= char_count <= max_wc:
            s = 1.0
            detail = f"{char_count} chars in range [{lo}, {max_wc}]"
        elif char_count < lo:
            s = max(char_count / lo, 0.0)
            detail = f"{char_count} chars below min {lo}"
        else:
            overshoot = (char_count - max_wc) / max_wc
            s = max(1.0 - overshoot, 0.0)
            detail = f"{char_count} chars above max {max_wc} (overshoot {overshoot:.0%})"

        return EvalMetric(name=self.name, score=round(s, 3), detail=detail)


class CitationCoverageDim(EvalDimension):
    """Measures the breadth and quality of citation coverage."""
    name = "citation_coverage"
    weight = 1.5

    def score(self, markdown, preset, citations=None, **kw):
        if not citations:
            return EvalMetric(name=self.name, score=0.5, detail="No citations generated")

        total = len(citations)
        fact_backed = sum(1 for c in citations if c.fact_key)
        source_backed = sum(1 for c in citations if c.source_url and not c.fact_key)
        ungrounded = total - fact_backed - source_backed

        coverage = (fact_backed + source_backed) / total if total else 0
        fact_bonus = min(fact_backed / max(total * 0.3, 1), 1.0) * 0.2

        s = min(coverage + fact_bonus, 1.0)
        return EvalMetric(
            name=self.name,
            score=round(s, 3),
            detail=f"fact={fact_backed}, source={source_backed}, none={ungrounded}",
        )


class ContentDiversityDim(EvalDimension):
    """Measures topic diversity — penalizes repetitive content."""
    name = "content_diversity"
    weight = 0.8

    def score(self, markdown, preset, **kw):
        h3_titles = re.findall(r"^### \d+\.\s*(.+)", markdown, re.MULTILINE)
        if len(h3_titles) < 2:
            return EvalMetric(name=self.name, score=1.0, detail="Too few items to measure")

        words: list[set[str]] = []
        for title in h3_titles:
            tokens = set(title.lower().split())
            chars = set(title)
            words.append(tokens | chars)

        pair_sims: list[float] = []
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                inter = len(words[i] & words[j])
                union = len(words[i] | words[j])
                pair_sims.append(inter / union if union else 0)

        avg_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0
        s = max(1.0 - avg_sim * 2, 0.0)

        return EvalMetric(
            name=self.name,
            score=round(s, 3),
            detail=f"avg_title_similarity={avg_sim:.2f} across {len(h3_titles)} items",
        )
