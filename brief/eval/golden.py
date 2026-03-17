"""Golden set evaluation — regression testing against known-good outputs.

Golden cases are YAML files in data/golden/ with structure:
    preset: stock_a_daily
    hint: ""
    expected:
        min_sections: 3
        must_contain: ["上证", "Claw 锐评"]
        must_not_contain: ["```markdown"]
        max_word_count: 2000
        min_grounding_score: 0.8

The GoldenSetRunner loads all cases, runs pipeline for each,
evaluates against expectations, and produces a pass/fail report.

Usage:
    runner = GoldenSetRunner("data/golden")
    results = runner.run_all(generate_fn)
    runner.print_report(results)
"""

from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from brief.models import EvalResult


@dataclass
class GoldenCase:
    """A single golden test case."""
    name: str
    preset: str
    hint: str = ""
    expected: dict = field(default_factory=dict)


@dataclass
class GoldenResult:
    """Result of running a single golden case."""
    case_name: str
    preset: str
    passed: bool
    checks: list[dict] = field(default_factory=list)
    eval_result: EvalResult | None = None
    error: str = ""


GenerateFn = Callable[[str, str], tuple[str, float, EvalResult | None]]
"""Signature: (preset_name, hint) -> (markdown, grounding_score, eval_result)"""


class GoldenSetRunner:
    """Loads and runs golden test cases for regression testing.

    Usage:
        runner = GoldenSetRunner("data/golden")
        results = runner.run_all(generate_fn)
        runner.print_report(results)
        runner.save_report(results, "output/golden_report.json")
    """

    def __init__(self, golden_dir: str | Path):
        self._dir = Path(golden_dir)
        self._cases = self._load_cases()

    def _load_cases(self) -> list[GoldenCase]:
        cases: list[GoldenCase] = []
        if not self._dir.exists():
            return cases

        for f in sorted(self._dir.glob("*.yaml")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if data and isinstance(data, dict):
                    cases.append(GoldenCase(
                        name=f.stem,
                        preset=data.get("preset", ""),
                        hint=data.get("hint", ""),
                        expected=data.get("expected", {}),
                    ))
            except Exception as e:
                print(f"[golden] Failed to load {f.name}: {e}")
        return cases

    @property
    def cases(self) -> list[GoldenCase]:
        return self._cases

    def run_all(
        self,
        generate_fn: GenerateFn,
        *,
        filter_presets: list[str] | None = None,
    ) -> list[GoldenResult]:
        """Execute all golden cases end-to-end.

        Args:
            generate_fn: Callable(preset_name, hint) -> (markdown, grounding_score, eval_result)
            filter_presets: Only run cases matching these presets (None = all).

        Returns:
            List of GoldenResult for each case.
        """
        results: list[GoldenResult] = []
        cases = self._cases
        if filter_presets:
            cases = [c for c in cases if c.preset in filter_presets]

        print(f"\n🧪 Golden Set: running {len(cases)} case(s)...")
        for i, case in enumerate(cases, 1):
            print(f"\n── Case [{i}/{len(cases)}] {case.name} (preset={case.preset}) ──")
            try:
                markdown, grounding_score, eval_result = generate_fn(case.preset, case.hint)
                result = self.check_case(case, markdown, eval_result, grounding_score)
            except Exception as e:
                result = GoldenResult(
                    case_name=case.name,
                    preset=case.preset,
                    passed=False,
                    error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-300:]}",
                )
            results.append(result)
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"   {status}")
            if result.error:
                print(f"   ERROR: {result.error[:200]}")

        return results

    def run_case(
        self,
        case_name: str,
        generate_fn: GenerateFn,
    ) -> GoldenResult:
        """Run a single golden case by name."""
        case = next((c for c in self._cases if c.name == case_name), None)
        if case is None:
            return GoldenResult(case_name=case_name, preset="", passed=False, error=f"Case '{case_name}' not found")

        try:
            markdown, grounding_score, eval_result = generate_fn(case.preset, case.hint)
            return self.check_case(case, markdown, eval_result, grounding_score)
        except Exception as e:
            return GoldenResult(case_name=case.name, preset=case.preset, passed=False, error=str(e))

    def check_case(
        self,
        case: GoldenCase,
        markdown: str,
        eval_result: EvalResult | None = None,
        grounding_score: float = 1.0,
    ) -> GoldenResult:
        checks: list[dict] = []
        all_pass = True
        exp = case.expected

        if "min_sections" in exp:
            h2 = len(re.findall(r"^## ", markdown, re.MULTILINE))
            ok = h2 >= exp["min_sections"]
            checks.append({"check": "min_sections", "expected": exp["min_sections"],
                           "actual": h2, "passed": ok})
            all_pass &= ok

        if "must_contain" in exp:
            for kw in exp["must_contain"]:
                ok = kw in markdown
                checks.append({"check": f"must_contain({kw})", "passed": ok})
                all_pass &= ok

        if "must_not_contain" in exp:
            for kw in exp["must_not_contain"]:
                ok = kw not in markdown
                checks.append({"check": f"must_not_contain({kw})", "passed": ok})
                all_pass &= ok

        if "max_word_count" in exp:
            ok = len(markdown) <= exp["max_word_count"]
            checks.append({"check": "max_word_count", "expected": exp["max_word_count"],
                           "actual": len(markdown), "passed": ok})
            all_pass &= ok

        if "min_grounding_score" in exp:
            ok = grounding_score >= exp["min_grounding_score"]
            checks.append({"check": "min_grounding_score",
                           "expected": exp["min_grounding_score"],
                           "actual": round(grounding_score, 3), "passed": ok})
            all_pass &= ok

        if "min_eval_score" in exp and eval_result:
            ok = eval_result.overall_score >= exp["min_eval_score"]
            checks.append({"check": "min_eval_score",
                           "expected": exp["min_eval_score"],
                           "actual": round(eval_result.overall_score, 3), "passed": ok})
            all_pass &= ok

        return GoldenResult(
            case_name=case.name,
            preset=case.preset,
            passed=all_pass,
            checks=checks,
            eval_result=eval_result,
        )

    @staticmethod
    def print_report(results: list[GoldenResult]):
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        rate = (passed / total * 100) if total else 0
        print(f"\n{'='*56}")
        print(f"  🧪 Golden Set Report: {passed}/{total} passed ({rate:.0f}%)")
        print(f"{'='*56}")

        for r in results:
            icon = "✅" if r.passed else "❌"
            print(f"\n{icon} {r.case_name} ({r.preset})")
            if r.error:
                print(f"   ERROR: {r.error[:200]}")
            for c in r.checks:
                ci = "✓" if c["passed"] else "✗"
                detail = ""
                if "expected" in c:
                    detail = f" (expected={c['expected']}, actual={c['actual']})"
                print(f"   {ci} {c['check']}{detail}")

            if r.eval_result:
                print(f"   eval_score: {r.eval_result.overall_score:.0%}")

    @staticmethod
    def save_report(results: list[GoldenResult], output_path: str | Path):
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        total = len(results)
        passed = sum(1 for r in results if r.passed)

        data = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 3) if total else 1.0,
            "cases": [
                {
                    "name": r.case_name,
                    "preset": r.preset,
                    "passed": r.passed,
                    "checks": r.checks,
                    "eval_score": r.eval_result.overall_score if r.eval_result else None,
                    "error": r.error,
                }
                for r in results
            ],
        }

        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Report saved to {out}")
