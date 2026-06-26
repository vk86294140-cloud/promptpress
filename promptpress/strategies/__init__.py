from .base import Strategy
from .code import CodeStrategy
from .dedup import DedupStrategy
from .extract import ExtractStrategy
from .html import HtmlStrategy
from .markdown import MarkdownStrategy
from .quoted import QuotedTextStrategy
from .stopword import StopwordStrategy
from .whitespace import WhitespaceStrategy

__all__ = [
    "Strategy",
    "WhitespaceStrategy",
    "MarkdownStrategy",
    "HtmlStrategy",
    "CodeStrategy",
    "QuotedTextStrategy",
    "DedupStrategy",
    "StopwordStrategy",
    "ExtractStrategy",
]
