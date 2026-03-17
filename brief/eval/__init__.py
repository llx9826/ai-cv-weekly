"""ClawCat Brief — Evaluation Framework

Automated quality evaluation with pluggable dimensions and golden-set
regression testing.

Usage:
    from brief.eval import EvalRunner

    runner = EvalRunner(preset)
    result = runner.evaluate(markdown, items, fact_table, citations)
    print(result.overall_score)

Golden set usage:
    from brief.eval import GoldenSetRunner

    runner = GoldenSetRunner(golden_dir="data/golden")
    results = runner.run_all(pipeline_fn)
"""

from brief.eval.dimensions import (
    EvalDimension,
    FactAccuracyDim,
    StructureCompletenessDim,
    WordCountHitDim,
    CitationCoverageDim,
    ContentDiversityDim,
)
from brief.eval.runner import EvalRunner
from brief.eval.golden import GoldenSetRunner

__all__ = [
    "EvalDimension",
    "FactAccuracyDim",
    "StructureCompletenessDim",
    "WordCountHitDim",
    "CitationCoverageDim",
    "ContentDiversityDim",
    "EvalRunner",
    "GoldenSetRunner",
]
