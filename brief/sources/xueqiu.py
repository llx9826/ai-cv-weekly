"""LunaClaw Brief — Xueqiu (雪球) Data Source

Aggregates trending discussions and hot stock mentions from Xueqiu community.
Useful for market sentiment analysis and retail investor pulse.

Since Xueqiu's web API requires auth, we use a combination of:
  - Xueqiu public RSS/trending endpoints
  - HN Algolia search for Xueqiu-adjacent Chinese market sentiment content
"""

import re
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("xueqiu")
class XueqiuSource(BaseSource):
    """Xueqiu (雪球) hot posts and sentiment data source."""

    name = "xueqiu"

    _HOT_URL = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json"
    _HOT_PARAMS = {
        "size": "15",
        "type": "12",  # 热门讨论
        "_type": "12",
    }

    _HN_QUERIES = [
        "China stock sentiment OR retail investor OR 散户",
        "Xueqiu OR 雪球 OR Chinese stock market",
        "A-share rally OR A-share crash OR 涨停 OR 跌停",
        "港股 OR 恒生 OR Hang Seng",
    ]

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            await self._fetch_hot_stocks(session, items)
            await self._fetch_hn_sentiment(session, items)

        seen: set[str] = set()
        unique: list[Item] = []
        for item in items:
            key = item.item_id
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    async def _fetch_hot_stocks(self, session: aiohttp.ClientSession, items: list[Item]):
        """Fetch hot stock discussions from Xueqiu."""
        try:
            # Need cookies from main page first
            async with session.get(
                "https://xueqiu.com/", headers=self._HEADERS
            ) as _:
                pass

            async with session.get(
                self._HOT_URL,
                params=self._HOT_PARAMS,
                headers=self._HEADERS,
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)
                stock_list = data.get("data", {}).get("items", [])
                for stock in stock_list[:15]:
                    code = stock.get("code", "")
                    name = stock.get("name", "")
                    current = stock.get("current", "")
                    percent = stock.get("percent", 0)
                    exchange = stock.get("exchange", "")

                    if not name:
                        continue

                    sign = "+" if percent and percent > 0 else ""
                    title = f"🔥 {name}({code}) {sign}{percent:.2f}%" if percent else f"🔥 {name}({code})"
                    raw = f"当前价：{current}，涨跌幅：{sign}{percent:.2f}%，交易所：{exchange}"

                    items.append(Item(
                        title=title,
                        url=f"https://xueqiu.com/S/{code}",
                        source="xueqiu",
                        raw_text=raw,
                        published_at=datetime.now().isoformat(),
                        meta={
                            "sub_source": "雪球热股",
                            "category": "hot_stock",
                            "percent_change": percent,
                            "price": str(current),
                        },
                    ))
        except Exception:
            pass

    async def _fetch_hn_sentiment(self, session: aiohttp.ClientSession, items: list[Item]):
        """Fallback: Chinese market sentiment via HN search."""
        for query in self._HN_QUERIES:
            try:
                url = (
                    f"https://hn.algolia.com/api/v1/search"
                    f"?query={query}&tags=story&numericFilters=points>5"
                )
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    for story in data.get("hits", [])[:4]:
                        title = story.get("title", "")
                        if not title:
                            continue
                        story_url = story.get("url") or (
                            f"https://news.ycombinator.com/item?id={story.get('objectID', '')}"
                        )
                        items.append(Item(
                            title=title,
                            url=story_url,
                            source="xueqiu",
                            raw_text="",
                            published_at=story.get("created_at", ""),
                            meta={
                                "points": story.get("points", 0),
                                "comments": story.get("num_comments", 0),
                                "sub_source": "HN Sentiment",
                                "category": "sentiment",
                            },
                        ))
            except Exception:
                continue
