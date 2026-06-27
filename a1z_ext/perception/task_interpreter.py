"""Simple task interpretation for the initial non-grasping data loop."""

from __future__ import annotations

from a1z_ext.interfaces.schemas import TaskSpec


def interpret_text_instruction(instruction: str) -> TaskSpec:
    text = instruction.strip()
    if not text:
        raise ValueError("instruction must not be empty")
    normalized = text.lower()
    attributes = [token for token in normalized.replace(",", " ").split() if token not in {"pick", "grab", "the"}]
    return TaskSpec.from_text(text, attributes=attributes)

