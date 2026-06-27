#!/usr/bin/env python3

"""Single-window live mosaic preview for a locally attached Intel RealSense D405."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageOps, ImageTk


DEFAULT_RGB_DEVICE = "/dev/video4"
DEFAULT_DEPTH_DEVICE = "/dev/video0"


class StreamReader:
    def __init__(
        self,
        *,
        device: str,
        input_format: str,
        width: int,
        height: int,
        fps: int,
        output_pix_fmt: str,
        bytes_per_frame: int,
        title: str,
    ) -> None:
        self.device = device
        self.input_format = input_format
        self.width = width
        self.height = height
        self.fps = fps
        self.output_pix_fmt = output_pix_fmt
        self.bytes_per_frame = bytes_per_frame
        self.title = title
        self.proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "nobuffer",
            "-f",
            "v4l2",
            "-input_format",
            self.input_format,
            "-video_size",
            f"{self.width}x{self.height}",
            "-i",
            self.device,
            "-an",
            "-sn",
            "-vf",
            f"fps={self.fps}",
            "-pix_fmt",
            self.output_pix_fmt,
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-",
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

    def read_frame(self) -> Image.Image:
        if self.proc is None or self.proc.stdout is None:
            raise RuntimeError(f"{self.title} stream is not running")
        data = self._read_exactly(self.bytes_per_frame)
        if self.output_pix_fmt == "rgb24":
            return Image.frombytes("RGB", (self.width, self.height), data)
        if self.output_pix_fmt == "gray16le":
            return Image.frombytes("I;16", (self.width, self.height), data)
        raise RuntimeError(f"Unsupported output pixel format: {self.output_pix_fmt}")

    def _read_exactly(self, size: int) -> bytes:
        if self.proc is None or self.proc.stdout is None:
            raise RuntimeError(f"{self.title} stream is not running")
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.proc.stdout.read(size - len(chunks))
            if not chunk:
                raise RuntimeError(f"{self.title} stream ended mid-frame")
            chunks.extend(chunk)
        return bytes(chunks)

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=1.0)
        self.proc = None


class PreviewApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        rgb_device: str,
        depth_device: str,
        width: int,
        height: int,
        panel_width: int,
        fps: int,
    ) -> None:
        self.root = root
        self.root.title("D405 Mosaic Preview")
        self.root.minsize(panel_width * 2 + 48, panel_width * height // width + 92)

        self.width = width
        self.height = height
        self.panel_width = panel_width
        self.panel_height = max(1, round(height * panel_width / width))
        self.frame_interval_ms = max(15, int(1000 / max(1, fps)))

        self.status_var = tk.StringVar(value="Starting streams...")
        self._photo: ImageTk.PhotoImage | None = None
        self._running = True
        self._tick_after_id: str | None = None
        self._last_error: str | None = None

        self.rgb_stream = StreamReader(
            device=rgb_device,
            input_format="yuyv422",
            width=width,
            height=height,
            fps=fps,
            output_pix_fmt="rgb24",
            bytes_per_frame=width * height * 3,
            title="RGB",
        )
        self.depth_stream = StreamReader(
            device=depth_device,
            input_format="gray16le",
            width=width,
            height=height,
            fps=fps,
            output_pix_fmt="gray16le",
            bytes_per_frame=width * height * 2,
            title="Depth",
        )

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            self.rgb_stream.start()
            self.depth_stream.start()
        except Exception as exc:
            self._fatal(f"Failed to start D405 streams: {exc}")
            return

        self._schedule_next(50)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        self.canvas = tk.Label(frame, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        status = ttk.Label(frame, textvariable=self.status_var, anchor="w")
        status.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    def _schedule_next(self, delay_ms: int) -> None:
        if not self._running:
            return
        self._tick_after_id = self.root.after(delay_ms, self._tick)

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            rgb = self.rgb_stream.read_frame()
            depth_raw = self.depth_stream.read_frame()
            mosaic = self._compose_mosaic(rgb, depth_raw)
            self._photo = ImageTk.PhotoImage(mosaic)
            self.canvas.configure(image=self._photo)
            self.status_var.set(
                f"RGB {self.width}x{self.height} | Depth {self.width}x{self.height} | Refresh ~{1000 // self.frame_interval_ms} FPS"
            )
            self._last_error = None
        except Exception as exc:
            message = str(exc)
            self.status_var.set(f"Preview stalled: {message}")
            if message != self._last_error:
                print(message, file=sys.stderr)
                self._last_error = message
            self._restart_streams()
        self._schedule_next(self.frame_interval_ms)

    def _restart_streams(self) -> None:
        self.rgb_stream.stop()
        self.depth_stream.stop()
        try:
            self.rgb_stream.start()
            self.depth_stream.start()
        except Exception:
            pass

    def _compose_mosaic(self, rgb: Image.Image, depth_raw: Image.Image) -> Image.Image:
        rgb_panel = ImageOps.contain(rgb, (self.panel_width, self.panel_height))
        rgb_panel = self._letterbox(rgb_panel)

        depth_gray = depth_raw.convert("L")
        depth_gray = ImageOps.autocontrast(depth_gray, cutoff=(1, 1))
        depth_panel = ImageOps.colorize(depth_gray, black="#210a3a", white="#f9e721", mid="#27808e")
        depth_panel = ImageOps.contain(depth_panel, (self.panel_width, self.panel_height))
        depth_panel = self._letterbox(depth_panel)

        mosaic = Image.new("RGB", (self.panel_width * 2 + 16, self.panel_height), "#111111")
        mosaic.paste(rgb_panel, (0, 0))
        mosaic.paste(depth_panel, (self.panel_width + 16, 0))
        return mosaic

    def _letterbox(self, image: Image.Image) -> Image.Image:
        canvas = Image.new("RGB", (self.panel_width, self.panel_height), "#111111")
        x = (self.panel_width - image.width) // 2
        y = (self.panel_height - image.height) // 2
        canvas.paste(image, (x, y))
        return canvas

    def _fatal(self, message: str) -> None:
        self.status_var.set(message)
        self.root.after(50, lambda: messagebox.showerror("D405 Mosaic Preview", message))

    def _on_close(self) -> None:
        self._running = False
        if self._tick_after_id is not None:
            self.root.after_cancel(self._tick_after_id)
            self._tick_after_id = None
        self.rgb_stream.stop()
        self.depth_stream.stop()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgb-device", default=DEFAULT_RGB_DEVICE)
    parser.add_argument("--depth-device", default=DEFAULT_DEPTH_DEVICE)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--panel-width", type=int, default=640)
    parser.add_argument("--fps", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = tk.Tk()
    PreviewApp(
        root,
        rgb_device=args.rgb_device,
        depth_device=args.depth_device,
        width=args.width,
        height=args.height,
        panel_width=args.panel_width,
        fps=args.fps,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
