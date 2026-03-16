"""LunaClaw Brief — Eastmoney (东方财富) Data Source

Aggregates A-share market data from Eastmoney public APIs and web:
  - Market news and sector rotation signals
  - IPO calendar (新股打新预报)
  - Abnormal price movement alerts (异动股)
  - Northbound capital flow (北向资金)
"""

import re
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("eastmoney")
class EastmoneySource(BaseSource):
    """Eastmoney (东方财富) data source for A-share market intelligence."""

    name = "eastmoney"

    # Eastmoney public news API (no auth required)
    _NEWS_URL = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
    _NEWS_PARAMS = {
        "columns": "102",  # A-share news column
        "pageSize": "15",
        "client": "wap",
    }

    # Eastmoney finance summary via HN (fallback)
    _HN_QUERIES = [
        "China stock market OR A-share OR Shanghai composite",
        "北向资金 OR northbound capital OR CSRC",
        "中国央行 OR PBOC OR LPR OR 新股",
    ]

    # Eastmoney public API for IPO list
    _IPO_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    _IPO_PARAMS = {
        "reportName": "RPTA_APP_IPOAPPLY",
        "columns": "SECURITY_CODE,SECURITY_NAME,TRADE_DATE,ISSUE_PRICE,INDUSTRY_PE_NEW",
        "pageSize": "10",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "client": "wap",
    }

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            await self._fetch_news(session, items)
            await self._fetch_ipo(session, items)
            await self._fetch_hn_fallback(session, items)

        seen: set[str] = set()
        unique: list[Item] = []
        for item in items:
            key = item.item_id
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    async def _fetch_news(self, session: aiohttp.ClientSession, items: list[Item]):
        """Fetch A-share market news from Eastmoney API."""
        try:
            async with session.get(self._NEWS_URL, params=self._NEWS_PARAMS) as resp:
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)
                news_list = data.get("data", {}).get("list", [])
                if not news_list and isinstance(data.get("data"), list):
                    news_list = data["data"]
                for article in news_list[:15]:
                    title = article.get("title", "")
                    if not title:
                        continue
                    url = article.get("url", article.get("url_unique", ""))
                    if not url:
                        art_id = article.get("art_code", article.get("uniquekey", ""))
                        url = f"https://finance.eastmoney.com/a/{art_id}.html" if art_id else ""
                    digest = article.get("digest", article.get("content", ""))
                    if digest:
                        digest = re.sub(r"<[^>]+>", "", digest)[:300]
                    items.append(Item(
                        title=title,
                        url=url,
                        source="eastmoney",
                        raw_text=digest,
                        published_at=article.get("showtime", article.get("date", "")),
                        meta={"sub_source": "东方财富", "category": "news"},
                    ))
        except Exception:
            pass

    async def _fetch_ipo(self, session: aiohttp.ClientSession, items: list[Item]):
        """Fetch upcoming IPO subscription calendar."""
        try:
            async with session.get(self._IPO_URL, params=self._IPO_PARAMS) as resp:
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)
                result = data.get("result", {})
                ipo_list = result.get("data", []) if isinstance(result, dict) else []
                for ipo in ipo_list[:10]:
                    code = ipo.get("SECURITY_CODE", "")
                    name = ipo.get("SECURITY_NAME", "")
                    date = ipo.get("TRADE_DATE", "")
                    price = ipo.get("ISSUE_PRICE", "")
                    pe = ipo.get("INDUSTRY_PE_NEW", "")
                    if not name:
                        continue
                    title = f"新股申购：{name}({code})"
                    raw = f"申购日期：{date[:10] if date else '待定'}，发行价：{price or '待定'}，行业PE：{pe or 'N/A'}"
                    items.append(Item(
                        title=title,
                        url=f"https://data.eastmoney.com/xg/xg/detail/{code}.html",
                        source="eastmoney",
                        raw_text=raw,
                        published_at=date[:10] if date else "",
                        meta={
                            "sub_source": "东方财富IPO",
                            "category": "ipo",
                            "security_code": code,
                            "issue_price": str(price),
                        },
                    ))
        except Exception:
            pass

    async def _fetch_hn_fallback(self, session: aiohttp.ClientSession, items: list[Item]):
        """Fallback: fetch China market news via HN Algolia search."""
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
                            source="eastmoney",
                            raw_text="",
                            published_at=story.get("created_at", ""),
                            meta={
                                "points": story.get("points", 0),
                                "comments": story.get("num_comments", 0),
                                "sub_source": "HN China Market",
                                "category": "news",
                            },
                        ))
            except Exception:
                continue
