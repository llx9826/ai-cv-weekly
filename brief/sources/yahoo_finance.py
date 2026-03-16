"""LunaClaw Brief — Yahoo Finance RSS Data Source

Aggregates Yahoo Finance RSS feeds for market news, trending tickers,
and earnings calendar. Primarily US-market focused but includes global markets.
"""

import xml.etree.ElementTree as ET
import re
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("yahoo_finance")
class YahooFinanceSource(BaseSource):
    """Yahoo Finance RSS feed aggregator for market news and trending tickers."""

    name = "yahoo_finance"

    RSS_FEEDS = [
        ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance Top"),
        ("https://finance.yahoo.com/rss/topstories", "Yahoo Top Stories"),
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "S&P 500"),
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^IXIC&region=US&lang=en-US", "NASDAQ"),
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US", "Dow Jones"),
    ]

    HN_FINANCE_QUERIES = [
        "Yahoo Finance OR stock market OR Wall Street",
        "S&P 500 OR NASDAQ OR earnings report",
        "IPO OR treasury yield OR Federal Reserve",
    ]

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for feed_url, label in self.RSS_FEEDS:
                try:
                    async with session.get(feed_url) as resp:
                        if resp.status != 200:
                            continue
                        xml_text = await resp.text()
                        items.extend(self._parse_rss(xml_text, label))
                except Exception:
                    continue

            for query in self.HN_FINANCE_QUERIES:
                try:
                    url = (
                        f"https://hn.algolia.com/api/v1/search"
                        f"?query={query}&tags=story&numericFilters=points>15"
                    )
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        for story in data.get("hits", [])[:5]:
                            title = story.get("title", "")
                            if not title:
                                continue
                            story_url = story.get("url") or (
                                f"https://news.ycombinator.com/item?id={story.get('objectID', '')}"
                            )
                            items.append(Item(
                                title=title,
                                url=story_url,
                                source="yahoo_finance",
                                raw_text="",
                                published_at=story.get("created_at", ""),
                                meta={
                                    "points": story.get("points", 0),
                                    "comments": story.get("num_comments", 0),
                                    "sub_source": "HN Finance",
                                },
                            ))
                except Exception:
                    continue

        seen: set[str] = set()
        unique: list[Item] = []
        for item in items:
            if item.url and item.url not in seen:
                seen.add(item.url)
                unique.append(item)
        return unique

    @staticmethod
    def _parse_rss(xml_content: str, source_label: str) -> list[Item]:
        items: list[Item] = []
        try:
            root = ET.fromstring(xml_content)
            for entry in root.findall(".//item")[:12]:
                title_el = entry.find("title")
                link_el = entry.find("link")
                desc_el = entry.find("description")
                pub_el = entry.find("pubDate")
                if title_el is None or not title_el.text:
                    continue
                desc_text = ""
                if desc_el is not None and desc_el.text:
                    desc_text = re.sub(r"<[^>]+>", "", desc_el.text)[:300]
                items.append(Item(
                    title=title_el.text.strip(),
                    url=link_el.text.strip() if link_el is not None and link_el.text else "",
                    source="yahoo_finance",
                    raw_text=desc_text,
                    published_at=pub_el.text if pub_el is not None else "",
                    meta={"sub_source": source_label},
                ))
        except Exception:
            pass
        return items
