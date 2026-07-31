"""Read the repository's explicit real/sim runtime profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ManualMotionDefaults:
    """Operator-facing jog defaults selected by motion characteristics."""

    speed_rad_s: float = 0.5
    joint_step_deg: float = 2.0
    linear_step_mm: int = 10
    angular_step_deg: float = 5.0


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    label: str
    expected_backend: str
    host: str
    port: int
    socket_path: str
    environment: dict[str, str]
    camera_host: str = "127.0.0.1"
    camera_port: int = 0
    supports_hardware_inspection: bool = False
    supports_offline_maintenance: bool = False
    manual_motion_defaults: ManualMotionDefaults = field(
        default_factory=ManualMotionDefaults
    )


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
        "sim": (
            "仿真",
            "isaacsim",
            False,
            False,
            ManualMotionDefaults(),
        ),
        "real": (
            "真机",
            "socketcan",
            True,
            True,
            ManualMotionDefaults(
                speed_rad_s=0.25,
                joint_step_deg=1.0,
                linear_step_mm=5,
                angular_step_deg=2.0,
            ),
        ),
    }
    for name, (
        label,
        expected_backend,
        supports_hardware_inspection,
        supports_offline_maintenance,
        manual_motion_defaults,
    ) in definitions.items():
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
            camera_host=env.get("A1Z_CAMERA_BRIDGE_HOST", "127.0.0.1"),
            camera_port=int(env.get("A1Z_CAMERA_BRIDGE_PORT", "0")),
            supports_hardware_inspection=supports_hardware_inspection,
            supports_offline_maintenance=supports_offline_maintenance,
            manual_motion_defaults=manual_motion_defaults,
        )
    return profiles
