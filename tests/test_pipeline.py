from promptpress import Pipeline, compress
from promptpress.tokens import estimate_tokens

LONG = (
    "## Background\n\n"
    + "The system was really just designed to handle a very large number of "
      "requests per second across the entire fleet of servers. " * 8
    + "\n\nThe system was really just designed to handle a very large number of "
      "requests per second across the entire fleet of servers and racks. " * 2
    + "\n\n```python\n# setup\nx = 1  # one\n```\n"
)


def test_compress_reduces_tokens():
    r = compress(LONG)
    assert r.tokens_after < r.tokens_before
    assert r.text


def test_budget_met_stops_early():
    before = estimate_tokens(LONG)
    r = compress(LONG, budget=before - 5)  # trivially close budget
    assert r.met_budget
    # lossless/near-lossless stages should be enough; extract must not have run
    assert all(s.strategy != "extract" for s in r.stages)


def test_under_budget_input_untouched():
    r = compress("short text", budget=10_000)
    assert r.text == "short text"
    assert r.stages == []


def test_unmeetable_budget_flagged():
    r = compress(LONG, budget=1)
    assert not r.met_budget
    assert r.tokens_after < r.tokens_before


def test_max_level_respected():
    r = Pipeline(max_level=0).compress(LONG)
    assert all(s.level == 0 for s in r.stages)


def test_stage_reports_consistent():
    r = compress(LONG)
    for st in r.stages:
        assert st.saved > 0
    assert r.summary()


def test_code_survives_full_pipeline():
    r = compress(LONG, budget=1)
    assert "x = 1" in r.text
