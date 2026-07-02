# Resume Tailor

Paste a job description → get a **one-page resume tailored to that job**, written
in a plain human voice, scored by an AI recruiter, and revised until skills /
experience / industry / overall match are all **≥ 85%** (or the honest ceiling is
reached — it never invents experience to force a score).

```
job description ─► writer (senior-recruiter prompt) ─► recruiter/ATS scorer ─► <85%? revise (max 2x) ─► one-page resume + scores
```

## Getting updates

The app lives in a git repo — no zips. To update:

```powershell
cd C:\Users\vamsi\Desktop\Job-Automation\resume_app
git pull
pip install -r requirements.txt   # in case dependencies changed
```

Your `data/` folder (master resume + generated outputs) is gitignored and never touched by updates.

## Setup (Windows PowerShell)

```powershell
cd C:\Users\vamsi\Desktop\Job-Automation\resume_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Claude (recommended)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# or OpenAI instead
# $env:OPENAI_API_KEY = "sk-..."
# pip install openai

uvicorn app:app --port 8080
```

Open **http://localhost:8080**

macOS/Linux: same thing with `source .venv/bin/activate` and `export ANTHROPIC_API_KEY=...`.

## How to use

1. **My Resume tab** — paste your *master resume* once (every job, project,
   skill, metric you have — the more real detail, the better) and save.
2. **Tailor tab** — paste a job description, press **Ctrl+Enter**.
3. Review the score card and the rendered one-pager. **Download DOCX** (safest
   for ATS portals) or **Download PDF** (text-based, standard fonts, clickable
   email/LinkedIn/GitHub links) — both are generated server-side, no browser
   printing. Every result is also saved to `data/outputs/` and listed in the
   **History** tab.

### ATS notes

- Upload the **DOCX** to job portals (Workday, Eightfold, Taleo, iCIMS…) —
  their parsers handle it most reliably, so your auto-filled profile comes out
  clean instead of scrambled.
- The PDF uses Helvetica with a real text layer (verified extractable), no
  header location, no tables in the body, standard section names — the things
  ATS parsers care about.

## Which API — Claude, OpenAI, or Groq?

All three work. Auto-detection order: `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` →
`GROQ_API_KEY`, or force one with `RESUME_PROVIDER=anthropic|openai|groq`.

| Provider  | Default model               | Cost per tailored resume | Quality |
|-----------|-----------------------------|--------------------------|---------|
| Anthropic | `claude-sonnet-5`           | ~5–15¢                   | Best writing (recommended for jobs you care about) |
| NVIDIA    | `meta/llama-3.3-70b-instruct` | ~free (dev tier)       | Good, slightly more generic phrasing |
| Groq      | `llama-3.3-70b-versatile`   | ~free                    | Good, fastest |
| OpenAI    | `gpt-4o`                    | ~5–15¢                   | Good |

Use NVIDIA (key from build.nvidia.com — needs `pip install openai` once):

```powershell
$env:RESUME_PROVIDER = "nvidia"
$env:NVIDIA_API_KEY = "nvapi-your-key"
uvicorn app:app --port 8080
```

Use Groq (PowerShell — needs `pip install openai` once):

```powershell
$env:RESUME_PROVIDER = "groq"
$env:GROQ_API_KEY = "gsk_your_groq_key"
uvicorn app:app --port 8080
```

Want maximum quality for one important application? `$env:RESUME_MODEL = "claude-opus-4-8"`
(that's the ~$1/run model — the default is now Sonnet at a tenth of the cost).

## Honesty guardrail (read this)

The prompts hard-require the model to use **only facts from your master
resume**. It reorders, rewords, and re-emphasizes — it never adds employers,
titles, skills, or metrics you don't have. Missing JD requirements show up in
the "Not in your background" list so you can prepare to address them in an
interview instead of being surprised.

## Tests

```bash
pip install pytest && pytest tests/ -q     # runs offline in demo mode, no API key needed
```

## Files

- `app.py` — FastAPI server (UI, master resume storage, tailor endpoint, history)
- `pipeline.py` — write → score → revise loop
- `prompts.py` — recruiter writer / ATS scorer / reviser prompts + style rules
- `llm.py` — Anthropic / OpenAI / demo provider switch
- `static/index.html` — the whole UI (no build step)
- `data/` — your master resume + generated outputs (gitignored, stays local)
