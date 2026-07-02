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

## Which API? Free first, Claude kept as the quality option

Auto-detection order (first key found wins): **NVIDIA → Groq → Anthropic → OpenAI**.
Set your NVIDIA key and everything runs free; keep your Anthropic key saved too —
it is only used when you explicitly ask for it.

| Priority | Provider  | Default model                 | Cost per resume | Notes |
|----------|-----------|-------------------------------|-----------------|-------|
| 0        | Custom    | your `RESUME_MODEL`           | varies          | Any OpenAI-compatible endpoint (ZenMux, OpenRouter, Ollama...) via `RESUME_BASE_URL` + `RESUME_API_KEY` + `RESUME_MODEL` |
| 1        | NVIDIA    | `meta/llama-3.3-70b-instruct` | free (dev tier) | Key from build.nvidia.com |
| 2        | Groq      | `llama-3.3-70b-versatile`     | free            | Fastest |
| 3        | Gemini    | `gemini-2.5-flash`            | free tier       | Key from aistudio.google.com |
| 4        | Anthropic | `claude-sonnet-5`             | ~5–15¢          | Best writing — for jobs you really want |
| 5        | OpenAI    | `gpt-4o`                      | ~5–15¢          | |

Setup (PowerShell — `pip install openai` once for NVIDIA/Groq/OpenAI):

```powershell
$env:NVIDIA_API_KEY = "nvapi-your-key"     # free default (build.nvidia.com)
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # optional, only used on request
uvicorn app:app --port 8080
```

Gemini (free key from aistudio.google.com):

```powershell
$env:GEMINI_API_KEY = "AIza-your-key"
```

ZenMux or any other OpenAI-compatible service (copy base URL + model id from their docs):

```powershell
$env:RESUME_BASE_URL = "<base url from the service's docs>"
$env:RESUME_API_KEY  = "<their key>"
$env:RESUME_MODEL    = "<model id from their catalog>"
```

Per-run overrides:
- `$env:RESUME_PROVIDER = "anthropic"` — switch to Claude quality for an important application
- `$env:RESUME_MODEL = "meta/llama-3.1-405b-instruct"` — NVIDIA's biggest model (slower, stronger)
- Avoid `claude-opus-4-8` unless you accept ~$1+/run — that was the source of the high cost

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
