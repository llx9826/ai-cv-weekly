"""LunaClaw Brief — Editor base class.

LunaClaw Brief — Editor 基类
"""

from __future__ import annotations

import time
import random
from abc import ABC, abstractmethod

from brief.models import Item, ReportDraft, PresetConfig
from brief.llm import LLMClient


class BaseEditor(ABC):
    """所有 Editor 的基类，提供 LLM 调用与重试逻辑"""

    def __init__(self, preset: PresetConfig, llm: LLMClient):
        self.preset = preset
        self.llm = llm

    def generate(
        self, items: list[Item], issue_number: int, user_hint: str = ""
    ) -> ReportDraft | None:
        """带指数退避重试的生成入口"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(items, issue_number, user_hint)

        for attempt in range(3):
            try:
                response = self.llm.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=8000,
                )
                if not response:
                    self._backoff(attempt, "LLM 返回为空")
                    continue

                markdown = self._clean_markdown(response)
                return ReportDraft(markdown=markdown, issue_number=issue_number)

            except Exception as e:
                self._backoff(attempt, str(e)[:60])

        return None

    @abstractmethod
    def _build_system_prompt(self) -> str:
        ...

    @abstractmethod
    def _build_user_prompt(
        self, items: list[Item], issue_number: int, user_hint: str
    ) -> str:
        ...

    @staticmethod
    def _clean_markdown(response: str) -> str:
        text = response.strip()
        if text.startswith("```markdown"):
            text = text[11:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _backoff(attempt: int, reason: str):
        delay = min(1.0 * (2 ** attempt), 30.0) + random.uniform(0, 1)
        print(f"   [{reason}]，{delay:.1f}s 后重试 ({attempt + 1}/3)...")
        time.sleep(delay)
