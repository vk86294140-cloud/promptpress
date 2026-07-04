"""Provider abstraction: NVIDIA, Groq, Gemini, Anthropic, OpenAI, any
OpenAI-compatible custom endpoint (ZenMux, OpenRouter, Ollama, ...), or Demo.

Provider chain (first configured key wins as primary; the rest are automatic
fallbacks tried ONLY when the primary times out, never on other errors):
RESUME_PROVIDER override (forces exactly that one provider, no fallback) >
RESUME_BASE_URL (custom) > GROQ_API_KEY > NVIDIA_API_KEY > GEMINI_API_KEY >
ANTHROPIC_API_KEY > OPENAI_API_KEY > demo.

Groq is tried before NVIDIA by default: Groq's LPU hardware serves these
models markedly faster than NVIDIA's GPU-hosted free-tier endpoint, and a
fallback only adds a call when the primary actually fails — the common case
(primary succeeds) is exactly as fast as calling one provider directly.

Override the model with RESUME_MODEL=<model-id> (applies to whichever
provider ends up serving the call).

Cost per tailored resume (2-4 calls, ~5-15K tokens total):
  groq / nvidia / gemini     ~ free tiers
  anthropic claude-sonnet-5  ~ 3-6 cents typically (best writing quality)
  anthropic claude-opus-4-8  ~ 50c-1.50     (only via RESUME_MODEL override)
"""

import os
import threading

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_DEFAULT_MODELS = {
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "openai": DEFAULT_OPENAI_MODEL,
    "groq": DEFAULT_GROQ_MODEL,
    "nvidia": DEFAULT_NVIDIA_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
}

_KNOWN_PROVIDERS = ("anthropic", "openai", "groq", "nvidia", "gemini", "custom", "demo")

# Which provider/model actually served the most recent call, per-thread (the
# dev server runs sync routes in a threadpool, so a plain module global would
# leak across concurrent requests). Used to report the TRUE provider after a
# fallback, instead of the static "primary" name.
_local = threading.local()


def provider_chain() -> list:
    """Ordered list of providers to try. An explicit RESUME_PROVIDER means
    exactly that one provider, deliberately with NO automatic fallback — an
    explicit choice is never silently overridden."""
    forced = os.environ.get("RESUME_PROVIDER", "").strip().lower()
    if forced in _KNOWN_PROVIDERS:
        return [forced]

    chain = []
    if os.environ.get("RESUME_BASE_URL"):
        chain.append("custom")
    if os.environ.get("GROQ_API_KEY"):
        chain.append("groq")
    if os.environ.get("NVIDIA_API_KEY"):
        chain.append("nvidia")
    if os.environ.get("GEMINI_API_KEY"):
        chain.append("gemini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        chain.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        chain.append("openai")
    return chain or ["demo"]


def detect_provider() -> str:
    """The primary provider (chain[0]) — used for the status badge and as the
    default before any fallback has happened on this thread."""
    return provider_chain()[0]


def model_for(provider: str) -> str:
    override = os.environ.get("RESUME_MODEL", "").strip()
    if override:
        return override
    return _DEFAULT_MODELS.get(provider, "demo")


def active_model() -> str:
    return model_for(detect_provider())


def last_served_by() -> tuple:
    """(provider, model) that actually served the most recent complete() call
    on this thread — accurate even after a fallback, unlike detect_provider()."""
    return getattr(_local, "provider", detect_provider()), getattr(_local, "model", active_model())


# Every provider call is bounded to this many seconds, with NO silent SDK
# retries. Without this, the openai/anthropic SDKs default to ~10 minutes per
# call plus up to 2 automatic retries — and a tailor run chains multiple such
# calls (write, score, revision passes). One slow free-tier call anywhere in
# that chain could silently run past any frontend timeout. Bounding each call
# means a slow provider fails fast and predictably instead of hanging.
LLM_TIMEOUT = float(os.environ.get("RESUME_LLM_TIMEOUT", "45"))
LLM_MAX_RETRIES = int(os.environ.get("RESUME_LLM_MAX_RETRIES", "0"))


class ProviderTimeout(RuntimeError):
    """Raised when one provider in the chain times out — the only error type
    complete() will silently fall through to the next provider for. Any other
    exception (bad config, refusal, etc.) propagates immediately, since trying
    a different provider wouldn't fix it."""

    def __init__(self, provider: str, exc: Exception):
        self.provider = provider
        super().__init__(
            f"the {provider} provider didn't respond within {LLM_TIMEOUT:.0f}s "
            f"(it may be overloaded on its free tier) [{exc.__class__.__name__}]"
        )


def complete(system: str, user: str, max_tokens: int = 4096, kind: str = "text", temperature: float = None) -> str:
    """One LLM call, with automatic fallback across the provider chain — but
    ONLY on a timeout. `kind` is only used by the demo provider to fake
    sensible output."""
    chain = provider_chain()
    failures = []
    for provider in chain:
        try:
            text = _dispatch(provider, system, user, max_tokens, temperature, kind)
            _local.provider, _local.model = provider, model_for(provider)
            return text
        except ProviderTimeout as exc:
            failures.append(str(exc))
            continue
    if len(chain) == 1:
        raise RuntimeError(
            f"The AI provider failed: {failures[0]}. Nothing was faked. Try again, "
            f"or add a second free key (GROQ_API_KEY/NVIDIA_API_KEY/GEMINI_API_KEY) "
            f"as a fallback."
        )
    raise RuntimeError(
        f"All {len(chain)} configured providers timed out — " + "; ".join(failures) +
        ". Nothing was faked. This usually means every free tier you have is "
        "overloaded right now; try again shortly."
    )


def _dispatch(provider: str, system: str, user: str, max_tokens: int, temperature: float, kind: str) -> str:
    model = model_for(provider)
    if provider == "anthropic":
        return _anthropic(system, user, max_tokens, model)
    if provider == "openai":
        return _openai_compatible(system, user, max_tokens, model, provider, temperature=temperature)
    if provider == "groq":
        return _openai_compatible(system, user, max_tokens, model, provider, base_url=GROQ_BASE_URL,
                                  api_key=os.environ.get("GROQ_API_KEY"), temperature=temperature)
    if provider == "nvidia":
        return _openai_compatible(system, user, max_tokens, model, provider, base_url=NVIDIA_BASE_URL,
                                  api_key=os.environ.get("NVIDIA_API_KEY"), temperature=temperature)
    if provider == "gemini":
        return _openai_compatible(system, user, max_tokens, model, provider, base_url=GEMINI_BASE_URL,
                                  api_key=os.environ.get("GEMINI_API_KEY"), temperature=temperature)
    if provider == "custom":
        base = os.environ.get("RESUME_BASE_URL", "").strip()
        if not base or not os.environ.get("RESUME_MODEL"):
            raise RuntimeError(
                "Custom provider needs RESUME_BASE_URL, RESUME_API_KEY, and RESUME_MODEL "
                "set to what your service (e.g. ZenMux) documents."
            )
        return _openai_compatible(system, user, max_tokens, model, provider, base_url=base,
                                  api_key=os.environ.get("RESUME_API_KEY", "none"), temperature=temperature)
    return _demo(kind)


def _anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
    import anthropic as anthropic_sdk

    client = anthropic_sdk.Anthropic(timeout=LLM_TIMEOUT, max_retries=LLM_MAX_RETRIES)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except (anthropic_sdk.APITimeoutError, anthropic_sdk.APIConnectionError) as exc:
        raise ProviderTimeout("anthropic", exc) from exc
    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined this request. Rephrase and try again.")
    return "".join(block.text for block in response.content if block.type == "text")


def _openai_compatible(system: str, user: str, max_tokens: int, model: str, provider: str,
                       base_url: str = None, api_key: str = None,
                       temperature: float = None) -> str:
    import openai as openai_sdk
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=LLM_TIMEOUT, max_retries=LLM_MAX_RETRIES) \
        if base_url else OpenAI(timeout=LLM_TIMEOUT, max_retries=LLM_MAX_RETRIES)
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
    except (openai_sdk.APITimeoutError, openai_sdk.APIConnectionError) as exc:
        raise ProviderTimeout(provider, exc) from exc
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
