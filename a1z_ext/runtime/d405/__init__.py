from __future__ import annotations

from .settings import D405AssetSettings

__all__ = ["D405AssetSettings", "D405WristCameraAttachment", "attach_d405_wrist_camera"]


def __getattr__(name: str):
    if name in {"D405WristCameraAttachment", "attach_d405_wrist_camera"}:
        from .asset import D405WristCameraAttachment, attach_d405_wrist_camera

        exported = {
            "D405WristCameraAttachment": D405WristCameraAttachment,
            "attach_d405_wrist_camera": attach_d405_wrist_camera,
        }
        return exported[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
