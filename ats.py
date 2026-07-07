"""Deterministic ATS keyword scan — no LLM, no cost, instant.

Real ATS platforms (Workday, Taleo, iCIMS, Greenhouse) do literal keyword and
phrase matching before a human sees anything. This module extracts the terms a
parser would look for in the job description and reports exactly which ones the
resume covers. It complements the LLM recruiter score: the LLM judges fit, this
verifies literal keyword coverage.
"""

import re
from collections import Counter

# words that carry no signal in a JD
STOPWORDS = set("""
a about above across after again all also an and any are as at be because been
before being below between both but by can could did do does doing down during
each few for from further had has have having he her here hers him his how i if
in into is it its itself just me more most my no nor not now of off on once only
or other our ours out over own same she should so some such than that the their
theirs them then there these they this those through to too under until up very
was we were what when where which while who whom why will with you your yours
end own use form write via per within across bring build building built help
ability able according additional applicants applications apply are basis
benefits candidate candidates click color company compensation consideration
culture day days description disability employee employees employer employment
equal etc every excellent experience experienced gender great high highly hire
hiring ideal include includes including job join like looking love make
minimum month months mission must need needed new offer opportunity opportunities
organization orientation others pay people per plus position preferred provide
qualified qualifications race range receive regard related religion remote
required requirements responsibilities responsible role salary seeking sex
sexual status strong success team teams time title today understand veteran
we're welcome well who work working world years you'll
""".split())

# short tokens that are real tech terms and must survive length filtering
KEEP_SHORT = {"go", "r", "c", "c#", "ai", "ml", "qa", "ci", "cd", "js", "ts", "ui", "ux", "db", "aws", "gcp", "api", "sql", "etl", "sre", "nlp", "llm", "rag", "cnn", "gpu"}


def _tokens(text: str):
    return [w.rstrip("./-") for w in re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]*", text.lower())]


def extract_keywords(jd: str, limit: int = 30):
    """Top single terms and two-word phrases an ATS would match on."""
    words = _tokens(jd)
    singles = Counter(
        w for w in words
        if (len(w) > 2 or w in KEEP_SHORT) and w not in STOPWORDS
    )
    bigrams = Counter(
        f"{a} {b}" for a, b in zip(words, words[1:])
        if a not in STOPWORDS and b not in STOPWORDS
        and (len(a) > 2 or a in KEEP_SHORT) and (len(b) > 2 or b in KEEP_SHORT)
    )
    # phrases that repeat are strong signals; weight them above singles
    scored = [(count * 2.5, phrase) for phrase, count in bigrams.items() if count >= 2]
    scored += [(count, w) for w, count in singles.items() if count >= 1]
    scored.sort(key=lambda x: -x[0])

    keywords, seen = [], set()
    for _, term in scored:
        if term in seen or any(term in k or k in term for k in keywords):
            continue
        keywords.append(term)
        seen.add(term)
        if len(keywords) >= limit:
            break
    return keywords


def scan(jd: str, resume_md: str) -> dict:
    """Literal keyword coverage of the resume against the JD."""
    keywords = extract_keywords(jd)
    resume_low = resume_md.lower()
    matched = [k for k in keywords if k in resume_low]
    missing = [k for k in keywords if k not in resume_low]
    percent = round(100 * len(matched) / len(keywords)) if keywords else 0
    return {"percent": percent, "matched": matched, "missing": missing}


def _sections(resume_md: str) -> dict:
    """Split a tailored resume's markdown into {section_name: text} — the text
    before the first ## heading is the header/summary."""
    parts, current, lines = {}, "summary", []
    for line in resume_md.splitlines():
        m = re.match(r"##\s+(.+)", line)
        if m:
            parts[current] = "\n".join(lines)
            current, lines = m.group(1).strip().lower(), []
        else:
            lines.append(line)
    parts[current] = "\n".join(lines)
    return parts


def change_log(jd: str, master_resume: str, tailored_md: str) -> list:
    """Provenance report for every JD keyword the tailored resume uses.

    Deterministic and LLM-free. For each JD keyword found in the tailored
    resume: which sections it landed in, and whether the exact term also
    appears in the master resume ("from master resume") or was introduced by
    the tailoring as JD vocabulary ("JD-aligned phrasing"). The second kind
    is legitimate bridging (e.g. master says "Jenkins pipelines", JD and
    tailored resume say "CI/CD") but is exactly what the user should
    double-check reflects real work — so it's flagged, never hidden."""
    master_low = (master_resume or "").lower()
    sections = _sections(tailored_md)
    log = []
    for kw in extract_keywords(jd):
        found_in = [name for name, text in sections.items() if kw in text.lower()]
        if not found_in:
            continue
        log.append({
            "keyword": kw,
            "sections": found_in,
            "source": "master resume" if kw in master_low else "JD-aligned phrasing",
            "verify": kw not in master_low,
        })
    # flagged terms first — they're the ones worth a human look
    log.sort(key=lambda e: (not e["verify"], e["keyword"]))
    return log
