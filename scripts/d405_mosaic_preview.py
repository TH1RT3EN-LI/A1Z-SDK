#!/usr/bin/env python3

"""Standalone RGB-D preview using the same profile-aware bridge as the GUI."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "console"))

from a1z_console.camera_protocol import CameraProtocolClient  # noqa: E402
from a1z_console.profiles import load_profiles  # noqa: E402


class PreviewApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        profile_name: str,
        refresh_ms: int,
        preview_max_width: int,
    ) -> None:
        self.root = root
        self.root.title(f"A1Z RGB-D Preview · {profile_name}")
        self.root.minsize(920, 560)
        self._client = CameraProtocolClient(load_profiles(ROOT)[profile_name])
        self._refresh_ms = max(100, int(refresh_ms))
        self._preview_max_width = max(320, int(preview_max_width))
        self._photo: ImageTk.PhotoImage | None = None
        self._after_id: str | None = None
        self._last_error = ""

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        self._image_label = ttk.Label(frame, anchor=tk.CENTER)
        self._image_label.pack(fill=tk.BOTH, expand=True)
        self._status = tk.StringVar(value="正在连接 ROS RGB-D 相机桥…")
        ttk.Label(frame, textvariable=self._status, anchor=tk.W).pack(
            fill=tk.X,
            pady=(8, 0),
        )
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._schedule(10)

    def _schedule(self, delay_ms: int | None = None) -> None:
        self._after_id = self.root.after(
            self._refresh_ms if delay_ms is None else int(delay_ms),
            self._refresh,
        )

    def _refresh(self) -> None:
        try:
            payload = self._client.request(
                "camera_capture",
                {"preview_max_width": self._preview_max_width},
                timeout_s=5.0,
            )
            png = base64.b64decode(payload["preview_png_b64"])
            image = Image.open(BytesIO(png))
            image.load()
            self._photo = ImageTk.PhotoImage(image)
            self._image_label.configure(image=self._photo)
            self._status.set(
                f"{payload['profile']} · {payload['camera_source']} · "
                f"{payload['width']}×{payload['height']} · "
                f"同步差 {float(payload['sync_delta_ms']):.1f} ms"
            )
            self._last_error = ""
        except Exception as exc:
            message = str(exc)
            self._status.set(f"RGB-D 链路离线：{message}")
            if message != self._last_error:
                print(message, file=sys.stderr)
                self._last_error = message
        self._schedule()

    def _close(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["sim", "real"], default="real")
    parser.add_argument("--refresh-ms", type=int, default=500)
    parser.add_argument("--preview-max-width", type=int, default=960)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = tk.Tk()
    try:
        PreviewApp(
            root,
            profile_name=args.profile,
            refresh_ms=args.refresh_ms,
            preview_max_width=args.preview_max_width,
        )
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("A1Z RGB-D Preview", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
