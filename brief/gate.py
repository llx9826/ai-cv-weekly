"""ClawCat Brief — Quality Gate

Four-state decision layer that determines whether a generated report
can be published, needs retry, should be degraded, or must be blocked.

Verdicts:
    PASS    — Report meets all quality thresholds. Publish as-is.
    RETRY   — Fixable issues detected. Regenerate with stricter hints.
    DEGRADE — Partial issues. Strip ungrounded claims and publish.
    BLOCK   — Critical failures. Do not publish; log for debugging.

Gate strictness is fully configurable per-preset via PresetConfig fields:
    gate_grounding_pass   — Grounding score threshold for PASS (0 = auto)
    gate_grounding_block  — Below this, BLOCK or DEGRADE (0 = auto)
    gate_max_retries      — Max retry attempts (0 = auto, default 2)
    gate_block_on_critical — Whether critical grounding failures cause BLOCK
"""

from __future__ import annotations

import re

from brief.models import (
    PresetConfig, GateVerdict, GateResult,
    QualityResult,
)
from brief.grounding.protocol import GroundingResult

_FINANCE_TOPICS = {"finance", "stock_a", "stock_hk", "stock_us"}

_DEFAULTS = {
    "finance": {"grounding_pass": 0.85, "grounding_block": 0.2, "max_retries": 2, "block_critical": True},
    "general": {"grounding_pass": 0.5, "grounding_block": 0.15, "max_retries": 2, "block_critical": False},
}


class QualityGate:
    """Evaluates grounding + quality results and returns a binding verdict.

    All thresholds are read from PresetConfig first; if not set (0),
    falls back to topic-based defaults.
    """

    def __init__(self, preset: PresetConfig):
        self.preset = preset
        is_finance = preset.topic in _FINANCE_TOPICS
        defaults = _DEFAULTS["finance"] if is_finance else _DEFAULTS["general"]

        self._grounding_pass = preset.gate_grounding_pass or defaults["grounding_pass"]
        self._grounding_block = preset.gate_grounding_block or defaults["grounding_block"]
        self.max_retries = preset.gate_max_retries or defaults["max_retries"]
        self._block_critical = preset.gate_block_on_critical if preset.gate_block_on_critical is not None else defaults["block_critical"]
        self._quality_pass = 0.7

    def evaluate(
        self,
        gr: GroundingResult,
        qr: QualityResult,
        retry_count: int = 0,
    ) -> GateResult:
        """Produce a binding verdict from grounding + quality scores."""
        reasons: list[str] = []

        grounding_ok = gr.score >= self._grounding_pass
        quality_ok = qr.passed
        has_critical = any(i.severity == "error" for i in gr.issues)

        if grounding_ok and quality_ok:
            return GateResult(
                verdict=GateVerdict.PASS,
                grounding_score=gr.score,
                quality_score=qr.score,
                retry_count=retry_count,
            )

        if gr.score < self._grounding_block or has_critical:
            if retry_count < self.max_retries:
                reasons.append(f"Grounding critically low ({gr.score:.0%}), retrying")
                return GateResult(verdict=GateVerdict.RETRY, grounding_score=gr.score,
                                  quality_score=qr.score, reasons=reasons, retry_count=retry_count)
            reasons.append(f"Grounding critically low ({gr.score:.0%}) after {retry_count} retries")
            if self._block_critical:
                reasons.append("block_on_critical=True: blocking report")
                return GateResult(verdict=GateVerdict.BLOCK, grounding_score=gr.score,
                                  quality_score=qr.score, reasons=reasons, retry_count=retry_count)
            reasons.append("block_on_critical=False: degrading instead")
            return GateResult(verdict=GateVerdict.DEGRADE, grounding_score=gr.score,
                              quality_score=qr.score, reasons=reasons, retry_count=retry_count)

        if (not grounding_ok or not quality_ok) and retry_count < self.max_retries:
            if not grounding_ok:
                reasons.append(f"Grounding {gr.score:.0%} < {self._grounding_pass:.0%}")
            if not quality_ok:
                reasons.extend(qr.issues)
            return GateResult(verdict=GateVerdict.RETRY, grounding_score=gr.score,
                              quality_score=qr.score, reasons=reasons, retry_count=retry_count)

        if not grounding_ok:
            reasons.append(f"Grounding still {gr.score:.0%} after {retry_count} retries, degrading")
        if not quality_ok:
            reasons.extend(qr.issues)
            reasons.append(f"Quality failed after {retry_count} retries, degrading")
        return GateResult(verdict=GateVerdict.DEGRADE, grounding_score=gr.score,
                          quality_score=qr.score, reasons=reasons, retry_count=retry_count)

    def build_retry_hint(self, gr: GroundingResult, qr: QualityResult) -> str:
        hints: list[str] = []
        if not qr.passed:
            hints.append("请确保所有章节完整，不要遗漏任何必需章节。")
        if gr.score < self._grounding_pass:
            hints.append("请严格使用事实数据表中的数据。如果某项数据不在表中，写「暂无实时数据」，不要编造任何数字。")
            ungrounded = [i for i in gr.issues if i.severity in ("error", "warning")]
            if ungrounded:
                examples = ", ".join(i.span for i in ungrounded[:5] if i.span)
                if examples:
                    hints.append(f"以下数值未通过验证，请修正或删除：{examples}")
        return "\n".join(hints)

    @staticmethod
    def degrade_markdown(markdown: str, gr: GroundingResult) -> str:
        degraded = markdown
        replaced_count = 0
        for issue in gr.issues:
            if issue.severity in ("error", "warning") and issue.span:
                span = re.escape(issue.span)
                pattern = re.compile(rf"(?<!\w){span}(?!\w)")
                if pattern.search(degraded):
                    degraded = pattern.sub("「暂无实时数据」", degraded, count=1)
                    replaced_count += 1
        if replaced_count > 0 and "注：" not in degraded:
            degraded += "\n\n> 注：部分数据因未通过事实验证已被替换，请以官方数据为准。\n"
        return degraded
