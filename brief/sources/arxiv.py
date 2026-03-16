"""LunaClaw Brief — arXiv 数据源"""

import xml.etree.ElementTree as ET
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("arxiv")
class ArxivSource(BaseSource):
    name = "arxiv"

    QUERIES = [
        "search_query=cat:cs.CV&sortBy=submittedDate&sortOrder=descending&max_results=15",
        "search_query=cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=10",
    ]

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for query in self.QUERIES:
                try:
                    url = f"http://export.arxiv.org/api/query?{query}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            xml_content = await resp.text()
                            items.extend(self._parse_atom(xml_content))
                except Exception as e:
                    print(f"[arXiv] {e}")
        return items

    @staticmethod
    def _parse_atom(xml_content: str) -> list[Item]:
        items: list[Item] = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                id_el = entry.find("atom:id", ns)
                published_el = entry.find("atom:published", ns)
                if title_el is None or not title_el.text:
                    continue
                title = " ".join(title_el.text.strip().split())
                summary = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
                url = id_el.text.strip() if id_el is not None and id_el.text else ""
                published = published_el.text if published_el is not None else ""
                arxiv_id = url.split("/abs/")[-1] if "/abs/" in url else ""
                categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]
                items.append(Item(
                    title=title,
                    url=url,
                    source="arxiv",
                    raw_text=summary[:500],
                    published_at=published,
                    meta={"arxiv_id": arxiv_id, "categories": categories},
                ))
        except Exception as e:
            print(f"[arXiv] XML parse error: {e}")
        return items
