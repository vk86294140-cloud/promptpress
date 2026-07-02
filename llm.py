"""Provider abstraction: NVIDIA, Groq, Gemini, Anthropic, OpenAI, any
OpenAI-compatible custom endpoint (ZenMux, OpenRouter, Ollama, ...), or Demo.

Detection order (free providers first, Claude kept as the paid quality option):
RESUME_PROVIDER override > RESUME_BASE_URL (custom) > NVIDIA_API_KEY >
GROQ_API_KEY > GEMINI_API_KEY > ANTHROPIC_API_KEY > OPENAI_API_KEY > demo.
Override the model with RESUME_MODEL=<model-id>.

Custom endpoint (e.g. ZenMux): set RESUME_BASE_URL, RESUME_API_KEY, and
RESUME_MODEL to whatever that service documents.

Cost per tailored resume (2-5 calls, ~5-15K tokens):
  nvidia / groq / gemini     ~ free tiers
  anthropic claude-sonnet-5  ~ 5-15 cents   (best writing quality)
  anthropic claude-opus-4-8  ~ 50c-1.50     (only via RESUME_MODEL override)
"""

import os

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def detect_provider() -> str:
    forced = os.environ.get("RESUME_PROVIDER", "").strip().lower()
    if forced in ("anthropic", "openai", "groq", "nvidia", "gemini", "custom", "demo"):
        return forced
    if os.environ.get("RESUME_BASE_URL"):
        return "custom"
    if os.environ.get("NVIDIA_API_KEY"):
        return "nvidia"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
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
    return {
        "anthropic": DEFAULT_ANTHROPIC_MODEL,
        "openai": DEFAULT_OPENAI_MODEL,
        "groq": DEFAULT_GROQ_MODEL,
        "nvidia": DEFAULT_NVIDIA_MODEL,
        "gemini": DEFAULT_GEMINI_MODEL,
    }.get(provider, "demo")


def complete(system: str, user: str, max_tokens: int = 4096, kind: str = "text", temperature: float = None) -> str:
    """One LLM call. `kind` is only used by the demo provider to fake sensible output."""
    provider = detect_provider()
    if provider == "anthropic":
        return _anthropic(system, user, max_tokens)
    if provider == "openai":
        return _openai_compatible(system, user, max_tokens, temperature=temperature)
    if provider == "groq":
        return _openai_compatible(system, user, max_tokens, base_url=GROQ_BASE_URL,
                                  api_key=os.environ.get("GROQ_API_KEY"), temperature=temperature)
    if provider == "nvidia":
        return _openai_compatible(system, user, max_tokens, base_url=NVIDIA_BASE_URL,
                                  api_key=os.environ.get("NVIDIA_API_KEY"), temperature=temperature)
    if provider == "gemini":
        return _openai_compatible(system, user, max_tokens, base_url=GEMINI_BASE_URL,
                                  api_key=os.environ.get("GEMINI_API_KEY"), temperature=temperature)
    if provider == "custom":
        base = os.environ.get("RESUME_BASE_URL", "").strip()
        if not base or not os.environ.get("RESUME_MODEL"):
            raise RuntimeError(
                "Custom provider needs RESUME_BASE_URL, RESUME_API_KEY, and RESUME_MODEL "
                "set to what your service (e.g. ZenMux) documents."
            )
        return _openai_compatible(system, user, max_tokens, base_url=base,
                                  api_key=os.environ.get("RESUME_API_KEY", "none"), temperature=temperature)
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


def _openai_compatible(system: str, user: str, max_tokens: int,
                       base_url: str = None, api_key: str = None,
                       temperature: float = None) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key) if base_url else OpenAI()
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    response = client.chat.completions.create(
        model=active_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    return response.choices[0].message.content or ""


def _demo(kind: str) -> str:
    """Canned output so the UI and pipeline can be exercised with no API key."""
    if kind == "letter":
        return (
            "Dear Hiring Manager,\n\nYour team is building payment infrastructure at a scale "
            "I have spent six years working at. At Acme Payments I cut checkout p99 latency "
            "from 900ms to 210ms and led a zero-downtime migration of 40M monthly "
            "transactions.\n\nSincerely,\nJane Doe"
        )
    if kind == "score":
        return (
            '{"job_title": "Software Engineer", "company": "Demo Corp",'
            ' "skills_match": 88, "experience_match": 86, "industry_match": 87,'
            ' "overall": 87, "missing_keywords": ["Kubernetes"],'
            ' "improvements": [{"section": "skills", "fix": "Add the distributed-systems project to the top role"}]}'
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
