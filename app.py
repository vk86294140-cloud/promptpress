"""Resume Tailor — paste a job description, get a one-page tailored resume.

Run:  uvicorn app:app --port 8080     (from the resume_app directory)
Open: http://localhost:8080
"""

import datetime
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import llm
import pipeline
import prompts
import render

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

app = FastAPI(title="Resume Tailor")


def _check_auth(request):
    """Shared-password gate for hosted deployments. No APP_PASSWORD = open (local use)."""
    if APP_PASSWORD and request.headers.get("x-app-key", "") != APP_PASSWORD:
        raise HTTPException(401, "Access key required. Ask the person who shared this app for the key.")


def _user_slug(request) -> str:
    raw = (request.headers.get("x-user") or "default").lower()
    return re.sub(r"[^a-z0-9-]", "", raw)[:32] or "default"


def _master_file(user: str) -> Path:
    f = DATA_DIR / "users" / user / "master_resume.txt"
    legacy = DATA_DIR / "master_resume.txt"
    if user == "default" and not f.exists() and legacy.exists():
        return legacy  # pre-multiuser installs keep working
    return f


def _output_dir(user: str) -> Path:
    return DATA_DIR / "users" / user / "outputs"


class MasterResume(BaseModel):
    text: str


class TailorRequest(BaseModel):
    job_description: str


class CheckRequest(BaseModel):
    job_description: str
    resume_text: str


def _require_api_key():
    if llm.detect_provider() == "demo" and os.environ.get("RESUME_PROVIDER", "").lower() != "demo":
        raise HTTPException(
            400,
            "NO API KEY FOUND — refusing to generate a fake sample resume. In the SAME "
            "PowerShell window that runs the server, set your real key first: "
            '$env:RESUME_PROVIDER = "groq" and $env:GROQ_API_KEY = "gsk_..." '
            '(or $env:ANTHROPIC_API_KEY = "sk-ant-..."), then restart uvicorn.',
        )


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60] or "job"


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/status")
def status(request: Request):
    user = _user_slug(request)
    mf = _master_file(user)
    return {
        "provider": llm.detect_provider(),
        "model": llm.active_model(),
        "needs_key": bool(APP_PASSWORD),
        "user": user,
        "has_master_resume": mf.exists() and mf.stat().st_size > 0,
    }


@app.get("/api/master")
def get_master(request: Request):
    _check_auth(request)
    mf = _master_file(_user_slug(request))
    text = mf.read_text(encoding="utf-8") if mf.exists() else ""
    return {"text": text}


@app.post("/api/master")
def save_master(body: MasterResume, request: Request):
    _check_auth(request)
    mf = DATA_DIR / "users" / _user_slug(request) / "master_resume.txt"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(body.text, encoding="utf-8")
    return {"saved": True, "chars": len(body.text)}


@app.post("/api/tailor")
def tailor(body: TailorRequest, request: Request):
    _check_auth(request)
    _require_api_key()
    user = _user_slug(request)
    mf = _master_file(user)
    jd = body.job_description.strip()
    if len(jd) < 80:
        raise HTTPException(400, "That doesn't look like a full job description. Paste the whole posting.")
    if not mf.exists() or not mf.read_text(encoding="utf-8").strip():
        raise HTTPException(400, "Save your master resume first (My Resume tab).")

    master = mf.read_text(encoding="utf-8")
    try:
        result = pipeline.tailor(jd, master)
    except Exception as exc:  # surface LLM/parse errors to the UI
        raise HTTPException(502, f"Generation failed: {exc}") from exc

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{_slug(result['scores'].get('company') or '')}-{_slug(result['scores'].get('job_title') or '')}"
    out = _output_dir(user)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.md").write_text(result["resume_markdown"], encoding="utf-8")
    (out / f"{name}.json").write_text(
        json.dumps({**result, "job_description": jd}, indent=2), encoding="utf-8"
    )
    result["saved_as"] = name
    return result


@app.get("/api/history")
def history(request: Request):
    _check_auth(request)
    out = _output_dir(_user_slug(request))
    if not out.exists():
        return {"items": []}
    items = []
    for meta in sorted(out.glob("*.json"), reverse=True):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            items.append({
                "name": meta.stem,
                "job_title": data.get("scores", {}).get("job_title", ""),
                "company": data.get("scores", {}).get("company", ""),
                "overall": data.get("scores", {}).get("overall", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return {"items": items}


@app.post("/api/check")
def check(body: CheckRequest, request: Request):
    """Score any existing resume against a JD and return section improvements."""
    _check_auth(request)
    _require_api_key()
    jd = body.job_description.strip()
    resume = body.resume_text.strip()
    if len(jd) < 80:
        raise HTTPException(400, "Paste the whole job description.")
    if len(resume) < 120:
        raise HTTPException(400, "Paste the full resume text to check.")
    try:
        scores = pipeline.score(jd, resume)
    except Exception as exc:
        raise HTTPException(502, f"Check failed: {exc}") from exc
    return {"scores": scores, "provider": llm.detect_provider(), "model": llm.active_model()}


class CoverRequest(BaseModel):
    job_description: str
    resume_markdown: str


class CoverDocxRequest(BaseModel):
    letter_text: str


@app.post("/api/cover")
def cover(body: CoverRequest, request: Request):
    """Generate a matching cover letter from the tailored resume + JD."""
    _check_auth(request)
    _require_api_key()
    jd = body.job_description.strip()
    resume = body.resume_markdown.strip()
    if len(jd) < 80 or len(resume) < 120:
        raise HTTPException(400, "Need the job description and a tailored resume first.")
    try:
        letter = llm.complete(
            prompts.COVER_SYSTEM, prompts.cover_user(jd, resume),
            max_tokens=1024, kind="letter",
        ).strip()
    except Exception as exc:
        raise HTTPException(502, f"Cover letter failed: {exc}") from exc
    return {"letter": letter}


@app.post("/api/cover-docx")
def cover_docx(body: CoverDocxRequest, request: Request):
    _check_auth(request)
    """Render already-generated letter text to DOCX (no LLM call)."""
    if len(body.letter_text.strip()) < 50:
        raise HTTPException(400, "No letter text.")
    return Response(
        render.letter_to_docx(body.letter_text),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="cover-letter.docx"'},
    )


@app.get("/api/download/{name}/{fmt}")
def download(name: str, fmt: str, request: Request, key: str = "", user: str = ""):
    # downloads come from <a>/location navigation, which can't set headers —
    # accept the credentials as query params too
    if APP_PASSWORD and key != APP_PASSWORD and request.headers.get("x-app-key", "") != APP_PASSWORD:
        raise HTTPException(401, "Access key required.")
    u = re.sub(r"[^a-z0-9-]", "", (user or _user_slug(request)))[:32] or "default"
    safe = Path(name).name
    md_path = _output_dir(u) / f"{safe}.md"
    if not md_path.exists():
        raise HTTPException(404, "not found")
    md = md_path.read_text(encoding="utf-8")
    if fmt == "pdf":
        data, media = render.to_pdf(md), "application/pdf"
    elif fmt == "docx":
        data, media = render.to_docx(md), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        raise HTTPException(400, "format must be pdf or docx")
    return Response(
        data, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe}.{fmt}"'},
    )


@app.get("/api/history/{name}")
def history_item(name: str, request: Request):
    _check_auth(request)
    path = _output_dir(_user_slug(request)) / f"{Path(name).name}.json"
    if not path.exists():
        raise HTTPException(404, "not found")
    return json.loads(path.read_text(encoding="utf-8"))
