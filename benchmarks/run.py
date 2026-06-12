"""Compression benchmark over three realistic context types.

Run: python benchmarks/run.py
Prints a markdown table of token savings per max-level — the same table
shown in the README.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promptpress import Pipeline  # noqa: E402
from promptpress.tokens import estimate_tokens  # noqa: E402

PROSE = ("## Incident report\n\n" + (
    "The deployment to the production environment was really just initiated at "
    "approximately 14:32 UTC by the on-call engineer. The deployment was actually "
    "initiated at 14:32 UTC by the engineer who was on call at the time. After the "
    "rollout reached fifty percent of the fleet, the latency of the checkout service "
    "began to climb very rapidly, and the p95 latency crossed the alerting threshold. "
    "The on-call engineer decided to halt the rollout and begin an investigation into "
    "the root cause of the regression. It was eventually determined that a connection "
    "pool setting had been changed in the new release without a corresponding change "
    "to the database server configuration. "
) * 4)

CODE_HEAVY = (
    "Review this module:\n\n```python\n"
    + '"""Service layer for orders."""\n\n'
    + "\n\n".join(
        f'def handler_{i}(payload):\n    """Handle case {i}."""\n'
        f"    # validate first\n    if not payload:\n        return None\n"
        f"    result = payload.get('value', {i}) * {i}  # scale\n    return result"
        for i in range(12)
    )
    + "\n```\n"
)

CHAT_LOG = "\n\n".join(
    f"User asked about the {topic} configuration and the assistant explained that the "
    f"{topic} configuration is stored in the settings file and can be overridden with "
    f"environment variables at startup."
    for topic in ["logging", "cache", "logging", "database", "cache", "logging", "auth"]
)

SAMPLES = {"prose": PROSE, "code-heavy": CODE_HEAVY, "chat-log": CHAT_LOG}


def main() -> None:
    print("| sample | tokens | L0 lossless | L1 | L2 | L3 aggressive |")
    print("|---|---|---|---|---|---|")
    for name, text in SAMPLES.items():
        before = estimate_tokens(text)
        cells = []
        for level in range(4):
            r = Pipeline(max_level=level).compress(text)
            cells.append(f"-{(1 - r.ratio) * 100:.0f}%")
        print(f"| {name} | {before} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
