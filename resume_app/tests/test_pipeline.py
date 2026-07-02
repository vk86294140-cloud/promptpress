import os
import sys
from pathlib import Path

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
        for i in range(12)
    )
    _, pages_full = render._build_pdf(long_md, 1.0)
    assert pages_full > 1  # would overflow at full size
    fitted = render.to_pdf(long_md)
    # "/Type /Page" is a prefix of "/Type /Pages", so subtract the tree node
    assert fitted.count(b"/Type /Page") - fitted.count(b"/Type /Pages") == 1
