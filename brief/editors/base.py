"""LunaClaw Brief — Editor base class.

Abstract base for all editors, providing LLM invocation with:
  - Standard generate() with retry logic
  - Streaming generate_stream() that yields chunks
"""

from __future__ import annotations

import time
import random
from abc import ABC, abstractmethod
from typing import Generator

from brief.models import Item, ReportDraft, PresetConfig
from brief.llm import LLMClient


class BaseEditor(ABC):
    """Base class for all editors, providing LLM invocation and retry logic."""

    def __init__(self, preset: PresetConfig, llm: LLMClient):
        self.preset = preset
        self.llm = llm

    def generate(
        self, items: list[Item], issue_number: int, user_hint: str = ""
    ) -> ReportDraft | None:
        """Generate a report draft with exponential-backoff retry."""
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
                    self._backoff(attempt, "LLM returned empty")
                    continue

                markdown = self._clean_markdown(response)
                return ReportDraft(markdown=markdown, issue_number=issue_number)

            except Exception as e:
                self._backoff(attempt, str(e)[:60])

        return None

    def generate_stream(
        self, items: list[Item], issue_number: int, user_hint: str = ""
    ) -> Generator[str, None, None]:
        """Stream report generation, yielding Markdown chunks as they arrive."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(items, issue_number, user_hint)

        for chunk in self.llm.stream(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=8000,
        ):
            yield chunk

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
        """Strip markdown code fence wrappers from LLM response."""
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
        print(f"   [{reason}], retrying in {delay:.1f}s ({attempt + 1}/3)...")
        time.sleep(delay)
