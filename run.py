#!/usr/bin/env python3
"""
LunaClaw Brief — Entry point (CLI + OpenClaw Skill)

Usage:
  python run.py                                  # default ai_cv_weekly
  python run.py --preset stock_hk_daily          # explicit preset
  python run.py --hint "生成一个港股日报"           # auto-route by intent
  python run.py --hint "帮我看看腾讯和阿里"        # LLM-based intent routing
  python run.py --create-preset "我是新能源基金经理" # create custom preset
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from brief.presets import get_preset, PRESETS
from brief.pipeline import ReportPipeline


# ─── Intent → preset routing table (checked in order, first match wins) ───
_INTENT_ROUTES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"a\s*股|a.share|沪深|上证|深证|创业板|科创板", re.I), "stock_a_daily"),
    (re.compile(r"港股|hk(?:\s*stock)?(?=\s|$)|hang\s*seng|恒[生指]|hong\s*kong", re.I), "stock_hk_daily"),
    (re.compile(r"美股|us\s*stock|nasdaq|s&?p|道琼斯|wall\s*street|纳斯达克", re.I), "stock_us_daily"),
    (re.compile(r"金融周报|finance\s*weekly|投资周报", re.I), "finance_weekly"),
    (re.compile(r"金融日报|finance\s*daily|投资日报", re.I), "finance_daily"),
    (re.compile(r"日报|daily", re.I), "ai_daily"),
    (re.compile(r"周报|weekly", re.I), "ai_cv_weekly"),
]


def _infer_preset_regex(hint: str) -> str | None:
    """Try to match preset from hint using regex patterns (instant, free)."""
    for pattern, preset_name in _INTENT_ROUTES:
        if pattern.search(hint):
            return preset_name
    return None


def _infer_preset_llm(hint: str, config: dict) -> str | None:
    """Use LLM to classify user intent into a preset (fallback when regex fails)."""
    try:
        from brief.llm import LLMClient
        llm = LLMClient(config.get("llm", {}))

        preset_list = "\n".join(
            f"- {name}: {p.description or p.display_name}"
            for name, p in PRESETS.items()
        )

        system = f"""You are a preset classifier. Given a user's hint, pick the best preset.
Available presets:
{preset_list}

Return ONLY a JSON object: {{"preset": "<preset_name>"}}
If uncertain, return {{"preset": "ai_cv_weekly"}}."""

        result = llm.classify(system, hint)
        parsed = json.loads(result.strip().removeprefix("```json").removesuffix("```").strip())
        name = parsed.get("preset", "")
        if name in PRESETS:
            return name
    except Exception:
        pass
    return None


def _infer_preset(hint: str, explicit_preset: str, config: dict | None = None) -> str:
    """Hybrid preset router: regex first → LLM fallback → default."""
    if explicit_preset != "ai_cv_weekly":
        return explicit_preset
    if not hint:
        return explicit_preset

    # Fast path: regex
    matched = _infer_preset_regex(hint)
    if matched:
        return matched

    # Slow path: LLM classification
    if config:
        llm_matched = _infer_preset_llm(hint, config)
        if llm_matched:
            return llm_matched

    return explicit_preset


def load_config() -> dict:
    """Merge config.yaml + config.local.yaml (local wins)."""
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
        _deep_merge(config, local)

    config["project_root"] = str(root)
    return config


def _deep_merge(base: dict, override: dict):
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def generate_report(params: dict | None = None) -> dict:
    """OpenClaw Skill entry: accepts params dict, returns result dict."""
    params = params or {}
    explicit_preset = params.get("preset", "ai_cv_weekly")
    user_hint = params.get("hint", "")
    send_email = params.get("send_email", False)

    config = load_config()
    preset_name = _infer_preset(user_hint, explicit_preset, config)

    preset = get_preset(preset_name)
    pipeline = ReportPipeline(preset, config)
    return pipeline.run(user_hint=user_hint, send_email=send_email)


def create_custom_preset(description: str):
    """Create a custom preset from a natural language description."""
    from brief.custom_preset import generate_custom_preset
    config = load_config()
    preset = generate_custom_preset(description, config)
    if preset:
        print(f"\n✅ Custom preset '{preset.name}' created!")
        print(f"   Use: python run.py --preset {preset.name}")
    else:
        print("\n❌ Failed to create custom preset.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="LunaClaw Brief — AI-powered report engine")
    parser.add_argument(
        "--preset", default="ai_cv_weekly",
        help=f"Preset name ({' | '.join(PRESETS.keys())})",
    )
    parser.add_argument("--hint", default="", help="Extra hint (also used for auto-routing preset)")
    parser.add_argument("--email", action="store_true", help="Send report via email after generation")
    parser.add_argument("--create-preset", metavar="DESC", help="Create custom preset from description")
    args = parser.parse_args()

    if args.create_preset:
        create_custom_preset(args.create_preset)
        return

    config = load_config()
    preset_name = _infer_preset(args.hint, args.preset, config)
    if preset_name != args.preset and args.preset == "ai_cv_weekly":
        print(f"🧭 Intent detected → auto-routing to preset: {preset_name}")

    try:
        result = generate_report({
            "preset": preset_name,
            "hint": args.hint,
            "send_email": args.email,
        })
        if result.get("success"):
            print(f"\n🎉 报告已生成：{result.get('html_path', '')}")
        else:
            print(f"\n❌ 生成失败：{result.get('error', 'unknown')}")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 运行异常：{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
