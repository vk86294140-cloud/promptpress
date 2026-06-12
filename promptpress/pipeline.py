"""Budgeted compression pipeline.

Strategies are applied in aggressiveness order (lossless → aggressive) and
the pipeline STOPS as soon as the token budget is met — text is never made
lossier than the budget demands. Each stage's savings are recorded so the
caller can see exactly what was traded away.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .strategies.base import Strategy
from .strategies.code import CodeStrategy
from .strategies.dedup import DedupStrategy
from .strategies.extract import ExtractStrategy
from .strategies.markdown import MarkdownStrategy
from .strategies.stopword import StopwordStrategy
from .strategies.whitespace import WhitespaceStrategy
from .tokens import estimate_tokens


def default_strategies() -> list[Strategy]:
    return [
        WhitespaceStrategy(),
        MarkdownStrategy(),
        CodeStrategy(),
        DedupStrategy(),
        StopwordStrategy(),
        ExtractStrategy(),
    ]


@dataclass
class StageReport:
    strategy: str
    level: int
    tokens_before: int
    tokens_after: int

    @property
    def saved(self) -> int:
        return self.tokens_before - self.tokens_after


@dataclass
class CompressionResult:
    text: str
    tokens_before: int
    tokens_after: int
    budget: int | None
    met_budget: bool
    stages: list[StageReport] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.tokens_before == 0:
            return 1.0
        return self.tokens_after / self.tokens_before

    def summary(self) -> str:
        lines = [
            f"tokens: {self.tokens_before} -> {self.tokens_after} "
            f"({(1 - self.ratio) * 100:.1f}% saved)",
        ]
        if self.budget is not None:
            lines.append(f"budget {self.budget}: {'MET' if self.met_budget else 'NOT MET'}")
        for st in self.stages:
            lines.append(f"  [{st.level}] {st.strategy:<11} -{st.saved} tokens")
        return "\n".join(lines)


class Pipeline:
    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        max_level: int = 3,
        counter=estimate_tokens,
    ):
        self.strategies = sorted(strategies or default_strategies(), key=lambda s: s.level)
        self.max_level = max_level
        self.counter = counter

    def compress(self, text: str, budget: int | None = None) -> CompressionResult:
        before = self.counter(text)
        result = CompressionResult(
            text=text, tokens_before=before, tokens_after=before,
            budget=budget, met_budget=budget is None or before <= budget,
        )
        if result.met_budget and budget is not None:
            return result  # already under budget — touch nothing

        current = text
        for strat in self.strategies:
            if strat.level > self.max_level:
                break
            t_before = self.counter(current)
            candidate = strat.compress(current)
            t_after = self.counter(candidate)
            if t_after < t_before:  # never accept a stage that grows the text
                current = candidate
                result.stages.append(StageReport(strat.name, strat.level, t_before, t_after))
            if budget is not None and self.counter(current) <= budget:
                break  # budget met — stop before lossier stages

        result.text = current
        result.tokens_after = self.counter(current)
        result.met_budget = budget is None or result.tokens_after <= budget
        return result


def compress(text: str, budget: int | None = None, max_level: int = 3) -> CompressionResult:
    """One-call convenience API."""
    return Pipeline(max_level=max_level).compress(text, budget=budget)
