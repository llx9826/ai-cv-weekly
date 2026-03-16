#!/usr/bin/env python3
"""
LunaClaw Brief — 入口

用法:
  python run.py                        # 默认 ai_cv_weekly
  python run.py --preset ai_daily
  python run.py --preset ai_cv_weekly --email
  python run.py --preset ai_daily --hint "重点关注 OCR 方向"
"""

import argparse
import sys
from pathlib import Path

import yaml

from brief.presets import get_preset
from brief.pipeline import ReportPipeline


def load_config() -> dict:
    """合并 config.yaml + config.local.yaml（local 优先）"""
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
    """OpenClaw Skill 入口：接收 params，返回结果 dict"""
    params = params or {}
    preset_name = params.get("preset", "ai_cv_weekly")
    user_hint = params.get("hint", "")
    send_email = params.get("send_email", False)

    preset = get_preset(preset_name)
    config = load_config()
    pipeline = ReportPipeline(preset, config)
    return pipeline.run(user_hint=user_hint, send_email=send_email)


def main():
    parser = argparse.ArgumentParser(description="LunaClaw Brief — 智能简报引擎")
    parser.add_argument("--preset", default="ai_cv_weekly", help="Preset 名称")
    parser.add_argument("--hint", default="", help="给 LLM 的额外提示")
    parser.add_argument("--email", action="store_true", help="生成后发送邮件")
    args = parser.parse_args()

    try:
        result = generate_report({
            "preset": args.preset,
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
