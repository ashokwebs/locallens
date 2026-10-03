"""Plain data models (dataclasses → JSON)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Business:
    name: str
    data_id: str | None = None
    place_id: str | None = None
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    reviews: int = 0
    phone: str | None = None
    website: str | None = None
    has_hours: bool = False
    photos: int | None = None
    description: str | None = None
    thumbnail: str | None = None

    @classmethod
    def from_serp(cls, r: dict[str, Any]) -> "Business":
        gps = r.get("gps_coordinates") or {}
        cat = r.get("type") or ((r.get("types") or [None])[0])
        if isinstance(cat, list):  # live place results return "type" as a list
            cat = cat[0] if cat else None
        photos = r.get("photos_count")
        if photos is None and isinstance(r.get("images"), list):
            photos = len(r["images"])
        return cls(
            name=r.get("title", "").strip(),
            data_id=r.get("data_id"),
            place_id=r.get("place_id"),
            category=cat,
            address=r.get("address"),
            lat=gps.get("latitude"),
            lng=gps.get("longitude"),
            rating=r.get("rating"),
            reviews=int(r.get("reviews") or 0),
            phone=r.get("phone"),
            website=r.get("website"),
            has_hours=bool(r.get("operating_hours") or r.get("hours")),
            photos=photos,
            description=r.get("description"),
            thumbnail=r.get("thumbnail"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewStats:
    count_sampled: int = 0
    avg_rating_recent: float | None = None
    recent_90d: int = 0
    reply_rate: float | None = None          # share of sampled reviews with an owner response
    unanswered_negative: int = 0             # ≤3★ reviews without a reply
    praise: list[str] = field(default_factory=list)
    complaints: list[str] = field(default_factory=list)
    last_review_days: int | None = None


@dataclass
class Fix:
    title: str
    why: str
    impact: str      # high / medium / low
    effort: str      # 10 min / 1 hour / 1 day
    points: int      # score points this fix recovers (estimate)
    category: str


@dataclass
class Analysis:
    business: Business
    competitors: list[Business]
    ranks: dict[str, int | None]                     # query → map position (None = not in top 20)
    competitor_ranks: dict[str, dict[str, int | None]]
    reviews: ReviewStats
    competitor_reviews: dict[str, ReviewStats]
    website: dict[str, Any] | None
    score: int
    breakdown: dict[str, dict[str, Any]]
    competitor_scores: dict[str, int]
    fixes: list[Fix]
    summary_en: str
    summary_te: str
    searches_used: int
    mode: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
