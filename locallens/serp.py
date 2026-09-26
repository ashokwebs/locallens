"""SerpApi client: disk cache keyed by request params, a per-analysis search budget, and a fixtures mode.

Every live call is cached forever (SerpApi's free plan is 250 searches/month), so re-running an analysis costs 0 searches.
In fixtures mode (no SERPAPI_KEY, or LOCALLENS_FIXTURES=1) responses come from ./fixtures, recorded in SerpApi's
documented response shapes. Fixture businesses are fictional and labelled as demo data in the UI.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings, get_settings

API = "https://serpapi.com/search.json"


class BudgetExceeded(RuntimeError):
    pass


class SerpError(RuntimeError):
    pass


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def fixture_name(params: dict[str, Any]) -> str:
    """Stable, human-readable fixture filename for a request."""
    engine = params.get("engine", "google")
    if engine == "google_maps_reviews":
        return f"google_maps_reviews__{_norm(str(params.get('data_id', '')))}.json"
    if engine == "google_maps" and (params.get("data_id") or params.get("place_id")):
        return f"google_maps_place__{_norm(str(params.get('data_id') or params.get('place_id')))}.json"
    return f"{engine}__{_norm(str(params.get('q', '')))}.json"


@dataclass
class SerpClient:
    settings: Settings = field(default_factory=get_settings)
    budget: int | None = None
    searches: int = 0          # billable (non-cached) SerpApi calls in this session
    calls: int = 0             # all calls, including cache/fixture hits
    log: list[dict[str, Any]] = field(default_factory=list)

    def _cache_path(self, params: dict[str, Any]) -> Path:
        blob = json.dumps({k: v for k, v in sorted(params.items()) if k != "api_key"}, sort_keys=True)
        return self.settings.cache_dir / (hashlib.sha1(blob.encode()).hexdigest() + ".json")

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        self.calls += 1
        if self.settings.fixtures:
            path = self.settings.fixtures_dir / fixture_name(params)
            if not path.is_file():
                self.log.append({"params": params, "source": "fixture-missing"})
                return {"search_metadata": {"status": "Success"}, "error": "no fixture", "_fixture": path.name}
            self.log.append({"params": params, "source": "fixture"})
            return json.loads(path.read_text())
        cache = self._cache_path(params)
        if cache.is_file():
            self.log.append({"params": params, "source": "cache"})
            return json.loads(cache.read_text())
        if self.budget is not None and self.searches >= self.budget:
            raise BudgetExceeded(f"search budget of {self.budget} reached")
        query = urllib.parse.urlencode({**params, "api_key": self.settings.serpapi_key, "output": "json"})
        req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "LocalLens/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:  # network errors surface without leaking the key
            raise SerpError(f"SerpApi request failed for engine={params.get('engine')}: {type(exc).__name__}") from None
        if data.get("error") and "hasn't returned any results" not in data["error"]:
            raise SerpError(data["error"])
        self.searches += 1
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        self.log.append({"params": params, "source": "live"})
        return data

    # --- engines used by LocalLens -------------------------------------------------------------
    def maps_search(self, q: str, ll: str | None = None) -> dict[str, Any]:
        return self.search({"engine": "google_maps", "type": "search", "q": q, "ll": ll, "hl": "en", "gl": "in"})

    def maps_place(self, data_id: str) -> dict[str, Any]:
        return self.search({"engine": "google_maps", "type": "place", "data_id": data_id, "hl": "en"})

    def maps_reviews(self, data_id: str) -> dict[str, Any]:
        return self.search({"engine": "google_maps_reviews", "data_id": data_id, "hl": "en", "sort_by": "newestFirst"})

    def google(self, q: str, location: str | None = None) -> dict[str, Any]:
        return self.search({"engine": "google", "q": q, "location": location, "hl": "en", "gl": "in", "num": 10})
