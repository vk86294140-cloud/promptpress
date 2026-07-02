"""Provider abstraction: Anthropic (preferred), OpenAI (fallback), Demo (no key).

Set ANTHROPIC_API_KEY or OPENAI_API_KEY. If both are set, Anthropic wins.
Override with RESUME_PROVIDER=anthropic|openai|demo and RESUME_MODEL=<model-id>.
"""

import os

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_OPENAI_MODEL = "gpt-4o"


def detect_provider() -> str:
    forced = os.environ.get("RESUME_PROVIDER", "").strip().lower()
    if forced in ("anthropic", "openai", "demo"):
        return forced
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "demo"


def active_model() -> str:
    provider = detect_provider()
    override = os.environ.get("RESUME_MODEL", "").strip()
    if override:
        return override
    if provider == "anthropic":
        return DEFAULT_ANTHROPIC_MODEL
    if provider == "openai":
        return DEFAULT_OPENAI_MODEL
    return "demo"


def complete(system: str, user: str, max_tokens: int = 4096, kind: str = "text") -> str:
    """One LLM call. `kind` is only used by the demo provider to fake sensible output."""
    provider = detect_provider()
    if provider == "anthropic":
        return _anthropic(system, user, max_tokens)
    if provider == "openai":
        return _openai(system, user, max_tokens)
    return _demo(kind)


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model=active_model(),
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined this request. Rephrase and try again.")
    return "".join(block.text for block in response.content if block.type == "text")


def _openai(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=active_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def _demo(kind: str) -> str:
    """Canned output so the UI and pipeline can be exercised with no API key."""
    if kind == "score":
        return (
            '{"job_title": "Software Engineer", "company": "Demo Corp",'
            ' "skills_match": 88, "experience_match": 86, "industry_match": 87,'
            ' "overall": 87, "missing_keywords": ["Kubernetes"],'
            ' "fixes": ["Add the distributed-systems project to the top role"]}'
        )
    return (
        "# Jane Doe\n"
        "jane@example.com | (555) 010-0000 | linkedin.com/in/janedoe | github.com/janedoe\n\n"
        "Backend engineer with six years building payment and billing systems in Python and Go.\n\n"
        "## Skills\n"
        "**Languages:** Python, Go, SQL\n"
        "**Cloud & Infra:** AWS, Docker, Terraform\n"
        "**Data:** Postgres, Redis, Kafka\n\n"
        "## Experience\n"
        "**Senior Software Engineer — Acme Payments** | 2021 – Present\n"
        "- Cut checkout p99 latency from 900ms to 210ms by moving fraud checks off the hot path\n"
        "- Led the migration of 40M monthly transactions to a new ledger service with zero downtime\n"
        "- Mentored four engineers; two promoted within a year\n\n"
        "**Software Engineer — Widget Co** | 2018 – 2021\n"
        "- Built the internal billing reconciliation tool used by 30 finance staff daily\n"
        "- Reduced failed webhook deliveries 70% with a retry queue on Kafka\n\n"
        "## Education\n"
        "B.S. Computer Science, State University, 2018\n"
    )
