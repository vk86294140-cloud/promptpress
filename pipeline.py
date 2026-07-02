"""Tailor pipeline: write -> score -> (revise -> score) until every dimension >= 85."""

import json
import os
import re

import ats
import llm
import prompts

TARGET = 85
MAX_REVISIONS = int(os.environ.get("RESUME_MAX_REVISIONS", "2"))
DIMENSIONS = ("skills_match", "experience_match", "industry_match", "overall")


def _repair_json(text: str) -> str:
    """Fix the sloppy JSON open models emit: trailing commas, curly quotes, bare keys."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    text = re.sub(r",\s*([}\]])", r"\1", text)                       # trailing commas
    text = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_ -]*?)\s*:', r'\1"\2":', text)  # bare keys
    return text


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply, tolerating code fences, prose, and sloppy syntax."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_repair_json(text))


def score(job_description: str, resume_md: str) -> dict:
    """Recruiter/ATS check of any resume text against a JD (the PartyRock-style checker)."""
    last_error = None
    for _ in range(2):  # one retry on unparseable scorer output
        raw = llm.complete(
            prompts.SCORER_SYSTEM,
            prompts.scorer_user(job_description, resume_md),
            max_tokens=2048,
            kind="score",
            temperature=0.1,  # near-deterministic so the same resume scores consistently
        )
        try:
            scores = extract_json(raw)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
    else:
        raise RuntimeError(f"scorer returned unparseable output twice: {last_error}")
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
    try:
        scores = score(job_description, resume_md)
    except Exception:
        # never lose a written resume to a scoring hiccup — degrade gracefully
        scores = {k: 0 for k in DIMENSIONS}
        scores.update({"job_title": "", "company": "", "missing_keywords": [],
                       "improvements": [], "score_error": "Scoring failed this run — the resume itself is fine. Re-run Check to score it."})
    scores["ats_keyword_scan"] = ats.scan(job_description, resume_md)

    revisions = 0
    while revisions < MAX_REVISIONS and not scores.get("score_error") and not _meets_target(scores):
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
        revised_scores["ats_keyword_scan"] = ats.scan(job_description, revised)
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
