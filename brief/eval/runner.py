"""Eval runner — evaluates a single report across configurable dimensions.

Dimension selection and weight overrides are driven by PresetConfig:
    eval_dimensions: ["fact_accuracy", "word_count_hit"]  # empty = all
    eval_weights:    {"fact_accuracy": 3.0}               # empty = use defaults
"""

from __future__ import annotations

from brief.models import Item, PresetConfig, Citation, EvalResult, EvalMetric
from brief.eval.dimensions import (
    EvalDimension,
    FactAccuracyDim,
    StructureCompletenessDim,
    WordCountHitDim,
    CitationCoverageDim,
    ContentDiversityDim,
)

_ALL_DIMS: dict[str, EvalDimension] = {
    d.name: d for d in [
        FactAccuracyDim(),
        StructureCompletenessDim(),
        WordCountHitDim(),
        CitationCoverageDim(),
        ContentDiversityDim(),
    ]
}


def _build_dims(preset: PresetConfig) -> list[EvalDimension]:
    """Select and configure dimensions based on preset config."""
    names = preset.eval_dimensions or list(_ALL_DIMS.keys())
    weight_overrides = preset.eval_weights or {}

    dims: list[EvalDimension] = []
    for name in names:
        dim = _ALL_DIMS.get(name)
        if dim is None:
            continue
        if name in weight_overrides:
            dim = type(dim)()
            dim.weight = weight_overrides[name]
        dims.append(dim)
    return dims or list(_ALL_DIMS.values())


class EvalRunner:
    """Evaluates a generated report across multiple quality dimensions.

    Dimension selection and weight overrides are read from PresetConfig.
    If eval_dimensions is empty, all available dimensions are used.
    If eval_weights contains overrides, they replace the dimension defaults.

    Usage:
        runner = EvalRunner(preset)
        result = runner.evaluate(markdown, items, fact_table, citations)
        print(f"Overall: {result.overall_score:.0%}")
    """

    def __init__(
        self,
        preset: PresetConfig,
        dimensions: list[EvalDimension] | None = None,
    ):
        self.preset = preset
        self._dims = dimensions if dimensions is not None else _build_dims(preset)

    def evaluate(
        self,
        markdown: str,
        items: list[Item] | None = None,
        fact_table=None,
        citations: list[Citation] | None = None,
        issue_label: str = "",
    ) -> EvalResult:
        metrics: list[EvalMetric] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for dim in self._dims:
            metric = dim.score(
                markdown=markdown,
                preset=self.preset,
                items=items,
                fact_table=fact_table,
                citations=citations,
            )
            metrics.append(metric)
            weighted_sum += metric.score * dim.weight
            weight_total += dim.weight

        overall = weighted_sum / weight_total if weight_total > 0 else 0.0

        return EvalResult(
            preset=self.preset.name,
            issue_label=issue_label,
            metrics=metrics,
            overall_score=round(overall, 4),
        )

    def compare(self, baseline: EvalResult, current: EvalResult) -> dict:
        baseline_map = {m.name: m for m in baseline.metrics}
        current_map = {m.name: m for m in current.metrics}

        deltas: list[dict] = []
        for name in current_map:
            cur = current_map[name]
            base = baseline_map.get(name)
            if base:
                delta = cur.score - base.score
                deltas.append({
                    "dimension": name,
                    "baseline": base.score,
                    "current": cur.score,
                    "delta": round(delta, 4),
                    "improved": delta > 0,
                })

        return {
            "overall_baseline": baseline.overall_score,
            "overall_current": current.overall_score,
            "overall_delta": round(current.overall_score - baseline.overall_score, 4),
            "dimensions": deltas,
        }
