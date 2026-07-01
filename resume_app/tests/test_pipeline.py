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
