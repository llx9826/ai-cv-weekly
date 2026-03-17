"""ClawCat Brief — Report Output Sanitizer

Removes internal pipeline artifacts (JSON fragments, debug fields, scoring
metadata) from the final Markdown before rendering. Runs after the Quality
Gate and before the Renderer.
"""

from __future__ import annotations

import re


_FORBIDDEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # JSON / dict fragments
    (re.compile(r"```json\s*\n[\s\S]*?\n```"), ""),
    (re.compile(r"\{['\"]?\w+['\"]?\s*:\s*['\"]?[^}]{0,200}['\"]?\s*\}"), ""),
    # Pipeline internal fields
    (re.compile(r"(?i)\b(?:score|grounding|confidence|gate_verdict|eval_score)\s*[:=]\s*[\d.]+%?"), ""),
    (re.compile(r"(?i)\btotal[_\s]?items\s*[:=]\s*\d+"), ""),
    (re.compile(r"(?i)\bsources?[_\s]?used\s*[:=]\s*\d+"), ""),
    # Citation debug tags
    (re.compile(r"\[(?:FACT|SOURCE|UNGROUNDED)\]"), ""),
    (re.compile(r"(?:未溯源|ungrounded)\s*\d+%"), ""),
    # Stray field labels that shouldn't be in reader-facing content
    (re.compile(r"(?i)\bcitation[_\s]?summary\b"), ""),
]


class ReportSanitizer:
    """Cleans LLM-generated Markdown of internal pipeline artifacts."""

    @staticmethod
    def sanitize(markdown: str) -> str:
        result = markdown
        for pattern, replacement in _FORBIDDEN_PATTERNS:
            result = pattern.sub(replacement, result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
