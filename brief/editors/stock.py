"""ClawCat Brief — Stock Market Editors (A-Share / HK / US)

Three specialized editors for regional stock market daily briefs,
using the unified Markdown Schema and compact 3-chapter structure.
"""

from datetime import datetime

from brief.models import Item, PresetConfig
from brief.editors.base import BaseEditor
from brief.registry import register_editor

_SCHEMA_RULES = """【Markdown Schema — 必须严格遵守】
- `## 章节标题` 划分章节
- `### N. 条目标题` 每个条目用三级标题，N 为阿拉伯数字序号
- `**标签**：内容` 结构化字段（如"**涨跌幅**：+3.2%"）
- `**🦞 Claw 锐评**：` 锐评段落，独占一行
- `- item` 无序列表
- 禁止使用 `*   ` 星号列表代替 ### 标题
- 输出纯 Markdown，不要用 ```markdown 包裹"""

_COMMON_PRINCIPLES = """【核心原则】
1. 基于事实，不编造数据
2. 给出明确方向性判断，不骑墙
3. 风险提示必须具体
4. 禁止空话："值得关注""具有重要意义"
5. 金融术语保持行业惯例（P/E、EPS、YoY 等不翻译）

【事实约束（Fact Table Grounding）】
- 所有具体数值（指数点位、涨跌幅、成交额、资金流、股价）必须来自「事实数据表」
- 若某项数据不在事实数据表中，写「暂无实时数据」或省略该数据点
- 严禁编造任何具体数字，包括百分比、金额、点位
- 可以基于事实数据做定性判断（如"放量上涨""缩量调整"），但定量数据必须有据

【写作风格】
- 像给机构客户写盘前/盘后简报
- 有立场、有判断、有风险提示
- 🦞 Claw 锐评要犀利，说清多空逻辑

【Claw 锐评格式】
在每条事件后用独立段落：
**🦞 Claw 锐评**：一句话投资判断 + 上行催化 / 下行风险"""


def _build_item_block(items: list[Item], max_items: int = 10) -> str:
    lines: list[str] = []
    for i, item in enumerate(items[:max_items], 1):
        sub = item.meta.get("sub_source", item.source)
        pts = item.meta.get("points", 0)
        pts_str = f" ({pts}pts)" if pts else ""
        raw = item.raw_text[:250] if item.raw_text else ""
        lines.append(f"{i}. **{item.title}**{pts_str}\n   来源：{sub} | {item.url}\n   {raw}\n")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# A-Share (A股) Editor — 3 chapters
# ──────────────────────────────────────────────

@register_editor("stock_a")
class AShareEditor(BaseEditor):
    """A-share (沪深) market daily brief editor — compact 3-chapter format."""

    def _build_system_prompt(self) -> str:
        word_lo, word_hi = self.preset.target_word_count
        return f"""你是 {self.brand_name} 的 A 股研究主编，拥有 10 年国内证券研究经验。
你的读者是 A 股散户投资者与私募基金经理。

{_COMMON_PRINCIPLES}

{_SCHEMA_RULES}

【日报结构 — 严格 3 个章节，不可多不可少】

## 一、今日大盘与资金
- 用 `- ` 列出上证指数、深证成指、创业板指涨跌幅、成交额
- 北向资金净流入/流出金额、涨跌家数
- 2-3 条方向性判断，每条含 **判断**：和 **依据**：字段

## 二、板块热点与异动
- 3-4 条热点，每条用 `### N. 标题`
- **涨跌幅**：具体百分比  **驱动因素**：简要分析
- **代表个股**：列出 1-2 只代表股及涨跌幅
- **🦞 Claw 锐评**：一句话多空判断
- 末尾可附 1-2 条异动股提醒（涨跌幅超 7%），简要说明原因

## 三、🦞 Claw 策略与风险
- 短期仓位方向建议（2-3 句话）
- 本周需关注的风险事件
- "本简报仅供参考，不构成投资建议。"

{ self._engagement_rules(getattr(self.preset, 'target_audience', '')) }

【字数要求】严格控制 {word_lo}-{word_hi} 字，3 个章节缺一不可。宁可精炼也不要凑字。"""

    def _build_user_prompt(self, items: list[Item], issue_label: str, user_hint: str) -> str:
        today = self._today_context()
        prompt = f"请生成 {issue_label} 期 {self.preset.display_name}。\n\n"
        prompt += f"**日期**: {today}\n**素材数**: {len(items)} 条\n"
        if user_hint:
            prompt += f"**用户提示**: {user_hint}\n"
        prompt += f"\n**今日 A 股相关资讯**:\n\n{_build_item_block(items)}\n"
        word_lo, word_hi = self.preset.target_word_count
        prompt += f"\n【要求】3 个章节完整，{word_lo}-{word_hi} 字，每条用 ### N. 格式并带 Claw 锐评。精炼为主，不要凑字。\n\n请生成 A 股日报："
        return prompt


# ──────────────────────────────────────────────
# HK Stock (港股) Editor — 3 chapters
# ──────────────────────────────────────────────

@register_editor("stock_hk")
class HKStockEditor(BaseEditor):
    """Hong Kong stock market daily brief editor — compact 3-chapter format."""

    def _build_system_prompt(self) -> str:
        word_lo, word_hi = self.preset.target_word_count
        return f"""你是 {self.brand_name} 的港股研究主编，熟悉 HKEX 上市规则和南向/北向资金流。
你的读者是关注港股的机构交易员和高净值投资者。

{_COMMON_PRINCIPLES}

{_SCHEMA_RULES}

【日报结构 — 严格 3 个章节，不可多不可少】

## 一、今日港股大盘与资金
- 用 `- ` 列出恒生指数、恒生科技、国企指数涨跌幅
- 成交额、南向资金净流入/流出
- 2-3 条方向性判断，每条含 **判断**：和 **依据**：字段

## 二、板块热点与异动
- 3-4 条热点（中概股/科技巨头/生物医药），每条用 `### N. 标题`
- **涨跌幅**：具体百分比  **驱动因素**：事件分析
- **代表个股**：1-2 只代表股及涨跌
- **🦞 Claw 锐评**：一句话多空判断
- 末尾可附异动股提醒

## 三、🦞 Claw 策略与风险
- AH 溢价与跨市场联动关键信号
- 短期方向建议（2-3 句话）
- "本简报仅供参考，不构成投资建议。"

{ self._engagement_rules(getattr(self.preset, 'target_audience', '')) }

【字数要求】严格控制 {word_lo}-{word_hi} 字，3 个章节缺一不可。宁可精炼也不要凑字。"""

    def _build_user_prompt(self, items: list[Item], issue_label: str, user_hint: str) -> str:
        today = self._today_context()
        prompt = f"请生成 {issue_label} 期 {self.preset.display_name}。\n\n"
        prompt += f"**日期**: {today}\n**素材数**: {len(items)} 条\n"
        if user_hint:
            prompt += f"**用户提示**: {user_hint}\n"
        prompt += f"\n**今日港股相关资讯**:\n\n{_build_item_block(items)}\n"
        word_lo, word_hi = self.preset.target_word_count
        prompt += f"\n【要求】3 个章节完整，{word_lo}-{word_hi} 字，每条用 ### N. 格式并带 Claw 锐评。精炼为主，不要凑字。\n\n请生成港股日报："
        return prompt


# ──────────────────────────────────────────────
# US Stock (美股) Editor — 3 chapters
# ──────────────────────────────────────────────

@register_editor("stock_us")
class USStockEditor(BaseEditor):
    """US stock market daily brief editor — compact 3-chapter format."""

    def _build_system_prompt(self) -> str:
        word_lo, word_hi = self.preset.target_word_count
        return f"""你是 {self.brand_name} 的美股研究主编，拥有华尔街买方研究背景。
你的读者是关注美股的机构投资者和跨境投资者。

{_COMMON_PRINCIPLES}

{_SCHEMA_RULES}

【日报结构 — 严格 3 个章节，不可多不可少】

## 一、今日美股大盘与宏观
- 用 `- ` 列出 S&P 500、NASDAQ、Dow Jones 涨跌幅
- VIX 波动率、美债 10Y 收益率变动
- 2-3 条方向性判断，每条含 **判断**：和 **依据**：字段

## 二、热点个股与板块
- 3-4 条热点（科技巨头/半导体/AI 概念/生物科技），每条用 `### N. 标题`
- **涨跌幅**：具体百分比  **驱动因素**：财报/产品/监管
- **期权信号**：异常期权活动（如有）
- **🦞 Claw 锐评**：一句话多空判断
- 末尾可附异动股提醒

## 三、🦞 Claw 策略与风险
- Fed 政策与利率展望（如有新动态）
- 行业配置方向建议（2-3 句话）
- "本简报仅供参考，不构成投资建议。"

{ self._engagement_rules(getattr(self.preset, 'target_audience', '')) }

【字数要求】严格控制 {word_lo}-{word_hi} 字，3 个章节缺一不可。宁可精炼也不要凑字。"""

    def _build_user_prompt(self, items: list[Item], issue_label: str, user_hint: str) -> str:
        today = self._today_context()
        prompt = f"请生成 {issue_label} 期 {self.preset.display_name}。\n\n"
        prompt += f"**日期**: {today}\n**素材数**: {len(items)} 条\n"
        if user_hint:
            prompt += f"**用户提示**: {user_hint}\n"
        prompt += f"\n**今日美股相关资讯**:\n\n{_build_item_block(items)}\n"
        word_lo, word_hi = self.preset.target_word_count
        prompt += f"\n【要求】3 个章节完整，{word_lo}-{word_hi} 字，每条用 ### N. 格式并带 Claw 锐评。精炼为主，不要凑字。\n\n请生成美股日报："
        return prompt
