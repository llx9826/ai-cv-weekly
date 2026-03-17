"""Fact Table protocol — FactSource ABC and FactTable container.

FactSource is the structured-data counterpart to BaseSource (free-text).
Instead of returning list[Item], it returns list[Fact] — typed key-value
pairs with provenance metadata.

FactTable aggregates facts from multiple FactSources and provides:
  - Prompt injection: format facts as a Markdown table for the LLM
  - Lookup: retrieve fact values for claim-level verification
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

from brief.models import Fact


class FactSource(ABC):
    """Abstract base for structured data sources that return verified facts."""

    name: str = "base_fact"

    def __init__(self, global_config: dict | None = None):
        self._config = global_config or {}

    @abstractmethod
    async def fetch_facts(self, since: datetime, until: datetime) -> list[Fact]:
        """Fetch structured facts for the given time window."""
        ...


class FactTable:
    """Aggregates facts from multiple FactSources into a queryable table.

    Provides two key capabilities:
      1. to_prompt() — formats facts as a Markdown table for LLM injection
      2. lookup()    — retrieves fact values for post-generation verification
    """

    def __init__(self, facts: list[Fact] | None = None):
        self._facts: list[Fact] = facts or []
        self._by_key: dict[str, Fact] = {}
        self._by_category: dict[str, list[Fact]] = defaultdict(list)
        self._all_values: set[str] = set()
        if facts:
            self._index(facts)

    def _index(self, facts: list[Fact]):
        for f in facts:
            self._by_key[f.key] = f
            self._by_category[f.category].append(f)
            self._all_values.add(f.value)
            for token in _extract_numeric_tokens(f.value):
                self._all_values.add(token)

    def add_facts(self, facts: list[Fact]):
        self._facts.extend(facts)
        self._index(facts)

    @property
    def facts(self) -> list[Fact]:
        return self._facts

    @property
    def is_empty(self) -> bool:
        return len(self._facts) == 0

    def lookup(self, key: str) -> Fact | None:
        return self._by_key.get(key)

    def has_value(self, value: str) -> bool:
        """Check if a numeric value (or close variant) exists in the table."""
        normalized = value.replace(",", "").replace(" ", "").strip()
        return normalized in self._all_values or value in self._all_values

    def categories(self) -> list[str]:
        return list(self._by_category.keys())

    def facts_by_category(self, category: str) -> list[Fact]:
        return self._by_category.get(category, [])

    def to_prompt(self) -> str:
        """Format the fact table as a structured prompt block for LLM injection.

        Groups facts by category and renders them as a Markdown table.
        Includes strict constraint instructions.
        """
        if not self._facts:
            return ""

        lines: list[str] = [
            "",
            "【事实数据表 — 以下数据已验证，报告中的数值必须来自此表】",
        ]

        _CAT_LABELS = {
            "index": "大盘指数",
            "stock": "个股行情",
            "sector": "板块概况",
            "capital_flow": "资金流向",
            "ipo": "新股日历",
            "macro": "宏观数据",
            "general": "其他数据",
        }

        for cat in self._ordered_categories():
            cat_facts = self._by_category[cat]
            cat_label = _CAT_LABELS.get(cat, cat)
            lines.append(f"\n**{cat_label}**：")
            lines.append("| 指标 | 数值 | 来源 |")
            lines.append("|------|------|------|")
            for f in cat_facts:
                label = f.label or f.key
                val = f"{f.value}{f.unit}" if f.unit and f.unit not in f.value else f.value
                lines.append(f"| {label} | {val} | {f.source} |")

        lines.append("")
        lines.append(
            "【严格约束】报告中所有具体数值（指数点位、涨跌幅、金额、百分比）"
            "必须引用上表中的数据。若某项数据不在表中，写「暂无实时数据」而非编造。"
        )
        lines.append("")

        return "\n".join(lines)

    def _ordered_categories(self) -> list[str]:
        priority = ["index", "stock", "sector", "capital_flow", "ipo", "macro"]
        ordered = [c for c in priority if c in self._by_category]
        ordered.extend(c for c in self._by_category if c not in ordered)
        return ordered

    @classmethod
    async def from_sources(
        cls,
        sources: list[FactSource],
        since: datetime,
        until: datetime,
    ) -> "FactTable":
        """Fetch facts from multiple sources in parallel and build a FactTable."""
        table = cls()
        if not sources:
            return table

        async def _safe_fetch(src: FactSource) -> list[Fact]:
            try:
                return await src.fetch_facts(since, until)
            except Exception as e:
                print(f"  [fact] {src.name} failed: {str(e)[:80]}")
                return []

        results = await asyncio.gather(*[_safe_fetch(s) for s in sources])
        for facts in results:
            if facts:
                table.add_facts(facts)

        return table


def _extract_numeric_tokens(value: str) -> list[str]:
    """Extract individual numeric substrings from a value for fuzzy matching."""
    import re
    tokens: list[str] = []
    for m in re.finditer(r"[\d,.]+", value):
        raw = m.group(0).replace(",", "")
        if raw and raw != ".":
            tokens.append(raw)
    return tokens
