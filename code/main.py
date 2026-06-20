#!/usr/bin/env python3
"""Entry point for multi-modal damage claim review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from claim_reviewer.config import load_settings
from claim_reviewer.reviewer import ClaimReviewer


def verify_api_access(settings) -> None:
    if settings.provider == "gemini":
        if not settings.gemini_api_key:
            raise SystemExit("GEMINI_API_KEY is not set. Add it to code/.env.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.model)
        try:
            model.generate_content("ping", generation_config={"max_output_tokens": 1})
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"Gemini API check failed: {exc}") from exc
        return

    if not settings.openai_api_key:
        raise SystemExit(
            "OPENAI_API_KEY is not set. Add it to code/.env or use --provider gemini."
        )
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "insufficient_quota" in message:
            raise SystemExit(
                "OpenAI returned insufficient_quota. Use --provider gemini or add billing at "
                "https://platform.openai.com/account/billing."
            ) from exc
        if "invalid_api_key" in message or "Incorrect API key" in message:
            raise SystemExit("OpenAI rejected the API key in code/.env.") from exc
        raise SystemExit(f"OpenAI API check failed: {message}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review damage claims from CSV input.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input claims CSV (default: dataset/claims.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: output.csv at repo root)",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "gemini"],
        default="auto",
        help="Vision API provider (auto prefers Gemini when GEMINI_API_KEY is set)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (default: gemini-2.0-flash or gpt-4o depending on provider)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable response caching",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    overrides = {
        "provider": args.provider,
        "use_cache": not args.no_cache,
    }
    if args.model:
        overrides["model"] = args.model
    settings = load_settings(**overrides)

    input_csv = args.input or settings.claims_csv
    output_csv = args.output or (settings.repo_root / "output.csv")

    print(f"Using provider={settings.provider}, model={settings.model}")
    print("Checking API access...")
    verify_api_access(settings)

    reviewer = ClaimReviewer(settings)
    reviewer.process_csv(input_csv, output_csv)

    usage = reviewer.usage
    print("\nRun complete.")
    print(f"Output: {output_csv}")
    print(
        f"Usage: calls={usage.model_calls}, cache_hits={usage.cache_hits}, "
        f"images={usage.images_processed}, "
        f"tokens_in={usage.input_tokens}, tokens_out={usage.output_tokens}, "
        f"latency={usage.total_latency_s:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
