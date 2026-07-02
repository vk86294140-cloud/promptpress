"""Resume Tailor — paste a job description, get a one-page tailored resume.

Run:  uvicorn app:app --port 8080     (from the resume_app directory)
Open: http://localhost:8080
"""

import datetime
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import llm
import pipeline
import render

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "outputs"
MASTER_FILE = DATA_DIR / "master_resume.txt"

app = FastAPI(title="Resume Tailor")


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
def status():
    return {
        "provider": llm.detect_provider(),
        "model": llm.active_model(),
        "has_master_resume": MASTER_FILE.exists() and MASTER_FILE.stat().st_size > 0,
    }


@app.get("/api/master")
def get_master():
    text = MASTER_FILE.read_text(encoding="utf-8") if MASTER_FILE.exists() else ""
    return {"text": text}


@app.post("/api/master")
def save_master(body: MasterResume):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_FILE.write_text(body.text, encoding="utf-8")
    return {"saved": True, "chars": len(body.text)}


@app.post("/api/tailor")
def tailor(body: TailorRequest):
    _require_api_key()
    jd = body.job_description.strip()
    if len(jd) < 80:
        raise HTTPException(400, "That doesn't look like a full job description. Paste the whole posting.")
    if not MASTER_FILE.exists() or not MASTER_FILE.read_text(encoding="utf-8").strip():
        raise HTTPException(400, "Save your master resume first (My Resume tab).")

    master = MASTER_FILE.read_text(encoding="utf-8")
    try:
        result = pipeline.tailor(jd, master)
    except Exception as exc:  # surface LLM/parse errors to the UI
        raise HTTPException(502, f"Generation failed: {exc}") from exc

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{_slug(result['scores'].get('company') or '')}-{_slug(result['scores'].get('job_title') or '')}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.md").write_text(result["resume_markdown"], encoding="utf-8")
    (OUTPUT_DIR / f"{name}.json").write_text(
        json.dumps({**result, "job_description": jd}, indent=2), encoding="utf-8"
    )
    result["saved_as"] = name
    return result


@app.get("/api/history")
def history():
    if not OUTPUT_DIR.exists():
        return {"items": []}
    items = []
    for meta in sorted(OUTPUT_DIR.glob("*.json"), reverse=True):
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
def check(body: CheckRequest):
    """Score any existing resume against a JD and return section improvements."""
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


@app.get("/api/download/{name}/{fmt}")
def download(name: str, fmt: str):
    safe = Path(name).name
    md_path = OUTPUT_DIR / f"{safe}.md"
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
def history_item(name: str):
    if _slug(name) != name.lower().replace("--", "-") and "/" in name:
        raise HTTPException(400, "bad name")
    path = OUTPUT_DIR / f"{Path(name).name}.json"
    if not path.exists():
        raise HTTPException(404, "not found")
    return json.loads(path.read_text(encoding="utf-8"))
