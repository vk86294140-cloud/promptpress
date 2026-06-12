from promptpress.tokens import estimate_tokens


def test_empty():
    assert estimate_tokens("") == 0


def test_monotonic_with_length():
    short = estimate_tokens("hello world")
    long = estimate_tokens("hello world " * 50)
    assert long > short * 30


def test_prose_in_plausible_range():
    # ~4 chars/token on English prose; allow a generous band
    text = ("The quick brown fox jumps over the lazy dog and keeps running "
            "through the quiet forest until it reaches the river bank.") * 10
    est = estimate_tokens(text)
    assert len(text) / 6 < est < len(text) / 2.5


def test_code_denser_than_prose():
    code = "def f(x):\n    return {k: v**2 for k, v in x.items()}\n" * 20
    assert estimate_tokens(code) > len(code) / 6


def test_cjk_counted_per_char():
    assert estimate_tokens("日本語のテキスト") >= 7
