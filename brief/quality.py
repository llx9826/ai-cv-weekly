"""LunaClaw Brief — LLM output quality checking (LLM 输出质量检查)."""

import re

from brief.models import PresetConfig, QualityResult


class QualityChecker:
    """根据 preset 配置检查 Markdown 结构与质量"""

    def __init__(self, preset: PresetConfig):
        self.preset = preset

    def check(self, markdown: str) -> QualityResult:
        issues: list[str] = []
        checks_passed = 0
        checks_total = 0

        # 1. Word count (字数)
        checks_total += 1
        char_count = len(markdown)
        if char_count >= self.preset.min_word_count:
            checks_passed += 1
        else:
            issues.append(f"字数不足: {char_count} < {self.preset.min_word_count}")

        # 2. Section count (章节数)
        checks_total += 1
        section_count = len(re.findall(r"^## ", markdown, re.MULTILINE))
        if section_count >= self.preset.min_sections:
            checks_passed += 1
        else:
            issues.append(f"章节不足: {section_count} < {self.preset.min_sections}")

        # 3. Sharp commentary check (sharp mode only) (锐评（仅 sharp 模式）)
        if self.preset.tone == "sharp":
            checks_total += 1
            if "锐评" in markdown:
                checks_passed += 1
            else:
                issues.append("缺少锐评")

        # 4. Must not start with code block (common LLM issue) (不能以代码块开头（LLM 常见问题）)
        checks_total += 1
        stripped = markdown.strip()
        if not stripped.startswith("```"):
            checks_passed += 1
        else:
            issues.append("输出以代码块开头，可能格式异常")

        # 5. Item count (at least some ### subheadings) (条目数量（至少有一些 ### 子标题）)
        if self.preset.cycle == "weekly":
            checks_total += 1
            item_count = len(re.findall(r"^### ", markdown, re.MULTILINE))
            if item_count >= 5:
                checks_passed += 1
            else:
                issues.append(f"条目不足: {item_count} < 5")

        score = checks_passed / checks_total if checks_total > 0 else 0
        return QualityResult(
            passed=score >= 0.7,
            score=score,
            issues=issues,
        )
