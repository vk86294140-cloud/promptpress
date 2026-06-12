"""Protected-region handling.

Compression must never mangle code fences, inline code, URLs, or quoted
strings — these carry exact-match semantics for the model. Strategies that
rewrite prose first swap protected regions for sentinel placeholders, run,
then restore them.
"""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"```.*?```", re.DOTALL),          # fenced code blocks
    re.compile(r"`[^`\n]+`"),                     # inline code
    re.compile(r"https?://\S+"),                  # URLs
    re.compile(r'"[^"\n]{1,200}"'),               # short double-quoted strings
]

_SENTINEL = "\x00PP{}\x00"


def shield(text: str) -> tuple[str, list[str]]:
    """Replace protected regions with sentinels; return (text, regions)."""
    regions: list[str] = []

    def stash(m: re.Match) -> str:
        regions.append(m.group(0))
        return _SENTINEL.format(len(regions) - 1)

    for pat in _PATTERNS:
        text = pat.sub(stash, text)
    return text, regions


def unshield(text: str, regions: list[str]) -> str:
    """Restore stashed regions. Sentinels a strategy deleted stay deleted."""
    for i, region in enumerate(regions):
        text = text.replace(_SENTINEL.format(i), region)
    return text
