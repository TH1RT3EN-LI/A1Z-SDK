#!/usr/bin/env python3

"""Run the non-grasping open-vocabulary data loop with synthetic inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from a1z_ext.perception.pipeline import run_pipeline_from_frame_capture
from a1z_ext.runtime.frame_sources.sample_rgbd import SampleRGBDFrameSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the non-grasping open-vocabulary data loop.")
    parser.add_argument("--instruction", required=True, help="Natural-language pick instruction.")
    parser.add_argument(
        "--output-dir",
        default="/workspace/A1Z/runtime/open_vocab_loop",
        help="Directory for the generated bundle.",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = SampleRGBDFrameSource(width=args.width, height=args.height).capture()
    bundle = run_pipeline_from_frame_capture(
        instruction=args.instruction,
        capture=capture,
        output_dir=output_dir,
    )

    print(f"task_id={bundle.task.task_id}")
    print(f"grounding_candidates={len(bundle.grounding_candidates)}")
    print(f"mask_candidates={len(bundle.mask_candidates)}")
    print(f"object_descriptors={len(bundle.object_descriptors)}")
    print(f"bundle_path={output_dir / 'bundle.json'}")


if __name__ == "__main__":
    main()
