"""Main claim review orchestration."""

from __future__ import annotations

from pathlib import Path

from .config import Settings
from .data_loader import (
    ClaimInput,
    EvidenceRequirement,
    UserHistory,
    load_claims,
    load_evidence_requirements,
    load_user_history,
    resolve_image_path,
    write_output_csv,
)
from .evidence import format_requirements, select_requirements
from .history import format_user_history, merge_history_flags
from .schema import OUTPUT_COLUMNS, normalize_risk_flags, validate_and_normalize
from .vlm_client import UsageStats, VLMClient


class ClaimReviewer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.user_history = load_user_history(self.settings.user_history_csv)
        self.requirements = load_evidence_requirements(self.settings.evidence_requirements_csv)
        self.client = VLMClient(self.settings)
        self.usage = UsageStats()

    def review_claim_row(self, claim: ClaimInput) -> dict[str, str]:
        history = self.user_history.get(claim.user_id)
        req_subset = select_requirements(
            self.requirements, claim.claim_object, claim.user_claim
        )
        evidence_block = format_requirements(req_subset)
        history_block = format_user_history(history)

        image_paths = [
            resolve_image_path(self.settings, rel) for rel in claim.image_path_list()
        ]
        image_ids = claim.image_ids()
        self._validate_images(image_paths)

        raw = self.client.review_claim(
            claim_object=claim.claim_object,
            user_claim=claim.user_claim,
            image_paths=image_paths,
            image_ids=image_ids,
            evidence_block=evidence_block,
            history_block=history_block,
        )
        self.usage.merge(self.client.usage)

        normalized = validate_and_normalize(raw, claim.claim_object)
        merged_flags = merge_history_flags(
            raw.get("risk_flags", []), history
        )
        normalized["risk_flags"] = normalize_risk_flags(merged_flags)

        return {
            "user_id": claim.user_id,
            "image_paths": claim.image_paths,
            "user_claim": claim.user_claim,
            "claim_object": claim.claim_object,
            **normalized,
        }

    def process_csv(self, input_csv: Path, output_csv: Path) -> list[dict[str, str]]:
        claims = load_claims(input_csv)
        results: list[dict[str, str]] = []
        for index, claim in enumerate(claims, start=1):
            print(f"[{index}/{len(claims)}] Reviewing {claim.user_id} ({claim.claim_object})")
            try:
                results.append(self.review_claim_row(claim))
            except Exception as exc:  # noqa: BLE001 - keep batch running
                print(f"  ERROR: {exc}")
                results.append(self._fallback_row(claim, str(exc)))
            write_output_csv(output_csv, results, OUTPUT_COLUMNS)
        return results

    def _fallback_row(self, claim: ClaimInput, error: str) -> dict[str, str]:
        history = self.user_history.get(claim.user_id)
        flags = []
        if history and history.history_flags != "none":
            flags = [f for f in history.history_flags.split(";") if f.strip()]
        return {
            "user_id": claim.user_id,
            "image_paths": claim.image_paths,
            "user_claim": claim.user_claim,
            "claim_object": claim.claim_object,
            "evidence_standard_met": "false",
            "evidence_standard_met_reason": f"Automated review failed: {error[:120]}",
            "risk_flags": ";".join(flags) if flags else "manual_review_required",
            "issue_type": "unknown",
            "object_part": "unknown",
            "claim_status": "not_enough_information",
            "claim_status_justification": "Claim could not be reviewed automatically and requires manual review.",
            "supporting_image_ids": "none",
            "valid_image": "false",
            "severity": "unknown",
        }

    def _validate_images(self, image_paths: list[Path]) -> None:
        missing = [str(p) for p in image_paths if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Missing image files: {missing[:3]}")
