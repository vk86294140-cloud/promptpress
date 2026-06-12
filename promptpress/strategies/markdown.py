"""Markdown decoration stripping (level 1, near-lossless).

Removes formatting the model doesn't need for comprehension: horizontal
rules, bold/italic markers, blockquote chevrons, trailing header hashes.
Structure that carries meaning (headers, lists, tables, code) is kept.
"""

from __future__ import annotations

import re

from ..protect import shield, unshield
from .base import Strategy


class MarkdownStrategy(Strategy):
    name = "markdown"
    level = 1

    def compress(self, text: str) -> str:
        body, regions = shield(text)
        body = re.sub(r"^\s*([-*_]\s*){3,}$", "", body, flags=re.MULTILINE)  # hrules
        body = re.sub(r"(\*\*|__)(.+?)\1", r"\2", body)                      # bold
        body = re.sub(r"(?<![\w*])([*_])([^*_\n]+)\1(?![\w*])", r"\2", body)  # italic
        body = re.sub(r"^(#{1,6} .*?)\s+#+\s*$", r"\1", body, flags=re.MULTILINE)
        body = re.sub(r"^>\s?", "", body, flags=re.MULTILINE)               # quotes
        body = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[image: \1]", body)      # images
        return unshield(body, regions)
