"""Token Budget Manager — controls input/output token budgets.

Uses tiktoken for accurate counting with a Map-Reduce strategy
for handling over-budget inputs without truncation.

Features:
  - Accurate token counting via tiktoken (with fallback)
  - Map-Reduce batching for long inputs
  - Maximum report length enforcement
"""

from __future__ import annotations

from brief.models import Item


def _count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Count tokens using tiktoken, with char-based fallback."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return len(text) // 3


def estimate_items_tokens(items: list[Item], max_chars_per_item: int = 400) -> int:
    """Estimate total tokens from a list of items."""
    total_text = ""
    for item in items:
        raw = item.raw_text[:max_chars_per_item] if item.raw_text else ""
        total_text += f"{item.title}\n{raw}\n"
    return _count_tokens(total_text)


class TokenBudget:
    """Manages token budgets for LLM calls.

    Args:
        context_window: Total context window of the model (tokens)
        output_reserve: Tokens reserved for output generation
        model: Model name for tiktoken encoding
    """

    def __init__(
        self,
        context_window: int = 128000,
        output_reserve: int = 8000,
        model: str = "gpt-4o-mini",
    ):
        self.context_window = context_window
        self.output_reserve = output_reserve
        self.model = model

    @property
    def input_budget(self) -> int:
        return self.context_window - self.output_reserve

    def count(self, text: str) -> int:
        return _count_tokens(text, self.model)

    def needs_batching(self, system_prompt: str, user_content: str) -> bool:
        total = self.count(system_prompt) + self.count(user_content)
        return total > self.input_budget

    def batch_items(
        self,
        items: list[Item],
        system_prompt: str,
        max_chars_per_item: int = 400,
    ) -> list[list[Item]]:
        """Split items into batches that fit within the input budget.

        Uses a greedy algorithm: keep adding items until the batch
        would exceed the budget, then start a new batch.
        """
        sys_tokens = self.count(system_prompt)
        available = self.input_budget - sys_tokens - 500

        batches: list[list[Item]] = []
        current_batch: list[Item] = []
        current_tokens = 0

        for item in items:
            raw = item.raw_text[:max_chars_per_item] if item.raw_text else ""
            item_text = f"{item.title}\n{raw}\n"
            item_tokens = self.count(item_text)

            if current_tokens + item_tokens > available and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(item)
            current_tokens += item_tokens

        if current_batch:
            batches.append(current_batch)

        return batches if batches else [items]

    def enforce_output_limit(self, text: str, max_word_count: int) -> str:
        """Trim report text to max_word_count (Chinese characters).

        Trims at sentence boundaries to avoid broken text.
        """
        if max_word_count <= 0 or len(text) <= max_word_count:
            return text

        cutoff = text[:max_word_count]
        for sep in ["。\n", "。", ".\n", "\n\n", "\n"]:
            last = cutoff.rfind(sep)
            if last > max_word_count * 0.7:
                return cutoff[:last + len(sep)]

        return cutoff
