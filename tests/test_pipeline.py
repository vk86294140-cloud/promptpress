import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["RESUME_PROVIDER"] = "demo"

import pipeline  # noqa: E402


def test_extract_json_plain():
    assert pipeline.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced_with_prose():
    text = 'Here you go:\n```json\n{"overall": 90}\n```\nDone.'
    assert pipeline.extract_json(text) == {"overall": 90}


def test_extract_json_embedded():
    text = 'Sure. {"skills_match": 88, "fixes": []} hope that helps'
    assert pipeline.extract_json(text)["skills_match"] == 88


def test_tailor_demo_end_to_end():
    result = pipeline.tailor("Fake job description " * 10, "Fake master resume")
    assert result["resume_markdown"].startswith("# ")
    assert result["target_met"] is True
    assert result["provider"] == "demo"
    for key in pipeline.DIMENSIONS:
        assert 0 <= result["scores"][key] <= 100


SAMPLE_MD = """# Jane Doe
jane@example.com | (555) 010-0000 | linkedin.com/in/janedoe | github.com/janedoe

Backend engineer with six years in payments.

## Skills
**Languages:** Python, Go
**Cloud:** AWS, Docker

## Experience
**Senior Software Engineer — Acme Payments** | 2021 – Present
- Cut checkout p99 latency from 900ms to 210ms

## Education
B.S. Computer Science, State University, 2018
"""


def test_render_parse():
    import render
    doc = render.parse(SAMPLE_MD)
    assert doc["name"] == "Jane Doe"
    assert len(doc["contact"]) == 4
    titles = [s["title"] for s in doc["sections"]]
    assert titles == ["Skills", "Experience", "Education"]
    skills_kinds = [i[0] for i in doc["sections"][0]["items"]]
    assert skills_kinds == ["text", "text"]  # skill groups are NOT role lines
    assert doc["sections"][1]["items"][0][0] == "role"


def test_render_links():
    import render
    assert render.link_for("jane@example.com")[0] == "mailto:jane@example.com"
    assert render.link_for("linkedin.com/in/janedoe")[0] == "https://linkedin.com/in/janedoe"
    assert render.link_for("github.com/janedoe")[0] == "https://github.com/janedoe"
    assert render.link_for("(555) 010-0000")[0] is None


def test_render_pdf_and_docx():
    import render
    pdf = render.to_pdf(SAMPLE_MD)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert b"/URI" in pdf  # hyperlinks embedded
    docx = render.to_docx(SAMPLE_MD)
    assert docx[:2] == b"PK" and len(docx) > 1000


def test_pdf_autofits_long_resume_to_one_page():
    import render
    long_md = SAMPLE_MD + "".join(
        f"\n**Engineer — Company {i}** | 20{10+i} – 20{11+i}\n"
        "- Did a fairly long piece of work that takes a full line to describe properly\n"
        "- Another substantial bullet with enough words to wrap onto a second line sometimes\n"
        for i in range(14)
    )
    _, pages_full = render._build_pdf(long_md, 1.0)
    assert pages_full > 1  # would overflow at full size
    fitted = render.to_pdf(long_md)
    # "/Type /Page" is a prefix of "/Type /Pages", so subtract the tree node
    assert fitted.count(b"/Type /Page") - fitted.count(b"/Type /Pages") == 1


def test_ats_scan():
    import ats
    jd = ("Looking for a Python engineer with AWS, Docker, Kubernetes, React and "
          "TypeScript experience. Python and AWS required. Machine learning a plus. "
          "Machine learning models in production.")
    scan = ats.scan(jd, "Python developer with AWS, Docker and React experience")
    assert 0 < scan["percent"] < 100
    assert "python" in scan["matched"] and "kubernetes" in scan["missing"]


def test_tailor_includes_ats_scan_and_demo_letter():
    result = pipeline.tailor("Python AWS Docker engineer " * 10, "Python AWS master resume")
    assert "ats_keyword_scan" in result["scores"]
    import llm
    assert "Dear Hiring Manager" in llm.complete("s", "u", kind="letter")


def test_nvidia_provider_detection(monkeypatch):
    import llm
    monkeypatch.setenv("RESUME_PROVIDER", "")
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    assert llm.detect_provider() == "nvidia"
    assert llm.active_model() == "meta/llama-3.3-70b-instruct"


def test_gemini_and_custom_provider_detection(monkeypatch):
    import llm
    monkeypatch.setenv("RESUME_PROVIDER", "")
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "RESUME_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    assert llm.detect_provider() == "gemini"
    assert llm.active_model() == "gemini-2.5-flash"
    monkeypatch.setenv("RESUME_BASE_URL", "https://zenmux.example/v1")
    assert llm.detect_provider() == "custom"


def test_extract_json_repairs_sloppy_llm_output():
    sloppy = """{
  "job_title": "Engineer",
  skills_match: 70,
  "improvements": [
    {"section": "skills", "fix": "add python"},
  ],
}"""
    d = pipeline.extract_json(sloppy)
    assert d["skills_match"] == 70 and d["improvements"][0]["section"] == "skills"


def test_job_ranking():
    import jobs as jobs_mod
    master = "Python engineer with AWS, Docker, machine learning, PyTorch experience"
    listing = [
        {"title": "Python ML Engineer", "company": "A", "description": "Python AWS machine learning PyTorch Docker " * 5},
        {"title": "Accountant", "company": "B", "description": "bookkeeping ledgers accounting payroll taxes audits " * 5},
    ]
    ranked = jobs_mod.rank(listing, master)
    assert ranked[0]["title"] == "Python ML Engineer"
    assert ranked[0]["fit"] > ranked[1]["fit"]


def test_job_html_strip():
    import jobs as jobs_mod
    assert jobs_mod._strip_html("<p>Python &amp; <b>AWS</b></p>") == "Python & AWS"


def test_freshness_filter():
    import time
    import jobs as jobs_mod
    now = time.time()
    listing = [
        {"title": "Fresh", "company": "A", "description": "x", "posted_epoch": now - 1800},
        {"title": "Old", "company": "B", "description": "x", "posted_epoch": now - 90000},
        {"title": "Unknown", "company": "C", "description": "x", "posted_epoch": None},
    ]
    fresh = jobs_mod.filter_fresh(listing, 1)
    assert [j["title"] for j in fresh] == ["Fresh"]
    assert len(jobs_mod.filter_fresh(listing, 0)) == 3


def test_epoch_parsing():
    import jobs as jobs_mod
    assert jobs_mod._epoch("2026-07-02T03:22:11Z") is not None
    assert jobs_mod._epoch("2026-07-02T03:22:11+00:00") is not None
    assert jobs_mod._epoch("garbage") is None
    assert jobs_mod._epoch("") is None


def test_query_relevance_matcher():
    import jobs as jobs_mod
    assert jobs_mod._matches("software engineer", "Senior Software Engineer", "python")
    assert not jobs_mod._matches("software engineer", "Communications Manager", "marketing pr")
    assert jobs_mod._matches("ml engineer", "Machine Learning (ML) Engineer", "")
    assert jobs_mod._matches("", "anything at all", "x")


def test_experience_level_estimation():
    import jobs as jobs_mod
    assert jobs_mod.estimate_experience_level("5+ years experience required")["level"] == "senior"
    assert jobs_mod.estimate_experience_level("Senior Staff Engineer, deep expertise")["level"] == "senior"
    assert jobs_mod.estimate_experience_level("0-2 years experience, entry level welcome")["level"] == "entry_mid"
    assert jobs_mod.estimate_experience_level("Junior developer role")["level"] == "entry_mid"
    assert jobs_mod.estimate_experience_level("Exciting opportunity to join our team")["level"] == "unclear"


def test_genuineness_scoring():
    import jobs as jobs_mod
    good = jobs_mod.score_genuineness({
        "url": "https://boards.greenhouse.io/acme/jobs/123",
        "salary": "$120,000 - $150,000",
        "description": "We are a team of 40 engineers building payment infra. " * 20,
    })
    assert good["score"] >= 70 and good["label"] == "Looks legitimate"

    bad = jobs_mod.score_genuineness({
        "url": "https://randomboard.example.com/job/1",
        "salary": "",
        "description": "Earn $5000 per week from home! No experience necessary! Send us your bank details to start. Wire transfer required for starter kit.",
    })
    assert bad["score"] < 40 and any("scam" in s for s in bad["signals"])


def test_entry_level_filter_never_silently_drops_unclear():
    import jobs as jobs_mod
    master = "python engineer"
    listing = [
        {"title": "Senior Python Engineer", "company": "A", "description": "5+ years experience python " * 5, "url": "", "salary": ""},
        {"title": "Python Engineer", "company": "B", "description": "join our growing team, python role " * 5, "url": "", "salary": ""},
    ]
    ranked = jobs_mod.rank(listing, master)
    filtered = [j for j in ranked if j["experience"]["level"] != "senior"]
    titles = [j["title"] for j in filtered]
    assert "Senior Python Engineer" not in titles
    assert "Python Engineer" in titles  # "unclear"/entry_mid jobs are kept, not dropped


def test_country_estimation():
    import jobs as jobs_mod
    assert jobs_mod.estimate_country({"location": "Austin, TX"})["is_us"] is True
    assert jobs_mod.estimate_country({"location": "New York, United States"})["is_us"] is True
    assert jobs_mod.estimate_country({"location": "London, UK"})["is_us"] is False
    assert jobs_mod.estimate_country({"location": "Berlin, Germany"})["is_us"] is False
    assert jobs_mod.estimate_country({"location": "Remote"})["is_us"] is None
    assert jobs_mod.estimate_country({"location": ""})["is_us"] is None


def test_usa_only_filter_excludes_non_us_and_ambiguous_but_keeps_visible():
    import jobs as jobs_mod
    master = "python engineer"
    listing = [
        {"title": "Python Engineer", "company": "A", "description": "python role " * 5,
         "url": "", "salary": "", "location": "Austin, TX"},
        {"title": "Python Engineer", "company": "B", "description": "python role " * 5,
         "url": "", "salary": "", "location": "London, UK"},
        {"title": "Python Engineer", "company": "C", "description": "python role " * 5,
         "url": "", "salary": "", "location": "Remote"},
    ]
    ranked = jobs_mod.rank(listing, master)
    # every job keeps a country field regardless of filtering (transparent, auditable)
    assert all("country" in j for j in ranked)
    strict = [j for j in ranked if j["country"]["is_us"] is True]
    assert [j["company"] for j in strict] == ["A"]  # only the clear-US listing survives


def test_llm_client_gets_bounded_timeout_and_no_silent_retries(monkeypatch):
    """The actual root cause of the 4-minute hang: OpenAI()/Anthropic() clients
    previously had no explicit timeout/retry limit, defaulting to ~10 minutes
    and 2 silent retries per call. Verify the fix passes bounded values."""
    import llm
    captured = {}

    class FakeResponse:
        choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = type("Chat", (), {"completions": type("Comp", (), {
                "create": staticmethod(lambda **kw: FakeResponse())
            })()})()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    llm._openai_compatible("sys", "user", 100, "test-model", "groq",
                           base_url="https://example.com", api_key="k")
    assert captured.get("timeout") == llm.LLM_TIMEOUT
    assert captured.get("max_retries") == llm.LLM_MAX_RETRIES
    assert llm.LLM_TIMEOUT <= 120  # bounded, not the SDK's ~600s default


def test_provider_timeout_error_is_clear_and_specific():
    """The write step must never fail silently or hang — timing out should
    raise a specific, actionable message naming the provider and the limit."""
    import llm
    err = llm.ProviderTimeout("nvidia", TimeoutError("slow"))
    assert "nvidia" in str(err)
    assert f"{llm.LLM_TIMEOUT:.0f}s" in str(err)


def test_provider_chain_prefers_groq_over_nvidia(monkeypatch):
    """Groq's LPU hardware is materially faster than NVIDIA's GPU-hosted free
    tier for the same models — verify it's tried first when both are set."""
    import llm
    monkeypatch.delenv("RESUME_PROVIDER", raising=False)
    monkeypatch.delenv("RESUME_BASE_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    chain = llm.provider_chain()
    assert chain.index("groq") < chain.index("nvidia")
    assert llm.detect_provider() == "groq"


def test_explicit_provider_override_disables_fallback(monkeypatch):
    """An explicit RESUME_PROVIDER is a deliberate choice — it must never be
    silently overridden by an automatic fallback, even if other keys exist."""
    import llm
    monkeypatch.setenv("RESUME_PROVIDER", "nvidia")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    assert llm.provider_chain() == ["nvidia"]


def test_automatic_fallback_on_timeout_only(monkeypatch):
    """complete() should transparently fall through to the next provider in
    the chain ONLY on a ProviderTimeout — and last_served_by() must then
    accurately report which provider really answered, not the primary."""
    import llm
    monkeypatch.delenv("RESUME_PROVIDER", raising=False)
    monkeypatch.delenv("RESUME_BASE_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    assert llm.provider_chain() == ["groq", "nvidia"]

    def fake_dispatch(provider, system, user, max_tokens, temperature, kind):
        if provider == "groq":
            raise llm.ProviderTimeout("groq", TimeoutError())
        return f"served by {provider}"

    monkeypatch.setattr(llm, "_dispatch", fake_dispatch)
    result = llm.complete("sys", "user")
    assert result == "served by nvidia"
    assert llm.last_served_by() == ("nvidia", llm.model_for("nvidia"))


def test_non_timeout_errors_do_not_trigger_fallback(monkeypatch):
    """A real error (e.g. a refusal) must surface immediately — silently
    retrying on a different provider wouldn't fix it and would hide the
    real problem."""
    import llm
    monkeypatch.delenv("RESUME_PROVIDER", raising=False)
    monkeypatch.delenv("RESUME_BASE_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    calls = []

    def fake_dispatch(provider, system, user, max_tokens, temperature, kind):
        calls.append(provider)
        raise RuntimeError("the model refused this request")

    monkeypatch.setattr(llm, "_dispatch", fake_dispatch)
    with pytest.raises(RuntimeError, match="refused"):
        llm.complete("sys", "user")
    assert calls == ["groq"]  # never tried nvidia — this wasn't a timeout


def test_all_providers_timing_out_gives_one_combined_clear_message(monkeypatch):
    import llm
    monkeypatch.delenv("RESUME_PROVIDER", raising=False)
    monkeypatch.delenv("RESUME_BASE_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")

    def fake_dispatch(provider, system, user, max_tokens, temperature, kind):
        raise llm.ProviderTimeout(provider, TimeoutError())

    monkeypatch.setattr(llm, "_dispatch", fake_dispatch)
    with pytest.raises(RuntimeError) as exc_info:
        llm.complete("sys", "user")
    msg = str(exc_info.value)
    assert "groq" in msg and "nvidia" in msg and "Nothing was faked" in msg


def test_revision_failure_keeps_the_already_written_resume(monkeypatch):
    """A slow/failed revision call must not lose the real, already-scored
    resume from the write step — it should degrade gracefully, not crash."""
    import llm
    calls = {"n": 0}

    def fake_complete(system, user, max_tokens=4096, kind="text", temperature=None):
        if kind == "resume":
            calls["n"] += 1
            if calls["n"] == 1:
                return "# Real Written Resume\nreal@example.com\n\nSome content"
            raise RuntimeError("provider timed out")  # the revision call fails
        return '{"skills_match": 60, "experience_match": 60, "industry_match": 60, "overall": 60}'

    monkeypatch.setattr(llm, "complete", fake_complete)
    result = pipeline.tailor("some job description " * 10, "some master resume")
    assert "Real Written Resume" in result["resume_markdown"]
    assert result["revisions"] == 0  # loop broke on the failed revision, didn't crash
