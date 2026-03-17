"""Data Source Connectivity Test

Tests all registered data sources (text + fact) for:
  - Network reachability
  - Non-empty response
  - Response time

Usage:
    python -m testcode.test_source_connectivity
    python -m testcode.test_source_connectivity --facts-only
    python -m testcode.test_source_connectivity --text-only
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta

from brief.sources import create_sources
from brief.facts import create_fact_sources, FactTable


_TEXT_SOURCES = [
    "github", "arxiv", "hackernews", "paperswithcode",
    "finnews", "yahoo_finance", "eastmoney", "xueqiu", "rss",
]

_FACT_SOURCES = [
    "sina_a_share", "sina_hk", "sina_us", "eastmoney_fact",
]


async def test_text_sources():
    """Test all text (Item) data sources for connectivity."""
    print("=" * 60)
    print("Text Source Connectivity Test")
    print("=" * 60)

    now = datetime.now()
    since = now - timedelta(days=1)
    sources = create_sources(_TEXT_SOURCES, {})

    results: list[tuple[str, bool, int, str]] = []

    for source in sources:
        t0 = time.monotonic()
        try:
            items = await source.fetch(since, now)
            elapsed = int((time.monotonic() - t0) * 1000)
            count = len(items) if items else 0
            ok = count > 0
            results.append((source.name, ok, elapsed, f"{count} items"))
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append((source.name, False, elapsed, str(e)[:60]))

    _print_results(results)
    return results


async def test_fact_sources():
    """Test all Fact (structured data) sources for connectivity."""
    print("=" * 60)
    print("Fact Source Connectivity Test")
    print("=" * 60)

    now = datetime.now()
    since = now - timedelta(days=1)
    sources = create_fact_sources(_FACT_SOURCES)

    results: list[tuple[str, bool, int, str]] = []

    for source in sources:
        t0 = time.monotonic()
        try:
            facts = await source.fetch_facts(since, now)
            elapsed = int((time.monotonic() - t0) * 1000)
            count = len(facts) if facts else 0
            ok = count > 0
            categories = set(f.category for f in facts) if facts else set()
            results.append((
                source.name, ok, elapsed,
                f"{count} facts, categories: {categories}" if ok else "0 facts"
            ))
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append((source.name, False, elapsed, str(e)[:60]))

    _print_results(results)
    return results


async def test_fact_table_assembly():
    """End-to-end test: assemble a FactTable from all fact sources."""
    print("=" * 60)
    print("Fact Table Assembly Test")
    print("=" * 60)

    now = datetime.now()
    since = now - timedelta(days=1)
    sources = create_fact_sources(_FACT_SOURCES)

    table = await FactTable.from_sources(sources, since, now)
    print(f"\nTotal facts: {len(table.facts)}")
    print(f"Categories: {table.categories()}")
    print(f"Is empty: {table.is_empty}")

    prompt = table.to_prompt()
    print(f"\nPrompt length: {len(prompt)} chars")
    print("\n--- Prompt Preview (first 1500 chars) ---")
    print(prompt[:1500])

    print("\n--- Fact Lookup Test ---")
    for key_prefix in ["sh000001", "rt_hkHSI", "gb_$dji", "northbound"]:
        for f in table.facts:
            if key_prefix in f.key:
                print(f"  lookup({f.key}) = {f.label}: {f.value}")
                break

    return table


def _print_results(results: list[tuple[str, bool, int, str]]):
    print(f"\n{'Source':<20} {'Status':<8} {'Time':>7}  {'Details'}")
    print("-" * 70)
    for name, ok, elapsed_ms, detail in results:
        status = "PASS" if ok else "FAIL"
        icon = "✅" if ok else "❌"
        print(f"{icon} {name:<18} {status:<8} {elapsed_ms:>5}ms  {detail}")

    passed = sum(1 for _, ok, _, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} sources passed\n")


async def main():
    args = set(sys.argv[1:])
    facts_only = "--facts-only" in args
    text_only = "--text-only" in args

    if not facts_only:
        await test_text_sources()
        print()

    if not text_only:
        await test_fact_sources()
        print()
        await test_fact_table_assembly()


if __name__ == "__main__":
    asyncio.run(main())
