"""ClawCat Brief — Sina Finance FactSource

Fetches real-time market data from Sina Finance public API (hq.sinajs.cn).
Returns structured Fact objects for A-share, HK, and US market indices
and hot individual stocks.

API format (GBK encoded, CSV-like):
  var hq_str_sh000001="上证指数,open,prev_close,price,high,low,...成交量,成交额,..."
  var hq_str_rt_hkHSI="HSI,恒生指数,prev_close,open,high,low,price,change,change_pct,..."
  var hq_str_gb_$dji="道琼斯,price,change_pct,datetime,change,open,high,low,..."
"""

from __future__ import annotations

import re
from datetime import datetime

import aiohttp

from brief.models import Fact
from brief.facts.protocol import FactSource
from brief.registry import register_fact_source

_SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

_A_SHARE_INDICES = {
    "sh000001": ("上证综指", "index"),
    "sz399001": ("深证成指", "index"),
    "sz399006": ("创业板指", "index"),
    "sh000300": ("沪深300", "index"),
    "sh000905": ("中证500", "index"),
}

_HK_INDICES = {
    "rt_hkHSI": ("恒生指数", "index"),
    "rt_hkHSCEI": ("恒生国企指数", "index"),
    "rt_hkHSTECH": ("恒生科技指数", "index"),
}

_US_INDICES = {
    "gb_$dji": ("道琼斯", "index"),
    "gb_$ixic": ("纳斯达克", "index"),
    "gb_$inx": ("标普500", "index"),
}

_HOT_A_STOCKS = [
    "sh600519", "sz000858", "sh601318", "sz300750", "sh600036",
    "sh601899", "sz002594", "sh600900", "sz000001", "sh601012",
]


@register_fact_source("sina_market")
class SinaFactSource(FactSource):
    """Sina Finance real-time quote FactSource for A/HK/US markets."""

    name = "sina_market"

    def __init__(self, global_config: dict | None = None, markets: list[str] | None = None):
        super().__init__(global_config)
        self._markets = markets or ["a_share"]

    async def fetch_facts(self, since: datetime, until: datetime) -> list[Fact]:
        facts: list[Fact] = []
        timeout = aiohttp.ClientTimeout(total=12)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if "a_share" in self._markets:
                codes = list(_A_SHARE_INDICES.keys()) + _HOT_A_STOCKS
                facts.extend(await self._fetch_a_share(session, codes))

            if "hk" in self._markets:
                codes = list(_HK_INDICES.keys())
                facts.extend(await self._fetch_hk(session, codes))

            if "us" in self._markets:
                codes = list(_US_INDICES.keys())
                facts.extend(await self._fetch_us(session, codes))

        return facts

    async def _fetch_a_share(
        self, session: aiohttp.ClientSession, codes: list[str]
    ) -> list[Fact]:
        """Parse A-share data: name,open,prev_close,price,high,low,...vol,amount,..."""
        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        raw = await self._get(session, url)
        if not raw:
            return []

        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        for line in raw.strip().split("\n"):
            m = re.match(r'var hq_str_(\w+)="(.+)"', line.strip())
            if not m:
                continue
            code = m.group(1)
            fields = m.group(2).split(",")
            if len(fields) < 9:
                continue

            name = fields[0]
            try:
                price = float(fields[3])
                prev_close = float(fields[2])
            except (ValueError, IndexError):
                continue

            if prev_close == 0:
                continue

            change = price - prev_close
            change_pct = (change / prev_close) * 100
            sign = "+" if change >= 0 else ""

            meta = _A_SHARE_INDICES.get(code)
            is_index = meta is not None
            label = meta[0] if meta else name
            category = "index" if is_index else "stock"

            facts.append(Fact(
                key=f"{code}.price",
                value=f"{price:.2f}",
                label=f"{label}",
                unit="点" if is_index else "元",
                timestamp=now_ts,
                source="新浪行情",
                category=category,
            ))
            facts.append(Fact(
                key=f"{code}.change_pct",
                value=f"{sign}{change_pct:.2f}%",
                label=f"{label}涨跌幅",
                unit="",
                timestamp=now_ts,
                source="新浪行情",
                category=category,
            ))
            facts.append(Fact(
                key=f"{code}.change",
                value=f"{sign}{change:.2f}",
                label=f"{label}涨跌",
                unit="点" if is_index else "元",
                timestamp=now_ts,
                source="新浪行情",
                category=category,
            ))

            try:
                volume = int(fields[8])
                amount = float(fields[9])
                if is_index:
                    facts.append(Fact(
                        key=f"{code}.amount",
                        value=_format_amount(amount),
                        label=f"{label}成交额",
                        unit="",
                        timestamp=now_ts,
                        source="新浪行情",
                        category=category,
                    ))
            except (ValueError, IndexError):
                pass

        return facts

    async def _fetch_hk(
        self, session: aiohttp.ClientSession, codes: list[str]
    ) -> list[Fact]:
        """Parse HK data: symbol,name,prev_close,open,high,low,price,change,change_pct,..."""
        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        raw = await self._get(session, url)
        if not raw:
            return []

        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        for line in raw.strip().split("\n"):
            m = re.match(r'var hq_str_(\w+)="(.+)"', line.strip())
            if not m:
                continue
            code = m.group(1)
            fields = m.group(2).split(",")
            if len(fields) < 9:
                continue

            meta = _HK_INDICES.get(code)
            label = meta[0] if meta else fields[1] if len(fields) > 1 else code

            try:
                price = float(fields[6])
                change = float(fields[7])
                change_pct = float(fields[8])
            except (ValueError, IndexError):
                continue

            sign = "+" if change >= 0 else ""

            facts.append(Fact(
                key=f"{code}.price",
                value=f"{price:.2f}",
                label=label,
                unit="点",
                timestamp=now_ts,
                source="新浪行情",
                category="index",
            ))
            facts.append(Fact(
                key=f"{code}.change_pct",
                value=f"{sign}{change_pct:.2f}%",
                label=f"{label}涨跌幅",
                unit="",
                timestamp=now_ts,
                source="新浪行情",
                category="index",
            ))

        return facts

    async def _fetch_us(
        self, session: aiohttp.ClientSession, codes: list[str]
    ) -> list[Fact]:
        """Parse US data: name,price,change_pct,datetime,change,open,high,low,..."""
        url = f"https://hq.sinajs.cn/list={','.join(codes)}"
        raw = await self._get(session, url)
        if not raw:
            return []

        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        for line in raw.strip().split("\n"):
            m = re.match(r'var hq_str_([^=]+)="(.+)"', line.strip())
            if not m:
                continue
            code = m.group(1)
            fields = m.group(2).split(",")
            if len(fields) < 5:
                continue

            meta = _US_INDICES.get(code)
            label = meta[0] if meta else fields[0]

            try:
                price = float(fields[1])
                change_pct = float(fields[2])
                change = float(fields[4])
            except (ValueError, IndexError):
                continue

            sign = "+" if change >= 0 else ""

            facts.append(Fact(
                key=f"{code}.price",
                value=f"{price:.2f}",
                label=label,
                unit="点",
                timestamp=now_ts,
                source="新浪行情",
                category="index",
            ))
            facts.append(Fact(
                key=f"{code}.change_pct",
                value=f"{sign}{change_pct:.2f}%",
                label=f"{label}涨跌幅",
                unit="",
                timestamp=now_ts,
                source="新浪行情",
                category="index",
            ))

        return facts

    async def _get(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            async with session.get(url, headers=_SINA_HEADERS) as resp:
                if resp.status != 200:
                    return ""
                raw_bytes = await resp.read()
                return raw_bytes.decode("gbk", errors="replace")
        except Exception:
            return ""


def _format_amount(amount: float) -> str:
    """Format CNY amount into human-readable form (亿/万)."""
    if amount >= 1e8:
        return f"{amount / 1e8:.1f}亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.1f}万"
    return f"{amount:.0f}"
