"""Review intelligence: velocity, owner-reply rate, unanswered negatives, and praise/complaint themes.

Themes come from a transparent keyword lexicon (works with no LLM). If an LLM is configured, it refines the
theme labels, but the counts always come from the lexicon so numbers stay verifiable.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from .models import ReviewStats

PRAISE = {
    "friendly staff": r"friendly|polite|courteous|kind staff|helpful",
    "explains clearly": r"explain|patient(ly)? listen|clear(ly)?",
    "clean & hygienic": r"clean|hygien|neat|tidy",
    "painless / gentle": r"painless|no pain|gentle|comfortable",
    "good value": r"afford|reasonable|value for money|fair price|cheap",
    "quick service": r"quick|fast|on time|no waiting|prompt",
    "tasty food": r"tasty|delicious|yummy|flavo",
    "expert / skilled": r"expert|experienced|skilled|professional|best doctor",
    "good ambience": r"ambien|atmosphere|cozy|spacious|nice place",
}
COMPLAINTS = {
    "long waiting time": r"wait|waiting|delay|late|took (too )?long|hours? to",
    "rude staff": r"rude|arrogant|misbehav|unprofessional|shout",
    "expensive / overcharged": r"expensive|overcharg|costly|too much money|high price|charged extra",
    "not clean": r"dirty|unclean|unhygien|smell",
    "no response on phone": r"not (picking|answering|responding)|no response|didn'?t (pick|answer)|unreachable",
    "parking problem": r"parking",
    "bad food / quality": r"stale|cold food|bland|tasteless|poor quality|bad quality",
    "wrong info online": r"closed when|wrong (timing|address|location)|timings? (are )?wrong|shows open",
}


def _parse_date(r: dict[str, Any]) -> date | None:
    iso = r.get("iso_date") or r.get("iso_date_of_last_edit")
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def analyse_reviews(payload: dict[str, Any], today: date | None = None) -> ReviewStats:
    reviews = payload.get("reviews") or []
    today = today or date.today()
    stats = ReviewStats(count_sampled=len(reviews))
    if not reviews:
        return stats
    dates = [d for d in (_parse_date(r) for r in reviews) if d]
    if dates:
        stats.recent_90d = sum(1 for d in dates if (today - d).days <= 90)
        stats.last_review_days = min((today - d).days for d in dates)
    recent = [r.get("rating") for r in reviews if r.get("rating") is not None][:20]
    stats.avg_rating_recent = round(sum(recent) / len(recent), 2) if recent else None
    replied = [r for r in reviews if (r.get("response") or {}).get("snippet")]
    stats.reply_rate = round(len(replied) / len(reviews), 2)
    stats.unanswered_negative = sum(
        1 for r in reviews if (r.get("rating") or 5) <= 3 and not (r.get("response") or {}).get("snippet"))
    praise, complaints = Counter(), Counter()
    for r in reviews:
        text = (r.get("snippet") or "").lower()
        rating = r.get("rating") or 0
        if rating >= 4:
            for label, pat in PRAISE.items():
                if re.search(pat, text):
                    praise[label] += 1
        if rating <= 3 or rating == 0:
            for label, pat in COMPLAINTS.items():
                if re.search(pat, text):
                    complaints[label] += 1
    stats.praise = [f"{k} ({v})" for k, v in praise.most_common(4)]
    stats.complaints = [f"{k} ({v})" for k, v in complaints.most_common(4)]
    return stats
