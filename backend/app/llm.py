"""Pluggable LLM providers. Provider is chosen by LLM_PROVIDER (auto = first key found).

All providers implement `generate(system, user) -> str`. If no key is configured the RAG
layer falls back to an extractive answer built from retrieved passages, so the app still
works fully offline (just less fluent).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from .config import settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class AnthropicLLM:
    name = "anthropic"

    def __init__(self):
        import anthropic

        self._anthropic = anthropic
        # Pin the endpoint so an ambient ANTHROPIC_BASE_URL (e.g. a desktop-app proxy) never receives the key.
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"],
                                          base_url=os.getenv("CIVICROUTE_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
        self.model = settings.anthropic_model

    def generate(self, system: str, user: str) -> str:
        a = self._anthropic
        kwargs = dict(
            model=self.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low"},  # short grounded answers; low effort keeps latency/cost down
        )
        try:
            try:
                # Server-side refusal fallback (opt-in default for current Opus models).
                resp = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            except a.BadRequestError as e:
                if "fallback" not in str(e).lower():
                    raise
                resp = self.client.messages.create(**kwargs)
        except a.AuthenticationError as e:
            raise LLMError("Anthropic API key is invalid") from e
        except a.RateLimitError as e:
            raise LLMError("Rate limited by Anthropic - try again shortly") from e
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise LLMError("Could not reach Anthropic API") from e
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined to answer this request")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


class GeminiLLM:
    name = "gemini"

    def __init__(self):
        from google import genai

        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        self.model = settings.gemini_model

    def generate(self, system: str, user: str) -> str:
        from google.genai import types

        try:
            resp = self.client.models.generate_content(
                model=self.model, contents=user,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.1),
            )
        except Exception as e:
            raise LLMError(f"Gemini error: {e}") from e
        return (resp.text or "").strip()


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat API: OpenAI itself, Groq (free tier) and xAI Grok."""

    ENDPOINTS = {
        # name: (api key env var, base URL, model setting)
        "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1", "openai_model"),
        "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "groq_model"),
        "xai": ("XAI_API_KEY", "https://api.x.ai/v1", "xai_model"),
    }

    def __init__(self, name: str):
        from openai import OpenAI

        key_env, base_url, model_attr = self.ENDPOINTS[name]
        self.name = name
        self.client = OpenAI(api_key=os.environ[key_env], base_url=base_url, max_retries=2, timeout=60)
        self.model = getattr(settings, model_attr)

    # Tried in order if the configured model is retired (Groq retires models regularly).
    FALLBACK_MODELS = {
        "groq": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
        "xai": ["grok-4.3", "grok-4.20"],
        "openai": ["gpt-4o-mini"],
    }

    def _replacement_model(self) -> str | None:
        try:
            available = {m.id for m in self.client.models.list().data}
        except Exception:
            return None
        for m in self.FALLBACK_MODELS.get(self.name, []):
            if m in available and m != self.model:
                return m
        return None

    def _create(self, system: str, user: str):
        return self.client.chat.completions.create(
            model=self.model, temperature=0.1, max_tokens=4000,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )

    def generate(self, system: str, user: str) -> str:
        import openai

        try:
            try:
                resp = self._create(system, user)
            except openai.NotFoundError:
                replacement = self._replacement_model()
                if not replacement:
                    raise
                log.warning("%s model %r is unavailable - switching to %r (set %s_MODEL in .env to make this permanent)",
                            self.name, self.model, replacement, self.name.upper())
                self.model = replacement
                resp = self._create(system, user)
        except openai.RateLimitError as e:
            raise LLMError(f"{self.name} rate limit reached (free tiers have per-minute/day caps) - try again shortly") from e
        except openai.AuthenticationError as e:
            raise LLMError(f"{self.name} API key is invalid") from e
        except openai.APIError as e:
            raise LLMError(f"{self.name} error: {e}") from e
        return (resp.choices[0].message.content or "").strip()


PROVIDERS = {
    "groq": (lambda: OpenAICompatibleLLM("groq"), ("GROQ_API_KEY",)),
    "anthropic": (AnthropicLLM, ("ANTHROPIC_API_KEY",)),  # only an explicit API key, never ambient tokens
    "xai": (lambda: OpenAICompatibleLLM("xai"), ("XAI_API_KEY",)),
    "gemini": (GeminiLLM, ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    "openai": (lambda: OpenAICompatibleLLM("openai"), ("OPENAI_API_KEY",)),
}
PROVIDERS["grok"] = PROVIDERS["xai"]  # alias


@lru_cache(maxsize=1)
def get_llm():
    choice = settings.llm_provider.lower()
    if choice == "none":
        return None
    order = [choice] if choice in PROVIDERS else list(PROVIDERS)
    for name in order:
        cls, keys = PROVIDERS[name]
        if choice == "auto" and not any(os.getenv(k) for k in keys):
            continue
        try:
            llm = cls()
            log.info("LLM provider: %s (%s)", name, llm.model)
            return llm
        except Exception as exc:
            log.warning("Could not initialise %s: %s", name, exc)
    log.info("No LLM configured - using extractive answers")
    return None
