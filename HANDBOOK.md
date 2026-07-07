# Resume Tailor — Owner's Handbook

Everything you need to use the app, host it for friends, and keep it running.
The [README](README.md) is the technical reference; this is the plain-language
guide.

---

## Part 1 — Using the app

### First-time setup (once per person)

1. Open the app (locally: double-click `start.bat` / `start.sh`; hosted: open
   the URL you were given and enter the access key once).
2. Enter a workspace name when asked (your first name is fine). Everything you
   save is private to that name — pick one and stick with it, on every device
   you use.
3. Go to the **My Resume** tab and paste your **master resume**: every job,
   project, skill, metric, certification, and school you have — not a polished
   one-pager, a complete inventory. Plain text is fine. The more real detail
   here, the better every tailored resume gets. Click **Save**.

This works for any profession — software, construction management, nursing,
finance. The app maps whatever the job posting asks for to whatever your
resume actually says.

### Tailoring a resume (the everyday flow)

1. **Tailor tab** → paste the full job posting → **Tailor my resume**
   (or Ctrl+Enter). Takes a few seconds to about a minute.
2. Read the score card:
   - **Skills / Experience / Industry / Overall** — an AI recruiter's
     judgment. 85%+ means "interview pile".
   - **ATS keywords** — the percentage of the posting's literal keywords your
     resume covers (this is what automated screeners check).
   - **Not in your background** — requirements you genuinely don't have.
     Nothing is invented to hide them; be ready to address these in an
     interview.
   - **Keyword provenance (change log)** — every job-posting keyword the
     resume uses, and where it came from. Terms flagged in orange were
     introduced as job-posting vocabulary — read each one and confirm it
     honestly describes work you did. If one doesn't, remove it before
     applying.
3. Download **DOCX** for uploading to job portals (Workday, Taleo, iCIMS
   parse it most reliably) or **PDF** for emailing a human.
4. Optional: **Cover letter** button generates a matching letter from the
   same facts.

Every result is saved in your **History** tab.

### Finding jobs

**Find Jobs tab** → type a job title → Search. Free, instant, no AI cost.
- **Freshness dropdown**: "Last hour" postings have almost no applicants yet —
  the single biggest edge. Check a few times a day.
- **USA only**: hides listings that don't clearly resolve to a US location.
- **Entry/mid-level only**: hides listings that explicitly read Senior/Staff+.
- Each listing shows a legitimacy read (scam-pattern check), a US/Non-US
  badge, and a fit % against *your* resume. One click on **Tailor** turns a
  listing into a tailored resume.

### The one rule that never bends

The app only ever uses facts from your master resume. It reorders, rewords,
and translates your real work into the job posting's vocabulary — it never
invents employers, titles, dates, degrees, or metrics. If a score looks low,
the honest fix is adding more *real* detail to your master resume, not
fabricating. The change log exists so you can verify this on every single run.

### Deleting your data

**My Resume tab → Delete all my data** removes your master resume, all
generated history, and this browser's backup. Nothing survives; there are no
server-side copies or backups.

---

## Part 2 — Hosting it (both options are $0)

### Option A — Host on Render (recommended for sharing)

One deployment in the cloud; you and your friends each get a private
workspace at the same URL. Free tier, no credit card.

**One-time setup (~10 minutes):**

1. Make sure the code is in a GitHub repo you own.
2. Create a free account at [render.com](https://render.com) (sign in with
   GitHub).
3. Click **New → Blueprint**, pick your repo. Render reads `render.yaml`
   automatically.
4. It asks for two values:
   - `APP_PASSWORD` — invent a password; this is what you'll share with
     friends.
   - `NVIDIA_API_KEY` (or `GROQ_API_KEY` / `GEMINI_API_KEY`) — your free LLM
     key. Everyone shares this one key.
5. Click deploy. In a few minutes you get a URL like
   `https://resume-tailor-xxxx.onrender.com`.

**Inviting someone:** send them the URL and the password. That's it. They
pick their own workspace name on first visit; their resume and history are
theirs alone. This works for any number of friends — each new person is just
a new workspace name, zero setup on your side.

**Free-tier facts to know:**
- The app **sleeps after ~15 idle minutes**; the first visit after that takes
  ~40 seconds to wake. Normal, not broken.
- **No persistent disk**: redeploys reset the server's files. Master resumes
  auto-restore from each person's browser backup on next visit. Generated
  history doesn't survive redeploys — download PDFs/DOCX you want to keep.
- The built-in rate limit (30 AI runs per person per hour) protects your
  shared LLM quota. Change it with a `RESUME_RATE_LIMIT` env var in Render.

### Option B — Run it on your own computer

**Just you:** double-click `start.bat` (Windows) or `start.sh` (Mac/Linux).
It updates itself, installs anything new, and opens your browser. Your `.env`
file holds your keys and is never overwritten or committed.

**You + a friend for an evening (no deploy):**
1. Start the app normally.
2. In a second terminal: `npx localtunnel --port 8080`
   (or `ngrok http 8080` with a free ngrok account).
3. Send your friend the printed URL. They use the app through your machine —
   their workspace is still separate from yours.
4. Ctrl+C the tunnel when done. Nothing stays online.

Use Option A instead if the sharing is ongoing — Option B only works while
your computer is on.

---

## Part 3 — Keeping it running

### Updating the app

- **Local:** the launcher pulls the latest code on every start — updating is
  automatic. Manual: `git pull` then `pip install -r requirements.txt`.
- **Render:** push to the connected branch; Render rebuilds and swaps
  automatically, and only switches traffic once the new version is healthy.

### Checking it's healthy

- Open `/api/status` on your URL — it returns the running version and which
  LLM provider is active. If the version doesn't match your latest code, the
  deploy didn't finish (check Render's deploy log).
- Every push to GitHub runs the automated test suite
  (**Actions** tab on the repo) — red X means don't deploy that commit.

### When something breaks

| Symptom | Cause | Fix |
|---|---|---|
| "Access key required" | Wrong/missing password | Re-enter the key; rotate it in Render → Environment if compromised |
| "No LLM API key configured" | Key not set on the server | Add `NVIDIA_API_KEY` (or another) in Render → Environment, redeploy |
| "Timed out" errors | Free LLM provider is slow/down | Retry; or set a different provider's key; or raise `RESUME_LLM_TIMEOUT` |
| Rate-limit message (429) | Someone hit the hourly cap | Wait, or raise `RESUME_RATE_LIMIT` in Render → Environment |
| First visit takes ~40s | Free tier waking from sleep | Normal — subsequent requests are instant |
| Resume gone after update | Free-tier disk reset | Reopens automatically from browser backup on that person's next visit |
| App looks stale/old | Deploy didn't finish, or (local) zombie server | Check `/api/status` version; local: the launcher auto-kills stale servers |

### Rolling back a bad update

Render dashboard → your service → **Events** → find the last good deploy →
**Rollback to this deploy**. Live again in ~1 minute. (Or `git revert` the
bad commit and push.)

### Rotating secrets

- **App password:** change `APP_PASSWORD` in Render → Environment; tell your
  friends the new one. Old sessions stop working immediately.
- **LLM key:** generate a fresh key at the provider, swap it in Render →
  Environment. Never paste keys in chats, commits, or the frontend — env
  vars only.

### Costs to expect

$0 by default: Render free tier + a free LLM provider (NVIDIA/Groq/Gemini).
The only optional costs: Claude for highest writing quality (~5–15¢ per
resume, only when you set `RESUME_PROVIDER=anthropic`), and Render's Starter
plan (~$7/mo) if you ever want history to survive redeploys.
