"""Extractive summarization via TextRank (level 3, aggressive).

Pure-stdlib implementation of the TextRank algorithm (Mihalcea & Tarau,
2004): sentences are nodes, edges are word-overlap similarity, and PageRank
power iteration scores centrality. The top-K most central sentences are
kept in original order, so the result reads as a faithful extract rather
than a paraphrase — nothing is generated, so nothing can be hallucinated.
"""

from __future__ import annotations

import math
import re

from .base import Strategy

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_WORDS = re.compile(r"[a-z0-9]+")


def _similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    if overlap == 0:
        return 0.0
    return overlap / (math.log(len(a) + 1) + math.log(len(b) + 1))


def textrank(sentences: list[str], damping: float = 0.85, iters: int = 30) -> list[float]:
    """PageRank scores for each sentence."""
    n = len(sentences)
    if n == 0:
        return []
    word_sets = [set(_WORDS.findall(s.lower())) for s in sentences]
    sim = [[_similarity(word_sets[i], word_sets[j]) if i != j else 0.0
            for j in range(n)] for i in range(n)]
    out_weight = [sum(row) or 1.0 for row in sim]
    scores = [1.0 / n] * n
    for _ in range(iters):
        new = []
        for i in range(n):
            rank = sum(sim[j][i] / out_weight[j] * scores[j] for j in range(n))
            new.append((1 - damping) / n + damping * rank)
        delta = sum(abs(a - b) for a, b in zip(new, scores))
        scores = new
        if delta < 1e-6:
            break
    return scores


class ExtractStrategy(Strategy):
    name = "extract"
    level = 3

    def __init__(self, keep_ratio: float = 0.5, min_sentences: int = 3):
        self.keep_ratio = keep_ratio
        self.min_sentences = min_sentences

    def compress(self, text: str) -> str:
        # operate per prose paragraph; code blocks pass through untouched
        out_blocks = []
        for block in re.split(r"\n\s*\n", text):
            if "```" in block or block.lstrip().startswith(("#", "-", "*", "|")):
                out_blocks.append(block)
                continue
            sents = [s for s in _SENT_SPLIT.split(block.strip()) if s.strip()]
            if len(sents) <= self.min_sentences:
                out_blocks.append(block)
                continue
            keep_n = max(self.min_sentences, math.ceil(len(sents) * self.keep_ratio))
            scores = textrank(sents)
            ranked = sorted(range(len(sents)), key=lambda i: scores[i], reverse=True)
            chosen = sorted(ranked[:keep_n])  # original order
            out_blocks.append(" ".join(sents[i] for i in chosen))
        return "\n\n".join(out_blocks)
