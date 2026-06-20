#!/usr/bin/env python3
"""Build output.csv from offline prediction JSON batches."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_reviewer.config import Settings
from claim_reviewer.data_loader import load_claims, write_output_csv
from claim_reviewer.schema import OUTPUT_COLUMNS


def main() -> int:
    settings = Settings()
    claims = load_claims(settings.claims_csv)
    eval_dir = ROOT / "evaluation"
    batch_files = [
        eval_dir / "predictions_batch1.json",
        eval_dir / "predictions_batch2.json",
        eval_dir / "predictions_batch3.json",
    ]

    merged: dict[tuple[str, str, str], dict] = {}
    for batch_file in batch_files:
        if not batch_file.exists():
            print(f"Missing {batch_file}")
            continue
        rows = json.loads(batch_file.read_text(encoding="utf-8"))
        print(f"Loaded {len(rows)} rows from {batch_file.name}")
        for row in rows:
            key = (row["user_id"], row["image_paths"], row["claim_object"])
            merged[key] = row

    ordered = []
    missing = []
    for claim in claims:
        key = (claim.user_id, claim.image_paths, claim.claim_object)
        if key in merged:
            ordered.append(merged[key])
        else:
            missing.append(key)

    if missing:
        print(f"WARNING: {len(missing)} claims still missing predictions")
        for m in missing[:5]:
            print(" ", m)

    output = settings.repo_root / "output.csv"
    write_output_csv(output, ordered, OUTPUT_COLUMNS)
    print(f"Wrote {len(ordered)}/{len(claims)} rows to {output}")
    return 0 if len(ordered) == len(claims) else 1


if __name__ == "__main__":
    raise SystemExit(main())
