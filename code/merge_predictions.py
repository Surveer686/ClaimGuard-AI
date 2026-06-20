#!/usr/bin/env python3
"""Merge JSON prediction arrays into output.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_reviewer.data_loader import load_claims, write_output_csv
from claim_reviewer.schema import OUTPUT_COLUMNS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--predictions", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    claims = load_claims(args.claims)
    merged: dict[tuple[str, str, str], dict] = {}

    for pred_file in args.predictions:
        rows = json.loads(pred_file.read_text(encoding="utf-8"))
        for row in rows:
            key = (row["user_id"], row["image_paths"], row["claim_object"])
            merged[key] = row

    ordered = []
    for claim in claims:
        key = (claim.user_id, claim.image_paths, claim.claim_object)
        if key not in merged:
            raise KeyError(f"Missing prediction for {key}")
        ordered.append(merged[key])

    write_output_csv(args.output, ordered, OUTPUT_COLUMNS)
    print(f"Wrote {len(ordered)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
