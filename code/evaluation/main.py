#!/usr/bin/env python3
"""Evaluate claim reviewer against labeled sample claims."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_reviewer.config import load_settings
from claim_reviewer.data_loader import load_claims, write_output_csv
from claim_reviewer.reviewer import ClaimReviewer
from claim_reviewer.schema import OUTPUT_COLUMNS


PREDICTION_FIELDS = [
    "evidence_standard_met",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "supporting_image_ids",
    "valid_image",
    "severity",
]


@dataclass
class FieldMetrics:
    exact: int = 0
    total: int = 0

    @property
    def accuracy(self) -> float:
        return self.exact / self.total if self.total else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate on sample_claims.csv")
    parser.add_argument(
        "--compare-model",
        default="gpt-4o-mini",
        help="Secondary model for strategy comparison",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory for evaluation artifacts",
    )
    return parser.parse_args()


def read_labeled_sample(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def compare_rows(expected: dict[str, str], predicted: dict[str, str]) -> dict[str, bool]:
    results = {}
    for field in PREDICTION_FIELDS:
        exp = expected.get(field, "").strip().lower()
        pred = predicted.get(field, "").strip().lower()
        if field == "risk_flags":
            exp_set = set(x for x in exp.split(";") if x and x != "none")
            pred_set = set(x for x in pred.split(";") if x and x != "none")
            results[field] = exp_set == pred_set
        else:
            results[field] = exp == pred
    return results


def run_evaluation(reviewer: ClaimReviewer, sample_rows: list[dict[str, str]]) -> dict:
    field_metrics = {field: FieldMetrics() for field in PREDICTION_FIELDS}
    per_row = []
    claim_status_counter: Counter[str] = Counter()

    for index, expected in enumerate(sample_rows, start=1):
        claim = load_claims_from_row(expected)
        print(f"[eval {index}/{len(sample_rows)}] {claim.user_id}")
        predicted = reviewer.review_claim_row(claim)
        matches = compare_rows(expected, predicted)
        for field, ok in matches.items():
            field_metrics[field].total += 1
            field_metrics[field].exact += int(ok)
        claim_status_counter[predicted["claim_status"]] += 1
        per_row.append(
            {
                "user_id": expected["user_id"],
                "matches": matches,
                "expected_claim_status": expected.get("claim_status"),
                "predicted_claim_status": predicted.get("claim_status"),
            }
        )

    return {
        "field_accuracy": {k: v.accuracy for k, v in field_metrics.items()},
        "claim_status_distribution": dict(claim_status_counter),
        "rows": per_row,
        "usage": asdict(reviewer.usage),
    }


def load_claims_from_row(row: dict[str, str]):
    from claim_reviewer.data_loader import ClaimInput

    return ClaimInput(
        user_id=row["user_id"],
        image_paths=row["image_paths"],
        user_claim=row["user_claim"],
        claim_object=row["claim_object"],
    )


def main() -> int:
    args = parse_args()
    settings = load_settings()
    sample_path = settings.sample_claims_csv
    sample_rows = read_labeled_sample(sample_path)

    print("=== Strategy A: gpt-4o (primary) ===")
    started = time.time()
    primary = ClaimReviewer(load_settings(model="gpt-4o"))
    primary_results = run_evaluation(primary, sample_rows)
    primary_elapsed = time.time() - started

    print("\n=== Strategy B: gpt-4o-mini (comparison) ===")
    started = time.time()
    secondary = ClaimReviewer(load_settings(model=args.compare_model, cache_dir=settings.cache_dir / "mini"))
    secondary_results = run_evaluation(secondary, sample_rows)
    secondary_elapsed = time.time() - started

    predictions = []
    final_reviewer = ClaimReviewer(load_settings(model="gpt-4o"))
    for row in sample_rows:
        predictions.append(final_reviewer.review_claim_row(load_claims_from_row(row)))

    pred_path = args.output_dir / "sample_predictions.csv"
    write_output_csv(pred_path, predictions, OUTPUT_COLUMNS)

    summary = {
        "primary_model": "gpt-4o",
        "compare_model": args.compare_model,
        "sample_rows": len(sample_rows),
        "primary": primary_results,
        "secondary": secondary_results,
        "primary_elapsed_s": primary_elapsed,
        "secondary_elapsed_s": secondary_elapsed,
    }
    summary_path = args.output_dir / "metrics.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nField accuracy (primary gpt-4o):")
    for field, acc in primary_results["field_accuracy"].items():
        print(f"  {field}: {acc:.1%}")

    print(f"\nWrote {pred_path}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
