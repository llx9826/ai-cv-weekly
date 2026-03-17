"""ClawCat Brief — Report Pipeline

10-stage pipeline with quality gate, citation tracing, and full observability:

  Fetch → FactFetch → Score → Select → Dedup → Edit → Budget → Gate → Cite → Render → Output

Key integrations:
  - Async parallel fetch (asyncio.gather)
  - Three-level memory (ItemStore / TopicStore / ContentStore)
  - Grounding system (temporal, entity, fact-table, structure)
  - Quality Gate (pass / retry / degrade / block)
  - Citation engine (claim → evidence → source traceability)
  - Eval framework (multi-dimensional quality scoring)
  - Pipeline observability (full trace per run)

Supports both synchronous (run) and streaming (run_stream) execution.
Both paths enforce the same gate semantics — no path can bypass quality control.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

from brief.models import (
    PresetConfig, ReportDraft, GateVerdict,
)
from brief.sources import create_sources
from brief.facts import FactTable, create_fact_sources
from brief.scoring import Scorer, Selector
from brief.memory import MemoryManager
from brief.editors import create_editor
from brief.quality import QualityChecker
from brief.grounding import GroundingPipeline
from brief.token_budget import TokenBudget
from brief.gate import QualityGate
from brief.citation import CitationEngine
from brief.observability import PipelineTracer
from brief.eval.runner import EvalRunner
from brief.renderer.jinja2 import Jinja2Renderer
from brief.sender import EmailSender, WebhookSender
from brief.middleware import (
    PipelineContext, MiddlewareChain,
    TimingMiddleware, MetricsMiddleware, PipelineMiddleware,
)
from brief.log import BriefLogger


def _make_issue_label(cycle: str) -> str:
    """Generate a date-based issue label.

    Daily  → "2026-03-17"
    Weekly → "03.10~03.16"
    """
    now = datetime.now()
    if cycle == "weekly":
        end = now
        start = end - timedelta(days=6)
        return f"{start.strftime('%m.%d')}~{end.strftime('%m.%d')}"
    return now.strftime("%Y-%m-%d")


class ReportPipeline:
    """Orchestrates the full report generation flow with quality gate enforcement.

    The pipeline guarantees:
      - PASS reports are rendered and delivered
      - RETRY reports are regenerated (up to max_retries)
      - DEGRADE reports have ungrounded claims stripped before delivery
      - BLOCK reports are never rendered or delivered

    Usage:
        pipeline = ReportPipeline(preset, global_config)
        result = pipeline.run(user_hint="focus on OCR")
    """

    def __init__(self, preset: PresetConfig, global_config: dict):
        self.preset = preset
        self.config = global_config
        self.project_root = Path(global_config.get("project_root", "."))
        self._chain = MiddlewareChain()
        self._log = BriefLogger("pipeline")

        self._chain.add(TimingMiddleware())
        self._chain.add(MetricsMiddleware())

    def use(self, mw: PipelineMiddleware) -> "ReportPipeline":
        """Register a custom middleware. Returns self for chaining."""
        self._chain.add(mw)
        return self

    def run(
        self,
        user_hint: str = "",
        send_email: bool = False,
    ) -> dict:
        """Synchronous entry point. Runs the async pipeline internally."""
        return asyncio.run(self._run_async(user_hint, send_email))

    def run_stream(
        self,
        user_hint: str = "",
    ) -> Generator[dict, None, None]:
        """Streaming entry point. Yields progress events as dicts.

        Enforces the same quality gate as run() — blocked reports
        yield an error event instead of a result.
        """
        yield from self._run_stream_sync(user_hint)

    def _create_memory_manager(self) -> MemoryManager:
        data_dir = self.project_root / "data"
        llm_cfg = self.config.get("llm", {})
        llm = None
        try:
            from brief.llm import LLMClient
            llm = LLMClient(llm_cfg)
        except Exception:
            pass
        return MemoryManager.create_default(data_dir, llm=llm)

    # ────────────────────────────────────────────
    # Shared: verify + gate + cite (used by both run and stream)
    # ────────────────────────────────────────────

    def _verify_and_gate(
        self,
        draft: ReportDraft,
        deduped: list,
        fact_table: FactTable,
        editor,
        user_hint: str,
        memory_context: dict | None,
        issue_label: str,
        log,
    ) -> tuple:
        """Run grounding + quality + gate loop. Returns final draft and gate result."""
        from brief.models import GateVerdict

        grounding = GroundingPipeline.create_default(fact_table=fact_table)
        checker = QualityChecker(self.preset)
        gate = QualityGate(self.preset)
        ft_arg = fact_table if not fact_table.is_empty else None

        retry_count = 0

        while True:
            if self.preset.max_word_count > 0:
                budget = TokenBudget(
                    context_window=self.config.get("llm", {}).get("context_window", 128000),
                    output_reserve=self.config.get("llm", {}).get("output_reserve", 8000),
                )
                draft.markdown = budget.enforce_output_limit(
                    draft.markdown, self.preset.max_word_count
                )

            gr = grounding.run(draft.markdown, deduped)
            qr = checker.check(draft.markdown)

            log.info(f"Gate check #{retry_count}: grounding={gr.score:.0%}, quality={qr.score:.0%}")
            for gi in gr.issues:
                if gi.severity in ("error", "warning"):
                    log.warn(f"  ⚠️ [{gi.checker}] {gi.message}")

            gate_result = gate.evaluate(gr, qr, retry_count)

            if gate_result.verdict == GateVerdict.PASS:
                log.info("✅ Gate: PASS")
                return draft, gate_result, gr, qr, retry_count

            if gate_result.verdict == GateVerdict.RETRY:
                retry_count += 1
                retry_hint = gate.build_retry_hint(gr, qr)
                full_hint = (user_hint + "\n" if user_hint else "") + retry_hint
                log.info(f"🔄 Gate: RETRY (attempt {retry_count})")

                new_draft = editor.generate(
                    deduped, issue_label, full_hint,
                    memory_context=memory_context,
                    fact_table=ft_arg,
                )
                if new_draft:
                    draft = new_draft
                    continue
                log.warn("Retry generation failed, proceeding with current draft")
                gate_result.verdict = GateVerdict.DEGRADE

            if gate_result.verdict == GateVerdict.DEGRADE:
                log.warn("⚠️ Gate: DEGRADE — stripping ungrounded claims")
                draft.markdown = QualityGate.degrade_markdown(draft.markdown, gr)
                gate_result.degraded_markdown = draft.markdown
                return draft, gate_result, gr, qr, retry_count

            if gate_result.verdict == GateVerdict.BLOCK:
                log.error("🚫 Gate: BLOCK — report will not be published")
                return draft, gate_result, gr, qr, retry_count

            return draft, gate_result, gr, qr, retry_count

    # ────────────────────────────────────────────
    # run() — synchronous path
    # ────────────────────────────────────────────

    async def _run_async(self, user_hint: str, send_email: bool) -> dict:
        p = self.preset
        ctx = PipelineContext(preset_name=p.name)
        self._chain.fire_pipeline_start(ctx)
        tracer = PipelineTracer(preset=p.name)

        now = datetime.now()
        since = now - timedelta(days=p.time_range_days)
        time_range = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        log = self._log.bind(preset=p.name)

        issue_label = _make_issue_label(p.cycle)
        ctx.issue_label = issue_label
        tracer._trace.issue_label = issue_label

        brand_name = self.config.get("brand", {}).get("full_name", "ClawCat Brief")
        print(f"\n{'='*50}")
        print(f"🦞 {brand_name} — {p.display_name}")
        print(f"{'='*50}")

        # ── Phase 1: Fetch ──
        self._chain.fire_phase_start("fetch", ctx)
        tracer.phase_start("fetch")
        log.info(f"Phase 1: Fetch — {len(p.sources)} sources (parallel)")
        sources = create_sources(p.sources, self.config)

        async def _safe_fetch(source):
            try:
                items = await source.fetch(since, now)
                return source.name, items or []
            except Exception as e:
                log.warn(f"  ❌ {source.name}", error=str(e)[:60])
                return source.name, []

        fetch_results = await asyncio.gather(*[_safe_fetch(s) for s in sources])

        all_items = []
        sources_used = []
        for name, items in fetch_results:
            if items:
                all_items.extend(items)
                sources_used.append(name)
                log.info(f"  ✅ {name}", count=len(items))
        ctx.phase_counts["fetch"] = len(all_items)
        self._chain.fire_phase_end("fetch", ctx)
        tracer.phase_end("fetch")

        if not all_items:
            log.error("No items fetched, aborting.")
            tracer.record_fetch(len(sources), 0, 0)
            tracer.finalize()
            tracer.save(self.project_root / "output")
            return {"success": False, "error": "no_items"}

        # ── Phase 1b: Fact Fetch ──
        fact_table = FactTable()
        if p.fact_sources:
            self._chain.fire_phase_start("fact_fetch", ctx)
            tracer.phase_start("fact_fetch")
            log.info(f"Phase 1b: Fact Fetch — {len(p.fact_sources)} fact sources")
            fact_sources = create_fact_sources(p.fact_sources, self.config)
            fact_table = await FactTable.from_sources(fact_sources, since, now)
            ctx.phase_counts["fact_fetch"] = len(fact_table.facts)
            self._chain.fire_phase_end("fact_fetch", ctx)
            tracer.phase_end("fact_fetch")
            log.info("Fact Fetch complete", facts=len(fact_table.facts))

        tracer.record_fetch(len(sources), len(sources_used), len(all_items), len(fact_table.facts))

        # ── Phase 2: Score ──
        self._chain.fire_phase_start("score", ctx)
        tracer.phase_start("score")
        scorer = Scorer(p)
        scored = scorer.score(all_items)
        ctx.phase_counts["score"] = len(scored)
        self._chain.fire_phase_end("score", ctx)
        tracer.phase_end("score")

        # ── Phase 3: Select ──
        self._chain.fire_phase_start("select", ctx)
        selector = Selector(p)
        selected = selector.select(scored)
        ctx.phase_counts["select"] = len(selected)
        self._chain.fire_phase_end("select", ctx)

        # ── Phase 4: Dedup ──
        self._chain.fire_phase_start("dedup", ctx)
        memory = self._create_memory_manager()
        deduped = memory.filter_items(selected, p.name, p.dedup_window_days)
        is_rerun = not deduped
        if is_rerun:
            deduped = selected
        ctx.phase_counts["dedup"] = len(deduped)
        self._chain.fire_phase_end("dedup", ctx)
        tracer.record_scoring(len(scored), len(selected), len(deduped))

        # ── Phase 5: Edit (LLM) ──
        self._chain.fire_phase_start("edit", ctx)
        tracer.phase_start("edit")
        editor = create_editor(p, self.config)

        hint = user_hint
        if is_rerun:
            hint = (hint + "\n" if hint else "") + "（注意：本期为重新生成，请尽量提供不同的视角和表述。）"

        memory_context = memory.recall_all(p.name)
        draft = editor.generate(
            deduped, issue_label, hint,
            memory_context=memory_context,
            fact_table=fact_table if not fact_table.is_empty else None,
        )
        if not draft:
            log.error("LLM generation failed.")
            tracer.finalize()
            tracer.save(self.project_root / "output")
            return {"success": False, "error": "llm_failed"}
        ctx.phase_counts["edit"] = draft.word_count
        self._chain.fire_phase_end("edit", ctx)
        tracer.phase_end("edit")

        # ── Phase 6: Quality Gate (verify → retry → degrade → block) ──
        self._chain.fire_phase_start("gate", ctx)
        tracer.phase_start("gate")

        draft, gate_result, gr, qr, retry_count = self._verify_and_gate(
            draft, deduped, fact_table, editor, user_hint,
            memory_context, issue_label, log,
        )

        tracer.phase_end("gate")
        tracer.record_llm(
            model=editor.llm.model,
            usage_summary=editor.llm.usage.summary(),
        )
        tracer.record_gate(
            verdict=gate_result.verdict.value,
            grounding_score=gr.score,
            quality_score=qr.score,
            retry_count=retry_count,
        )
        self._chain.fire_phase_end("gate", ctx)

        if gate_result.verdict == GateVerdict.BLOCK:
            log.error("Report blocked by quality gate. Not rendering or sending.")
            tracer.finalize()
            trace_path = tracer.save(self.project_root / "output")
            tracer.print_summary()
            return {
                "success": False,
                "error": "quality_gate_blocked",
                "gate_verdict": "block",
                "grounding_score": gr.score,
                "quality_score": qr.score,
                "trace_path": trace_path,
            }

        # ── Phase 7: Citation (Claim → Evidence → Source) ──
        self._chain.fire_phase_start("citation", ctx)
        tracer.phase_start("citation")
        citation_engine = CitationEngine()
        citations = citation_engine.generate(
            draft.markdown, deduped,
            fact_table if not fact_table.is_empty else None,
        )
        citation_summary = CitationEngine.summary(citations)
        tracer.record_citations(citation_summary["total"], citation_summary["grounded"])
        tracer.phase_end("citation")
        self._chain.fire_phase_end("citation", ctx)
        log.info("Citations", **citation_summary)

        # ── Phase 8: Eval ──
        eval_runner = EvalRunner(p)
        eval_result = eval_runner.evaluate(
            draft.markdown, deduped, fact_table, citations, issue_label,
        )
        log.info(f"Eval score: {eval_result.overall_score:.0%}")

        # ── Phase 9: Render ──
        self._chain.fire_phase_start("render", ctx)
        tracer.phase_start("render")
        template_dir = self.project_root / "templates"
        static_dir = self.project_root / "static"
        output_dir = self.project_root / "output"
        renderer = Jinja2Renderer(template_dir, static_dir, output_dir)

        stats = {
            "total_items": len(all_items),
            "sources_used": len(sources_used),
            "selected_items": len(deduped),
            "word_count": draft.word_count,
            "gate_verdict": gate_result.verdict.value,
            "grounding_score": f"{gr.score:.0%}",
            "citations": citation_summary,
            "eval_score": f"{eval_result.overall_score:.0%}",
        }
        brand = self.config.get("brand", {})
        render_result = renderer.render(draft, p, time_range, stats, brand=brand, citations=citations)
        tracer.phase_end("render")
        self._chain.fire_phase_end("render", ctx)

        # ── Save citations alongside report ──
        citations_path = output_dir / f"{p.name}_{issue_label}_citations.json"
        with open(citations_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": citation_summary,
                "citations": CitationEngine.to_json(citations),
                "eval": {
                    "overall": eval_result.overall_score,
                    "dimensions": [
                        {"name": m.name, "score": m.score, "detail": m.detail}
                        for m in eval_result.metrics
                    ],
                },
            }, f, ensure_ascii=False, indent=2)

        # ── Memory Save ──
        if not is_rerun:
            memory.save_all(p.name, issue_label, deduped, draft.markdown)

        # ── Phase 10: Output ──
        sent_email_ok = False
        sent_webhook_ok = False
        if send_email:
            self._chain.fire_phase_start("output", ctx)
            email_cfg = self.config.get("email", {})
            if email_cfg:
                email_cfg["brand_name"] = brand_name
                sender = EmailSender(email_cfg)
                html_content = Path(render_result["html_path"]).read_text(encoding="utf-8")
                subject = f"🦞 {brand_name} {p.display_name} — {issue_label}"
                sender.send(
                    subject=subject,
                    html_content=html_content,
                    text_content=draft.markdown[:2000],
                    attachment_path=render_result.get("pdf_path"),
                )
                sent_email_ok = True
            webhook_cfg = self.config.get("webhook", {})
            if webhook_cfg and webhook_cfg.get("url"):
                wh = WebhookSender(webhook_cfg)
                wh.send(
                    f"🦞 {brand_name} {p.display_name} — {issue_label}",
                    draft.markdown[:2000],
                    render_result.get("html_path", ""),
                )
                sent_webhook_ok = True
            self._chain.fire_phase_end("output", ctx)

        self._chain.fire_pipeline_end(ctx)

        # ── Observability: finalize and persist trace ──
        tracer.record_output(
            word_count=draft.word_count,
            html_path=render_result.get("html_path", ""),
            pdf_path=render_result.get("pdf_path", ""),
            sent_email=sent_email_ok,
            sent_webhook=sent_webhook_ok,
        )
        tracer.finalize()
        trace_path = tracer.save(self.project_root / "output")
        tracer.print_summary()

        print(f"\n{'='*50}")
        verdict_icon = {"pass": "✅", "degrade": "⚠️"}.get(gate_result.verdict.value, "❓")
        print(f"{verdict_icon} {issue_label} — {p.display_name} [{gate_result.verdict.value.upper()}]")
        print(f"{'='*50}\n")

        return {
            "success": True,
            "issue_label": issue_label,
            "preset": p.name,
            "gate_verdict": gate_result.verdict.value,
            "grounding_score": gr.score,
            "quality_score": qr.score,
            "eval_score": eval_result.overall_score,
            "word_count": draft.word_count,
            "citations": citation_summary,
            "trace_path": trace_path,
            "metrics": ctx.extras.get("metrics", {}),
            **render_result,
        }

    # ────────────────────────────────────────────
    # run_stream() — streaming path (same gate semantics)
    # ────────────────────────────────────────────

    def _run_stream_sync(self, user_hint: str) -> Generator[dict, None, None]:
        p = self.preset
        now = datetime.now()
        since = now - timedelta(days=p.time_range_days)
        time_range = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        issue_label = _make_issue_label(p.cycle)
        log = self._log.bind(preset=p.name)
        tracer = PipelineTracer(preset=p.name, issue_label=issue_label)

        # Phase 1: Fetch
        tracer.phase_start("fetch")
        yield {"type": "phase", "phase": "fetch", "status": "start"}
        sources = create_sources(p.sources, self.config)
        all_items = []
        sources_used = []
        sources_attempted = len(sources)
        for source in sources:
            try:
                items = asyncio.run(source.fetch(since, now))
                if items:
                    all_items.extend(items)
                    sources_used.append(source.name)
            except Exception:
                pass
        tracer.phase_end("fetch")
        yield {"type": "phase", "phase": "fetch", "status": "done", "count": len(all_items)}

        if not all_items:
            yield {"type": "error", "error": "no_items"}
            return

        # Phase 1b: Fact Fetch
        fact_table = FactTable()
        if p.fact_sources:
            tracer.phase_start("fact_fetch")
            yield {"type": "phase", "phase": "fact_fetch", "status": "start"}
            fact_sources = create_fact_sources(p.fact_sources, self.config)
            fact_table = asyncio.run(FactTable.from_sources(fact_sources, since, now))
            tracer.phase_end("fact_fetch")
            yield {"type": "phase", "phase": "fact_fetch", "status": "done", "count": len(fact_table.facts)}

        tracer.record_fetch(
            sources_attempted=sources_attempted,
            sources_succeeded=len(sources_used),
            items_fetched=len(all_items),
            facts_fetched=len(fact_table.facts),
        )

        # Phase 2-4: Score → Select → Dedup
        tracer.phase_start("score_select")
        scorer = Scorer(p)
        scored = scorer.score(all_items)
        selector = Selector(p)
        selected = selector.select(scored)
        memory = self._create_memory_manager()
        deduped = memory.filter_items(selected, p.name, p.dedup_window_days)
        is_rerun = not deduped
        if is_rerun:
            deduped = selected
        tracer.phase_end("score_select")
        tracer.record_scoring(len(scored), len(selected), len(deduped))
        yield {"type": "phase", "phase": "select", "status": "done",
               "scored": len(scored), "selected": len(selected), "deduped": len(deduped)}

        # Phase 5: Streaming LLM generation
        tracer.phase_start("edit")
        yield {"type": "phase", "phase": "edit", "status": "start"}
        editor = create_editor(p, self.config)
        hint = user_hint
        if is_rerun:
            hint = (hint + "\n" if hint else "") + "（注意：本期为重新生成，请尽量提供不同的视角和表述。）"
        memory_context = memory.recall_all(p.name)

        markdown_chunks: list[str] = []
        ft_arg = fact_table if not fact_table.is_empty else None
        for chunk in editor.generate_stream(
            deduped, issue_label, hint,
            memory_context=memory_context, fact_table=ft_arg,
        ):
            markdown_chunks.append(chunk)
            yield {"type": "chunk", "content": chunk}

        full_markdown = "".join(markdown_chunks)
        full_markdown = editor._clean_markdown(full_markdown)
        tracer.phase_end("edit")
        yield {"type": "phase", "phase": "edit", "status": "done", "chars": len(full_markdown)}

        # Phase 6: Quality Gate (same logic as run)
        tracer.phase_start("gate")
        draft = ReportDraft(markdown=full_markdown, issue_label=issue_label)

        draft, gate_result, gr, qr, retry_count = self._verify_and_gate(
            draft, deduped, fact_table, editor, user_hint,
            memory_context, issue_label, log,
        )

        tracer.record_gate(
            verdict=gate_result.verdict.value,
            grounding_score=gr.score,
            quality_score=qr.score,
            retry_count=retry_count,
        )
        tracer.record_llm(
            model=editor.llm.model,
            usage_summary=editor.llm.usage.summary(),
        )
        tracer.phase_end("gate")

        if gate_result.verdict == GateVerdict.BLOCK:
            tracer.finalize()
            tracer.save(self.project_root / "output")
            yield {
                "type": "error",
                "error": "quality_gate_blocked",
                "gate_verdict": "block",
                "grounding_score": gr.score,
                "quality_score": qr.score,
            }
            return

        # Phase 7: Citation
        tracer.phase_start("citation")
        citation_engine = CitationEngine()
        citations = citation_engine.generate(draft.markdown, deduped, ft_arg)
        citation_summary = CitationEngine.summary(citations)
        tracer.record_citations(
            total=citation_summary.get("total", 0),
            grounded=citation_summary.get("grounded", 0),
        )
        tracer.phase_end("citation")

        # Phase 7b: Eval
        tracer.phase_start("eval")
        eval_runner = EvalRunner(p)
        eval_result = eval_runner.evaluate(
            draft.markdown, deduped, fact_table, citations, issue_label,
        )
        tracer.phase_end("eval")

        yield {
            "type": "phase", "phase": "gate", "status": "done",
            "gate_verdict": gate_result.verdict.value,
            "grounding_score": gr.score,
            "quality_score": qr.score,
            "eval_score": eval_result.overall_score,
            "citations": citation_summary,
        }

        # Phase 8: Render
        tracer.phase_start("render")
        template_dir = self.project_root / "templates"
        static_dir = self.project_root / "static"
        output_dir = self.project_root / "output"
        renderer = Jinja2Renderer(template_dir, static_dir, output_dir)

        stats = {
            "total_items": len(all_items),
            "sources_used": len(sources_used),
            "selected_items": len(deduped),
            "word_count": draft.word_count,
            "gate_verdict": gate_result.verdict.value,
            "citations": citation_summary,
            "eval_score": f"{eval_result.overall_score:.0%}",
        }
        brand = self.config.get("brand", {})
        render_result = renderer.render(draft, p, time_range, stats, brand=brand, citations=citations)
        tracer.phase_end("render")

        # Save citation + eval sidecar
        citations_path = output_dir / f"{p.name}_{issue_label}_citations.json"
        with open(citations_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": citation_summary,
                "citations": CitationEngine.to_json(citations),
                "eval": {
                    "overall": eval_result.overall_score,
                    "dimensions": [
                        {"name": m.name, "score": m.score, "detail": m.detail}
                        for m in eval_result.metrics
                    ],
                },
            }, f, ensure_ascii=False, indent=2)

        tracer.record_output(
            word_count=draft.word_count,
            html_path=render_result.get("html_path", ""),
            pdf_path=render_result.get("pdf_path", ""),
        )

        if not is_rerun:
            memory.save_all(p.name, issue_label, deduped, draft.markdown)

        tracer.finalize()
        trace_path = tracer.save(self.project_root / "output")
        tracer.print_summary()

        yield {
            "type": "result",
            "success": True,
            "issue_label": issue_label,
            "preset": p.name,
            "gate_verdict": gate_result.verdict.value,
            "grounding_score": gr.score,
            "quality_score": qr.score,
            "eval_score": eval_result.overall_score,
            "citations": citation_summary,
            "word_count": draft.word_count,
            "trace_path": trace_path,
            **render_result,
        }
