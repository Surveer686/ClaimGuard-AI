"""Allowed output values and validation helpers."""

from __future__ import annotations

CLAIM_STATUSES = {"supported", "contradicted", "not_enough_information"}

ISSUE_TYPES = {
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
}

CAR_PARTS = {
    "front_bumper",
    "rear_bumper",
    "door",
    "hood",
    "windshield",
    "side_mirror",
    "headlight",
    "taillight",
    "fender",
    "quarter_panel",
    "body",
    "unknown",
}

LAPTOP_PARTS = {
    "screen",
    "keyboard",
    "trackpad",
    "hinge",
    "lid",
    "corner",
    "port",
    "base",
    "body",
    "unknown",
}

PACKAGE_PARTS = {
    "box",
    "package_corner",
    "package_side",
    "seal",
    "label",
    "contents",
    "item",
    "unknown",
}

OBJECT_PARTS = {
    "car": CAR_PARTS,
    "laptop": LAPTOP_PARTS,
    "package": PACKAGE_PARTS,
}

RISK_FLAGS = {
    "none",
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
}

SEVERITIES = {"none", "low", "medium", "high", "unknown"}

OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "extracted_claim_summary": {"type": "string"},
        "evidence_standard_met": {"type": "boolean"},
        "evidence_standard_met_reason": {"type": "string"},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "issue_type": {"type": "string"},
        "object_part": {"type": "string"},
        "claim_status": {"type": "string"},
        "claim_status_justification": {"type": "string"},
        "supporting_image_ids": {"type": "array", "items": {"type": "string"}},
        "valid_image": {"type": "boolean"},
        "severity": {"type": "string"},
        "per_image_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "image_id": {"type": "string"},
                    "quality_issues": {"type": "array", "items": {"type": "string"}},
                    "visible_object": {"type": "string"},
                    "relevant_to_claim": {"type": "boolean"},
                },
                "required": ["image_id", "relevant_to_claim"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "extracted_claim_summary",
        "evidence_standard_met",
        "evidence_standard_met_reason",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "claim_status_justification",
        "supporting_image_ids",
        "valid_image",
        "severity",
    ],
    "additionalProperties": False,
}


def normalize_bool(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    return "true" if text in {"true", "1", "yes"} else "false"


def normalize_risk_flags(flags: list[str] | str) -> str:
    if isinstance(flags, str):
        parts = [f.strip() for f in flags.split(";") if f.strip()]
    else:
        parts = [str(f).strip() for f in flags if str(f).strip()]
    valid = [f for f in parts if f in RISK_FLAGS and f != "none"]
    return ";".join(valid) if valid else "none"


def normalize_supporting_ids(ids: list[str] | str) -> str:
    if isinstance(ids, str):
        parts = [i.strip() for i in ids.split(";") if i.strip()]
    else:
        parts = [str(i).strip() for i in ids if str(i).strip()]
    parts = [p for p in parts if p.lower() != "none"]
    return ";".join(parts) if parts else "none"


def closest_allowed(value: str, allowed: set[str], default: str = "unknown") -> str:
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if text in allowed:
        return text
    for candidate in allowed:
        if candidate in text or text in candidate:
            return candidate
    return default


def validate_and_normalize(result: dict, claim_object: str) -> dict:
    parts = OBJECT_PARTS.get(claim_object, {"unknown"})

    issue_type = closest_allowed(result.get("issue_type", "unknown"), ISSUE_TYPES)
    object_part = closest_allowed(result.get("object_part", "unknown"), parts)
    claim_status = closest_allowed(
        result.get("claim_status", "not_enough_information"),
        CLAIM_STATUSES,
        default="not_enough_information",
    )
    severity = closest_allowed(result.get("severity", "unknown"), SEVERITIES)

    flags = result.get("risk_flags", [])
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split(";") if f.strip()]
    normalized_flags = []
    for flag in flags:
        norm = closest_allowed(flag, RISK_FLAGS, default="")
        if norm and norm != "none" and norm not in normalized_flags:
            normalized_flags.append(norm)

    supporting = normalize_supporting_ids(result.get("supporting_image_ids", []))

    return {
        "evidence_standard_met": normalize_bool(result.get("evidence_standard_met", False)),
        "evidence_standard_met_reason": str(result.get("evidence_standard_met_reason", "")).strip(),
        "risk_flags": ";".join(normalized_flags) if normalized_flags else "none",
        "issue_type": issue_type,
        "object_part": object_part,
        "claim_status": claim_status,
        "claim_status_justification": str(result.get("claim_status_justification", "")).strip(),
        "supporting_image_ids": supporting,
        "valid_image": normalize_bool(result.get("valid_image", False)),
        "severity": severity,
    }
