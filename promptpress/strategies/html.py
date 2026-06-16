"""HTML/XML tag stripping (level 1, near-lossless).

Context pulled from web pages, scraped docs, or RAG sources is often littered
with markup the model doesn't need to understand the text: ``<div>``, ``<span>``,
``<a href=...>`` wrappers, and HTML comments. Stripping the tags (while keeping
the visible text and decoding the common entities) cuts tokens without losing
meaning. Code fences, inline code, URLs, and quoted strings are shielded first,
so a literal ``<tag>`` inside a code block survives untouched.
"""

from __future__ import annotations

import re

from ..protect import shield, unshield
from .base import Strategy

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Drop whole non-content elements together with their contents.
_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*(?:\s[^<>]*?)?/?>")
_ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
}


class HtmlStrategy(Strategy):
    name = "html"
    level = 1

    def compress(self, text: str) -> str:
        # Cheap guard: no tags and no entities means nothing to do.
        if "<" not in text and "&" not in text:
            return text
        body, regions = shield(text)
        body = _COMMENT.sub("", body)
        body = _SCRIPT_STYLE.sub("", body)
        body = _TAG.sub("", body)
        for entity, char in _ENTITIES.items():
            body = body.replace(entity, char)
        # Tag removal can leave runs of spaces and empty lines behind.
        body = re.sub(r"[ \t]{2,}", " ", body)
        body = re.sub(r"\n{3,}", "\n\n", body)
        return unshield(body, regions)
