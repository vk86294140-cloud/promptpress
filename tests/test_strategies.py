from promptpress.strategies import (
    CodeStrategy,
    DedupStrategy,
    ExtractStrategy,
    HtmlStrategy,
    MarkdownStrategy,
    StopwordStrategy,
    WhitespaceStrategy,
)


# ── whitespace ──────────────────────────────────────────────────────────

def test_whitespace_collapses_prose_but_not_code():
    text = "hello    world\n\n\n\nbye\n\n```\n    indented   code\n```\n"
    out = WhitespaceStrategy().compress(text)
    assert "hello world" in out
    assert "\n\n\n" not in out
    assert "    indented   code" in out


def test_whitespace_idempotent():
    s = WhitespaceStrategy()
    once = s.compress("a  b\n\n\nc")
    assert s.compress(once) == once


# ── markdown ────────────────────────────────────────────────────────────

def test_markdown_strips_bold_keeps_headers():
    out = MarkdownStrategy().compress("# Title\n\n**bold** and *ital* text\n\n---\n")
    assert "# Title" in out
    assert "**" not in out and "bold" in out
    assert "---" not in out


def test_markdown_preserves_code_and_urls():
    text = "see `**not bold**` and https://x.com/**path** ok\n```\n**raw**\n```"
    out = MarkdownStrategy().compress(text)
    assert "`**not bold**`" in out
    assert "https://x.com/**path**" in out
    assert "**raw**" in out


# ── code ────────────────────────────────────────────────────────────────

def test_code_strips_python_comments_and_docstrings():
    text = (
        "```python\n"
        'def f():\n    """Docstring dies."""\n    # comment dies\n'
        '    x = "# not a comment"\n    return x\n'
        "```"
    )
    out = CodeStrategy().compress(text)
    assert "Docstring dies" not in out
    assert "comment dies" not in out
    assert '"# not a comment"' in out
    assert "return x" in out


def test_code_generic_language():
    text = "```js\n// gone\nconst x = 1;\n\nconst y = 2;\n```"
    out = CodeStrategy().compress(text)
    assert "// gone" not in out
    assert "const x = 1;" in out and "const y = 2;" in out


# ── dedup ───────────────────────────────────────────────────────────────

def test_dedup_drops_near_duplicate_paragraphs():
    para = "The deployment failed because the health check timed out after thirty seconds."
    text = f"{para}\n\nUnrelated paragraph about databases and indexing strategies.\n\n{para} Extra word."
    out = DedupStrategy().compress(text)
    assert out.count("health check timed out") == 1
    assert "databases and indexing" in out


def test_dedup_never_touches_code():
    block = "```\nsame line\nsame line\n```"
    text = f"{block}\n\n{block}"
    out = DedupStrategy().compress(text)
    assert out.count("same line") == 4


# ── stopword ────────────────────────────────────────────────────────────

def test_stopword_drops_articles_keeps_facts():
    out = StopwordStrategy().compress("The server just really needs a restart of the daemon.")
    low = f" {out.lower()} "
    for w in (" the ", " just ", " really ", " a "):
        assert w not in low
    out_low = out.lower()
    assert "server" in out_low and "restart" in out_low and "daemon" in out_low


def test_stopword_protects_code_and_quotes():
    text = 'Run `the command` and check "the exact value" please.'
    out = StopwordStrategy().compress(text)
    assert "`the command`" in out
    assert '"the exact value"' in out
    assert "please" not in out.lower().replace('"the exact value"', "")


# ── extract ─────────────────────────────────────────────────────────────

def _para(n):
    return " ".join(
        f"Sentence number {i} talks about system design and tradeoffs in detail." for i in range(n)
    )


def test_extract_halves_long_paragraphs():
    out = ExtractStrategy(keep_ratio=0.5).compress(_para(10))
    kept = out.count("Sentence number")
    assert 3 <= kept <= 6


def test_extract_leaves_short_paragraphs_alone():
    text = "One. Two. Three."
    assert ExtractStrategy().compress(text) == text


def test_extract_skips_code_and_lists():
    text = "```\ncode\n```\n\n- item one\n- item two"
    assert ExtractStrategy().compress(text) == text


# ── html ────────────────────────────────────────────────────────────────

def test_html_strips_tags_keeps_text():
    out = HtmlStrategy().compress('<div class="x"><p>Hello <b>world</b></p></div>')
    assert "Hello world" in out
    assert "<div" not in out and "<b>" not in out


def test_html_decodes_entities():
    out = HtmlStrategy().compress("Tom &amp; Jerry &lt;3 &nbsp;done")
    assert "Tom & Jerry <3" in out
    assert "&amp;" not in out and "&nbsp;" not in out


def test_html_drops_comments_script_style():
    text = "<!-- secret --><style>p{color:red}</style><script>evil()</script>Visible"
    out = HtmlStrategy().compress(text)
    assert "Visible" in out
    assert "secret" not in out and "evil()" not in out and "color:red" not in out


def test_html_preserves_code_and_urls():
    text = "see `<div>` literal and https://x.com/<a> then <span>strip me</span>"
    out = HtmlStrategy().compress(text)
    assert "`<div>`" in out                  # inline code untouched
    assert "https://x.com/<a>" in out        # URL untouched
    assert "<span>" not in out and "strip me" in out


def test_html_noop_without_tags():
    text = "plain prose, nothing to strip here."
    assert HtmlStrategy().compress(text) == text
