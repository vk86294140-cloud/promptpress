"""Strategy interface.

A strategy is a pure text→text transform with a declared aggressiveness
level. The pipeline orders strategies by level and applies them until the
token budget is met, so cheap lossless passes always run before lossy ones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    #: Identifier used in CLI flags and reports.
    name: str = "base"
    #: 0 = lossless, 1 = near-lossless, 2 = lossy-but-safe, 3 = aggressive.
    level: int = 0

    @abstractmethod
    def compress(self, text: str) -> str:
        """Return a compressed version of *text*. Must be idempotent."""
        raise NotImplementedError
