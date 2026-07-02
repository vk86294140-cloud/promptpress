"""Tailor pipeline: write -> score -> (revise -> score) until every dimension >= 85."""

import json
import os
import re

import llm
import prompts

TARGET = 85
MAX_REVISIONS = int(os.environ.get("RESUME_MAX_REVISIONS", "2"))
DIMENSIONS = ("skills_match", "experience_match", "industry_match", "overall")


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply, tolerating code fences and prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def score(job_description: str, resume_md: str) -> dict:
    """Recruiter/ATS check of any resume text against a JD (the PartyRock-style checker)."""
    raw = llm.complete(
        prompts.SCORER_SYSTEM,
        prompts.scorer_user(job_description, resume_md),
        max_tokens=2048,
        kind="score",
    )
    scores = extract_json(raw)
    for key in DIMENSIONS:
        scores[key] = max(0, min(100, int(scores.get(key, 0))))
    scores.setdefault("missing_keywords", [])
    scores.setdefault("improvements", [])
    scores.setdefault("job_title", "")
    scores.setdefault("company", "")
    return scores


def _meets_target(scores: dict) -> bool:
    return all(scores[key] >= TARGET for key in DIMENSIONS)


def tailor(job_description: str, master_resume: str) -> dict:
    resume_md = llm.complete(
        prompts.WRITER_SYSTEM,
        prompts.writer_user(job_description, master_resume),
        max_tokens=4096,
        kind="resume",
    ).strip()
    scores = score(job_description, resume_md)

    revisions = 0
    while revisions < MAX_REVISIONS and not _meets_target(scores):
        revised = llm.complete(
            prompts.REVISER_SYSTEM,
            prompts.reviser_user(
                job_description, master_resume, resume_md,
                json.dumps(scores, indent=2),
            ),
            max_tokens=4096,
            kind="resume",
        ).strip()
        revised_scores = score(job_description, revised)
        # keep the revision only if it didn't make things worse
        if revised_scores["overall"] >= scores["overall"]:
            resume_md, scores = revised, revised_scores
        revisions += 1

    return {
        "resume_markdown": resume_md,
        "scores": scores,
        "revisions": revisions,
        "target_met": _meets_target(scores),
        "provider": llm.detect_provider(),
        "model": llm.active_model(),
    }
