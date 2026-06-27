"""Helpers for decoding camera payloads from the Isaac-side TCP server."""

from __future__ import annotations

import base64
import zlib

import numpy as np


def decode_array(payload: dict) -> np.ndarray:
    compression = payload.get("compression", "")
    if compression != "zlib":
        raise ValueError(f"Unsupported payload compression: {compression}")
    raw = zlib.decompress(base64.b64decode(payload["data_b64"]))
    arr = np.frombuffer(raw, dtype=np.dtype(str(payload["dtype"])))
    return arr.reshape(tuple(int(v) for v in payload["shape"]))
