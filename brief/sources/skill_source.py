"""ClawCat Brief — OpenClaw Skill Data Source Adapter

Fetches data from any OpenClaw skill that returns structured items.
Designed to integrate with the ClawHub ecosystem, e.g.:

  - @nesdeq/openclaw-feeds  (21 news + 26 finance + 10 games RSS feeds)
  - Any skill with a fetch/query function returning JSON items

Config example:
    sources_config:
      skill:
        skills:
          - name: "@nesdeq/openclaw-feeds"
            function: "fetch_feeds"
            params:
              category: "finance"
              limit: 20
          - name: "@custom/my-data-skill"
            function: "get_items"

OpenClaw Skill 数据源适配器：可调用 ClawHub 上的任意数据 skill 获取结构化内容。
"""

import json
import subprocess
from datetime import datetime

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("skill")
class SkillSource(BaseSource):
    """Adapter that invokes OpenClaw skills as data sources (OpenClaw Skill 数据源适配器)."""

    name = "skill"

    def __init__(self, global_config: dict):
        super().__init__(global_config)
        skill_cfg = global_config.get("sources_config", {}).get("skill", {})
        self._skills: list[dict] = skill_cfg.get("skills", [])
        self._timeout: int = skill_cfg.get("timeout", 30)

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        for skill_cfg in self._skills:
            try:
                skill_items = self._invoke_skill(skill_cfg, since, until)
                items.extend(skill_items)
            except Exception as e:
                print(f"[SkillSource] Failed to invoke {skill_cfg.get('name', '?')}: {e}")
        return items

    def _invoke_skill(
        self, skill_cfg: dict, since: datetime, until: datetime
    ) -> list[Item]:
        """Invoke an OpenClaw skill and parse its output into Items.

        Tries two methods:
        1. npx clawhub run (CLI invocation)
        2. Direct Python import (if skill is installed locally)
        """
        skill_name = skill_cfg.get("name", "")
        func_name = skill_cfg.get("function", "fetch")
        params = skill_cfg.get("params", {})
        params["since"] = since.isoformat()
        params["until"] = until.isoformat()

        result = self._try_cli_invoke(skill_name, func_name, params)
        if result is not None:
            return self._parse_skill_output(result, skill_name)

        result = self._try_python_invoke(skill_name, func_name, params)
        if result is not None:
            return self._parse_skill_output(result, skill_name)

        return []

    def _try_cli_invoke(
        self, skill_name: str, func_name: str, params: dict
    ) -> list[dict] | None:
        """Try invoking skill via npx clawhub run."""
        try:
            cmd = [
                "npx", "clawhub", "run", skill_name,
                "--function", func_name,
                "--params", json.dumps(params),
                "--output", "json",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return None

    @staticmethod
    def _try_python_invoke(
        skill_name: str, func_name: str, params: dict
    ) -> list[dict] | None:
        """Try importing skill as a Python module (for locally installed skills)."""
        module_name = skill_name.replace("@", "").replace("/", ".").replace("-", "_")
        try:
            import importlib
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name, None)
            if callable(func):
                result = func(params)
                if isinstance(result, list):
                    return result
        except (ImportError, AttributeError):
            pass
        return None

    @staticmethod
    def _parse_skill_output(data: list[dict], skill_name: str) -> list[Item]:
        """Normalize skill output into Item list.

        Expected format per item:
          {"title": "...", "url": "...", "summary": "...", "published_at": "...", ...}
        """
        items: list[Item] = []
        if not isinstance(data, list):
            return items

        for entry in data:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title", "")
            if not title:
                continue
            items.append(Item(
                title=title,
                url=entry.get("url", entry.get("link", "")),
                source=f"skill:{skill_name}",
                raw_text=entry.get("summary", entry.get("description", entry.get("content", "")))[:500],
                published_at=entry.get("published_at", entry.get("pubDate", "")),
                meta={
                    "sub_source": skill_name,
                    "points": entry.get("points", 0),
                    "stars": entry.get("stars", 0),
                    **{k: v for k, v in entry.items()
                       if k not in ("title", "url", "link", "summary", "description",
                                    "content", "published_at", "pubDate", "points", "stars")},
                },
            ))
        return items
