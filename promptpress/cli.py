"""promptpress CLI.

    promptpress compress prompt.md --budget 4000 --report
    promptpress count prompt.md
    cat prompt.md | promptpress compress - --max-level 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import compress
from .tokens import estimate_tokens


def _read(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    return Path(src).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="promptpress", description="LLM context compression")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compress", help="compress a file (or - for stdin)")
    c.add_argument("input")
    c.add_argument("--budget", type=int, default=None, help="target token budget")
    c.add_argument("--max-level", type=int, default=3, choices=range(4),
                   help="max aggressiveness: 0 lossless .. 3 extractive")
    c.add_argument("-o", "--output", default=None, help="write result here (default stdout)")
    c.add_argument("--report", action="store_true", help="print per-stage savings to stderr")

    n = sub.add_parser("count", help="estimate tokens in a file (or - for stdin)")
    n.add_argument("input")

    args = ap.parse_args(argv)
    text = _read(args.input)

    if args.cmd == "count":
        print(estimate_tokens(text))
        return 0

    result = compress(text, budget=args.budget, max_level=args.max_level)
    if args.output:
        Path(args.output).write_text(result.text, encoding="utf-8")
    else:
        sys.stdout.write(result.text)
    if args.report:
        print(result.summary(), file=sys.stderr)
    return 0 if result.met_budget else 2


if __name__ == "__main__":
    sys.exit(main())
