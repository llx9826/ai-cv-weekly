"""ClawCat Brief — Generic RSS Source Adapter

Configurable RSS feed aggregator that reads feed URLs from config.yaml.
Supports any standard RSS 2.0 / Atom feed.

Config example:
    sources_config:
      rss:
        feeds:
          - url: "https://feeds.bbci.co.uk/news/business/rss.xml"
            label: "BBC Business"
          - url: "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
            label: "NYT Tech"

Generic RSS 数据源适配器：从 config.yaml 读取 RSS 订阅列表，支持任意 RSS/Atom 格式。
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source

_DEFAULT_FEEDS: list[dict] = [
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "label": "Ars Technica"},
    {"url": "https://www.wired.com/feed/rss", "label": "Wired"},
    {"url": "https://techcrunch.com/feed/", "label": "TechCrunch"},
    {"url": "https://www.theverge.com/rss/index.xml", "label": "The Verge"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "label": "NYT Tech"},
]

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@register_source("rss")
class RSSSource(BaseSource):
    """Generic RSS/Atom feed aggregator (通用 RSS/Atom 数据源)."""

    name = "rss"

    def __init__(self, global_config: dict):
        super().__init__(global_config)
        rss_cfg = global_config.get("sources_config", {}).get("rss", {})
        self._feeds: list[dict] = rss_cfg.get("feeds", _DEFAULT_FEEDS)
        self._max_per_feed: int = rss_cfg.get("max_per_feed", 10)

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for feed_cfg in self._feeds:
                url = feed_cfg.get("url", "")
                label = feed_cfg.get("label", url[:40])
                if not url:
                    continue
                try:
                    async with session.get(url, proxy=self.proxy) as resp:
                        if resp.status != 200:
                            continue
                        xml_text = await resp.text()
                        parsed = self._parse_feed(xml_text, label)
                        items.extend(parsed[:self._max_per_feed])
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
    def _parse_feed(xml_text: str, label: str) -> list[Item]:
        """Parse RSS 2.0 or Atom feed into Items."""
        items: list[Item] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items

        # RSS 2.0
        for entry in root.findall(".//item"):
            title = _text(entry, "title")
            link = _text(entry, "link")
            desc = re.sub(r"<[^>]+>", "", _text(entry, "description"))[:400]
            pub = _text(entry, "pubDate")
            if title:
                items.append(Item(
                    title=title.strip(),
                    url=link.strip(),
                    source="rss",
                    raw_text=desc.strip(),
                    published_at=pub,
                    meta={"sub_source": label},
                ))

        # Atom
        for entry in root.findall(".//atom:entry", _ATOM_NS):
            title = _text_ns(entry, "atom:title")
            link_el = entry.find("atom:link", _ATOM_NS)
            link = link_el.get("href", "") if link_el is not None else ""
            summary = re.sub(r"<[^>]+>", "", _text_ns(entry, "atom:summary"))[:400]
            updated = _text_ns(entry, "atom:updated") or _text_ns(entry, "atom:published")
            if title:
                items.append(Item(
                    title=title.strip(),
                    url=link.strip(),
                    source="rss",
                    raw_text=summary.strip(),
                    published_at=updated,
                    meta={"sub_source": label},
                ))

        return items


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return child.text or "" if child is not None else ""


def _text_ns(el: ET.Element, tag: str) -> str:
    child = el.find(tag, _ATOM_NS)
    return child.text or "" if child is not None else ""
