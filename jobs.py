"""Job discovery: search live job boards and rank results by fit
against the user's master resume. Stdlib-only, no LLM calls (free + instant).

Sources (all fetched in one search, merged and de-duplicated):
- Remotive (remote jobs, full descriptions) — no API key needed
- RemoteOK (remote jobs, epoch timestamps) — no API key needed
- Jobicy (remote jobs) — no API key needed
- Adzuna (16 countries, salary data) — free key from developer.adzuna.com
  via ADZUNA_APP_ID + ADZUNA_APP_KEY
- JSearch via RapidAPI (Google-for-Jobs: LinkedIn/Indeed/Glassdoor postings,
  best freshness) — free tier key via JSEARCH_API_KEY

Freshness: every job carries posted_epoch/age_minutes; search() can filter to
jobs posted within the last N hours — a just-posted job has few applicants.
"""

import datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request

import ats

TIMEOUT = 15


def _epoch(iso: str):
    """Parse an ISO-ish timestamp to epoch seconds; None when unparseable."""
    if not iso:
        return None
    try:
        cleaned = iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return None


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "resume-tailor/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _matches(query: str, *texts) -> bool:
    """True when every significant query word appears in the combined text
    (boards without server-side search return their whole feed)."""
    words = [w for w in re.findall(r"[a-z0-9+#.]+", query.lower())
             if len(w) > 2 or w in ats.KEEP_SHORT]
    blob = " ".join(t or "" for t in texts).lower()
    return all(w in blob for w in words) if words else True


def _remoteok(query: str):
    data = _get_json("https://remoteok.com/api")
    jobs = []
    for j in (data[1:] if isinstance(data, list) else []):  # element 0 is a legal notice
        title = j.get("position") or ""
        desc = _strip_html(j.get("description", ""))
        tags = " ".join(j.get("tags") or [])
        if not _matches(query, title, tags, desc[:1000]):
            continue
        url = j.get("url") or ""
        salary = ""
        if j.get("salary_min"):
            salary = f"${int(j['salary_min']):,}"
            if j.get("salary_max"):
                salary += f" – ${int(j['salary_max']):,}"
        jobs.append({
            "title": title,
            "company": j.get("company", ""),
            "location": j.get("location") or "Remote",
            "salary": salary,
            "url": url if url.startswith("http") else "https://remoteok.com" + url,
            "source": "remoteok",
            "posted_epoch": int(j["epoch"]) if j.get("epoch") else _epoch(j.get("date", "")),
            "description": (desc + " " + tags)[:8000],
        })
    return jobs


def _jobicy(query: str):
    url = "https://jobicy.com/api/v2/remote-jobs?count=50"
    jobs = []
    for j in _get_json(url).get("jobs", []):
        title = j.get("jobTitle", "")
        desc = _strip_html(j.get("jobDescription") or j.get("jobExcerpt") or "")
        industry = " ".join(j.get("jobIndustry") or []) if isinstance(j.get("jobIndustry"), list) else str(j.get("jobIndustry") or "")
        if not _matches(query, title, industry, desc[:1000]):
            continue
        jobs.append({
            "title": title,
            "company": j.get("companyName", ""),
            "location": j.get("jobGeo", "Remote"),
            "salary": "",
            "url": j.get("url", ""),
            "source": "jobicy",
            "posted_epoch": _epoch(j.get("pubDate", "")),
            "description": desc[:8000],
        })
    return jobs


def _remotive(query: str):
    url = "https://remotive.com/api/remote-jobs?limit=30&search=" + urllib.parse.quote(query)
    jobs = []
    for j in _get_json(url).get("jobs", []):
        jobs.append({
            "title": j.get("title", ""),
            "company": j.get("company_name", ""),
            "location": j.get("candidate_required_location", "Remote"),
            "salary": j.get("salary", ""),
            "url": j.get("url", ""),
            "source": "remotive",
            "posted_epoch": _epoch(j.get("publication_date", "")),
            "description": _strip_html(j.get("description", ""))[:8000],
        })
    return jobs


def _adzuna(query: str, location: str):
    app_id = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        return []
    country = os.environ.get("ADZUNA_COUNTRY", "us")
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        f"?app_id={app_id}&app_key={app_key}&results_per_page=25"
        f"&what={urllib.parse.quote(query)}&sort_by=date&max_days_old=2"
        + (f"&where={urllib.parse.quote(location)}" if location else "")
        + "&content-type=application/json"
    )
    jobs = []
    for j in _get_json(url).get("results", []):
        salary = ""
        if j.get("salary_min"):
            salary = f"${int(j['salary_min']):,}"
            if j.get("salary_max"):
                salary += f" – ${int(j['salary_max']):,}"
        jobs.append({
            "title": j.get("title", ""),
            "company": (j.get("company") or {}).get("display_name", ""),
            "location": (j.get("location") or {}).get("display_name", ""),
            "salary": salary,
            "url": j.get("redirect_url", ""),
            "source": "adzuna",
            "posted_epoch": _epoch(j.get("created", "")),
            "description": _strip_html(j.get("description", ""))[:8000],
        })
    return jobs


def _jsearch(query: str, location: str):
    """Google-for-Jobs aggregator (LinkedIn/Indeed/Glassdoor postings) via RapidAPI."""
    key = os.environ.get("JSEARCH_API_KEY", "")
    if not key:
        return []
    q = query + (f" in {location}" if location else "")
    url = ("https://jsearch.p.rapidapi.com/search?num_pages=1&date_posted=today&query="
           + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        "User-Agent": "resume-tailor/1.0",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    jobs = []
    for j in data.get("data", []):
        loc = ", ".join(x for x in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if x)
        salary = ""
        if j.get("job_min_salary"):
            salary = f"${int(j['job_min_salary']):,}"
            if j.get("job_max_salary"):
                salary += f" – ${int(j['job_max_salary']):,}"
        jobs.append({
            "title": j.get("job_title", ""),
            "company": j.get("employer_name", ""),
            "location": loc or ("Remote" if j.get("job_is_remote") else ""),
            "salary": salary,
            "url": j.get("job_apply_link", ""),
            "source": j.get("job_publisher", "jsearch").lower(),
            "posted_epoch": j.get("job_posted_at_timestamp"),
            "description": _strip_html(j.get("job_description", ""))[:8000],
        })
    return jobs


def rank(jobs: list, master_resume: str) -> list:
    """Fit-score each job's description against the master resume (keyword scan)."""
    for job in jobs:
        text = f"{job['title']} {job['description']}"
        job["fit"] = ats.scan(text, master_resume)["percent"] if job["description"] else 0
    jobs.sort(key=lambda j: -j["fit"])
    return jobs


def filter_fresh(jobs: list, max_age_hours: float) -> list:
    """Keep jobs posted within the window (jobs without a timestamp are dropped)."""
    if not max_age_hours:
        return jobs
    cutoff = time.time() - max_age_hours * 3600
    return [j for j in jobs if j.get("posted_epoch") and j["posted_epoch"] >= cutoff]


def search(query: str, location: str, master_resume: str,
           limit: int = 15, max_age_hours: float = 0) -> dict:
    """Search all available boards, filter by freshness, rank by fit."""
    jobs, errors = [], []
    for name, fetch in (("jsearch", lambda: _jsearch(query, location)),
                        ("remotive", lambda: _remotive(query)),
                        ("remoteok", lambda: _remoteok(query)),
                        ("jobicy", lambda: _jobicy(query)),
                        ("adzuna", lambda: _adzuna(query, location))):
        try:
            jobs.extend(fetch())
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    # de-dup by title+company
    seen, unique = set(), []
    for j in jobs:
        key = (j["title"].lower(), j["company"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(j)
    fresh = filter_fresh(unique, max_age_hours)
    now = time.time()
    for j in fresh:
        j["age_minutes"] = int((now - j["posted_epoch"]) / 60) if j.get("posted_epoch") else None
    ranked = rank(fresh, master_resume)[:limit]
    return {
        "jobs": ranked,
        "errors": errors,
        "adzuna_enabled": bool(os.environ.get("ADZUNA_APP_ID")),
        "jsearch_enabled": bool(os.environ.get("JSEARCH_API_KEY")),
        "total_before_freshness_filter": len(unique),
    }
