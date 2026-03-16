"""LunaClaw Brief — 金融资讯数据源

聚合 Hacker News 金融板块 + Finnhub 新闻 + 通用金融 RSS。
"""

import xml.etree.ElementTree as ET
import re
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("finnews")
class FinNewsSource(BaseSource):
    name = "finnews"

    HN_QUERIES = [
        "stock market OR investing OR fintech",
        "venture capital OR IPO OR fundraising",
        "cryptocurrency OR bitcoin OR DeFi",
        "interest rate OR federal reserve OR central bank",
        "earnings report OR revenue OR valuation",
    ]

    RSS_FEEDS = [
        ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business"),
        ("https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "NYT Business"),
    ]

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Hacker News 金融相关
            for query in self.HN_QUERIES:
                try:
                    url = (
                        f"https://hn.algolia.com/api/v1/search"
                        f"?query={query}&tags=story&numericFilters=points>10"
                    )
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        for story in data.get("hits", [])[:6]:
                            title = story.get("title", "")
                            if not title:
                                continue
                            story_url = story.get("url") or (
                                f"https://news.ycombinator.com/item?id={story.get('objectID', '')}"
                            )
                            items.append(Item(
                                title=title,
                                url=story_url,
                                source="finnews_hn",
                                raw_text="",
                                published_at=story.get("created_at", ""),
                                meta={
                                    "points": story.get("points", 0),
                                    "comments": story.get("num_comments", 0),
                                    "sub_source": "Hacker News",
                                },
                            ))
                except Exception:
                    continue

            # RSS 金融新闻
            for feed_url, source_label in self.RSS_FEEDS:
                try:
                    async with session.get(feed_url) as resp:
                        if resp.status != 200:
                            continue
                        xml_content = await resp.text()
                        items.extend(self._parse_rss(xml_content, source_label))
                except Exception:
                    continue

        # URL 去重
        seen: set[str] = set()
        unique: list[Item] = []
        for item in items:
            if item.url not in seen:
                seen.add(item.url)
                unique.append(item)
        return unique

    @staticmethod
    def _parse_rss(xml_content: str, source_label: str) -> list[Item]:
        items: list[Item] = []
        try:
            root = ET.fromstring(xml_content)
            for entry in root.findall(".//item")[:15]:
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
                    source="finnews_rss",
                    raw_text=desc_text,
                    published_at=pub_el.text if pub_el is not None else "",
                    meta={"sub_source": source_label},
                ))
        except Exception:
            pass
        return items
