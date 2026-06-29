"""Configuration objects for OpenAI-compatible VLM providers."""

from __future__ import annotations

from dataclasses import dataclass
import os


_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4.1-mini",
    },
    "gpt": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4.1-mini",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "model": "moonshot-v1-8k-vision-preview",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "model": "moonshot-v1-8k-vision-preview",
    },
}


@dataclass(frozen=True, slots=True)
class LLMProviderConfig:
    """Runtime config for a VLM provider using the Chat Completions shape."""

    provider: str
    model: str
    base_url: str
    api_key_env: str
    timeout_s: float = 30.0
    max_tokens: int = 512
    temperature: float = 0.0

    @classmethod
    def for_provider(
        cls,
        provider: str,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str | None = None,
        timeout_s: float = 30.0,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> "LLMProviderConfig":
        provider_key = provider.strip().lower()
        defaults = _PROVIDER_DEFAULTS.get(provider_key, {})
        resolved_model = model or defaults.get("model")
        resolved_base_url = base_url or defaults.get("base_url")
        resolved_api_key_env = api_key_env or defaults.get("api_key_env")

        if not resolved_model:
            raise ValueError("LLM model must be configured")
        if not resolved_base_url:
            raise ValueError("LLM base_url must be configured")
        if not resolved_api_key_env:
            raise ValueError("LLM api_key_env must be configured")

        return cls(
            provider=provider_key,
            model=resolved_model,
            base_url=resolved_base_url.rstrip("/"),
            api_key_env=resolved_api_key_env,
            timeout_s=float(timeout_s),
            max_tokens=int(max_tokens),
            temperature=float(temperature),
        )

    @classmethod
    def from_env(cls, prefix: str = "A1Z_VLM_") -> "LLMProviderConfig":
        provider = os.environ.get(f"{prefix}PROVIDER", "openai")
        return cls.for_provider(
            provider,
            model=os.environ.get(f"{prefix}MODEL") or None,
            base_url=os.environ.get(f"{prefix}BASE_URL") or None,
            api_key_env=os.environ.get(f"{prefix}API_KEY_ENV") or None,
            timeout_s=float(os.environ.get(f"{prefix}TIMEOUT_S", "30.0")),
            max_tokens=int(os.environ.get(f"{prefix}MAX_TOKENS", "512")),
            temperature=float(os.environ.get(f"{prefix}TEMPERATURE", "0.0")),
        )

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)
