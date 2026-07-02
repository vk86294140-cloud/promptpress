"""Job discovery: search live job boards and rank results by fit
against the user's master resume. Stdlib-only, no LLM calls (free + instant).

Sources:
- Remotive (remote jobs, full descriptions) — no API key needed
- Adzuna (16 countries, salary data) — free key from developer.adzuna.com
  via ADZUNA_APP_ID + ADZUNA_APP_KEY
"""

import json
import os
import re
import urllib.parse
import urllib.request

import ats

TIMEOUT = 15


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "resume-tailor/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


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
        f"&what={urllib.parse.quote(query)}"
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
            "description": _strip_html(j.get("description", ""))[:8000],
        })
    return jobs


def rank(jobs: list, master_resume: str) -> list:
    """Fit-score each job's description against the master resume (keyword scan)."""
    for job in jobs:
        text = f"{job['title']} {job['description']}"
        job["fit"] = ats.scan(text, master_resume)["percent"] if job["description"] else 0
    jobs.sort(key=lambda j: -j["fit"])
    return jobs


def search(query: str, location: str, master_resume: str, limit: int = 15) -> dict:
    """Search all available boards, rank by fit, return the top matches."""
    jobs, errors = [], []
    for name, fetch in (("remotive", lambda: _remotive(query)),
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
    ranked = rank(unique, master_resume)[:limit]
    return {
        "jobs": ranked,
        "errors": errors,
        "adzuna_enabled": bool(os.environ.get("ADZUNA_APP_ID")),
    }
