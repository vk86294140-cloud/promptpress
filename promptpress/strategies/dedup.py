"""Near-duplicate paragraph removal via shingle Jaccard similarity (level 2).

Long contexts (chat history, concatenated docs, retries) repeat themselves.
Each paragraph is reduced to a set of word 3-shingles; a paragraph whose
shingle set overlaps an earlier one above the threshold is dropped. This is
the MinHash idea without the hashing — exact Jaccard is fine at prompt scale
(hundreds of paragraphs, not millions).
"""

from __future__ import annotations

import re

from .base import Strategy

_WORDS = re.compile(r"[a-z0-9]+")


def _shingles(text: str, k: int = 3) -> frozenset:
    words = _WORDS.findall(text.lower())
    if len(words) < k:
        return frozenset([" ".join(words)]) if words else frozenset()
    return frozenset(" ".join(words[i:i + k]) for i in range(len(words) - k + 1))


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class DedupStrategy(Strategy):
    name = "dedup"
    level = 2

    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold

    def compress(self, text: str) -> str:
        # split on blank lines, but never split/drop inside code fences
        blocks: list[str] = []
        fence_buf: list[str] = []
        in_fence = False
        for chunk in re.split(r"\n\s*\n", text):
            opens = chunk.count("```")
            if in_fence:
                fence_buf.append(chunk)
                if opens % 2 == 1:
                    blocks.append("\n\n".join(fence_buf))
                    fence_buf, in_fence = [], False
                continue
            if opens % 2 == 1:
                fence_buf, in_fence = [chunk], True
                continue
            blocks.append(chunk)
        if fence_buf:
            blocks.append("\n\n".join(fence_buf))

        kept: list[str] = []
        seen: list[frozenset] = []
        for block in blocks:
            if "```" in block:
                kept.append(block)  # code blocks are never deduped
                continue
            sh = _shingles(block)
            if any(_jaccard(sh, prev) >= self.threshold for prev in seen):
                continue
            seen.append(sh)
            kept.append(block)
        return "\n\n".join(kept)
