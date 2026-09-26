"""The LocalLens agent: plan → search → compare → act.

analyze_business("Sunrise Dental Care, Mangalagiri") runs ≈9 SerpApi searches:
  1  google_maps search         resolve the business (place_results or best local_results match)
  1  google_maps place          details (hours, photos, description) when the search didn't include them
  1  google_maps search @ll     real competitors near its coordinates (also rank query #1)
  2  google_maps search @ll     two more intent queries for rank tracking
  4  google_maps_reviews        the business + its top 3 competitors
The website audit runs locally (no search).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Any, Callable

from .audit import audit_website
from .fixes import build_fixes
from .models import Analysis, Business, ReviewStats
from .reviews import analyse_reviews
from .scoring import score_business
from .serp import SerpClient
from .summary import summary_en, summary_te

Progress = Callable[[str], None]


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _clean_category(cat: str | None) -> str:
    if not cat:
        return "business"
    return re.sub(r"\s+", " ", cat).strip().lower()


def _area(b: Business, city_hint: str | None) -> str:
    if city_hint:
        return city_hint
    if b.address:
        parts = [p.strip() for p in b.address.split(",") if p.strip()]
        for p in reversed(parts):
            if not re.search(r"\d{6}|andhra|india|pradesh", p, re.I):
                return p
    return "near me"


def _position(results: list[dict[str, Any]], b: Business) -> int | None:
    for r in results:
        if (b.data_id and r.get("data_id") == b.data_id) or (b.place_id and r.get("place_id") == b.place_id):
            return int(r.get("position") or results.index(r) + 1)
    for r in results:
        if _similar(r.get("title", ""), b.name) > 0.85:
            return int(r.get("position") or results.index(r) + 1)
    return None


@dataclass
class Plan:
    """What the agent decided to search, recorded for transparency in the report."""
    resolve_query: str
    competitor_query: str = ""
    rank_queries: tuple[str, ...] = ()


def resolve(client: SerpClient, query: str) -> Business | None:
    data = client.maps_search(query)
    if data.get("place_results"):
        return Business.from_serp(data["place_results"])
    results = data.get("local_results") or []
    if not results:
        return None
    name = query.split(",")[0]
    best = max(results, key=lambda r: _similar(r.get("title", ""), name))
    return Business.from_serp(best)


def enrich(client: SerpClient, b: Business) -> Business:
    """Fetch place details if the search result lacked them (hours/photos/description)."""
    if b.data_id and (b.photos is None or not b.has_hours or b.description is None):
        place = client.maps_place(b.data_id).get("place_results")
        if place:
            detailed = Business.from_serp(place)
            for field in ("photos", "description", "website", "phone"):
                if getattr(b, field) in (None, "") and getattr(detailed, field) not in (None, ""):
                    setattr(b, field, getattr(detailed, field))
            b.has_hours = b.has_hours or detailed.has_hours
    return b


def analyze_business(query: str, city: str | None = None, client: SerpClient | None = None,
                     audit: bool = True, progress: Progress | None = None, today: date | None = None) -> Analysis:
    client = client or SerpClient()
    client.budget = client.budget or client.settings.max_searches_per_analysis
    say = progress or (lambda _m: None)
    notes: list[str] = []
    start_searches = client.searches

    say(f"Resolving '{query}' on Google Maps")
    b = resolve(client, query if not city or city.lower() in query.lower() else f"{query}, {city}")
    if not b:
        raise LookupError(f"Could not find '{query}' on Google Maps")
    b = enrich(client, b)
    category = _clean_category(b.category)
    area = _area(b, city)
    ll = f"@{b.lat},{b.lng},14z" if b.lat and b.lng else None
    plan = Plan(resolve_query=query, competitor_query=f"{category} in {area}",
                rank_queries=(f"{category} in {area}", f"best {category} {area}", f"{category} near me"))

    say(f"Finding real competitors: '{plan.competitor_query}' around its location")
    ranks: dict[str, int | None] = {}
    comp_positions: dict[str, dict[str, int | None]] = {}
    competitors: list[Business] = []
    for i, q in enumerate(plan.rank_queries):
        results = client.maps_search(q, ll=ll).get("local_results") or []
        ranks[q] = _position(results, b)
        if i == 0:
            for r in results:
                c = Business.from_serp(r)
                same = (c.data_id and c.data_id == b.data_id) or _similar(c.name, b.name) > 0.85
                if not same and len(competitors) < 5:
                    competitors.append(c)
        for c in competitors:
            comp_positions.setdefault(c.name, {})[q] = _position(results, c)

    say(f"Reading recent reviews for {b.name} and the top 3 competitors")
    rs = analyse_reviews(client.maps_reviews(b.data_id), today=today) if b.data_id else ReviewStats()
    comp_reviews: dict[str, ReviewStats] = {}
    for c in competitors[:3]:
        comp_reviews[c.name] = analyse_reviews(client.maps_reviews(c.data_id), today=today) if c.data_id else ReviewStats()

    website = None
    if audit and b.website:
        say(f"Auditing the website {b.website}")
        website = audit_website(b.website)
    elif not b.website:
        notes.append("No website linked on the Google listing.")

    peer_reviews = [c.reviews for c in competitors]
    peer_recent = [s.recent_90d for s in comp_reviews.values()]
    score, breakdown = score_business(b, ranks, rs, website, peer_reviews, peer_recent)
    comp_scores = {}
    for c in competitors[:3]:
        cs = comp_reviews.get(c.name, ReviewStats())
        comp_scores[c.name], _ = score_business(c, comp_positions.get(c.name, {}), cs, None,
                                                peer_reviews, peer_recent, website_estimate=True)

    fix_pairs = build_fixes(b, ranks, rs, website, competitors, comp_reviews)
    fixes = [f for f, _ in fix_pairs]
    fixes_te = [t for _, t in fix_pairs]
    avg_comp = round(mean(comp_scores.values())) if comp_scores else None
    analysis = Analysis(
        business=b, competitors=competitors, ranks=ranks, competitor_ranks=comp_positions, reviews=rs,
        competitor_reviews=comp_reviews, website=website, score=score, breakdown=breakdown,
        competitor_scores=comp_scores, fixes=fixes,
        summary_en=summary_en(b, score, avg_comp, fixes), summary_te=summary_te(b, score, avg_comp, fixes_te),
        searches_used=client.searches - start_searches, mode=client.settings.mode, notes=notes,
    )
    say(f"Done: Visibility Score {score}/100 using {analysis.searches_used} live searches")
    return analysis


def quick_score(b: Business, rank: int | None, peer_reviews: list[int]) -> tuple[int, list[str]]:
    """Cheap score for prospect mode (no review/place calls): uses only the search result itself."""
    rs = ReviewStats()
    score, breakdown = score_business(b, {"area": rank}, rs, None, peer_reviews, [], website_estimate=True)
    gaps = []
    if not b.website:
        gaps.append("no website")
    if not b.has_hours:
        gaps.append("no hours")
    if (b.rating or 0) < 4.0:
        gaps.append(f"rating {b.rating}")
    if b.reviews < (sorted(peer_reviews)[len(peer_reviews) // 2] if peer_reviews else 0):
        gaps.append(f"only {b.reviews} reviews")
    return score, gaps


def scan_area(category: str, area: str, client: SerpClient | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Prospect mode for agencies: 1 search → every business in the area ranked by fixable gap."""
    client = client or SerpClient()
    results = client.maps_search(f"{category} in {area}").get("local_results") or []
    businesses = [Business.from_serp(r) for r in results][:limit]
    peer_reviews = [b.reviews for b in businesses]
    rows = []
    for pos, b in enumerate(businesses, 1):
        score, gaps = quick_score(b, pos, peer_reviews)
        rows.append({"business": b.to_dict(), "position": pos, "quick_score": score, "gaps": gaps,
                     "opportunity": len(gaps) * 10 + (100 - score) // 2})
    rows.sort(key=lambda r: -r["opportunity"])
    return rows
