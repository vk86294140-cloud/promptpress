"""Code-aware compression of fenced blocks (level 1).

Python blocks are processed with the real `tokenize` module so strings
containing '#' are never corrupted; other languages get a conservative
regex pass (full-line comments and blank lines only).
"""

from __future__ import annotations

import io
import re
import tokenize

from .base import Strategy

_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_LINE_COMMENT = re.compile(r"^\s*(//|#)(?![!\[]).*$", re.MULTILINE)


def _strip_python(src: str) -> str:
    """Drop comments and standalone docstrings via the tokenizer."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return _strip_generic(src)

    drop_lines: set[int] = set()
    prev_significant = None
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            drop_lines.update(range(tok.start[0], tok.end[0] + 1))
        elif tok.type == tokenize.STRING:
            # a STRING is a docstring when it's an expression statement, i.e.
            # the previous significant token was NEWLINE/INDENT/DEDENT or none
            if prev_significant in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                drop_lines.update(range(tok.start[0], tok.end[0] + 1))
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev_significant = tok.type

    kept = []
    for i, line in enumerate(src.splitlines(), 1):
        if i in drop_lines:
            # comment lines may share the line with code — salvage that part;
            # docstring lines drop entirely
            if "#" in line:
                stripped = _strip_trailing_comment(line)
                if stripped.strip():
                    kept.append(stripped)
            continue
        if line.strip():
            kept.append(line.rstrip())
    return "\n".join(kept)


def _strip_trailing_comment(line: str) -> str:
    # only strip when '#' is clearly not inside a string: no quotes before it
    idx = line.find("#")
    if idx > 0 and '"' not in line[:idx] and "'" not in line[:idx]:
        return line[:idx].rstrip()
    return "" if line.lstrip().startswith("#") else line


def _strip_generic(src: str) -> str:
    src = _LINE_COMMENT.sub("", src)
    return "\n".join(l.rstrip() for l in src.splitlines() if l.strip())


class CodeStrategy(Strategy):
    name = "code"
    level = 1

    def compress(self, text: str) -> str:
        def repl(m: re.Match) -> str:
            lang, body = m.group(1), m.group(2)
            stripped = _strip_python(body) if lang in ("python", "py") else _strip_generic(body)
            return f"```{lang}\n{stripped}\n```"

        return _FENCE.sub(repl, text)
