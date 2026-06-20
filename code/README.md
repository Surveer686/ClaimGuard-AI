# Multi-Modal Evidence Review

Vision-language pipeline that verifies damage claims for cars, laptops, and packages using submitted images, chat transcripts, user history, and minimum evidence requirements.

## Architecture

```text
claims.csv + images + user_history.csv + evidence_requirements.csv
        │
        ▼
  ClaimReviewer
    ├── evidence requirement retrieval
    ├── user history risk context
    └── GPT-4o vision call (structured JSON)
        │
        ▼
   output.csv
```

Each claim gets one VLM call with all images attached. Responses are cached on disk by prompt/image hash to avoid repeat API cost during development.

## Setup

```bash
cd code
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
set OPENAI_API_KEY=your_key_here   # Windows
# export OPENAI_API_KEY=your_key_here  # macOS/Linux
```

## Run predictions

From the repo root:

```bash
python code/main.py
```

Options:

- `--input dataset/claims.csv`
- `--output output.csv`
- `--model gpt-4o`
- `--no-cache`

## Evaluate on sample labels

```bash
python code/evaluation/main.py
```

This compares **gpt-4o** vs **gpt-4o-mini** on `dataset/sample_claims.csv`, writes `code/evaluation/metrics.json`, and saves `code/evaluation/sample_predictions.csv`.

## Design notes

- **Images first**: decisions are grounded in visible evidence; history only adds risk flags.
- **Prompt injection defense**: chat/image instructions to auto-approve are ignored; `text_instruction_present` is flagged.
- **Evidence rules**: requirements from `evidence_requirements.csv` are injected into the prompt.
- **Structured output**: JSON schema constrains fields to allowed enums.
- **Rate limiting**: configurable RPM throttle and exponential backoff retries.
- **Caching**: `code/.cache/` stores per-claim responses.

## Environment variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required for inference |

## Submission artifacts

| Path | Description |
|---|---|
| `code/` | Runnable solution |
| `code/evaluation/` | Evaluation scripts + report |
| `output.csv` | Predictions for `dataset/claims.csv` |
