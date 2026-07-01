#!/usr/bin/env python3

"""Send one RGB image to a Kimi-compatible VLM and emit SAM-friendly grounding JSON."""

from __future__ import annotations

import argparse
from binascii import Error as BinasciiError
import json
import os
from pathlib import Path
import sys
import struct
import time
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from a1z_ext.llm import LLMClient, LLMClientError, LLMImage, LLMProviderConfig
from a1z_ext.llm.images import bytes_to_data_url
from a1z_ext.runtime.ros_env import ensure_ros_logging_env


DEFAULT_SYSTEM_PROMPT = """You are a visual grounding model for robotics.
Return JSON only.
Do not wrap the JSON in markdown fences.
Use the provided image size exactly.
If the target object is not visible with enough confidence, return found=false and set candidates to [].
If found=true, return one to three candidates ranked best-first.
Each candidate must be a tight 2D prompt for SAM in image pixel coordinates.
Use integer coordinates.
Prefer one foreground point near the visual center of the target object.
The bbox format is [x0, y0, x1, y1] in XYXY pixel coordinates.
Do not invent hidden objects.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call a Kimi/OpenAI-compatible VLM and emit SAM-friendly grounding JSON."
    )
    parser.add_argument(
        "--image",
        default="",
        help="Path to an RGB image file.",
    )
    parser.add_argument(
        "--ros-topic",
        default="",
        help="ROS image topic to capture a single frame from before sending to the VLM.",
    )
    parser.add_argument(
        "--ros-timeout-s",
        type=float,
        default=10.0,
        help="Timeout while waiting for one ROS image frame.",
    )
    parser.add_argument(
        "--capture-path",
        default="",
        help="Optional path to save the ROS-captured PNG frame.",
    )
    parser.add_argument(
        "--target",
        default="pen",
        help="Target object text to ground in the image.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("A1Z_VLM_PROVIDER", "kimi"),
        help="LLM provider name understood by LLMProviderConfig.",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "runtime" / "vlm_grounding" / "pen_grounding_for_sam.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--image-detail",
        default="high",
        help="Image detail hint for the VLM API.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=600,
        help="Override max_tokens for this request.",
    )
    return parser


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        os.environ.setdefault(key, value)


def build_user_prompt(*, target: str, width: int, height: int) -> str:
    return (
        f'Target object: "{target}".\n'
        f"Image size: width={width}, height={height}.\n"
        "Task: detect whether at least one instance of the target object is visible.\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "target": "<string>",\n'
        '  "image_size": {"width": <int>, "height": <int>},\n'
        '  "found": <true|false>,\n'
        '  "summary": "<short string>",\n'
        '  "candidates": [\n'
        "    {\n"
        '      "rank": <int starting at 0>,\n'
        '      "label": "<string>",\n'
        '      "score": <float 0..1>,\n'
        '      "bbox_xyxy": [x0, y0, x1, y1],\n'
        '      "point_xy": [x, y],\n'
        '      "prompt_type": "box+point"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Coordinates must stay inside the image bounds.\n"
        "- x0 < x1 and y0 < y1.\n"
        "- If the target is not visible or confidence is below 0.35, set found=false and candidates=[].\n"
        "- Do not output any text before or after the JSON.\n"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty VLM response")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < 0 or end <= start:
            raise ValueError("VLM response did not contain a JSON object") from None
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("VLM response JSON root must be an object")
    return parsed


def _coerce_int_pair(value: Any, *, name: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a list of length 2")
    result = []
    for item in value:
        if not isinstance(item, (int, float)):
            raise ValueError(f"{name} must contain numbers")
        result.append(int(round(float(item))))
    return result


def _coerce_bbox(value: Any, *, width: int, height: int) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("bbox_xyxy must be a list of length 4")
    raw = []
    for item in value:
        if not isinstance(item, (int, float)):
            raise ValueError("bbox_xyxy must contain numbers")
        raw.append(int(round(float(item))))

    x0, y0, x1, y1 = raw
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0 = min(max(x0, 0), width - 1)
    x1 = min(max(x1, 0), width - 1)
    y0 = min(max(y0, 0), height - 1)
    y1 = min(max(y1, 0), height - 1)
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"invalid bbox after clamping: {[x0, y0, x1, y1]}")
    return [x0, y0, x1, y1]


def _coerce_score(value: Any) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("score must be numeric")
    score = float(value)
    return min(1.0, max(0.0, score))


def normalize_grounding_payload(
    payload: dict[str, Any],
    *,
    target: str,
    image_path: Path,
    width: int,
    height: int,
) -> dict[str, Any]:
    found = bool(payload.get("found", False))
    candidates_raw = payload.get("candidates", [])
    if candidates_raw is None:
        candidates_raw = []
    if not isinstance(candidates_raw, list):
        raise ValueError("candidates must be a list")

    candidates: list[dict[str, Any]] = []
    for rank, candidate in enumerate(candidates_raw):
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be an object")
        bbox = _coerce_bbox(candidate.get("bbox_xyxy"), width=width, height=height)
        point = _coerce_int_pair(candidate.get("point_xy"), name="point_xy")
        point[0] = min(max(point[0], 0), width - 1)
        point[1] = min(max(point[1], 0), height - 1)
        x0, y0, x1, y1 = bbox
        if not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1):
            point = [(x0 + x1) // 2, (y0 + y1) // 2]
        candidates.append(
            {
                "candidate_id": f"{uuid4()}",
                "task_id": f"{uuid4()}",
                "source_model": "kimi_vlm",
                "text_prompt": target,
                "bbox_xyxy": bbox,
                "point_xy": point,
                "score": _coerce_score(candidate.get("score", 0.0)),
                "rank": rank,
                "frame_id": "camera_color_frame",
                "label": str(candidate.get("label", target)),
                "prompt_type": str(candidate.get("prompt_type", "box+point")),
            }
        )

    return {
        "target": target,
        "image_path": str(image_path),
        "image_size": {"width": width, "height": height},
        "provider": "kimi_vlm",
        "found": found and bool(candidates),
        "summary": str(payload.get("summary", "")).strip(),
        "candidates": candidates if found else [],
    }


def _read_image_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError(f"image file too small: {path}")

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if data[:2] == b"\xff\xd8":
        index = 2
        length = len(data)
        while index + 9 < length:
            while index < length and data[index] == 0xFF:
                index += 1
            if index >= length:
                break
            marker = data[index]
            index += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > length:
                break
            segment_size = struct.unpack(">H", data[index : index + 2])[0]
            if segment_size < 2 or index + segment_size > length:
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if index + 7 > length:
                    break
                height, width = struct.unpack(">HH", data[index + 3 : index + 7])
                return int(width), int(height)
            index += segment_size
        raise ValueError(f"could not parse JPEG size: {path}")

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height

    raise ValueError(f"unsupported image format for size probing: {path}")


def _capture_ros_image_png_bytes(
    *,
    ros_topic: str,
    timeout_s: float,
) -> tuple[bytes, dict[str, Any]]:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Image as RosImage

    from a1z_open_vocab.image_encoding import ros_image_to_png_bytes

    class OneShotImageNode(Node):
        def __init__(self) -> None:
            super().__init__("a1z_kimi_grounding_capture")
            self.message: RosImage | None = None
            qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
            )
            self.subscription = self.create_subscription(
                RosImage,
                ros_topic,
                self._handle_image,
                qos,
            )

        def _handle_image(self, message: RosImage) -> None:
            self.message = message

    ensure_ros_logging_env()
    rclpy.init(args=None)
    node = OneShotImageNode()
    deadline = time.monotonic() + timeout_s
    try:
        while rclpy.ok() and node.message is None and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        if node.message is None:
            raise TimeoutError(f"timed out waiting for ROS image on topic {ros_topic}")
        message = node.message
        png_bytes = ros_image_to_png_bytes(message)
        metadata = {
            "source": "ros_topic",
            "ros_topic": ros_topic,
            "encoding": message.encoding,
            "width": int(message.width),
            "height": int(message.height),
            "step": int(message.step),
            "header": {
                "frame_id": str(message.header.frame_id),
                "stamp_sec": int(message.header.stamp.sec),
                "stamp_nanosec": int(message.header.stamp.nanosec),
            },
        }
        return png_bytes, metadata
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def _resolve_image_input(
    *,
    image_arg: str,
    ros_topic: str,
    ros_timeout_s: float,
    capture_path_arg: str,
) -> tuple[str, int, int, Path, dict[str, Any]]:
    has_file = bool(image_arg.strip())
    has_ros = bool(ros_topic.strip())
    if has_file == has_ros:
        raise ValueError("exactly one of --image or --ros-topic must be provided")

    if has_file:
        image_path = Path(image_arg).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"image not found: {image_path}")
        width, height = _read_image_size(image_path)
        data_url = LLMImage.from_file(image_path).data_url
        metadata = {
            "source": "file",
            "image_path": str(image_path),
        }
        return data_url, width, height, image_path, metadata

    png_bytes, ros_metadata = _capture_ros_image_png_bytes(
        ros_topic=ros_topic.strip(),
        timeout_s=ros_timeout_s,
    )
    capture_path = Path(capture_path_arg).resolve() if capture_path_arg.strip() else (
        REPO_ROOT / "runtime" / "vlm_grounding" / "ros_capture.png"
    )
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture_path.write_bytes(png_bytes)
    width = int(ros_metadata["width"])
    height = int(ros_metadata["height"])
    data_url = bytes_to_data_url(png_bytes, mime_type="image/png")
    ros_metadata["image_path"] = str(capture_path)
    return data_url, width, height, capture_path, ros_metadata


def main() -> int:
    args = build_parser().parse_args()

    load_env_file(REPO_ROOT / "config" / "a1z_vlm.env")
    data_url, width, height, image_path, image_source_metadata = _resolve_image_input(
        image_arg=args.image,
        ros_topic=args.ros_topic,
        ros_timeout_s=args.ros_timeout_s,
        capture_path_arg=args.capture_path,
    )

    config = LLMProviderConfig.from_env()
    if args.provider:
        config = LLMProviderConfig.for_provider(
            args.provider,
            model=os.environ.get("A1Z_VLM_MODEL") or None,
            base_url=os.environ.get("A1Z_VLM_BASE_URL") or None,
            api_key_env=os.environ.get("A1Z_VLM_API_KEY_ENV") or None,
            timeout_s=float(os.environ.get("A1Z_VLM_TIMEOUT_S", "30.0")),
            max_tokens=args.max_tokens,
            temperature=float(os.environ.get("A1Z_VLM_TEMPERATURE", "0.0")),
        )
    else:
        config = LLMProviderConfig(
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            api_key_env=config.api_key_env,
            timeout_s=config.timeout_s,
            max_tokens=args.max_tokens,
            temperature=config.temperature,
        )

    client = LLMClient(config)
    response = client.complete_with_images(
        text=build_user_prompt(target=args.target, width=width, height=height),
        images=[LLMImage(data_url=data_url, detail=args.image_detail)],
        system_text=DEFAULT_SYSTEM_PROMPT,
    )

    parsed = extract_json_object(response.content)
    normalized = normalize_grounding_payload(
        parsed,
        target=args.target,
        image_path=image_path,
        width=width,
        height=height,
    )
    normalized["provider"] = response.provider
    normalized["model"] = response.model
    normalized["raw_content"] = response.content
    normalized["image_source"] = image_source_metadata

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"provider={response.provider}")
    print(f"model={response.model}")
    print(f"image={image_path}")
    print(f"target={args.target}")
    print(f"found={normalized['found']}")
    print(f"candidates={len(normalized['candidates'])}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, TimeoutError, ValueError, LLMClientError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
