"""LunaClaw Brief — 轻量缓存层

基于文件系统的 TTL 缓存，减少重复 API 调用。

用法:
    cache = FileCache(Path("data/cache"), ttl_seconds=3600)
    data = cache.get("github_search_cv")
    if data is None:
        data = await fetch_from_api()
        cache.set("github_search_cv", data)
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class FileCache:
    """基于文件的 TTL 缓存"""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.ttl = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Any | None:
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("_ts", 0) > self.ttl:
                path.unlink(missing_ok=True)
                return None
            return data.get("value")
        except (json.JSONDecodeError, IOError):
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: Any):
        path = self._key_path(key)
        data = {"_ts": time.time(), "value": value}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def invalidate(self, key: str):
        self._key_path(key).unlink(missing_ok=True)

    def clear(self):
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)

    def _key_path(self, key: str) -> Path:
        h = hashlib.md5(key.encode()).hexdigest()[:12]
        return self.cache_dir / f"{h}.json"
