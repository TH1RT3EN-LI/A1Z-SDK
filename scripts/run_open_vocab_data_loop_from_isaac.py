#!/usr/bin/env python3

"""Run the non-grasping open-vocabulary data loop from Isaac via the shared frame source."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import carb
import omni.kit.app
import omni.kit.async_engine

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.dirname(__file__)
SDK_DIR = os.path.join(ROOT_DIR, "vendor", "GALAXEA-A1Z")
SDK_VENV_DIR = os.environ.get("A1Z_SDK_VENV_DIR", "/home/ubuntu/.venvs/a1z-sdk")
SDK_VENV_SITE_DIRS = [
    os.path.join(SDK_VENV_DIR, "lib", "python3.11", "site-packages"),
    os.path.join(
        SDK_VENV_DIR,
        "lib",
        "python3.11",
        "site-packages",
        "cmeel.prefix",
        "lib",
        "python3.11",
        "site-packages",
    ),
]

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SDK_DIR not in sys.path:
    sys.path.insert(0, SDK_DIR)
for site_dir in SDK_VENV_SITE_DIRS:
    if os.path.isdir(site_dir) and site_dir not in sys.path:
        sys.path.insert(0, site_dir)

from a1z_ext.perception.pipeline import run_pipeline_from_frame_capture
from a1z_ext.runtime.frame_sources.isaac_rgbd import IsaacD405FrameSource, IsaacD405FrameSourceConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the non-grasping open-vocabulary data loop from Isaac.")
    parser.add_argument(
        "--instruction",
        default=os.environ.get("A1Z_OPEN_VOCAB_INSTRUCTION"),
        help="Natural-language pick instruction.",
    )
    parser.add_argument(
        "--stage-path",
        default=os.environ.get("A1Z_WORLD_USD", "/workspace/A1Z/build/scenes/A1Z_G1Z_world.usd"),
        help="Absolute path to the world USD.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("A1Z_OPEN_VOCAB_OUTPUT_DIR", "/workspace/A1Z/runtime/open_vocab_loop_isaac"),
        help="Directory for generated bundle and raw observation artifacts.",
    )
    parser.add_argument(
        "--articulation-root",
        default=os.environ.get("A1Z_ISAAC_ARTICULATION_ROOT", "/World/A1Z_G1Z/Geometry"),
        help="Articulation root prim path.",
    )
    parser.add_argument(
        "--control-freq",
        type=int,
        default=int(os.environ.get("A1Z_ISAAC_CONTROL_FREQ_HZ", "60")),
        help="Isaac backend control frequency.",
    )
    parser.add_argument("--width", type=int, default=int(os.environ.get("A1Z_D405_WIDTH", "1280")))
    parser.add_argument("--height", type=int, default=int(os.environ.get("A1Z_D405_HEIGHT", "720")))
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--capture-frames", type=int, default=8)
    parser.add_argument("--post-camera-warmup-frames", type=int, default=45)
    return parser


def _write_progress(output_dir: Path, step: str, extra: dict[str, object] | None = None) -> None:
    payload: dict[str, object] = {"step": step}
    if extra:
        payload.update(extra)
    with (output_dir / "progress.json").open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=True, indent=2)


async def startup() -> None:
    args, _extras = build_parser().parse_known_args()
    if not args.instruction:
        raise SystemExit("--instruction or A1Z_OPEN_VOCAB_INSTRUCTION is required")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    error_path = output_dir / "error.txt"
    if error_path.exists():
        error_path.unlink()

    os.environ.setdefault("A1Z_D405_ENABLED", "1")

    app = omni.kit.app.get_app()
    frame_source: IsaacD405FrameSource | None = None

    def progress(step: str, extra: dict[str, object] | None = None) -> None:
        _write_progress(output_dir, step, extra)

    try:
        progress("startup", {"stage_path": args.stage_path})
        frame_source = IsaacD405FrameSource(
            simulation_app=app,
            config=IsaacD405FrameSourceConfig(
                root_dir=ROOT_DIR,
                stage_path=args.stage_path,
                width=args.width,
                height=args.height,
                warmup_frames=args.warmup_frames,
                capture_frames=args.capture_frames,
                post_camera_warmup_frames=args.post_camera_warmup_frames,
                control_freq_hz=args.control_freq,
                with_gripper=True,
                articulation_root_prim=args.articulation_root,
            ),
            progress_callback=progress,
        )
        capture = await frame_source.capture_async()
        progress("observation_captured")

        bundle = run_pipeline_from_frame_capture(
            instruction=args.instruction,
            capture=capture,
            output_dir=output_dir,
        )
        progress(
            "bundle_written",
            {
                "grounding_candidates": len(bundle.grounding_candidates),
                "mask_candidates": len(bundle.mask_candidates),
                "object_descriptors": len(bundle.object_descriptors),
            },
        )

        print(f"task_id={bundle.task.task_id}")
        print(f"grounding_candidates={len(bundle.grounding_candidates)}")
        print(f"mask_candidates={len(bundle.mask_candidates)}")
        print(f"object_descriptors={len(bundle.object_descriptors)}")
        print(f"color_camera_path={capture.source_info.get('color_camera_path', '')}")
        print(f"depth_camera_path={capture.source_info.get('depth_camera_path', '')}")
        print(f"bundle_path={output_dir / 'bundle.json'}")
    except Exception as exc:
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        carb.log_error(f"Open-vocabulary Isaac data loop failed: {exc}")
        raise
    finally:
        if frame_source is not None:
            try:
                frame_source.close()
            except Exception as close_exc:
                carb.log_warn(f"Isaac frame source close failed: {close_exc}")
        try:
            app.post_quit()
        except Exception:
            pass


def main() -> None:
    omni.kit.async_engine.run_coroutine(startup())


if __name__ == "__main__":
    main()
