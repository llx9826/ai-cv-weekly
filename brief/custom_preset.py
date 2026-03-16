"""LunaClaw Brief — Custom Preset Generator

Generates PresetConfig from a natural language description using LLM.
Persists to data/custom_presets/ as YAML for reuse.

Usage:
  python run.py --create-preset "我是新能源基金经理，每天关注光伏、锂电、风电板块"
"""

import json
import re
from pathlib import Path

import yaml

from brief.models import PresetConfig
from brief.llm import LLMClient
from brief.registry import SourceRegistry


_SYSTEM_PROMPT = """You are a report configuration generator for LunaClaw Brief.
Given a user's description of their reporting needs, generate a PresetConfig JSON.

Available source adapters: {sources}
Available editor types: tech_weekly, tech_daily, finance_weekly, finance_daily, stock_a, stock_hk, stock_us

Return ONLY valid JSON with these fields:
{{
  "name": "snake_case_name (≤30 chars, unique)",
  "display_name": "Human readable name",
  "cycle": "daily" | "weekly",
  "editor_type": "pick from available editor types above",
  "sources": ["list", "of", "source", "names"],
  "time_range_days": 1 or 7,
  "max_items": 10-25,
  "domain_keywords": {{"keyword": weight(1-5)}},
  "source_weights": {{"source": weight(1-3)}},
  "low_value_keywords": ["list"],
  "sections": ["section_ids"],
  "target_word_count": [min, max],
  "tone": "sharp" | "neutral",
  "min_sections": 2-6,
  "min_word_count": 600-3500,
  "dedup_window_days": 3-30,
  "template": "report",
  "description": "one-line description of this preset",
  "show_disclaimer": true/false
}}

Rules:
- Pick sources that best match the user's domain
- Generate 10-20 relevant domain keywords with appropriate weights
- Set word count based on cycle (daily: 800-1500, weekly: 3000-5500)
- Finance/stock presets should have show_disclaimer=true
- Name should be descriptive and unique"""


def generate_custom_preset(description: str, config: dict) -> PresetConfig | None:
    """Generate a custom PresetConfig from natural language and save to YAML."""
    try:
        llm = LLMClient(config.get("llm", {}))
    except ValueError as e:
        print(f"[custom_preset] LLM not configured: {e}")
        return None

    available_sources = list(SourceRegistry.list_all().keys())
    system = _SYSTEM_PROMPT.format(sources=", ".join(available_sources))

    result = llm.chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": description},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    if not result:
        print("[custom_preset] LLM returned empty response")
        return None

    try:
        clean = result.strip()
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"[custom_preset] Failed to parse LLM output: {e}")
        print(f"[custom_preset] Raw: {result[:200]}")
        return None

    if "target_word_count" in data and isinstance(data["target_word_count"], list):
        data["target_word_count"] = tuple(data["target_word_count"])

    try:
        preset = PresetConfig(**data)
    except (TypeError, ValueError) as e:
        print(f"[custom_preset] Invalid preset config: {e}")
        return None

    save_dir = Path(config.get("project_root", ".")) / "data" / "custom_presets"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{preset.name}.yaml"

    save_data = {**data}
    if "target_word_count" in save_data and isinstance(save_data["target_word_count"], tuple):
        save_data["target_word_count"] = list(save_data["target_word_count"])

    with open(save_path, "w", encoding="utf-8") as f:
        yaml.dump(save_data, f, allow_unicode=True, default_flow_style=False)

    print(f"[custom_preset] Saved to {save_path}")

    from brief.presets import PRESETS
    PRESETS[preset.name] = preset

    return preset
