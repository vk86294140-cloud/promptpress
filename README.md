# Resume Tailor

Paste a job description → get a **one-page resume tailored to that job**, written
in a plain human voice, scored by an AI recruiter, and revised until skills /
experience / industry / overall match are all **≥ 85%** (or the honest ceiling is
reached — it never invents experience to force a score).

```
job description ─► writer (senior-recruiter prompt) ─► recruiter/ATS scorer ─► <85%? revise (max 2x) ─► one-page resume + scores
```

## Running it — just double-click, no typing

**Windows:** double-click **`start.bat`** in the `resume_app` folder.
**macOS/Linux:** double-click **`start.sh`** (or run `./start.sh` once to make it
executable, then double-click).

That single file does everything, every time:
- Pulls the latest code and installs any new dependencies
- First run only: creates the Python environment, then opens a template so you
  can paste in one free API key (Notepad on Windows, your default editor on
  Mac/Linux) — save and close it to continue
- Starts the server and **opens your browser automatically** to
  `http://localhost:8080`

After the first run there is nothing to configure — every future launch is
just: double-click, wait a few seconds, browser opens. Keep that window open
while you use the app; closing it (or Ctrl+C) stops the server.

Your key lives in a local `.env` file (copied from `.env.example` on first
run) — it's gitignored, so it's never committed or pushed, and it survives
every update since `start.bat`/`start.sh` never touch it after creating it.

### Manual setup (if you prefer typing commands, or `start.bat` doesn't fit your setup)

```powershell
cd C:\Users\vamsi\Desktop\Job-Automation\resume_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt openai

# Claude (recommended)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

uvicorn app:app --port 8080
```

Open **http://localhost:8080**. macOS/Linux: `source .venv/bin/activate` and `export ANTHROPIC_API_KEY=...`.

To update manually: `git pull` then `pip install -r requirements.txt`. Your
`data/` folder (master resume + generated outputs) is gitignored and never
touched by updates.

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

Auto-detection order (first key found wins): **NVIDIA → Groq → Gemini → Anthropic → OpenAI**.
Set your NVIDIA key and everything runs free; keep your Anthropic key saved too —
it is only used when you explicitly ask for it.

**Easiest way to set any of these:** put them in your `.env` file (see
[Running it](#running-it--just-double-click-no-typing) above) — `start.bat`/
`start.sh` read it automatically, no PowerShell needed. The `$env:` commands
below are only for the manual-setup path.

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

## Find Jobs (job discovery)

The **Find Jobs** tab searches live job boards and ranks every listing by keyword
fit against your master resume — instantly and at zero AI cost. One click on
"Tailor" turns a listing into a tailored resume; "Apply link" opens the posting.

- **Remotive, RemoteOK, Jobicy** (remote) and **The Muse** (incl. on-site US jobs): work out of the box, no keys.
- **Adzuna** (US + 15 countries, salary data, on-site jobs): free key from
  developer.adzuna.com — set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`
  (and optionally `ADZUNA_COUNTRY`, default `us`) on the server.
- **JSearch** (Google-for-Jobs: LinkedIn/Indeed/Glassdoor postings — the best
  source for very fresh jobs): free tier at rapidapi.com/search/jsearch —
  subscribe to the JSearch API and set `JSEARCH_API_KEY` to your RapidAPI key.
- **Jooble** (large Indeed-style aggregator): request a free key at
  jooble.org/api/about → `JOOBLE_API_KEY`.
- **Findwork** (developer jobs, date-sorted): free key at
  findwork.dev/developers/api → `FINDWORK_API_KEY`.
- **Arbeitnow** (Europe + remote): keyless, included automatically.

### Beating the applicant crowd

There is no public API that reports applicant counts (that data lives inside
LinkedIn only). The working strategy: **apply to jobs posted within the last
hour — they have almost no applicants yet.** Use the freshness dropdown
("Last hour" / "Last 3 hours"), check a few times a day, and tailor + apply
immediately when a high-fit fresh posting appears. Each listing shows its age;
green minutes = the window where you're among the first applicants.

## Go live (share with friends, free)

The app is deployable as-is. Recommended: **Render.com free tier** (no card needed).

1. Push this code to your GitHub repo (`resume-tailor`).
2. Go to render.com → New → **Blueprint** → connect the repo (it reads `render.yaml`).
3. When asked, set two environment variables:
   - `APP_PASSWORD` — the shared access key you'll give friends
   - `NVIDIA_API_KEY` (or `GROQ_API_KEY` / `GEMINI_API_KEY`) — the free LLM key everyone shares
4. Deploy. You get a URL like `https://resume-tailor-xxxx.onrender.com`.
5. Send friends the URL + the access key.

Each visitor enters a first name once (their own private workspace: own master
resume, own history — nobody sees anyone else's data) and the access key once.
Both are remembered by their browser.

Security model (right-sized for a private 10-user app): one shared access key on
every API route, per-user data isolation, filename sanitization on all paths, no
accounts/emails stored, HTTPS provided by Render. Don't post the URL publicly —
anyone with URL + key can use your LLM quota.

Free-tier notes: the service sleeps after ~15 idle minutes (first request takes
~40s to wake up).
Alternatives: Fly.io (`fly launch` — reads the Dockerfile) or any Docker host.

### Free-tier persistence (no disk)

Render's free tier has **no persistent disk** — the server's filesystem resets
every time you redeploy (push new code). That would normally mean everyone's
saved master resume vanishes on the next update. The app compensates
automatically:

- Every "Save master resume" also mirrors the text into that browser's
  `localStorage`, keyed to the person's workspace name.
- On page load, if the server comes back empty (fresh deploy) but the browser
  has a backup, the app **silently restores it to the server** and shows a
  one-line notice. The next visit is normal.

What this does **not** cover: generated resume/cover-letter **history** —
that's server-only and is lost on redeploy on the free tier. Download the
PDF/DOCX for anything you want to keep. If that matters more than the $0
price, Render's paid Starter plan (~$7/mo) adds a real persistent disk — just
add a `disk:` block back to `render.yaml` at that point.

## Tests

```bash
pip install pytest && pytest tests/ -q     # runs offline in demo mode, no API key needed
```

## Files

- `start.bat` / `start.sh` — double-click launcher (update, install, load `.env`, open browser)
- `.env.example` — copy to `.env` and fill in your keys (gitignored, stays local)
- `app.py` — FastAPI server (multi-user workspaces, auth, all endpoints)
- `pipeline.py` — write → score → revise loop
- `prompts.py` — recruiter writer / ATS scorer / reviser prompts + style rules
- `llm.py` — NVIDIA / Groq / Gemini / Anthropic / OpenAI / custom provider switch
- `ats.py` — deterministic (LLM-free) keyword/phrase scanner
- `jobs.py` — job discovery (Remotive / Adzuna / JSearch), freshness filtering, fit ranking
- `render.py` — ATS-safe PDF/DOCX/cover-letter rendering
- `static/index.html` — the whole UI (no build step)
- `Dockerfile` / `render.yaml` — deployment kit for going live (see [Go live](#go-live-share-with-friends-free))
- `data/` — master resumes + generated outputs, per user (gitignored, stays local)
