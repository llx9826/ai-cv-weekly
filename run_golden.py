#!/usr/bin/env python3
"""ClawCat Brief — Golden Set Regression Runner

Usage:
  python run_golden.py                         # run all golden cases
  python run_golden.py --preset stock_a_daily  # only run cases for this preset
  python run_golden.py --case ai_daily         # run a single case by name
  python run_golden.py --output report.json    # save report to file
"""

import argparse
import sys
from pathlib import Path

import yaml

from brief.eval.golden import GoldenSetRunner
from brief.pipeline import ReportPipeline
from brief.presets import get_preset
from brief.eval.runner import EvalRunner
from brief.citation import CitationEngine


def load_config() -> dict:
    root = Path(__file__).parent
    config: dict = {}
    base_path = root / "config.yaml"
    if base_path.exists():
        with open(base_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    local_path = root / "config.local.yaml"
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
            config.update(local)
    return config


def make_generate_fn(config: dict):
    """Build the generate function expected by GoldenSetRunner.run_all()."""

    def generate(preset_name: str, hint: str):
        preset = get_preset(preset_name)
        if not preset:
            raise ValueError(f"Preset '{preset_name}' not found")

        pipeline = ReportPipeline(preset, config)
        result = pipeline.run(user_hint=hint, send_email=False, send_webhook=False)

        if not result.get("success"):
            raise RuntimeError(f"Pipeline failed: {result.get('error', 'unknown')}")

        md_path = result.get("md_path")
        if not md_path:
            raise RuntimeError("No markdown output")

        markdown = Path(md_path).read_text(encoding="utf-8")
        grounding_score = result.get("grounding_score", 1.0)

        eval_runner = EvalRunner(preset)
        eval_result = eval_runner.evaluate(markdown, issue_label=result.get("issue_label", ""))

        return markdown, grounding_score, eval_result

    return generate


def main():
    parser = argparse.ArgumentParser(description="Golden Set Regression Runner")
    parser.add_argument("--golden-dir", default="data/golden", help="Golden cases directory")
    parser.add_argument("--preset", help="Only run cases for this preset")
    parser.add_argument("--case", help="Run a single case by name")
    parser.add_argument("--output", default="output/golden_report.json", help="Report output path")
    args = parser.parse_args()

    config = load_config()
    runner = GoldenSetRunner(args.golden_dir)

    if not runner.cases:
        print(f"No golden cases found in {args.golden_dir}")
        sys.exit(1)

    generate_fn = make_generate_fn(config)

    if args.case:
        result = runner.run_case(args.case, generate_fn)
        results = [result]
    else:
        filter_presets = [args.preset] if args.preset else None
        results = runner.run_all(generate_fn, filter_presets=filter_presets)

    runner.print_report(results)
    runner.save_report(results, args.output)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
