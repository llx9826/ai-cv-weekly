"""LunaClaw Brief — Hacker News 数据源"""

from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("hackernews")
class HackerNewsSource(BaseSource):
    name = "hackernews"

    QUERIES = [
        "computer vision OR OCR OR multimodal OR vision model",
        "AI image detection segmentation",
        "LLM agent transformer",
    ]

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for query in self.QUERIES:
                try:
                    url = (
                        f"https://hn.algolia.com/api/v1/search"
                        f"?query={query}&tags=story&numericFilters=points>5"
                    )
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        for story in data.get("hits", [])[:8]:
                            title = story.get("title", "")
                            if not title:
                                continue
                            story_url = story.get("url") or (
                                f"https://news.ycombinator.com/item?id={story.get('objectID', '')}"
                            )
                            items.append(Item(
                                title=title,
                                url=story_url,
                                source="hackernews",
                                raw_text="",
                                published_at=story.get("created_at", ""),
                                meta={
                                    "points": story.get("points", 0),
                                    "comments": story.get("num_comments", 0),
                                },
                            ))
                except Exception as e:
                    print(f"[HN] {e}")
        return items
