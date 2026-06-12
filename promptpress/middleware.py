"""Drop-in Anthropic SDK wrapper that compresses message content before send.

Usage:
    from promptpress.middleware import CompressedAnthropic
    client = CompressedAnthropic(budget_per_message=4000)
    client.messages.create(model=..., messages=[...], max_tokens=...)

Only string content and text blocks are compressed; tool calls, images and
system internals pass through untouched. The `anthropic` package is an
optional dependency — importing this module without it raises at
construction time, not import time.
"""

from __future__ import annotations

from .pipeline import Pipeline


class _CompressedMessages:
    def __init__(self, inner, pipeline: Pipeline, budget: int | None):
        self._inner = inner
        self._pipeline = pipeline
        self._budget = budget

    def create(self, **kwargs):
        messages = kwargs.get("messages")
        if messages:
            kwargs["messages"] = [self._compress_message(m) for m in messages]
        system = kwargs.get("system")
        if isinstance(system, str):
            kwargs["system"] = self._pipeline.compress(system, budget=self._budget).text
        return self._inner.create(**kwargs)

    def _compress_message(self, msg: dict) -> dict:
        content = msg.get("content")
        if isinstance(content, str):
            return {**msg, "content": self._pipeline.compress(content, budget=self._budget).text}
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    compressed = self._pipeline.compress(block["text"], budget=self._budget).text
                    new_blocks.append({**block, "text": compressed})
                else:
                    new_blocks.append(block)
            return {**msg, "content": new_blocks}
        return msg


class CompressedAnthropic:
    """Wraps anthropic.Anthropic; everything except messages.create is proxied."""

    def __init__(self, budget_per_message: int | None = None, max_level: int = 2, **anthropic_kwargs):
        import anthropic  # optional dependency, imported lazily

        self._client = anthropic.Anthropic(**anthropic_kwargs)
        pipeline = Pipeline(max_level=max_level)
        self.messages = _CompressedMessages(self._client.messages, pipeline, budget_per_message)

    def __getattr__(self, item):
        return getattr(self._client, item)
