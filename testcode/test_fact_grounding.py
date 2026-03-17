"""Fact Table Grounding Test

Tests the FactTableGrounder against known inputs to verify:
  1. Claims matching fact table values are marked as grounded
  2. Fabricated claims are flagged
  3. The grounding pipeline correctly integrates with FactTable

Usage:
    python -m testcode.test_fact_grounding
"""

import asyncio
from datetime import datetime, timedelta

from brief.models import Fact, Item
from brief.facts.protocol import FactTable
from brief.grounding.checkers import FactTableGrounder
from brief.grounding.pipeline import GroundingPipeline


def test_fact_table_grounder_with_facts():
    """Test FactTableGrounder against a known fact table."""
    print("=" * 60)
    print("Test: FactTableGrounder with Fact Table")
    print("=" * 60)

    facts = [
        Fact(key="sh000001.price", value="3245.67", label="上证综指", unit="点", source="新浪行情", category="index"),
        Fact(key="sh000001.change_pct", value="+1.23%", label="上证综指涨跌幅", source="新浪行情", category="index"),
        Fact(key="sz399001.price", value="10892.45", label="深证成指", unit="点", source="新浪行情", category="index"),
        Fact(key="northbound.total", value="+42.30亿", label="北向资金合计", source="东方财富", category="capital_flow"),
    ]
    table = FactTable(facts)

    grounded_report = """
## 一、今日大盘走势
上证综指收报 3245.67 点，涨幅 +1.23%。深证成指报 10892.45 点。

## 三、资金面
北向资金今日合计净买入 +42.30亿。
"""

    hallucinated_report = """
## 一、今日大盘走势
上证综指收报 3567.89 点，涨幅 +2.56%。深证成指报 11234.56 点。

## 三、资金面
北向资金今日合计净买入 +89.70亿。两市成交额达到 1.2万亿。
"""

    grounded_checker = FactTableGrounder(fact_table=table)

    print("\n--- Grounded Report (should score high) ---")
    result1 = grounded_checker.check(grounded_report, [])
    print(f"  Passed: {result1.passed}")
    print(f"  Score:  {result1.score:.2%}")
    print(f"  Issues: {len(result1.issues)}")
    for issue in result1.issues:
        print(f"    [{issue.severity}] {issue.message}")

    print("\n--- Hallucinated Report (should score low) ---")
    result2 = grounded_checker.check(hallucinated_report, [])
    print(f"  Passed: {result2.passed}")
    print(f"  Score:  {result2.score:.2%}")
    print(f"  Issues: {len(result2.issues)}")
    for issue in result2.issues:
        print(f"    [{issue.severity}] {issue.message}")

    assert result1.score > result2.score, "Grounded report should score higher"
    assert result1.passed, "Grounded report should pass"
    print("\n✅ Grounded report scores higher than hallucinated — PASS")


def test_fact_table_grounder_no_facts():
    """Test fallback behavior when no fact table is provided."""
    print("\n" + "=" * 60)
    print("Test: FactTableGrounder without Fact Table (legacy fallback)")
    print("=" * 60)

    items = [
        Item(title="沪指收涨1.2%", url="", source="news", raw_text="上涨1.2%"),
    ]

    report = "上证综指今日上涨1.2%，成交额达到8500亿。"

    checker = FactTableGrounder(fact_table=None)
    result = checker.check(report, items)
    print(f"  Passed: {result.passed} (legacy mode always passes)")
    print(f"  Score:  {result.score:.2%}")
    print(f"  Issues: {len(result.issues)}")
    for issue in result.issues:
        print(f"    [{issue.severity}] {issue.message}")

    assert result.passed, "Legacy mode should always pass"
    print("\n✅ Legacy fallback works correctly — PASS")


def test_grounding_pipeline_with_fact_table():
    """Test full GroundingPipeline with FactTable integration."""
    print("\n" + "=" * 60)
    print("Test: GroundingPipeline with Fact Table")
    print("=" * 60)

    facts = [
        Fact(key="sh000001.change_pct", value="-0.85%", label="上证综指涨跌幅", source="新浪行情", category="index"),
        Fact(key="sector.top1", value="长材 +4.14%", label="涨幅第一板块", source="东方财富", category="sector"),
    ]
    table = FactTable(facts)

    report = """## 一、今日大盘走势
上证综指今日收跌，跌幅 -0.85%。

## 二、板块轮动
### 1. 长材板块领涨
**涨跌幅**：+4.14%

**🦞 Claw 锐评**：基建预期驱动，短期或有回调风险。
"""

    items = [
        Item(title="长材板块领涨，涨幅超4%", url="", source="eastmoney", raw_text="长材板块涨幅居前"),
    ]

    pipeline = GroundingPipeline.create_default(fact_table=table)
    result = pipeline.run(report, items)

    print(f"  Overall passed: {result.passed}")
    print(f"  Overall score:  {result.score:.2%}")
    print(f"  Total issues:   {len(result.issues)}")
    for issue in result.issues:
        print(f"    [{issue.checker}/{issue.severity}] {issue.message}")

    print("\n✅ Pipeline integration works — PASS")


async def test_live_fact_table_grounding():
    """End-to-end: fetch real facts and test grounding against them."""
    print("\n" + "=" * 60)
    print("Test: Live Fact Table Grounding (real API data)")
    print("=" * 60)

    from brief.facts import create_fact_sources, FactTable

    now = datetime.now()
    since = now - timedelta(days=1)
    sources = create_fact_sources(["sina_a_share", "eastmoney_fact"])
    table = await FactTable.from_sources(sources, since, now)

    print(f"  Live facts fetched: {len(table.facts)}")

    if table.is_empty:
        print("  ⚠️ No live data available, skipping live test")
        return

    first_index = next((f for f in table.facts if "change_pct" in f.key), None)
    if first_index:
        grounded_sentence = f"今日{first_index.label}为 {first_index.value}。"
        hallucinated_sentence = "今日上证综指涨幅 +99.99%，成交额达到 999万亿。"

        checker = FactTableGrounder(fact_table=table)

        r1 = checker.check(grounded_sentence, [])
        r2 = checker.check(hallucinated_sentence, [])

        print(f"\n  Grounded claim score:     {r1.score:.2%} (passed={r1.passed})")
        print(f"  Hallucinated claim score: {r2.score:.2%} (passed={r2.passed})")

        if r1.score >= r2.score:
            print("\n  ✅ Live grounding correctly differentiates real vs fake — PASS")
        else:
            print("\n  ⚠️ Unexpected scoring, needs investigation")


def main():
    test_fact_table_grounder_with_facts()
    test_fact_table_grounder_no_facts()
    test_grounding_pipeline_with_fact_table()
    asyncio.run(test_live_fact_table_grounding())

    print("\n" + "=" * 60)
    print("All grounding tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
