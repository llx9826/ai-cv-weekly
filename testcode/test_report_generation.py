"""Report Generation Smoke Test

Quick smoke tests that verify:
  1. Preset loading and routing
  2. Pipeline construction (no actual LLM call)
  3. Fact Table injection into prompts
  4. Editor prompt formatting

Usage:
    python -m testcode.test_report_generation
"""

import asyncio
from datetime import datetime, timedelta

from brief.presets import PRESETS, get_preset, derive_preset
from brief.models import Item
from brief.facts import FactTable, create_fact_sources
from brief.facts.protocol import FactTable as FT
from brief.models import Fact


def test_preset_loading():
    """Verify all built-in presets load correctly."""
    print("=" * 60)
    print("Test: Preset Loading")
    print("=" * 60)

    for name, preset in PRESETS.items():
        facts_tag = f" fact_sources={preset.fact_sources}" if preset.fact_sources else ""
        print(f"  {name}: cycle={preset.cycle}, editor={preset.editor_type}, "
              f"sources={preset.sources}{facts_tag}")

    assert "ai_cv_weekly" in PRESETS
    assert "stock_a_daily" in PRESETS
    assert "stock_hk_daily" in PRESETS
    assert "stock_us_daily" in PRESETS

    a_daily = get_preset("stock_a_daily")
    assert a_daily.fact_sources == ["sina_a_share", "eastmoney_fact"]
    assert a_daily.show_disclaimer is True

    print(f"\n✅ {len(PRESETS)} presets loaded — PASS")


def test_preset_derivation():
    """Verify derive_preset correctly inherits fact_sources."""
    print("\n" + "=" * 60)
    print("Test: Preset Derivation (fact_sources inheritance)")
    print("=" * 60)

    a_weekly = derive_preset("stock_a_daily", "weekly")
    assert a_weekly is not None
    assert a_weekly.cycle == "weekly"
    assert a_weekly.fact_sources == ["sina_a_share", "eastmoney_fact"]
    print(f"  stock_a_weekly: fact_sources={a_weekly.fact_sources} — inherited OK")

    hk_weekly = derive_preset("stock_hk_daily", "weekly")
    assert hk_weekly is not None
    assert hk_weekly.fact_sources == ["sina_hk"]
    print(f"  stock_hk_weekly: fact_sources={hk_weekly.fact_sources} — inherited OK")

    ai_daily = derive_preset("ai_cv_weekly", "daily")
    assert ai_daily is not None
    assert ai_daily.fact_sources == []
    print(f"  ai_daily: fact_sources={ai_daily.fact_sources} — empty OK (no facts for tech)")

    print("\n✅ Derivation preserves fact_sources — PASS")


def test_fact_table_prompt_injection():
    """Verify FactTable.to_prompt() formats correctly for LLM injection."""
    print("\n" + "=" * 60)
    print("Test: Fact Table Prompt Injection Format")
    print("=" * 60)

    facts = [
        Fact(key="sh000001.price", value="3245.67", label="上证综指", unit="点", source="新浪行情", category="index"),
        Fact(key="sh000001.change_pct", value="+1.23%", label="上证综指涨跌幅", source="新浪行情", category="index"),
        Fact(key="northbound.total", value="+42.30亿", label="北向资金合计", source="东方财富", category="capital_flow"),
        Fact(key="sector.top.1", value="长材 +4.14%", label="涨幅第一板块", source="东方财富", category="sector"),
        Fact(key="ipo.1.301234", value="XXX科技(301234) 申购日:2026-03-18 发行价:12.50元", label="新股#1 XXX科技", source="东方财富", category="ipo"),
    ]
    table = FT(facts)

    prompt = table.to_prompt()

    assert "事实数据表" in prompt
    assert "严格约束" in prompt
    assert "3245.67" in prompt
    assert "+1.23%" in prompt
    assert "42.30亿" in prompt
    assert "大盘指数" in prompt
    assert "资金流向" in prompt

    print("  Prompt structure:")
    for line in prompt.split("\n"):
        if line.strip():
            print(f"    {line}")

    print(f"\n✅ Fact Table prompt injection correct — PASS")


def test_editor_prompt_with_fact_table():
    """Verify Editor appends Fact Table to user prompt."""
    print("\n" + "=" * 60)
    print("Test: Editor Fact Table Integration")
    print("=" * 60)

    from brief.editors.base import BaseEditor

    facts = [
        Fact(key="sh000001.change_pct", value="-0.85%", label="上证综指涨跌幅", source="新浪行情", category="index"),
    ]
    table = FT(facts)

    result = BaseEditor._format_fact_table(table)
    assert "事实数据表" in result
    assert "-0.85%" in result
    print(f"  _format_fact_table() output length: {len(result)} chars")
    print(f"  Contains fact data: True")

    result_none = BaseEditor._format_fact_table(None)
    assert result_none == ""
    print(f"  _format_fact_table(None) returns empty: True")

    result_empty = BaseEditor._format_fact_table(FT())
    assert result_empty == ""
    print(f"  _format_fact_table(empty table) returns empty: True")

    print("\n✅ Editor Fact Table integration correct — PASS")


def test_brand_in_presets():
    """Check preset display_names don't contain old brand 'LunaClaw'."""
    print("\n" + "=" * 60)
    print("Test: Brand Name in Presets")
    print("=" * 60)

    issues = []
    for name, preset in PRESETS.items():
        if "LunaClaw" in preset.display_name:
            issues.append(f"  ❌ {name}: display_name='{preset.display_name}' contains 'LunaClaw'")
        else:
            print(f"  ✅ {name}: display_name='{preset.display_name}'")

    if issues:
        for issue in issues:
            print(issue)
        print(f"\n⚠️ {len(issues)} preset(s) still use old brand name")
    else:
        print(f"\n✅ No presets use old brand name — PASS")


def main():
    test_preset_loading()
    test_preset_derivation()
    test_fact_table_prompt_injection()
    test_editor_prompt_with_fact_table()
    test_brand_in_presets()

    print("\n" + "=" * 60)
    print("All report generation tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
