"""Read the repository's explicit real/sim runtime profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    label: str
    expected_backend: str
    host: str
    port: int
    socket_path: str
    environment: dict[str, str]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_profiles(repo_root: Path) -> dict[str, RuntimeProfile]:
    common = _read_env(repo_root / "config" / "common.env")
    profiles: dict[str, RuntimeProfile] = {}
    definitions = {
        "sim": ("仿真", "isaacsim"),
        "real": ("真机", "socketcan"),
    }
    for name, (label, expected_backend) in definitions.items():
        env = dict(common)
        env.update(_read_env(repo_root / "config" / f"{name}.env"))
        env["A1Z_PROFILE"] = name
        profiles[name] = RuntimeProfile(
            name=name,
            label=label,
            expected_backend=expected_backend,
            host=env.get("A1Z_TCP_HOST", "127.0.0.1"),
            port=int(env.get("A1Z_TCP_PORT", "0")),
            socket_path=env.get("A1Z_SOCKET_PATH", ""),
            environment=env,
        )
    return profiles
