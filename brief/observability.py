"""ClawCat Brief — Pipeline Observability

Full-lifecycle tracing for every pipeline run. Records:
  - Source health (success/failure per source)
  - LLM token usage and cost
  - Grounding and quality scores
  - Gate decisions and retry counts
  - Citation coverage
  - Phase timings
  - Final output status

Traces are persisted as JSON for analysis, dashboarding, and debugging.

Usage:
    tracer = PipelineTracer(preset_name="stock_a_daily")
    tracer.record_fetch(sources_attempted=4, sources_ok=3, items=42)
    tracer.record_llm(model="gpt-4o-mini", calls=1, usage={...})
    tracer.record_gate("pass", grounding=0.92, quality=0.85)
    tracer.finalize()
    tracer.save(output_dir)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from brief.models import PipelineTrace


class PipelineTracer:
    """Collects observability data throughout a pipeline run."""

    def __init__(self, preset: str = "", issue_label: str = ""):
        self._trace = PipelineTrace(
            preset=preset,
            issue_label=issue_label,
            started_at=datetime.now().isoformat(),
        )
        self._start_time = time.time()
        self._phase_starts: dict[str, float] = {}

    @property
    def trace(self) -> PipelineTrace:
        return self._trace

    def phase_start(self, phase: str):
        self._phase_starts[phase] = time.time()

    def phase_end(self, phase: str):
        start = self._phase_starts.pop(phase, None)
        if start:
            self._trace.phase_timings[phase] = round(time.time() - start, 2)

    def record_fetch(
        self,
        sources_attempted: int,
        sources_succeeded: int,
        items_fetched: int,
        facts_fetched: int = 0,
    ):
        self._trace.sources_attempted = sources_attempted
        self._trace.sources_succeeded = sources_succeeded
        self._trace.items_fetched = items_fetched
        self._trace.facts_fetched = facts_fetched

    def record_scoring(self, scored: int, selected: int, deduped: int):
        self._trace.items_scored = scored
        self._trace.items_selected = selected
        self._trace.items_deduped = deduped

    def record_llm(self, model: str, usage_summary: dict):
        self._trace.llm_model = model
        self._trace.llm_calls = usage_summary.get("calls", 0)
        self._trace.prompt_tokens = usage_summary.get("prompt_tokens", 0)
        self._trace.completion_tokens = usage_summary.get("completion_tokens", 0)
        self._trace.estimated_cost_usd = usage_summary.get("estimated_cost_usd", 0.0)

    def record_gate(
        self,
        verdict: str,
        grounding_score: float,
        quality_score: float,
        retry_count: int = 0,
    ):
        self._trace.gate_verdict = verdict
        self._trace.grounding_score = grounding_score
        self._trace.quality_score = quality_score
        self._trace.retry_count = retry_count

    def record_citations(self, total: int, grounded: int):
        self._trace.citations_count = total
        self._trace.citations_grounded = grounded

    def record_output(
        self,
        word_count: int,
        html_path: str = "",
        pdf_path: str = "",
        sent_email: bool = False,
        sent_webhook: bool = False,
    ):
        self._trace.word_count = word_count
        self._trace.output_html = html_path
        self._trace.output_pdf = pdf_path
        self._trace.sent_email = sent_email
        self._trace.sent_webhook = sent_webhook

    def finalize(self):
        self._trace.completed_at = datetime.now().isoformat()
        self._trace.elapsed_seconds = round(time.time() - self._start_time, 2)

    def to_dict(self) -> dict:
        return asdict(self._trace)

    def save(self, output_dir: Path | str):
        """Persist trace as JSON file."""
        output_dir = Path(output_dir)
        traces_dir = output_dir / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._trace.preset}_{ts}.json"
        filepath = traces_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        return str(filepath)

    def print_summary(self):
        """Print a concise observability summary to stdout."""
        t = self._trace
        print(f"\n{'─'*50}")
        print(f"📊 Pipeline Trace — {t.preset} [{t.issue_label}]")
        print(f"{'─'*50}")
        print(f"  ⏱  Total: {t.elapsed_seconds:.1f}s")
        print(f"  📥 Sources: {t.sources_succeeded}/{t.sources_attempted} OK "
              f"→ {t.items_fetched} items, {t.facts_fetched} facts")
        print(f"  🎯 Scored→Selected→Deduped: "
              f"{t.items_scored}→{t.items_selected}→{t.items_deduped}")
        print(f"  🤖 LLM: {t.llm_model} | {t.llm_calls} calls | "
              f"{t.prompt_tokens}+{t.completion_tokens} tokens "
              f"(~${t.estimated_cost_usd:.4f})")
        print(f"  ✅ Gate: {t.gate_verdict.upper()} "
              f"(grounding={t.grounding_score:.0%}, quality={t.quality_score:.0%}, "
              f"retries={t.retry_count})")
        if t.citations_count:
            print(f"  📎 Citations: {t.citations_grounded}/{t.citations_count} grounded")
        print(f"  📝 Output: {t.word_count} chars")
        for phase, dur in t.phase_timings.items():
            print(f"     {phase:12s} {dur:5.1f}s")
        print(f"{'─'*50}")
