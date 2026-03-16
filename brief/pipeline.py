"""LunaClaw Brief — Report Pipeline

8-stage pipeline with middleware hooks and structured logging:

  Fetch → Score → Select → Dedup → Edit(LLM) → Quality → Render → Output

Supports both synchronous (run) and streaming (run_stream) execution.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

from brief.models import PresetConfig
from brief.sources import create_sources
from brief.scoring import Scorer, Selector
from brief.dedup import UsedItemStore, IssueCounter
from brief.editors import create_editor
from brief.quality import QualityChecker
from brief.renderer.jinja2 import Jinja2Renderer
from brief.sender import EmailSender, WebhookSender
from brief.middleware import (
    PipelineContext, MiddlewareChain,
    TimingMiddleware, MetricsMiddleware, PipelineMiddleware,
)
from brief.log import BriefLogger


class ReportPipeline:
    """Orchestrates the full report generation flow.

    Usage:
        pipeline = ReportPipeline(preset, global_config)
        pipeline.use(MyCustomMiddleware())
        result = pipeline.run(user_hint="focus on OCR")

        # Or streaming:
        for event in pipeline.run_stream(user_hint="..."):
            print(event)
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

        Event types:
          {"type": "phase", "phase": "fetch", "status": "done", ...}
          {"type": "chunk", "content": "...markdown chunk..."}
          {"type": "result", ...final result dict...}
        """
        yield from self._run_stream_sync(user_hint)

    async def _run_async(self, user_hint: str, send_email: bool) -> dict:
        p = self.preset
        ctx = PipelineContext(preset_name=p.name)
        self._chain.fire_pipeline_start(ctx)

        now = datetime.now()
        since = now - timedelta(days=p.time_range_days)
        time_range = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        log = self._log.bind(preset=p.name)

        print(f"\n{'='*50}")
        print(f"🦞 LunaClaw Brief — {p.display_name}")
        print(f"{'='*50}")

        # ── Phase 1: Fetch ──
        self._chain.fire_phase_start("fetch", ctx)
        log.info(f"Phase 1: Fetch — {len(p.sources)} sources")
        sources = create_sources(p.sources, self.config)
        all_items = []
        sources_used = []
        for source in sources:
            try:
                items = await source.fetch(since, now)
                if items:
                    all_items.extend(items)
                    sources_used.append(source.name)
                    log.info(f"  ✅ {source.name}", count=len(items))
            except Exception as e:
                log.warn(f"  ❌ {source.name}", error=str(e)[:60])
        ctx.phase_counts["fetch"] = len(all_items)
        self._chain.fire_phase_end("fetch", ctx)
        log.info("Fetch complete", total=len(all_items), sources=len(sources_used))

        if not all_items:
            log.error("No items fetched, aborting.")
            return {"success": False, "error": "no_items"}

        # ── Phase 2: Score ──
        self._chain.fire_phase_start("score", ctx)
        scorer = Scorer(p)
        scored = scorer.score(all_items)
        ctx.phase_counts["score"] = len(scored)
        self._chain.fire_phase_end("score", ctx)
        log.info("Phase 2: Score", valid=len(scored))

        # ── Phase 3: Select ──
        self._chain.fire_phase_start("select", ctx)
        selector = Selector(p)
        selected = selector.select(scored)
        ctx.phase_counts["select"] = len(selected)
        self._chain.fire_phase_end("select", ctx)
        log.info("Phase 3: Select", selected=len(selected))

        # ── Phase 4: Dedup ──
        self._chain.fire_phase_start("dedup", ctx)
        data_dir = self.project_root / "data"
        store = UsedItemStore(data_dir / "used_items.json")
        deduped = store.filter_unseen(selected, p.dedup_window_days)
        dup_count = len(selected) - len(deduped)
        is_rerun = False

        if not deduped:
            log.warn("All items seen before — regenerating with existing material")
            deduped = selected
            is_rerun = True

        ctx.phase_counts["dedup"] = len(deduped)
        self._chain.fire_phase_end("dedup", ctx)
        log.info("Phase 4: Dedup", kept=len(deduped), removed=dup_count,
                 rerun=is_rerun)

        # ── Phase 5: Edit (LLM) ──
        self._chain.fire_phase_start("edit", ctx)
        editor = create_editor(p, self.config)
        counter = IssueCounter(data_dir)
        issue_number = counter.next()
        ctx.issue_number = issue_number
        log.info(f"Phase 5: Edit (LLM) — issue #{issue_number}")
        hint = user_hint
        if is_rerun:
            hint = (hint + "\n" if hint else "") + "（注意：本期为重新生成，请尽量提供不同的视角和表述。）"
        draft = editor.generate(deduped, issue_number, hint)
        if not draft:
            log.error("LLM generation failed.")
            return {"success": False, "error": "llm_failed"}
        ctx.phase_counts["edit"] = draft.word_count
        self._chain.fire_phase_end("edit", ctx)
        log.info("Edit complete", chars=draft.word_count)

        # ── Phase 6: Quality ──
        self._chain.fire_phase_start("quality", ctx)
        checker = QualityChecker(p)
        qr = checker.check(draft.markdown)
        log.info(f"Phase 6: Quality — {'PASS' if qr.passed else 'FAIL'}", score=f"{qr.score:.0%}")
        if qr.issues:
            for issue in qr.issues:
                log.warn(f"  ⚠️ {issue}")

        if not qr.passed:
            log.info("Retrying generation for quality...")
            draft2 = editor.generate(deduped, issue_number, user_hint + "\n请确保所有章节完整。")
            if draft2:
                qr2 = checker.check(draft2.markdown)
                if qr2.score > qr.score:
                    draft, qr = draft2, qr2
                    log.info("Retry improved quality", score=f"{qr.score:.0%}")
        self._chain.fire_phase_end("quality", ctx)

        # ── Phase 7: Render ──
        self._chain.fire_phase_start("render", ctx)
        template_dir = self.project_root / "templates"
        static_dir = self.project_root / "static"
        output_dir = self.project_root / "output"
        renderer = Jinja2Renderer(template_dir, static_dir, output_dir)

        stats = {
            "total_items": len(all_items),
            "sources_used": len(sources_used),
            "selected_items": len(deduped),
            "word_count": draft.word_count,
        }
        render_result = renderer.render(draft, p, time_range, stats)
        self._chain.fire_phase_end("render", ctx)
        log.info("Phase 7: Render", html=render_result["html_path"])
        if render_result.get("pdf_path"):
            log.info("  PDF generated", path=render_result["pdf_path"])

        if not is_rerun:
            store.mark_used(deduped, issue_number)

        # ── Phase 8: Output (Email / Webhook) ──
        if send_email:
            self._chain.fire_phase_start("email", ctx)
            email_cfg = self.config.get("email", {})
            if email_cfg:
                log.info("Phase 8: Email — sending...")
                sender = EmailSender(email_cfg)
                html_content = Path(render_result["html_path"]).read_text(encoding="utf-8")
                subject = f"🦞 {p.display_name} — 第{issue_number}期"
                sender.send(
                    subject=subject,
                    html_content=html_content,
                    text_content=draft.markdown[:2000],
                    attachment_path=render_result.get("pdf_path"),
                )
            webhook_cfg = self.config.get("webhook", {})
            if webhook_cfg and webhook_cfg.get("url"):
                wh = WebhookSender(webhook_cfg)
                wh.send(
                    f"🦞 {p.display_name} — 第{issue_number}期",
                    draft.markdown[:2000],
                    render_result.get("html_path", ""),
                )
            self._chain.fire_phase_end("email", ctx)

        self._chain.fire_pipeline_end(ctx)

        print(f"\n{'='*50}")
        print(f"✅ Issue #{issue_number} — {p.display_name} generated!")
        print(f"{'='*50}\n")

        return {
            "success": True,
            "issue_number": issue_number,
            "preset": p.name,
            "quality_score": qr.score,
            "word_count": draft.word_count,
            "metrics": ctx.extras.get("metrics", {}),
            **render_result,
        }

    def _run_stream_sync(self, user_hint: str) -> Generator[dict, None, None]:
        """Streaming pipeline: yields events during execution."""
        p = self.preset
        now = datetime.now()
        since = now - timedelta(days=p.time_range_days)
        time_range = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"

        # Phase 1-4: run synchronously, yield phase events
        yield {"type": "phase", "phase": "fetch", "status": "start"}
        sources = create_sources(p.sources, self.config)
        all_items = []
        sources_used = []
        for source in sources:
            try:
                items = asyncio.run(source.fetch(since, now))
                if items:
                    all_items.extend(items)
                    sources_used.append(source.name)
            except Exception:
                pass
        yield {"type": "phase", "phase": "fetch", "status": "done", "count": len(all_items)}

        if not all_items:
            yield {"type": "error", "error": "no_items"}
            return

        yield {"type": "phase", "phase": "score", "status": "start"}
        scorer = Scorer(p)
        scored = scorer.score(all_items)
        yield {"type": "phase", "phase": "score", "status": "done", "count": len(scored)}

        yield {"type": "phase", "phase": "select", "status": "start"}
        selector = Selector(p)
        selected = selector.select(scored)
        yield {"type": "phase", "phase": "select", "status": "done", "count": len(selected)}

        yield {"type": "phase", "phase": "dedup", "status": "start"}
        data_dir = self.project_root / "data"
        store = UsedItemStore(data_dir / "used_items.json")
        deduped = store.filter_unseen(selected, p.dedup_window_days)
        is_rerun = not deduped
        if is_rerun:
            deduped = selected
        yield {"type": "phase", "phase": "dedup", "status": "done", "count": len(deduped), "rerun": is_rerun}

        # Phase 5: Streaming LLM generation
        yield {"type": "phase", "phase": "edit", "status": "start"}
        editor = create_editor(p, self.config)
        counter = IssueCounter(data_dir)
        issue_number = counter.next()

        hint = user_hint
        if is_rerun:
            hint = (hint + "\n" if hint else "") + "（注意：本期为重新生成，请尽量提供不同的视角和表述。）"

        markdown_chunks: list[str] = []
        for chunk in editor.generate_stream(deduped, issue_number, hint):
            markdown_chunks.append(chunk)
            yield {"type": "chunk", "content": chunk}

        full_markdown = "".join(markdown_chunks)
        full_markdown = editor._clean_markdown(full_markdown)
        yield {"type": "phase", "phase": "edit", "status": "done", "chars": len(full_markdown)}

        # Phase 6-7: Quality + Render
        from brief.models import ReportDraft
        draft = ReportDraft(markdown=full_markdown, issue_number=issue_number)

        checker = QualityChecker(p)
        qr = checker.check(draft.markdown)

        template_dir = self.project_root / "templates"
        static_dir = self.project_root / "static"
        output_dir = self.project_root / "output"
        renderer = Jinja2Renderer(template_dir, static_dir, output_dir)

        stats = {
            "total_items": len(all_items),
            "sources_used": len(sources_used),
            "selected_items": len(deduped),
            "word_count": draft.word_count,
        }
        render_result = renderer.render(draft, p, time_range, stats)

        if not is_rerun:
            store.mark_used(deduped, issue_number)

        yield {
            "type": "result",
            "success": True,
            "issue_number": issue_number,
            "preset": p.name,
            "quality_score": qr.score,
            "word_count": draft.word_count,
            **render_result,
        }
