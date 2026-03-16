"""LunaClaw Brief — Papers with Code 数据源"""

from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("paperswithcode")
class PapersWithCodeSource(BaseSource):
    name = "paperswithcode"

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                url = "https://paperswithcode.com/api/v1/papers/?ordering=-date&page=1&items_per_page=20"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return items
                    data = await resp.json()
                    for paper in data.get("results", []):
                        title = paper.get("title", "")
                        if not title:
                            continue
                        abstract = paper.get("abstract", "")
                        paper_url = paper.get("url_abs") or paper.get("url", "")
                        items.append(Item(
                            title=title,
                            url=paper_url,
                            source="paperswithcode",
                            raw_text=abstract[:500],
                            published_at=paper.get("date", ""),
                            meta={
                                "github_stars": paper.get("github_stars", 0),
                                "tasks": [t.get("name") for t in paper.get("tasks", [])],
                            },
                        ))
            except Exception as e:
                print(f"[PapersWithCode] {e}")
        return items
