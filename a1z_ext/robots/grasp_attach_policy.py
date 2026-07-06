"""Pure contact-selection policy for simulated grasp attachment."""

from __future__ import annotations

from typing import Sequence


def contains_disallowed_attach_candidate(candidates: Sequence[str]) -> bool:
    for candidate in candidates:
        if candidate == "/World/GroundPlane":
            return True
    return False


def candidate_contact_score(
    candidate: str,
    *,
    left_contact_details: list[dict[str, object]],
    right_contact_details: list[dict[str, object]],
) -> tuple[int, float]:
    support_count = 0
    separation_sum = 0.0
    for detail in [*left_contact_details, *right_contact_details]:
        if str(detail.get("rigid_body_candidate", "") or "") != candidate:
            continue
        support_count += 1
        separation_sum += float(detail.get("separation", 0.0) or 0.0)
    average_separation = separation_sum / float(support_count) if support_count > 0 else float("inf")
    return support_count, average_separation


def select_contact_candidate(
    *,
    left_candidates: list[str],
    right_candidates: list[str],
    left_contact_details: list[dict[str, object]],
    right_contact_details: list[dict[str, object]],
    require_bilateral_contact: bool,
) -> str:
    if require_bilateral_contact:
        candidate_pool = sorted(set(left_candidates).intersection(right_candidates))
    else:
        candidate_pool = sorted(set(left_candidates).union(right_candidates))

    filtered_candidates = [
        candidate for candidate in candidate_pool if not contains_disallowed_attach_candidate([candidate])
    ]
    if not filtered_candidates:
        return ""

    ranked = sorted(
        filtered_candidates,
        key=lambda candidate: (
            candidate_contact_score(
                candidate,
                left_contact_details=left_contact_details,
                right_contact_details=right_contact_details,
            )[0],
            -candidate_contact_score(
                candidate,
                left_contact_details=left_contact_details,
                right_contact_details=right_contact_details,
            )[1],
            candidate,
        ),
        reverse=True,
    )
    return str(ranked[0] or "")


def summarize_attach_contacts(
    *,
    left_raw_candidates: list[str],
    left_candidates: list[str],
    left_contact_details: list[dict[str, object]],
    right_raw_candidates: list[str],
    right_candidates: list[str],
    right_contact_details: list[dict[str, object]],
    target_body_path: str,
    require_bilateral_contact: bool,
) -> tuple[bool, str, dict[str, object]]:
    left_has_target_contact = bool(target_body_path) and target_body_path in left_candidates
    right_has_target_contact = bool(target_body_path) and target_body_path in right_candidates
    if target_body_path:
        if require_bilateral_contact:
            chosen = target_body_path if left_has_target_contact and right_has_target_contact else ""
        else:
            chosen = target_body_path if left_has_target_contact or right_has_target_contact else ""
    else:
        chosen = select_contact_candidate(
            left_candidates=left_candidates,
            right_candidates=right_candidates,
            left_contact_details=left_contact_details,
            right_contact_details=right_contact_details,
            require_bilateral_contact=require_bilateral_contact,
        )

    left_ground = contains_disallowed_attach_candidate(left_candidates)
    right_ground = contains_disallowed_attach_candidate(right_candidates)
    if chosen:
        left_has_chosen_contact = chosen in left_candidates
        right_has_chosen_contact = chosen in right_candidates
    else:
        left_has_chosen_contact = False
        right_has_chosen_contact = False

    selected_body_contact_ready = (
        (left_has_chosen_contact and right_has_chosen_contact)
        if require_bilateral_contact
        else (left_has_chosen_contact or right_has_chosen_contact)
    )

    summary: dict[str, object] = {
        "left_raw_contacts": left_raw_candidates,
        "right_raw_contacts": right_raw_candidates,
        "left_contacts": left_candidates,
        "right_contacts": right_candidates,
        "left_contact_details": left_contact_details,
        "right_contact_details": right_contact_details,
        "target_body_path": target_body_path or None,
        "chosen_body_path": chosen or None,
        "require_bilateral_contact": bool(require_bilateral_contact),
        "left_has_ground_contact": left_ground,
        "right_has_ground_contact": right_ground,
        "left_has_target_contact": left_has_target_contact,
        "right_has_target_contact": right_has_target_contact,
        "selected_body_contact_ready": selected_body_contact_ready,
        "shared_contact_candidates": sorted(set(left_candidates).intersection(right_candidates)),
        "ground_contact_present": bool(left_ground or right_ground),
    }
    summary["left_has_chosen_contact"] = left_has_chosen_contact
    summary["right_has_chosen_contact"] = right_has_chosen_contact
    if target_body_path:
        summary["left_has_selected_body_contact"] = left_has_target_contact
        summary["right_has_selected_body_contact"] = right_has_target_contact
    else:
        summary["left_has_selected_body_contact"] = left_has_chosen_contact
        summary["right_has_selected_body_contact"] = right_has_chosen_contact
    return bool(chosen), chosen, summary
