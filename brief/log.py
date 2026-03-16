"""LunaClaw Brief — 结构化日志

轻量级结构化日志，支持上下文绑定和阶段跟踪。
避免引入外部依赖（structlog 等），用 dataclass + JSON 实现。

用法:
    log = BriefLogger("pipeline")
    log.info("开始抓取", source="github", count=42)
    log.phase("fetch").info("完成", items=73)
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TextIO

_LEVEL_COLORS = {
    "DEBUG": "\033[90m",
    "INFO": "\033[36m",
    "WARN": "\033[33m",
    "ERROR": "\033[31m",
}
_RESET = "\033[0m"


@dataclass
class LogEntry:
    ts: str
    level: str
    module: str
    msg: str
    data: dict = field(default_factory=dict)


class BriefLogger:
    """结构化日志器"""

    def __init__(self, module: str, stream: TextIO | None = None):
        self._module = module
        self._stream = stream or sys.stderr
        self._context: dict[str, Any] = {}

    def bind(self, **kwargs) -> BriefLogger:
        new = BriefLogger(self._module, self._stream)
        new._context = {**self._context, **kwargs}
        return new

    def phase(self, name: str) -> BriefLogger:
        return self.bind(phase=name)

    def debug(self, msg: str, **kwargs):
        self._emit("DEBUG", msg, kwargs)

    def info(self, msg: str, **kwargs):
        self._emit("INFO", msg, kwargs)

    def warn(self, msg: str, **kwargs):
        self._emit("WARN", msg, kwargs)

    def error(self, msg: str, **kwargs):
        self._emit("ERROR", msg, kwargs)

    def _emit(self, level: str, msg: str, extra: dict):
        data = {**self._context, **extra}
        entry = LogEntry(
            ts=datetime.now().strftime("%H:%M:%S.%f")[:-3],
            level=level,
            module=self._module,
            msg=msg,
            data=data,
        )

        color = _LEVEL_COLORS.get(level, "")
        data_str = " ".join(f"{k}={v}" for k, v in data.items()) if data else ""
        line = f"{color}[{entry.ts}] {entry.level:5s}{_RESET} {entry.module}: {msg}"
        if data_str:
            line += f"  {_LEVEL_COLORS.get('DEBUG', '')}{data_str}{_RESET}"
        print(line, file=self._stream)
