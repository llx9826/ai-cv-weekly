"""LunaClaw Brief — 插件注册表

通过装饰器实现零配置的插件发现与注册。

用法:
    @register_source("github")
    class GitHubSource(BaseSource): ...

    source_cls = SourceRegistry.get("github")
"""

from __future__ import annotations

from typing import TypeVar, Callable

T = TypeVar("T")


class _Registry:
    """通用插件注册表"""

    def __init__(self, kind: str):
        self._kind = kind
        self._map: dict[str, type] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._map:
                raise ValueError(
                    f"[{self._kind}] '{name}' already registered "
                    f"({self._map[name].__name__}), cannot register {cls.__name__}"
                )
            self._map[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> type:
        if name not in self._map:
            raise KeyError(
                f"[{self._kind}] '{name}' not registered. "
                f"Available: {list(self._map.keys())}"
            )
        return self._map[name]

    def list_all(self) -> dict[str, type]:
        return dict(self._map)

    def has(self, name: str) -> bool:
        return name in self._map

    def __repr__(self) -> str:
        items = ", ".join(self._map.keys())
        return f"<{self._kind}Registry [{items}]>"


SourceRegistry = _Registry("Source")
EditorRegistry = _Registry("Editor")
RendererRegistry = _Registry("Renderer")

# 装饰器快捷方式
register_source = SourceRegistry.register
register_editor = EditorRegistry.register
register_renderer = RendererRegistry.register
