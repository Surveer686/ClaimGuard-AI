# Operational Analysis

## Models compared

| Strategy | Model | Role |
|---|---|---|
| A (primary) | `gpt-4o` | Final production predictions |
| B (comparison) | `gpt-4o-mini` | Lower-cost baseline |

Evaluation runs both on `dataset/sample_claims.csv` (19 labeled rows). Final `output.csv` uses Strategy A.

## Approximate model calls

| Dataset | Rows | Images (approx.) | VLM calls |
|---|---:|---:|---:|
| Sample evaluation | 19 | ~30 | 19 per strategy |
| Test predictions | 44 | ~82 | 44 |
| **Total (both strategies + final test run with cache)** | | | **~63–101** |

With disk caching enabled, re-runs skip already-seen claims. First full pass: 44 test + 38 eval (two strategies) = 82 calls if uncached; subsequent test-only runs = 44 calls.

## Token usage (estimates)

Per claim (gpt-4o, 1–3 high-detail images):

| Component | Input tokens | Output tokens |
|---|---:|---:|
| System + rules + evidence + history | ~900–1,200 | — |
| User transcript | ~150–400 | — |
| Each image (high detail) | ~600–1,100 | — |
| JSON response | — | ~250–450 |

**Sample set (19 claims, ~30 images):** ~45k–65k input, ~5k–9k output tokens per strategy.

**Test set (44 claims, ~82 images):** ~105k–150k input, ~12k–20k output tokens.

## Images processed

| Split | Image count |
|---|---:|
| Sample | ~30 |
| Test | ~82 |
| **Total** | **~112** |

## Cost estimate (test set)

Pricing assumptions (OpenAI GPT-4o, illustrative):

- Input: **$2.50 / 1M tokens**
- Output: **$10.00 / 1M tokens**
- High-detail images billed as tokens (~765–1,100 tokens each)

| Item | Estimate |
|---|---:|
| Input tokens (~130k) | ~$0.33 |
| Output tokens (~16k) | ~$0.16 |
| **Test set total** | **~$0.50–$0.80** |

Full uncached eval + test with both models: **~$1.20–$1.80**.

`gpt-4o-mini` comparison run is roughly **5–8× cheaper** but less accurate on fine-grained part/severity judgments.

## Latency / runtime

| Stage | Time |
|---|---|
| Single claim (1–3 images) | ~4–12 s |
| Sample eval (19 claims, sequential) | ~2–4 min |
| Test predictions (44 claims) | ~5–10 min |

Measured with 30 RPM throttle. Parallelism is intentionally limited to respect rate limits.

## TPM / RPM strategy

- **Throttle:** 30 requests/minute (`requests_per_minute` in config).
- **Retries:** 3 attempts with exponential backoff (2s, 4s, 8s).
- **Caching:** SHA-256 cache keyed by prompt + image paths/sizes under `code/.cache/`.
- **Batching:** one claim per request (all images in one call) to minimize calls vs. per-image requests.
- **No repeated history/evidence LLM calls:** rules and history are deterministic CSV lookups.

## Final strategy

**gpt-4o** with structured JSON output, high-detail images, evidence requirements in prompt, and post-processing to normalize enums and merge user-history risk flags. This balances accuracy on subtle mismatches (wrong part, severity exaggeration, prompt injection) against acceptable cost for 44 test claims.
