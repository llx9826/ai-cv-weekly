"""LunaClaw Brief — Source 工厂（Registry 驱动）"""

# 导入所有 Source 模块以触发 @register_source 装饰器
import brief.sources.github      # noqa: F401
import brief.sources.arxiv       # noqa: F401
import brief.sources.hackernews  # noqa: F401
import brief.sources.paperswithcode  # noqa: F401
import brief.sources.finnews     # noqa: F401

from brief.sources.base import BaseSource
from brief.registry import SourceRegistry


def create_sources(names: list[str], global_config: dict) -> list[BaseSource]:
    """根据名称列表创建 Source 实例（从 Registry 查找）"""
    sources = []
    for name in names:
        if SourceRegistry.has(name):
            cls = SourceRegistry.get(name)
            sources.append(cls(global_config))
        else:
            print(f"[warn] Source '{name}' not registered. Available: {list(SourceRegistry.list_all().keys())}")
    return sources
