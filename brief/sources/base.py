"""LunaClaw Brief — Data source base class.

LunaClaw Brief — 数据源基类
"""

from abc import ABC, abstractmethod
from datetime import datetime

from brief.models import Item


class BaseSource(ABC):
    """所有数据源适配器的基类"""

    name: str = "unknown"

    def __init__(self, global_config: dict):
        self.global_config = global_config
        self.proxy = None
        proxy_cfg = global_config.get("proxy", {})
        if proxy_cfg.get("enabled"):
            self.proxy = proxy_cfg.get("http")

    @abstractmethod
    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        ...
