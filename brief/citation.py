"""ClawCat Brief — Citation Engine (Claim → Evidence → Source Traceability)

Extracts factual claims from generated reports and traces each claim
back to its evidence source (Item, Fact, or both).

This provides:
  1. Verifiable provenance for every data point in the report
  2. Confidence scoring for each citation link
  3. JSON-serializable citation map for downstream use (HTML tooltips, API)

Architecture:
  ClaimExtractor  — Pulls structured claims from markdown
  EvidenceMatcher — Matches claims against Items + FactTable
  CitationEngine  — Orchestrates extraction → matching → output
"""

from __future__ import annotations

import re
from dataclasses import asdict
from difflib import SequenceMatcher

from brief.models import Item, Fact, Citation


class ClaimExtractor:
    """Extracts verifiable claims from generated markdown.

    A "claim" is any statement containing a specific data point:
    numbers, percentages, currency amounts, named entities with attributes.
    """

    _NUMERIC_CLAIM = re.compile(
        r"([^。\n]{0,60}?"
        r"(?:[\$¥€£]?\s*[+-]?[\d,.]+\s*(?:%|亿|万|亿元|万元|billion|million|点|元|B|M|K)?)"
        r"[^。\n]{0,40}?)"
        r"[。\n]?"
    )

    _BOLD_CLAIM = re.compile(
        r"\*\*([^*]+)\*\*[：:]\s*([^\n]+)"
    )

    @classmethod
    def extract(cls, markdown: str) -> list[dict]:
        """Extract claims from markdown.

        Returns list of dicts with keys: text, claim_type, value_span.
        """
        claims: list[dict] = []
        seen: set[str] = set()

        for m in cls._BOLD_CLAIM.finditer(markdown):
            label, value = m.group(1).strip(), m.group(2).strip()
            if any(kw in label for kw in ("涨跌幅", "净流入", "净流出", "发行价",
                                           "成交额", "涨幅", "跌幅", "收益率",
                                           "市值", "估值")):
                key = f"{label}:{value[:30]}"
                if key not in seen:
                    seen.add(key)
                    claims.append({
                        "text": f"{label}：{value}",
                        "claim_type": "structured_field",
                        "label": label,
                        "value_span": value,
                    })

        for m in cls._NUMERIC_CLAIM.finditer(markdown):
            text = m.group(1).strip()
            if len(text) < 10 or text in seen:
                continue
            nums = re.findall(r"[+-]?[\d,.]+%?", text)
            if nums:
                seen.add(text)
                claims.append({
                    "text": text,
                    "claim_type": "numeric_sentence",
                    "label": "",
                    "value_span": nums[0],
                })

        return claims


class EvidenceMatcher:
    """Matches extracted claims against source items and fact table."""

    @staticmethod
    def match_against_items(
        claim: dict, items: list[Item], threshold: float = 0.3
    ) -> tuple[Item | None, float]:
        """Find the best matching source item for a claim."""
        best_item: Item | None = None
        best_score = 0.0
        claim_text = claim["text"].lower()

        for item in items:
            source_text = f"{item.title} {item.raw_text}".lower()

            ratio = SequenceMatcher(None, claim_text[:80], source_text[:200]).ratio()

            value = claim.get("value_span", "")
            if value and value in source_text:
                ratio = max(ratio, 0.7)

            if ratio > best_score:
                best_score = ratio
                best_item = item

        if best_score >= threshold:
            return best_item, best_score
        return None, 0.0

    @staticmethod
    def match_against_facts(
        claim: dict, fact_table
    ) -> tuple[Fact | None, float]:
        """Find the best matching Fact for a numeric claim."""
        if fact_table is None or fact_table.is_empty:
            return None, 0.0

        value_span = claim.get("value_span", "")
        if not value_span:
            return None, 0.0

        core_nums = re.findall(r"[\d,.]+", value_span)
        if not core_nums:
            return None, 0.0

        for fact in fact_table.facts:
            for num in core_nums:
                clean = num.replace(",", "")
                if clean in fact.value:
                    label_text = claim.get("label", "")
                    label_match = (
                        label_text and
                        any(kw in label_text for kw in (fact.label, fact.key.split(".")[-1]))
                    )
                    confidence = 0.95 if label_match else 0.7
                    return fact, confidence

        return None, 0.0


class CitationEngine:
    """Orchestrates claim extraction → evidence matching → citation output.

    Usage:
        engine = CitationEngine()
        citations = engine.generate(markdown, items, fact_table)
    """

    def __init__(self):
        self._extractor = ClaimExtractor()
        self._matcher = EvidenceMatcher()

    def generate(
        self,
        markdown: str,
        items: list[Item],
        fact_table=None,
    ) -> list[Citation]:
        """Extract claims and match each to its evidence source."""
        raw_claims = self._extractor.extract(markdown)
        citations: list[Citation] = []

        for claim in raw_claims:
            fact, fact_conf = self._matcher.match_against_facts(claim, fact_table)
            item, item_conf = self._matcher.match_against_items(claim, items)

            if fact and fact_conf >= 0.7:
                citations.append(Citation(
                    claim=claim["text"],
                    evidence=f"{fact.label}: {fact.value}",
                    source_name=fact.source,
                    fact_key=fact.key,
                    confidence=fact_conf,
                ))
            elif item and item_conf >= 0.3:
                citations.append(Citation(
                    claim=claim["text"],
                    evidence=item.raw_text[:120] if item.raw_text else item.title,
                    source_name=item.source,
                    source_url=item.url,
                    confidence=item_conf,
                ))
            else:
                citations.append(Citation(
                    claim=claim["text"],
                    evidence="",
                    source_name="ungrounded",
                    confidence=0.0,
                ))

        return citations

    @staticmethod
    def to_json(citations: list[Citation]) -> list[dict]:
        """Serialize citations to JSON-friendly format."""
        return [asdict(c) for c in citations]

    @staticmethod
    def summary(citations: list[Citation]) -> dict:
        """Produce a summary of citation quality."""
        total = len(citations)
        if total == 0:
            return {"total": 0, "grounded": 0, "ungrounded": 0, "ratio": 1.0}

        grounded = sum(1 for c in citations if c.confidence > 0)
        fact_backed = sum(1 for c in citations if c.fact_key)
        source_backed = sum(1 for c in citations if c.source_url and not c.fact_key)

        return {
            "total": total,
            "grounded": grounded,
            "ungrounded": total - grounded,
            "fact_backed": fact_backed,
            "source_backed": source_backed,
            "grounding_ratio": round(grounded / total, 3) if total else 1.0,
        }
