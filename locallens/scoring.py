"""Visibility Score (0-100): transparent, component-by-component, each compared with the real competitors.

    Map visibility      25  where the business ranks on Google Maps for real intent queries
    Reputation          25  star rating (15) + review volume vs the competitor median (10)
    Profile completeness 15 website, phone, hours, photos, description
    Momentum            15  reviews in the last 90 days vs competitors (10) + recency of the last review (5)
    Engagement          10  owner-reply rate on reviews
    Website health      10  audit score of the linked website (0 if none or unreachable)
"""
from __future__ import annotations

from statistics import median
from typing import Any

from .models import Business, ReviewStats

RANK_POINTS = {1: 25, 2: 21, 3: 18, 4: 13, 5: 13}


def _rank_points(pos: int | None) -> float:
    if pos is None:
        return 0
    if pos in RANK_POINTS:
        return RANK_POINTS[pos]
    return 8 if pos <= 10 else 3 if pos <= 20 else 0


def _clamp(x: float, lo: float = 0, hi: float = 1) -> float:
    return max(lo, min(hi, x))


def score_business(b: Business, ranks: dict[str, int | None], rs: ReviewStats, website: dict[str, Any] | None,
                   peer_reviews: list[int], peer_recent: list[int], website_estimate: bool = False
                   ) -> tuple[int, dict[str, dict[str, Any]]]:
    med_reviews = median(peer_reviews) if peer_reviews else max(b.reviews, 1)
    med_recent = median(peer_recent) if peer_recent else max(rs.recent_90d, 1)

    visibility = sum(_rank_points(p) for p in ranks.values()) / max(len(ranks), 1)
    rating_pts = 15 * _clamp(((b.rating or 0) - 3.5) / 1.4)
    volume_pts = 10 * _clamp(b.reviews / (med_reviews or 1), 0, 1)
    profile = {
        "website": 4 if b.website else 0,
        "phone": 3 if b.phone else 0,
        "hours": 3 if b.has_hours else 0,
        "photos": 3 if (b.photos or 0) >= 10 else (1.5 if (b.photos or 0) >= 3 else 0),
        "description": 2 if b.description else 0,
    }
    momentum = 10 * _clamp(rs.recent_90d / (med_recent or 1), 0, 1)
    if rs.last_review_days is not None:
        momentum += 5 if rs.last_review_days <= 30 else 3 if rs.last_review_days <= 90 else 0
    engagement = 10 * (rs.reply_rate or 0)
    if website_estimate:
        web_pts = 5.0 if b.website else 0.0          # competitors: presence only, not audited
    else:
        web_pts = 0.0 if not website or website.get("score") is None else website["score"] / 10

    breakdown = {
        "map_visibility": {"points": round(visibility, 1), "max": 25, "detail": ranks},
        "reputation": {"points": round(rating_pts + volume_pts, 1), "max": 25,
                       "detail": {"rating": b.rating, "reviews": b.reviews, "competitor_median_reviews": med_reviews}},
        "profile": {"points": round(sum(profile.values()), 1), "max": 15, "detail": profile},
        "momentum": {"points": round(momentum, 1), "max": 15,
                     "detail": {"reviews_last_90d": rs.recent_90d, "competitor_median_90d": med_recent,
                                "days_since_last_review": rs.last_review_days}},
        "engagement": {"points": round(engagement, 1), "max": 10, "detail": {"reply_rate": rs.reply_rate}},
        "website": {"points": round(web_pts, 1), "max": 10,
                    "detail": {"estimated": website_estimate,
                               "audit_score": None if website_estimate or not website else website.get("score")}},
    }
    total = round(sum(v["points"] for v in breakdown.values()))
    return int(total), breakdown
