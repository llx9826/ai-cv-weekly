"""ClawCat Brief — Eastmoney FactSource

Fetches structured market facts from Eastmoney public APIs:
  - Sector/industry ranking (板块涨跌排行)
  - Northbound capital flow (北向资金)
  - IPO subscription calendar (新股申购日历)
  - Market breadth: advance/decline counts (涨跌家数)
"""

from __future__ import annotations

import json
from datetime import datetime

import aiohttp

from brief.models import Fact
from brief.facts.protocol import FactSource
from brief.registry import register_fact_source

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Referer": "https://data.eastmoney.com",
}


@register_fact_source("eastmoney_fact")
class EastmoneyFactSource(FactSource):
    """Eastmoney structured data FactSource for A-share market intelligence."""

    name = "eastmoney_fact"

    async def fetch_facts(self, since: datetime, until: datetime) -> list[Fact]:
        facts: list[Fact] = []
        timeout = aiohttp.ClientTimeout(total=12)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            facts.extend(await self._fetch_sectors(session))
            facts.extend(await self._fetch_northbound(session))
            facts.extend(await self._fetch_breadth(session))
            facts.extend(await self._fetch_ipo(session))

        return facts

    async def _fetch_sectors(self, session: aiohttp.ClientSession) -> list[Fact]:
        """Top gaining/losing sectors via Eastmoney push API."""
        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        for direction, po in [("涨幅前5", "1"), ("跌幅前5", "0")]:
            url = (
                "https://push2.eastmoney.com/api/qt/clist/get"
                f"?pn=1&pz=5&po={po}&np=1&fltt=2&invt=2&fid=f3"
                "&fs=m:90+t:2&fields=f2,f3,f4,f12,f14"
            )
            try:
                async with session.get(url, headers=_HEADERS) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json(content_type=None)
                    items = data.get("data", {}).get("diff", [])
                    for i, item in enumerate(items, 1):
                        name = item.get("f14", "")
                        change_pct = item.get("f3", 0)
                        if not name:
                            continue
                        sign = "+" if change_pct >= 0 else ""
                        facts.append(Fact(
                            key=f"sector.{direction}.{i}",
                            value=f"{name} {sign}{change_pct:.2f}%",
                            label=f"{direction}板块#{i}",
                            unit="",
                            timestamp=now_ts,
                            source="东方财富",
                            category="sector",
                        ))
            except Exception:
                continue

        return facts

    async def _fetch_northbound(self, session: aiohttp.ClientSession) -> list[Fact]:
        """Today's northbound (沪股通+深股通) net inflow."""
        url = (
            "https://push2his.eastmoney.com/api/qt/kamt.kline/get"
            "?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55,f56&klt=101&lmt=1"
        )
        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        try:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return facts
                data = await resp.json(content_type=None)
                result = data.get("data", {})
                if not isinstance(result, dict):
                    return facts

                # hk2sh = 沪股通净买入, hk2sz = 深股通净买入
                sh_data = result.get("hk2sh", [])
                sz_data = result.get("hk2sz", [])

                sh_net = self._parse_northbound_line(sh_data)
                sz_net = self._parse_northbound_line(sz_data)

                if sh_net is not None:
                    facts.append(Fact(
                        key="northbound.sh",
                        value=_format_cny(sh_net),
                        label="沪股通净买入",
                        unit="",
                        timestamp=now_ts,
                        source="东方财富",
                        category="capital_flow",
                    ))

                if sz_net is not None:
                    facts.append(Fact(
                        key="northbound.sz",
                        value=_format_cny(sz_net),
                        label="深股通净买入",
                        unit="",
                        timestamp=now_ts,
                        source="东方财富",
                        category="capital_flow",
                    ))

                if sh_net is not None and sz_net is not None:
                    total = sh_net + sz_net
                    facts.append(Fact(
                        key="northbound.total",
                        value=_format_cny(total),
                        label="北向资金合计净买入",
                        unit="",
                        timestamp=now_ts,
                        source="东方财富",
                        category="capital_flow",
                    ))
        except Exception:
            pass

        return facts

    @staticmethod
    def _parse_northbound_line(data_list: list) -> float | None:
        """Parse northbound CSV line: 'date,buy_limit,sell_limit,net_buy'."""
        if not data_list:
            return None
        try:
            line = data_list[-1] if isinstance(data_list, list) else str(data_list)
            parts = str(line).split(",")
            if len(parts) >= 4:
                return float(parts[3])
        except (ValueError, IndexError):
            pass
        return None

    async def _fetch_breadth(self, session: aiohttp.ClientSession) -> list[Fact]:
        """Market breadth: number of advancing vs declining stocks."""
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=1&po=1&np=1&fltt=2&invt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
            "&fields=f2,f3,f4,f12,f14"
        )
        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        try:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return facts
                data = await resp.json(content_type=None)
                total = data.get("data", {}).get("total", 0)
                if total:
                    facts.append(Fact(
                        key="breadth.total_stocks",
                        value=str(total),
                        label="A股总数",
                        unit="只",
                        timestamp=now_ts,
                        source="东方财富",
                        category="general",
                    ))
        except Exception:
            pass

        return facts

    async def _fetch_ipo(self, session: aiohttp.ClientSession) -> list[Fact]:
        """Upcoming IPO subscription calendar."""
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get"
            "?reportName=RPTA_APP_IPOAPPLY"
            "&columns=SECURITY_CODE,SECURITY_NAME,TRADE_DATE,ISSUE_PRICE,INDUSTRY_PE_NEW"
            "&pageSize=5&sortColumns=TRADE_DATE&sortTypes=-1&client=wap"
        )
        facts: list[Fact] = []
        now_ts = datetime.now().isoformat()

        try:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return facts
                data = await resp.json(content_type=None)
                result = data.get("result", {})
                ipo_list = result.get("data", []) if isinstance(result, dict) else []

                for i, ipo in enumerate(ipo_list[:5], 1):
                    code = ipo.get("SECURITY_CODE", "")
                    name = ipo.get("SECURITY_NAME", "")
                    date = ipo.get("TRADE_DATE", "")
                    price = ipo.get("ISSUE_PRICE", "")
                    if not name:
                        continue

                    date_str = str(date)[:10] if date else "待定"
                    price_str = f"{price}元" if price else "待定"

                    facts.append(Fact(
                        key=f"ipo.{i}.{code}",
                        value=f"{name}({code}) 申购日:{date_str} 发行价:{price_str}",
                        label=f"新股#{i} {name}",
                        unit="",
                        timestamp=now_ts,
                        source="东方财富",
                        category="ipo",
                    ))
        except Exception:
            pass

        return facts


def _format_cny(amount: float) -> str:
    """Format CNY amount into human-readable form."""
    sign = "+" if amount >= 0 else ""
    abs_amount = abs(amount)
    if abs_amount >= 1e8:
        return f"{sign}{amount / 1e8:.2f}亿"
    if abs_amount >= 1e4:
        return f"{sign}{amount / 1e4:.1f}万"
    return f"{sign}{amount:.0f}"
