"""Built-in grounding checkers for common hallucination patterns.

TemporalGrounder — Detects temporal inconsistencies (future dates, wrong weekdays)
EntityGrounder   — Verifies entity names appear in source items
NumericGrounder  — Flags suspicious numeric claims not grounded in sources
StructureGrounder — Validates report structure against preset requirements
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from brief.models import Item
from brief.grounding.protocol import GroundingChecker, GroundingResult, GroundingIssue


class TemporalGrounder(GroundingChecker):
    """Detects temporal hallucinations: future dates, impossible timelines."""
    name = "temporal"

    def check(self, markdown: str, items: list[Item]) -> GroundingResult:
        issues: list[GroundingIssue] = []
        today = datetime.now()

        date_pattern = re.compile(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})[日号]?")
        for m in date_pattern.finditer(markdown):
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                dt = datetime(y, mo, d)
                if dt > today + timedelta(days=365):
                    issues.append(GroundingIssue(
                        checker=self.name,
                        severity="error",
                        message=f"Future date detected: {m.group(0)}",
                        span=m.group(0),
                    ))
            except ValueError:
                issues.append(GroundingIssue(
                    checker=self.name,
                    severity="warning",
                    message=f"Invalid date: {m.group(0)}",
                    span=m.group(0),
                ))

        score = 1.0 - min(len(issues) * 0.2, 1.0)
        return GroundingResult(passed=not any(i.severity == "error" for i in issues), score=score, issues=issues)


class EntityGrounder(GroundingChecker):
    """Verifies that key entities mentioned in the report appear in source items."""
    name = "entity"

    _ENTITY_PATTERN = re.compile(
        r"(?:【|《)([^】》]+)(?:】|》)|"       # Chinese brackets
        r"\*\*([^*]{2,40})\*\*|"              # Bold text
        r"(?:^|\s)([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]+)*)"  # CamelCase names
    )

    def check(self, markdown: str, items: list[Item]) -> GroundingResult:
        source_text = " ".join(
            f"{item.title} {item.raw_text}" for item in items
        ).lower()

        entities: set[str] = set()
        for m in self._ENTITY_PATTERN.finditer(markdown):
            entity = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            if entity and len(entity) >= 2:
                entities.add(entity)

        issues: list[GroundingIssue] = []
        skip_labels = {"涨跌幅", "驱动因素", "事件概要", "核心创新", "研究问题", "实验结果",
                       "内容概要", "背景脉络", "实际影响", "投资逻辑", "市场反应",
                       "Claw 锐评", "判断", "依据", "代表个股", "净流入", "净流出",
                       "申购日期", "发行价", "所属行业", "异动原因", "Claw", "锐评"}

        for entity in entities:
            if entity in skip_labels:
                continue
            if entity.lower() not in source_text and len(entity) > 3:
                issues.append(GroundingIssue(
                    checker=self.name,
                    severity="info",
                    message=f"Entity not found in sources: {entity}",
                    span=entity,
                ))

        total = len(entities - skip_labels) or 1
        ungrounded = len(issues)
        score = max(1.0 - ungrounded / total, 0.0)
        return GroundingResult(passed=score >= 0.3, score=score, issues=issues)


class NumericGrounder(GroundingChecker):
    """Flags numeric claims (percentages, dollar amounts) not found in sources."""
    name = "numeric"

    _NUM_PATTERN = re.compile(
        r"(?:[\$¥€£])\s*[\d,.]+[万亿BMKT]?|"  # Currency
        r"[\d,.]+\s*%|"                          # Percentages
        r"[\d,.]+\s*(?:亿|万|billion|million|trillion)"  # Large numbers
    )

    def check(self, markdown: str, items: list[Item]) -> GroundingResult:
        source_text = " ".join(f"{item.title} {item.raw_text}" for item in items)

        report_nums = set(m.group(0).strip() for m in self._NUM_PATTERN.finditer(markdown))
        source_nums = set(m.group(0).strip() for m in self._NUM_PATTERN.finditer(source_text))

        issues: list[GroundingIssue] = []
        for num in report_nums:
            if num not in source_nums:
                issues.append(GroundingIssue(
                    checker=self.name,
                    severity="info",
                    message=f"Numeric claim not in sources: {num}",
                    span=num,
                ))

        total = len(report_nums) or 1
        score = max(1.0 - len(issues) / total * 0.5, 0.0)
        return GroundingResult(passed=True, score=score, issues=issues)


class StructureGrounder(GroundingChecker):
    """Validates that the report has the expected section structure."""
    name = "structure"

    def check(self, markdown: str, items: list[Item]) -> GroundingResult:
        issues: list[GroundingIssue] = []

        h2_sections = re.findall(r"^## .+", markdown, re.MULTILINE)
        h3_items = re.findall(r"^### \d+\. .+", markdown, re.MULTILINE)

        if len(h2_sections) < 2:
            issues.append(GroundingIssue(
                checker=self.name,
                severity="error",
                message=f"Too few sections: found {len(h2_sections)}, expected ≥2",
            ))

        claw_count = markdown.count("🦞 Claw 锐评")
        if h3_items and claw_count < len(h3_items) * 0.3:
            issues.append(GroundingIssue(
                checker=self.name,
                severity="warning",
                message=f"Missing Claw reviews: {claw_count} reviews for {len(h3_items)} items",
            ))

        section_score = min(len(h2_sections) / 4, 1.0)
        review_score = min(claw_count / max(len(h3_items), 1), 1.0) if h3_items else 1.0
        score = section_score * 0.6 + review_score * 0.4

        return GroundingResult(
            passed=not any(i.severity == "error" for i in issues),
            score=score,
            issues=issues,
        )
