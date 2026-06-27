"""Small OpenAI-compatible VLM client.

The client intentionally uses only the Python standard library so the robot
runtime can choose its own SDKs later without changing the ROS entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import LLMProviderConfig
from .images import LLMImage


class LLMClientError(RuntimeError):
    """Raised when a VLM request cannot be completed."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    raw: dict[str, Any]


class LLMClient:
    """Blocking client for one-off text+image VLM requests."""

    def __init__(self, config: LLMProviderConfig) -> None:
        self._config = config

    @property
    def config(self) -> LLMProviderConfig:
        return self._config

    def complete_with_images(
        self,
        *,
        text: str,
        images: list[LLMImage],
        system_text: str | None = None,
    ) -> LLMResponse:
        if not images:
            raise LLMClientError("at least one image is required for a VLM request")

        payload = self.build_chat_payload(text=text, images=images, system_text=system_text)
        raw = self._post_json(payload)
        return LLMResponse(
            provider=self._config.provider,
            model=self._config.model,
            content=_extract_first_content(raw),
            raw=raw,
        )

    def build_chat_payload(
        self,
        *,
        text: str,
        images: list[LLMImage],
        system_text: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})

        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        content.extend(image.as_message_part() for image in images)
        messages.append({"role": "user", "content": content})

        return {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = self._config.api_key
        if not api_key:
            raise LLMClientError(
                f"missing API key: set environment variable {self._config.api_key_env}"
            )

        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self._config.chat_completions_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self._config.timeout_s) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"VLM HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise LLMClientError(f"VLM request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMClientError("VLM request timed out") from exc

        try:
            decoded = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError("VLM response was not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise LLMClientError("VLM response JSON must be an object")
        return decoded


def _extract_first_content(raw: dict[str, Any]) -> str:
    try:
        choice = raw["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMClientError("VLM response did not contain choices[0].message.content") from exc

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ]
        return "".join(text_parts)
    return str(content)
