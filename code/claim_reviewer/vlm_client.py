"""OpenAI vision client with caching, retries, and usage tracking."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings
from .images import normalize_image_bytes
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import RESPONSE_JSON_SCHEMA


@dataclass
class UsageStats:
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    images_processed: int = 0
    cache_hits: int = 0
    total_latency_s: float = 0.0

    def merge(self, other: UsageStats) -> None:
        self.model_calls += other.model_calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.images_processed += other.images_processed
        self.cache_hits += other.cache_hits
        self.total_latency_s += other.total_latency_s


@dataclass
class VLMClient:
    settings: Settings
    usage: UsageStats = field(default_factory=UsageStats)
    _last_request_ts: float = 0.0

    def review_claim(
        self,
        *,
        claim_object: str,
        user_claim: str,
        image_paths: list[Path],
        image_ids: list[str],
        evidence_block: str,
        history_block: str,
    ) -> dict:
        user_prompt = build_user_prompt(
            claim_object=claim_object,
            user_claim=user_claim,
            image_ids=image_ids,
            evidence_block=evidence_block,
            history_block=history_block,
        )
        cache_key = self._cache_key(user_prompt, image_paths)
        cached = self._read_cache(cache_key)
        if cached is not None:
            self.usage.cache_hits += 1
            return cached

        if self.settings.provider == "gemini":
            result, call_usage = self._call_gemini(user_prompt, image_paths, image_ids)
        else:
            result, call_usage = self._call_openai(user_prompt, image_paths, image_ids)

        self.usage.merge(call_usage)
        self._write_cache(cache_key, result)
        return result

    def _call_openai(
        self,
        user_prompt: str,
        image_paths: list[Path],
        image_ids: list[str],
    ) -> tuple[dict, UsageStats]:
        if not self.settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it before running the reviewer."
            )

        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        content: list[dict] = [{"type": "text", "text": user_prompt}]
        for path, image_id in zip(image_paths, image_ids, strict=True):
            content.append({"type": "text", "text": f"Image ID: {image_id}"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._encode_image(path), "detail": "high"},
                }
            )

        self._throttle()
        started = time.time()
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "claim_review",
                            "strict": False,
                            "schema": RESPONSE_JSON_SCHEMA,
                        },
                    },
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": content},
                    ],
                )
                latency = time.time() - started
                payload = json.loads(response.choices[0].message.content or "{}")
                usage = UsageStats(
                    model_calls=1,
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                    images_processed=len(image_paths),
                    total_latency_s=latency,
                )
                return payload, usage
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(self.settings.retry_base_delay * (2**attempt))

        raise RuntimeError(f"VLM call failed after retries: {last_error}")

    def _call_gemini(
        self,
        user_prompt: str,
        image_paths: list[Path],
        image_ids: list[str],
    ) -> tuple[dict, UsageStats]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to code/.env.")

        import google.generativeai as genai

        genai.configure(api_key=self.settings.gemini_api_key)
        model = genai.GenerativeModel(
            self.settings.model,
            system_instruction=SYSTEM_PROMPT,
        )

        parts: list[object] = [user_prompt]
        for path, image_id in zip(image_paths, image_ids, strict=True):
            data, mime = normalize_image_bytes(path)
            parts.append(f"Image ID: {image_id}")
            parts.append({"mime_type": mime, "data": data})

        self._throttle()
        started = time.time()
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            try:
                response = model.generate_content(
                    parts,
                    generation_config={
                        "temperature": self.settings.temperature,
                        "response_mime_type": "application/json",
                    },
                )
                latency = time.time() - started
                payload = self._parse_json_response(response.text or "{}")
                usage_meta = getattr(response, "usage_metadata", None)
                usage = UsageStats(
                    model_calls=1,
                    input_tokens=getattr(usage_meta, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(usage_meta, "candidates_token_count", 0) or 0,
                    images_processed=len(image_paths),
                    total_latency_s=latency,
                )
                return payload, usage
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(self.settings.retry_base_delay * (2**attempt))

        raise RuntimeError(f"VLM call failed after retries: {last_error}")

    def _parse_json_response(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def _throttle(self) -> None:
        min_interval = 60.0 / max(self.settings.requests_per_minute, 1)
        elapsed = time.time() - self._last_request_ts
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_ts = time.time()

    def _encode_image(self, path: Path) -> str:
        data, mime = normalize_image_bytes(path)
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _cache_key(self, prompt: str, image_paths: list[Path]) -> str:
        digest = hashlib.sha256()
        digest.update(self.settings.provider.encode("utf-8"))
        digest.update(self.settings.model.encode("utf-8"))
        digest.update(prompt.encode("utf-8"))
        for path in image_paths:
            digest.update(path.name.encode("utf-8"))
            digest.update(str(path.stat().st_size).encode("utf-8"))
        return digest.hexdigest()

    def _cache_path(self, key: str) -> Path:
        assert self.settings.cache_dir is not None
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.settings.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict | None:
        if not self.settings.use_cache:
            return None
        path = self._cache_path(key)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _write_cache(self, key: str, payload: dict) -> None:
        if not self.settings.use_cache:
            return
        self._cache_path(key).write_text(json.dumps(payload, indent=2), encoding="utf-8")
