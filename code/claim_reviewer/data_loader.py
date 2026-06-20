"""CSV loading and image path helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass
class ClaimInput:
    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str

    def image_path_list(self) -> list[str]:
        return [p.strip() for p in self.image_paths.split(";") if p.strip()]

    def image_ids(self) -> list[str]:
        return [Path(p).stem for p in self.image_path_list()]


@dataclass
class UserHistory:
    user_id: str
    past_claim_count: int
    accept_claim: int
    manual_review_claim: int
    rejected_claim: int
    last_90_days_claim_count: int
    history_flags: str
    history_summary: str


@dataclass
class EvidenceRequirement:
    requirement_id: str
    claim_object: str
    applies_to: str
    minimum_image_evidence: str


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_claims(path: Path) -> list[ClaimInput]:
    rows = []
    for row in _read_csv(path):
        rows.append(
            ClaimInput(
                user_id=row["user_id"],
                image_paths=row["image_paths"],
                user_claim=row["user_claim"],
                claim_object=row["claim_object"],
            )
        )
    return rows


def load_user_history(path: Path) -> dict[str, UserHistory]:
    history: dict[str, UserHistory] = {}
    for row in _read_csv(path):
        history[row["user_id"]] = UserHistory(
            user_id=row["user_id"],
            past_claim_count=int(row["past_claim_count"]),
            accept_claim=int(row["accept_claim"]),
            manual_review_claim=int(row["manual_review_claim"]),
            rejected_claim=int(row["rejected_claim"]),
            last_90_days_claim_count=int(row["last_90_days_claim_count"]),
            history_flags=row["history_flags"],
            history_summary=row["history_summary"],
        )
    return history


def load_evidence_requirements(path: Path) -> list[EvidenceRequirement]:
    reqs = []
    for row in _read_csv(path):
        reqs.append(
            EvidenceRequirement(
                requirement_id=row["requirement_id"],
                claim_object=row["claim_object"],
                applies_to=row["applies_to"],
                minimum_image_evidence=row["minimum_image_evidence"],
            )
        )
    return reqs


def resolve_image_path(settings: Settings, relative_path: str) -> Path:
    rel = relative_path.replace("\\", "/")
    if rel.startswith("images/"):
        return settings.dataset_dir / rel
    return settings.dataset_dir / rel


def write_output_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})
