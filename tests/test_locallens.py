import asyncio
import os
from datetime import date

os.environ["LOCALLENS_FIXTURES"] = "1"
os.environ["LOCALLENS_LLM"] = "off"

from fastapi.testclient import TestClient  # noqa: E402

from locallens.audit import score_findings  # noqa: E402
from locallens.engine import analyze_business, scan_area  # noqa: E402
from locallens.models import Business, ReviewStats  # noqa: E402
from locallens.reviews import analyse_reviews  # noqa: E402
from locallens.scoring import score_business  # noqa: E402
from locallens.serp import SerpClient, fixture_name  # noqa: E402
from locallens.web.app import create_app  # noqa: E402

TODAY = date(2026, 9, 27)


def test_fixture_names_are_stable():
    assert fixture_name({"engine": "google_maps", "q": "Dental clinic in Mangalagiri"}) == \
        "google_maps__dental-clinic-in-mangalagiri.json"
    assert fixture_name({"engine": "google_maps_reviews", "data_id": "0x1:0x2"}).startswith("google_maps_reviews__")
    assert fixture_name({"engine": "google_maps", "data_id": "0xab:0xcd"}).startswith("google_maps_place__")


def test_reviews_reply_rate_and_themes():
    payload = {"reviews": [
        {"rating": 5, "snippet": "Friendly staff and very clean", "iso_date": "2026-09-20T10:00:00Z",
         "response": {"snippet": "Thanks!"}},
        {"rating": 2, "snippet": "Had to wait 2 hours", "iso_date": "2026-09-01T10:00:00Z"},
        {"rating": 1, "snippet": "Rude staff, not picking calls", "iso_date": "2025-01-01T10:00:00Z"},
    ]}
    s = analyse_reviews(payload, today=TODAY)
    assert s.count_sampled == 3
    assert s.reply_rate == 0.33
    assert s.unanswered_negative == 2
    assert s.recent_90d == 2
    assert s.last_review_days == 7
    assert any(p.startswith("friendly staff") for p in s.praise)
    assert any(c.startswith("long waiting time") for c in s.complaints)


def test_score_is_bounded_and_rewards_rank():
    b = Business(name="X", rating=4.9, reviews=500, website="https://x", phone="1", has_hours=True, photos=50,
                 description="d")
    rs = ReviewStats(count_sampled=20, recent_90d=20, reply_rate=1.0, last_review_days=1)
    top, _ = score_business(b, {"q1": 1, "q2": 1}, rs, {"score": 100}, [100], [5])
    low, _ = score_business(b, {"q1": None, "q2": None}, rs, {"score": 100}, [100], [5])
    assert top == 100
    assert low == 75
    empty, _ = score_business(Business(name="Y"), {"q": None}, ReviewStats(), None, [10], [3])
    assert 0 <= empty <= 5


def test_audit_scoring():
    assert score_findings([{"severity": "critical"}, {"severity": "low"}, {"severity": "info"}]) == 78


def test_end_to_end_dental_demo():
    client = SerpClient()
    a = analyze_business("Sunrise Dental Care, Mangalagiri", client=client, audit=False, today=TODAY)
    assert a.business.name == "Sunrise Dental Care"
    assert a.mode == "fixtures" and a.searches_used == 0
    assert len(a.competitors) == 5
    assert a.ranks["dental clinic in Mangalagiri"] == 5
    assert a.score < min(a.competitor_scores.values())
    titles = " ".join(f.title for f in a.fixes)
    assert "opening hours" in titles and "website" in titles and "Reply to reviews" in titles
    assert a.fixes[0].impact == "high"
    assert "36/100" in a.summary_en or f"{a.score}/100" in a.summary_en
    assert "స్కోర్" in a.summary_te
    assert client.calls <= 9


def test_scan_area_ranks_by_opportunity():
    rows = scan_area("dental clinic", "Mangalagiri")
    assert rows[0]["business"]["name"] == "Nava Dental Care"
    assert rows[0]["opportunity"] >= rows[-1]["opportunity"]


def test_api():
    c = TestClient(create_app())
    assert c.get("/api/health").json()["mode"] == "fixtures"
    r = c.get("/api/analyze", params={"q": "Iron Temple Fitness, Vijayawada", "audit": "false"})
    assert r.status_code == 200 and r.json()["business"]["name"] == "Iron Temple Fitness"
    assert c.get("/report").status_code == 200
    assert c.get("/api/scan", params={"category": "gym", "area": "Vijayawada"}).json()["results"]
    assert c.get("/api/analyze", params={"q": "Nonexistent Place, Nowhere"}).status_code in (404, 502)


def test_mcp_tools_registered():
    from locallens.mcp_server import build_mcp
    tools = asyncio.run(build_mcp().list_tools())
    names = {t.name for t in tools}
    assert {"analyze_business_tool", "compare_competitors", "scan_area_tool"} <= names
