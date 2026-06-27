"""Image payload helpers for VLM requests."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LLMImage:
    """Image content represented as a data URL for OpenAI-compatible APIs."""

    data_url: str
    detail: str = "auto"

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        mime_type: str = "image/png",
        detail: str = "auto",
    ) -> "LLMImage":
        return cls(data_url=bytes_to_data_url(data, mime_type=mime_type), detail=detail)

    @classmethod
    def from_file(cls, path: str | Path, *, detail: str = "auto") -> "LLMImage":
        return cls(data_url=image_file_to_data_url(path), detail=detail)

    def as_message_part(self) -> dict[str, object]:
        return {
            "type": "image_url",
            "image_url": {
                "url": self.data_url,
                "detail": self.detail,
            },
        }


def bytes_to_data_url(data: bytes, *, mime_type: str = "image/png") -> str:
    encoded = b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def image_file_to_data_url(path: str | Path) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return bytes_to_data_url(source.read_bytes(), mime_type=mime_type)
