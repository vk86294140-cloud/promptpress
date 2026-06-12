"""Lossless whitespace normalization (level 0)."""

from __future__ import annotations

import re

from .base import Strategy


class WhitespaceStrategy(Strategy):
    name = "whitespace"
    level = 0

    def compress(self, text: str) -> str:
        out_lines: list[str] = []
        in_fence = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                out_lines.append(line.rstrip())
                continue
            if in_fence:
                out_lines.append(line.rstrip())  # keep indentation inside code
                continue
            # collapse runs of spaces/tabs in prose
            out_lines.append(re.sub(r"[ \t]{2,}", " ", line.strip()))
        text = "\n".join(out_lines)
        # at most one blank line between blocks
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n" if text.strip() else ""
