"""Evidence requirement selection for a claim."""

from __future__ import annotations

from .data_loader import EvidenceRequirement


def select_requirements(
    requirements: list[EvidenceRequirement],
    claim_object: str,
    claim_text: str,
) -> list[EvidenceRequirement]:
    text = claim_text.lower()
    selected: list[EvidenceRequirement] = []

    for req in requirements:
        if req.claim_object not in {claim_object, "all"}:
            continue
        if req.claim_object == "all" and req.requirement_id.startswith("REQ_GENERAL"):
            selected.append(req)
            continue
        if _requirement_matches(req, text):
            selected.append(req)

    if not selected:
        selected = [r for r in requirements if r.claim_object in {claim_object, "all"}]

    seen: set[str] = set()
    unique: list[EvidenceRequirement] = []
    for req in selected:
        if req.requirement_id not in seen:
            seen.add(req.requirement_id)
            unique.append(req)
    return unique


def _requirement_matches(req: EvidenceRequirement, text: str) -> bool:
    applies = req.applies_to.lower()
    keywords = _keywords_for_applies_to(applies)
    return any(kw in text for kw in keywords)


def _keywords_for_applies_to(applies_to: str) -> list[str]:
    mapping = {
        "dent or scratch": ["dent", "scratch", "scrape", "mark"],
        "crack, broken, or missing part": [
            "crack",
            "broken",
            "missing",
            "shatter",
            "mirror",
            "headlight",
            "taillight",
            "windshield",
            "glass",
            "key",
        ],
        "vehicle identity or orientation": [
            "blue car",
            "black car",
            "left side",
            "right side",
            "driver",
            "vehicle",
        ],
        "screen, keyboard, or trackpad": ["screen", "keyboard", "trackpad", "display", "key"],
        "hinge, lid, corner, body, or port": ["hinge", "lid", "corner", "body", "port", "base"],
        "crushed, torn, or seal damage": ["crush", "torn", "seal", "open", "corner", "box"],
        "water, stain, or label damage": ["water", "wet", "stain", "label", "oil"],
        "contents or inner item": ["missing", "contents", "inside", "item", "product"],
        "general claim review": ["damage", "claim", "review"],
        "multi-image rows": ["photo", "image", "upload"],
        "reviewability": ["photo", "image", "upload", "claim"],
    }
    return mapping.get(applies_to, applies_to.split())


def format_requirements(requirements: list[EvidenceRequirement]) -> str:
    if not requirements:
        return "No specific evidence requirements matched; apply general visual review standards."
    lines = []
    for req in requirements:
        lines.append(f"- [{req.requirement_id}] ({req.applies_to}): {req.minimum_image_evidence}")
    return "\n".join(lines)
