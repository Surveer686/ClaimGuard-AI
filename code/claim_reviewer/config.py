"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    _CODE_DIR = Path(__file__).resolve().parents[1]
    _ENV_FILE = _CODE_DIR / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    repo_root: Path = field(default_factory=_repo_root)
    dataset_dir: Path | None = None
    provider: str = "auto"
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_retries: int = 3
    retry_base_delay: float = 2.0
    requests_per_minute: int = 30
    cache_dir: Path | None = None
    use_cache: bool = True
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    def __post_init__(self) -> None:
        if self.dataset_dir is None:
            self.dataset_dir = self.repo_root / "dataset"
        if self.cache_dir is None:
            self.cache_dir = self.repo_root / "code" / ".cache"
        if self.openai_api_key is None:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if self.gemini_api_key is None:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if self.provider == "auto":
            self.provider = "gemini" if self.gemini_api_key else "openai"
        if self.provider == "gemini" and self.model.startswith("gpt"):
            self.model = "gemini-2.0-flash"

    @property
    def claims_csv(self) -> Path:
        return self.dataset_dir / "claims.csv"

    @property
    def sample_claims_csv(self) -> Path:
        return self.dataset_dir / "sample_claims.csv"

    @property
    def user_history_csv(self) -> Path:
        return self.dataset_dir / "user_history.csv"

    @property
    def evidence_requirements_csv(self) -> Path:
        return self.dataset_dir / "evidence_requirements.csv"

    @property
    def images_dir(self) -> Path:
        return self.dataset_dir / "images"


def load_settings(**overrides: object) -> Settings:
    settings = Settings()
    for key, value in overrides.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    return settings
