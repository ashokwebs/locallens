"""Settings from environment variables (loaded from ~/.config/hackstack/.env or ./.env). Keys are never logged."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and key.strip() not in os.environ:
            os.environ[key.strip()] = value


for _candidate in (ROOT / ".env", Path.home() / ".config" / "hackstack" / ".env"):
    _load_env_file(_candidate)


@dataclass(frozen=True)
class Settings:
    serpapi_key: str | None
    fixtures: bool
    cache_dir: Path
    fixtures_dir: Path
    max_searches_per_analysis: int
    llm_provider: str | None

    @property
    def mode(self) -> str:
        return "fixtures" if self.fixtures else "live"


def get_settings() -> Settings:
    key = os.environ.get("SERPAPI_KEY") or None
    forced = os.environ.get("LOCALLENS_FIXTURES", "").lower() in {"1", "true", "yes"}
    provider = None
    for name, env in (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"), ("openrouter", "OPENROUTER_API_KEY")):
        if os.environ.get(env):
            provider = name
            break
    if os.environ.get("LOCALLENS_LLM", "").lower() == "off":
        provider = None
    return Settings(
        serpapi_key=key,
        fixtures=forced or not key,
        cache_dir=Path(os.environ.get("LOCALLENS_CACHE", ROOT / ".cache" / "serp")),
        fixtures_dir=ROOT / "fixtures",
        max_searches_per_analysis=int(os.environ.get("LOCALLENS_MAX_SEARCHES", "14")),
        llm_provider=provider,
    )
