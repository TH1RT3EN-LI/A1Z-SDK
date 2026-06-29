"""VLM-based target mask selection from numbered automatic mask candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from a1z_ext.llm import LLMClient, LLMImage, LLMProviderConfig

from .automatic_masks import AutomaticMaskBundle, AutomaticMaskRecord, load_automatic_mask_bundle, resolve_workspace_path


DEFAULT_SYSTEM_PROMPT = """You are selecting one segmentation mask for a robot pick task.
Return JSON only.
Do not wrap the JSON in markdown fences.
You will receive:
1. the original RGB image,
2. an overlay image where candidate masks are labeled by mask ID,
3. a contact sheet showing candidate masks individually.
Choose the single mask ID that best matches the user instruction.
If the instruction does not match any candidate, set target_found=false and selected_mask_index=-1.
Prefer a whole-object mask over a partial mask unless the instruction explicitly asks for a part.
Set direct_grasp_recommended=true only when the chosen object appears clearly visible and reasonably isolated for a direct grasp attempt.
Only select from the candidate IDs listed in the prompt.
"""


@dataclass(frozen=True, slots=True)
class SelectedMaskDecision:
    instruction: str
    provider: str
    model: str
    target_found: bool
    selected_mask_index: int
    confidence: float
    direct_grasp_recommended: bool
    reason: str
    raw_content: str


@dataclass(frozen=True, slots=True)
class SelectedMaskResult:
    image_path: str
    overlay_path: str
    contact_sheet_path: str
    automatic_mask_summary_path: str
    selection_json_path: str
    decision: SelectedMaskDecision
    selected_mask: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty VLM response")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < 0 or end <= start:
            raise ValueError("VLM response did not contain a JSON object") from None
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("VLM response JSON root must be an object")
    return parsed


def _make_color(index: int) -> np.ndarray:
    palette = np.array(
        [
            [255, 99, 71],
            [135, 206, 235],
            [60, 179, 113],
            [255, 215, 0],
            [186, 85, 211],
            [255, 140, 0],
            [0, 191, 255],
            [124, 252, 0],
            [255, 105, 180],
            [72, 209, 204],
            [238, 130, 238],
            [154, 205, 50],
        ],
        dtype=np.uint8,
    )
    return palette[index % len(palette)]


def _load_mask(path: str) -> np.ndarray:
    return np.load(resolve_workspace_path(path)).astype(np.uint8)


def _boundary_touch_count(record: AutomaticMaskRecord, *, image_width: int, image_height: int) -> int:
    x, y, w, h = record.bbox_xywh
    x1 = x + w
    y1 = y + h
    return int(x <= 1) + int(y <= 1) + int(x1 >= image_width - 2) + int(y1 >= image_height - 2)


def filter_object_like_masks(
    bundle: AutomaticMaskBundle,
    *,
    max_area_ratio: float = 0.7,
    max_boundary_touches: int = 2,
) -> list[AutomaticMaskRecord]:
    image_path = resolve_workspace_path(bundle.image_path)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"failed to load image: {image_path}")
    height, width = image.shape[:2]
    image_area = float(width * height)

    filtered: list[AutomaticMaskRecord] = []
    for record in bundle.records:
        area_ratio = float(record.area) / image_area
        touches = _boundary_touch_count(record, image_width=width, image_height=height)
        bbox_x, bbox_y, bbox_w, bbox_h = record.bbox_xywh
        bbox_width_ratio = float(bbox_w) / float(width)
        bbox_height_ratio = float(bbox_h) / float(height)
        is_global_background = (
            area_ratio > max_area_ratio
            or (touches >= 3 and area_ratio > 0.45)
            or (bbox_width_ratio > 0.95 and bbox_height_ratio > 0.95)
        )
        if is_global_background:
            continue
        filtered.append(record)
    return filtered


def _draw_filtered_overlay(
    *,
    image_rgb: np.ndarray,
    records: list[AutomaticMaskRecord],
    output_path: Path,
) -> None:
    overlay = image_rgb.copy()
    for record in records:
        mask = _load_mask(record.mask_npy_path)
        color = _make_color(record.mask_index)
        alpha = 0.35
        mask_bool = mask.astype(bool)
        overlay[mask_bool] = (overlay[mask_bool] * (1.0 - alpha) + color * alpha).astype(np.uint8)

        x, y, w, h = record.bbox_xywh
        cv2.rectangle(overlay, (x, y), (x + w, y + h), tuple(int(v) for v in color.tolist()), 2)
        cv2.putText(
            overlay,
            str(record.mask_index),
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))


def _resize_to_fit(image: np.ndarray, *, width: int, height: int) -> np.ndarray:
    src_h, src_w = image.shape[:2]
    scale = min(width / src_w, height / src_h)
    resized = cv2.resize(image, (max(1, int(src_w * scale)), max(1, int(src_h * scale))), interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    y0 = (height - resized.shape[0]) // 2
    x0 = (width - resized.shape[1]) // 2
    canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
    return canvas


def _build_contact_sheet(
    *,
    image_rgb: np.ndarray,
    records: list[AutomaticMaskRecord],
    output_path: Path,
    cell_size: tuple[int, int] = (320, 220),
    columns: int = 3,
) -> None:
    cell_w, cell_h = cell_size
    rows = max(1, (len(records) + columns - 1) // columns)
    canvas = np.full((rows * cell_h, columns * cell_w, 3), 250, dtype=np.uint8)

    for idx, record in enumerate(records):
        row = idx // columns
        col = idx % columns
        x0 = col * cell_w
        y0 = row * cell_h

        mask = _load_mask(record.mask_npy_path).astype(bool)
        x, y, w, h = record.bbox_xywh
        margin = 18
        crop_x0 = max(0, x - margin)
        crop_y0 = max(0, y - margin)
        crop_x1 = min(image_rgb.shape[1], x + w + margin)
        crop_y1 = min(image_rgb.shape[0], y + h + margin)

        crop = image_rgb[crop_y0:crop_y1, crop_x0:crop_x1].copy()
        crop_mask = mask[crop_y0:crop_y1, crop_x0:crop_x1]
        dimmed = crop.copy()
        dimmed[~crop_mask] = (dimmed[~crop_mask] * 0.35 + 255 * 0.65).astype(np.uint8)
        preview = _resize_to_fit(dimmed, width=cell_w - 20, height=cell_h - 52)

        canvas[y0 + 32 : y0 + 32 + preview.shape[0], x0 + 10 : x0 + 10 + preview.shape[1]] = preview
        color = _make_color(record.mask_index)
        cv2.putText(
            canvas,
            f"ID {record.mask_index}",
            (x0 + 12, y0 + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            tuple(int(v) for v in color.tolist()),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"area={record.area}",
            (x0 + 110, y0 + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (60, 60, 60),
            1,
            cv2.LINE_AA,
        )
        cv2.rectangle(canvas, (x0 + 6, y0 + 28), (x0 + cell_w - 6, y0 + cell_h - 6), (210, 210, 210), 1)

    cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))


def _build_user_prompt(*, instruction: str, records: list[AutomaticMaskRecord]) -> str:
    candidate_lines = "\n".join(
        f"- id={record.mask_index}, area={record.area}, bbox_xywh={record.bbox_xywh}, "
        f"predicted_iou={record.predicted_iou:.4f}, stability_score={record.stability_score:.4f}"
        for record in records
    )
    valid_ids = [record.mask_index for record in records]
    return (
        f"Instruction: {instruction}\n"
        f"Valid candidate IDs: {valid_ids}\n"
        "Candidate stats:\n"
        f"{candidate_lines}\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "instruction": "<string>",\n'
        '  "target_found": <true|false>,\n'
        '  "selected_mask_index": <int or -1>,\n'
        '  "confidence": <float 0..1>,\n'
        '  "direct_grasp_recommended": <true|false>,\n'
        '  "reason": "<short string>"\n'
        "}\n"
        "Rules:\n"
        "- selected_mask_index must be one of the valid candidate IDs or -1.\n"
        "- If no candidate matches the instruction, set target_found=false and selected_mask_index=-1.\n"
        "- Prefer the mask that covers the whole target object over a partial sub-mask.\n"
        "- direct_grasp_recommended should be true only if the target seems directly graspable from the current view.\n"
        "- Output JSON only.\n"
    )


def _normalize_decision(
    payload: dict[str, Any],
    *,
    instruction: str,
    provider: str,
    model: str,
    raw_content: str,
    valid_ids: set[int],
) -> SelectedMaskDecision:
    target_found = bool(payload.get("target_found", False))
    selected_mask_index_raw = payload.get("selected_mask_index", -1)
    if not isinstance(selected_mask_index_raw, int):
        if isinstance(selected_mask_index_raw, float):
            selected_mask_index = int(round(selected_mask_index_raw))
        else:
            raise ValueError("selected_mask_index must be numeric")
    else:
        selected_mask_index = selected_mask_index_raw

    if selected_mask_index != -1 and selected_mask_index not in valid_ids:
        raise ValueError(
            f"selected_mask_index {selected_mask_index} is not in valid candidate IDs {sorted(valid_ids)}"
        )
    if not target_found:
        selected_mask_index = -1

    confidence_raw = payload.get("confidence", 0.0)
    if not isinstance(confidence_raw, (int, float)):
        raise ValueError("confidence must be numeric")
    confidence = min(1.0, max(0.0, float(confidence_raw)))

    return SelectedMaskDecision(
        instruction=instruction,
        provider=provider,
        model=model,
        target_found=target_found and selected_mask_index != -1,
        selected_mask_index=selected_mask_index,
        confidence=confidence,
        direct_grasp_recommended=bool(payload.get("direct_grasp_recommended", False)),
        reason=str(payload.get("reason", "")).strip(),
        raw_content=raw_content,
    )


def select_mask_with_vlm(
    *,
    instruction: str,
    automatic_mask_bundle: AutomaticMaskBundle | str | Path,
    output_dir: str | Path,
    llm_config: LLMProviderConfig,
    image_detail: str = "high",
    max_area_ratio: float = 0.7,
    max_boundary_touches: int = 2,
) -> SelectedMaskResult:
    bundle = (
        load_automatic_mask_bundle(automatic_mask_bundle)
        if isinstance(automatic_mask_bundle, (str, Path))
        else automatic_mask_bundle
    )
    image_path = resolve_workspace_path(bundle.image_path)
    image_rgb = cv2.cvtColor(cv2.imread(str(image_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if image_rgb.size == 0:
        raise FileNotFoundError(f"failed to load image for mask selection: {image_path}")

    candidate_records = filter_object_like_masks(
        bundle,
        max_area_ratio=max_area_ratio,
        max_boundary_touches=max_boundary_touches,
    )
    if not candidate_records:
        raise ValueError("no object-like masks remain after filtering")

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    overlay_path = output_root / "overlay_object_candidates.png"
    contact_sheet_path = output_root / "candidate_contact_sheet.png"
    selection_json_path = output_root / "selection.json"

    _draw_filtered_overlay(
        image_rgb=image_rgb,
        records=candidate_records,
        output_path=overlay_path,
    )
    _build_contact_sheet(
        image_rgb=image_rgb,
        records=candidate_records,
        output_path=contact_sheet_path,
    )

    client = LLMClient(llm_config)
    response = client.complete_with_images(
        text=_build_user_prompt(instruction=instruction, records=candidate_records),
        images=[
            LLMImage.from_file(image_path, detail=image_detail),
            LLMImage.from_file(overlay_path, detail=image_detail),
            LLMImage.from_file(contact_sheet_path, detail=image_detail),
        ],
        system_text=DEFAULT_SYSTEM_PROMPT,
    )
    parsed = _extract_json_object(response.content)
    decision = _normalize_decision(
        parsed,
        instruction=instruction,
        provider=response.provider,
        model=response.model,
        raw_content=response.content,
        valid_ids={record.mask_index for record in candidate_records},
    )

    selected_mask_payload: dict[str, Any] | None = None
    if decision.target_found:
        selected_record = next(record for record in candidate_records if record.mask_index == decision.selected_mask_index)
        selected_mask = _load_mask(selected_record.mask_npy_path)
        selected_mask_png_path = output_root / "selected_mask.png"
        selected_mask_npy_path = output_root / "selected_mask.npy"
        cv2.imwrite(str(selected_mask_png_path), selected_mask * 255)
        np.save(selected_mask_npy_path, selected_mask)
        selected_mask_payload = {
            "mask_index": selected_record.mask_index,
            "area": selected_record.area,
            "bbox_xywh": selected_record.bbox_xywh,
            "predicted_iou": selected_record.predicted_iou,
            "stability_score": selected_record.stability_score,
            "point_coords": selected_record.point_coords,
            "mask_png_path": str(selected_mask_png_path),
            "mask_npy_path": str(selected_mask_npy_path),
            "source_mask_png_path": selected_record.mask_png_path,
            "source_mask_npy_path": selected_record.mask_npy_path,
        }

    result = SelectedMaskResult(
        image_path=str(image_path),
        overlay_path=str(overlay_path),
        contact_sheet_path=str(contact_sheet_path),
        automatic_mask_summary_path=str(Path(bundle.overlay_path).resolve().parent / "summary.json"),
        selection_json_path=str(selection_json_path),
        decision=decision,
        selected_mask=selected_mask_payload,
    )
    selection_json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return result
