"""LunaClaw Brief — Source Factory (Registry-driven)

All sources are discovered via @register_source decorator.
Import each module to trigger registration.
"""

import brief.sources.github          # noqa: F401
import brief.sources.arxiv           # noqa: F401
import brief.sources.hackernews      # noqa: F401
import brief.sources.paperswithcode  # noqa: F401
import brief.sources.finnews         # noqa: F401
import brief.sources.yahoo_finance   # noqa: F401
import brief.sources.eastmoney       # noqa: F401
import brief.sources.xueqiu          # noqa: F401

from brief.sources.base import BaseSource
from brief.registry import SourceRegistry


def create_sources(names: list[str], global_config: dict) -> list[BaseSource]:
    """Create Source instances by name from the Registry."""
    sources = []
    for name in names:
        if SourceRegistry.has(name):
            cls = SourceRegistry.get(name)
            sources.append(cls(global_config))
        else:
            print(f"[warn] Source '{name}' not registered. Available: {list(SourceRegistry.list_all().keys())}")
    return sources
