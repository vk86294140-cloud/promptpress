"""Email cruft removal: quoted replies, signatures, disclaimers (level 2).

Context assembled from email threads, support tickets, or forwarded messages
carries three kinds of text a model almost never needs:

* **Quoted reply chains** — the ``> ...`` history re-pasted into every reply,
  and the ``On <date>, <name> wrote:`` attribution lines that introduce them.
* **Signatures** — everything after the RFC 3676 ``-- `` delimiter, plus the
  ubiquitous ``Sent from my iPhone`` footers.
* **Confidentiality disclaimers** — the boilerplate legal footer appended by
  corporate mail servers.

All three are dropped. Code fences, inline code, URLs, and quoted *strings*
are shielded first, so a shell redirect (``cmd > file``) inside a code block or
a ``>`` in inline code survives untouched. Marked level 2 (lossy-but-safe):
on prose that genuinely uses markdown blockquotes this removes them, which is
why it sits above the lossless passes in the ladder.
"""

from __future__ import annotations

import re

from ..protect import shield, unshield
from .base import Strategy

# Attribution line that introduces a quoted reply, e.g.
# "On Mon, Jun 23, 2025 at 4:01 PM Jane Doe <jane@x.com> wrote:"
_ATTRIBUTION = re.compile(r"^\s*On\b.*\bwrote:\s*$", re.IGNORECASE)
# A quoted line: one or more '>' (with optional leading spaces).
_QUOTED = re.compile(r"^\s*>+")
# RFC 3676 signature delimiter: a line that is exactly "--" or "-- ".
_SIG_DELIM = re.compile(r"^-- ?$")
# Mobile-client footers.
_SENT_FROM = re.compile(r"^\s*Sent from my .+$", re.IGNORECASE)
# Openers of a confidentiality/legal disclaimer block.
_DISCLAIMER = re.compile(
    r"^\s*(this (e-?mail|message)|the information (contained|in this)|"
    r"confidentiality notice|this communication)\b",
    re.IGNORECASE,
)


class QuotedTextStrategy(Strategy):
    name = "quoted"
    level = 2

    def compress(self, text: str) -> str:
        # Cheap guard: nothing that looks like email cruft.
        low = text.lower()
        if (">" not in text and "-- " not in text
                and "wrote:" not in low and "sent from my" not in low
                and "this email" not in low and "this e-mail" not in low):
            return text

        body, regions = shield(text)
        lines = body.split("\n")
        kept: list[str] = []
        for line in lines:
            # Signatures, disclaimers, and the quoted reply history all run to
            # the end of the message — truncate there. Truncating at the
            # attribution (rather than only dropping ``>`` lines) also catches a
            # reply body whose chevrons an earlier markdown pass already removed.
            if (_SIG_DELIM.match(line) or _DISCLAIMER.match(line)
                    or _ATTRIBUTION.match(line)):
                break
            if _QUOTED.match(line) or _SENT_FROM.match(line):
                continue  # stray quoted lines and mobile footers add no signal
            kept.append(line)

        out = "\n".join(kept)
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
        out = (out + "\n") if out else ""
        return unshield(out, regions)
