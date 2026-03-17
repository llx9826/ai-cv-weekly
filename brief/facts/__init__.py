"""ClawCat Brief — Fact Table subsystem (Deterministic Fact Injection).

Inspired by VeNRA's Universal Fact Ledger, the Fact Table architecture
separates structured market data from free-text news, injecting verified
numbers into LLM prompts and validating output claims against them.

Modules:
    protocol    — FactSource ABC + FactTable container
    sina        — Sina Finance real-time quotes (A/HK/US indices + stocks)
    eastmoney   — Eastmoney structured data (sector, capital flow, IPO)
"""

from brief.facts.protocol import FactSource, FactTable
from brief.registry import FactSourceRegistry

# Side-effect imports: trigger @register_fact_source decorators
import brief.facts.sina  # noqa: F401
import brief.facts.eastmoney_fact  # noqa: F401

_ALIAS_CONFIG: dict[str, tuple[str, dict]] = {
    "sina_a_share": ("sina_market", {"markets": ["a_share"]}),
    "sina_hk": ("sina_market", {"markets": ["hk"]}),
    "sina_us": ("sina_market", {"markets": ["us"]}),
    "sina_all": ("sina_market", {"markets": ["a_share", "hk", "us"]}),
    "eastmoney_fact": ("eastmoney_fact", {}),
}


def create_fact_sources(
    names: list[str], global_config: dict | None = None
) -> list[FactSource]:
    """Create FactSource instances by name using the unified registry.

    Names can be either direct registry keys (e.g. "eastmoney_fact")
    or convenience aliases (e.g. "sina_a_share" → SinaFactSource(markets=["a_share"])).
    """
    cfg = global_config or {}
    sources: list[FactSource] = []

    for name in names:
        if name in _ALIAS_CONFIG:
            reg_name, kwargs = _ALIAS_CONFIG[name]
            cls = FactSourceRegistry.get(reg_name)
            sources.append(cls(cfg, **kwargs))
        elif FactSourceRegistry.has(name):
            cls = FactSourceRegistry.get(name)
            sources.append(cls(cfg))
        else:
            avail = list(FactSourceRegistry.list_all().keys()) + list(_ALIAS_CONFIG.keys())
            print(f"[warn] Unknown fact source: '{name}'. Available: {sorted(set(avail))}")

    return sources


__all__ = ["FactSource", "FactTable", "create_fact_sources", "FactSourceRegistry"]
