"""LunaClaw Brief — LLM output quality checking."""

import re

from brief.models import PresetConfig, QualityResult

_EMPTY_PHRASES = [
    "值得关注", "有待观察", "具有重要意义", "推动行业发展",
    "持续关注", "密切关注", "有望", "或将",
    "进一步推动", "不断深化", "引发广泛关注",
    "备受瞩目", "意义重大", "前景广阔",
]

_EMPTY_PHRASE_THRESHOLD = 3


class QualityChecker:
    """Validates Markdown structure and quality according to preset configuration."""

    def __init__(self, preset: PresetConfig):
        self.preset = preset

    def check(self, markdown: str) -> QualityResult:
        """Run quality checks on the markdown and return a QualityResult."""
        issues: list[str] = []
        checks_passed = 0
        checks_total = 0

        # 1. Word count
        checks_total += 1
        char_count = len(markdown)
        if char_count >= self.preset.min_word_count:
            checks_passed += 1
        else:
            issues.append(f"字数不足: {char_count} < {self.preset.min_word_count}")

        # 2. Section count
        checks_total += 1
        section_count = len(re.findall(r"^## ", markdown, re.MULTILINE))
        if section_count >= self.preset.min_sections:
            checks_passed += 1
        else:
            issues.append(f"章节不足: {section_count} < {self.preset.min_sections}")

        # 3. Sharp commentary check (sharp mode only)
        if self.preset.tone == "sharp":
            checks_total += 1
            if "锐评" in markdown:
                checks_passed += 1
            else:
                issues.append("缺少锐评")

        # 4. Must not start with code block (common LLM issue)
        checks_total += 1
        stripped = markdown.strip()
        if not stripped.startswith("```"):
            checks_passed += 1
        else:
            issues.append("输出以代码块开头，可能格式异常")

        # 5. Item count (at least some ### subheadings)
        if self.preset.cycle == "weekly":
            checks_total += 1
            item_count = len(re.findall(r"^### ", markdown, re.MULTILINE))
            if item_count >= 5:
                checks_passed += 1
            else:
                issues.append(f"条目不足: {item_count} < 5")

        # 6. Empty-talk / boilerplate detection
        checks_total += 1
        empty_count = sum(markdown.count(p) for p in _EMPTY_PHRASES)
        if empty_count <= _EMPTY_PHRASE_THRESHOLD:
            checks_passed += 1
        else:
            issues.append(f"模板化表达过多: 检测到 {empty_count} 处空话")

        # 7. Hero summary presence
        checks_total += 1
        has_hero = bool(re.search(r"^##\s.*核心判断", markdown, re.MULTILINE))
        if has_hero:
            checks_passed += 1
        else:
            issues.append("缺少核心判断区域（hero_summary）")

        # 8. Strategy section presence
        checks_total += 1
        has_strategy = bool(re.search(
            r"^##\s.*(?:策略|趋势策略|Claw 策略|投资策略)", markdown, re.MULTILINE
        ))
        if has_strategy:
            checks_passed += 1
        else:
            issues.append("缺少策略层章节")

        score = checks_passed / checks_total if checks_total > 0 else 0
        return QualityResult(
            passed=score >= 0.6,
            score=score,
            issues=issues,
        )
