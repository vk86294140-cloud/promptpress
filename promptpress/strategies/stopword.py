"""Telegraphic prose compression (level 2).

Drops words that carry near-zero information for an LLM reader — articles,
fillers, hedges — outside protected regions. Inspired by "caveman"-style
prompt compression: models recover the grammar; the facts are what cost
tokens. Sentence-initial capitalization is repaired so output stays readable.
"""

from __future__ import annotations

import re

from ..protect import shield, unshield
from .base import Strategy

_DROP = {
    "a", "an", "the",
    "just", "really", "basically", "actually", "simply", "quite", "very",
    "rather", "somewhat", "perhaps", "maybe", "certainly", "definitely",
    "in order", "of course", "as well",
    "please", "kindly",
}

_PHRASES = [
    re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
    for p in sorted((p for p in _DROP if " " in p), key=len, reverse=True)
]
_SINGLE = re.compile(
    r"\b(" + "|".join(p for p in _DROP if " " not in p) + r")\b\s?",
    re.IGNORECASE,
)


class StopwordStrategy(Strategy):
    name = "stopword"
    level = 2

    def compress(self, text: str) -> str:
        body, regions = shield(text)
        for pat in _PHRASES:
            body = pat.sub("", body)
        body = _SINGLE.sub("", body)
        body = re.sub(r"[ \t]{2,}", " ", body)
        body = re.sub(r" ([,.;:!?])", r"\1", body)
        # repair sentence starts: ". word" -> ". Word"
        body = re.sub(
            r"(^|[.!?]\s+)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            body,
            flags=re.MULTILINE,
        )
        return unshield(body, regions)
