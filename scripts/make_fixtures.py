"""Generate demo fixtures in SerpApi's documented response shapes.

All businesses here are FICTIONAL (names end in "(demo)" in the UI banner). Live mode replaces them with real
SerpApi data; the shapes are the same, so the code path is identical.

Run: python scripts/make_fixtures.py
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallens.serp import fixture_name  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "fixtures"
TODAY = date(2026, 9, 27)
rng = random.Random(42)

WEEK = {d: "9 AM–1 PM, 5–9 PM" for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]}
WEEK["sunday"] = "Closed"


def biz(i, title, typ, rating, reviews, lat, lng, *, website=None, phone=None, hours=True, photos=20, desc=None,
        area="Mangalagiri", street="Main Road"):
    return {
        "title": title, "type": typ, "types": [typ], "rating": rating, "reviews": reviews,
        "place_id": f"ChIJdemo{i:04d}", "data_id": f"0x3a4a0demo{i:04d}:0x{i:04x}",
        "gps_coordinates": {"latitude": lat, "longitude": lng},
        "address": f"{10 + i}-{i % 7 + 1}, {street}, {area}, Andhra Pradesh 522503",
        "phone": phone or f"+91 9{rng.randint(100000000, 999999999)}", "website": website,
        "operating_hours": WEEK if hours else None, "photos_count": photos, "description": desc,
        "thumbnail": None,
    }


PRAISE_TXT = ["Very friendly staff and the doctor explained everything clearly.", "Clean and hygienic clinic, painless treatment.",
              "Quick service, no waiting at all. Reasonable price.", "Experienced doctor, very professional. Highly recommend.",
              "Good ambience and polite reception. Affordable.", "Treatment was gentle and the follow-up was on time."]
COMPLAIN_TXT = ["Had to wait almost 2 hours despite appointment.", "Staff was rude on the phone and not picking calls.",
                "Too expensive, charged extra for x-ray without telling.", "Timings shown on Google are wrong, found it closed.",
                "Waiting time is very long on weekends.", "Not responding to WhatsApp messages for appointment."]


def reviews(n, *, avg, reply_rate, recent_share, seed):
    r = random.Random(seed)
    out = []
    for k in range(n):
        days = r.randint(1, 80) if r.random() < recent_share else r.randint(95, 700)
        rating = 5 if r.random() < (avg - 3) / 2 else r.choice([4, 4, 3, 2, 1] if avg < 4.3 else [4, 5, 3])
        text = r.choice(PRAISE_TXT if rating >= 4 else COMPLAIN_TXT)
        d = TODAY - timedelta(days=days)
        rev = {"user": {"name": f"Customer {seed}-{k}"}, "rating": rating, "date": f"{days} days ago",
               "iso_date": d.isoformat() + "T10:00:00Z", "snippet": text, "likes": r.randint(0, 3)}
        if r.random() < reply_rate:
            rev["response"] = {"date": f"{max(days - 2, 0)} days ago", "snippet": "Thank you for your feedback!"}
        out.append(rev)
    out.sort(key=lambda x: x["iso_date"], reverse=True)
    return out


def write(params, payload):
    OUT.mkdir(exist_ok=True)
    payload = {"search_metadata": {"status": "Success", "demo_fixture": True}, **payload}
    (OUT / fixture_name(params)).write_text(json.dumps(payload, indent=1))


def scenario(target, comps, category, area, rank_orders, review_cfg):
    everyone = [target] + comps
    write({"engine": "google_maps", "q": f"{target['title']}, {area}"}, {"place_results": target})
    write({"engine": "google_maps", "data_id": target["data_id"]}, {"place_results": target})
    queries = [f"{category} in {area}", f"best {category} {area}", f"{category} near me"]
    for q, order in zip(queries, rank_orders):
        results = [dict(everyone[j], position=p) for p, j in enumerate(order, 1)]
        write({"engine": "google_maps", "q": q}, {"local_results": results})
    for b in everyone:
        cfg = review_cfg.get(b["title"], dict(avg=4.4, reply_rate=0.7, recent_share=0.5))
        write({"engine": "google_maps_reviews", "data_id": b["data_id"]},
              {"place_info": {"title": b["title"], "rating": b["rating"], "reviews": b["reviews"]},
               "reviews": reviews(20, seed=hash(b["title"]) % 1000, **cfg)})


def main():
    # Scenario 1: a dental clinic losing to its neighbours
    t = biz(1, "Sunrise Dental Care", "Dental clinic", 4.1, 38, 16.4312, 80.5681, hours=False, photos=4)
    c = [biz(2, "Smile Craft Dental Studio", "Dental clinic", 4.8, 212, 16.4330, 80.5702,
             website="https://example.org/smilecraft", photos=64, desc="Painless dental care, implants, braces."),
         biz(3, "Care32 Dental Hospital", "Dental clinic", 4.6, 147, 16.4291, 80.5660,
             website="https://example.org/care32", photos=41, desc="Family dentistry in Mangalagiri."),
         biz(4, "Pearl Dental Clinic", "Dental clinic", 4.5, 96, 16.4350, 80.5655, photos=22),
         biz(5, "Bright Smile Dentistry", "Dental clinic", 4.3, 61, 16.4275, 80.5720, photos=15),
         biz(6, "Nava Dental Care", "Dental clinic", 3.9, 23, 16.4368, 80.5690, hours=False, photos=3)]
    scenario(t, c, "dental clinic", "Mangalagiri",
             rank_orders=[[1, 2, 3, 4, 0, 5], [1, 2, 3, 4, 5, 0], [2, 1, 3, 0, 4, 5]],
             review_cfg={"Sunrise Dental Care": dict(avg=3.9, reply_rate=0.1, recent_share=0.2),
                         "Smile Craft Dental Studio": dict(avg=4.8, reply_rate=0.9, recent_share=0.6),
                         "Care32 Dental Hospital": dict(avg=4.6, reply_rate=0.7, recent_share=0.5),
                         "Pearl Dental Clinic": dict(avg=4.5, reply_rate=0.5, recent_share=0.4)})
    # Scenario 2: a gym that is ahead on rating but invisible on search
    t2 = biz(11, "Iron Temple Fitness", "Gym", 4.7, 89, 16.5062, 80.6480, area="Vijayawada", street="MG Road",
             website="https://example.org/irontemple", photos=12)
    c2 = [biz(12, "PowerZone Gym", "Gym", 4.5, 356, 16.5071, 80.6495, area="Vijayawada", street="MG Road",
              website="https://example.org/powerzone", photos=80, desc="24x7 gym, personal training, Zumba."),
          biz(13, "Fit Nation Vijayawada", "Gym", 4.4, 240, 16.5040, 80.6460, area="Vijayawada", photos=55,
              desc="Strength and cardio gym near Benz Circle."),
          biz(14, "Muscle Factory", "Gym", 4.2, 131, 16.5090, 80.6440, area="Vijayawada", photos=30),
          biz(15, "Anytime Strong", "Gym", 4.0, 77, 16.5020, 80.6505, area="Vijayawada", photos=18)]
    scenario(t2, c2, "gym", "Vijayawada", rank_orders=[[1, 2, 3, 4, 0], [1, 2, 0, 3, 4], [1, 2, 3, 0, 4]],
             review_cfg={"Iron Temple Fitness": dict(avg=4.7, reply_rate=0.3, recent_share=0.3)})
    print(f"wrote {len(list(OUT.glob('*.json')))} fixtures to {OUT}")


if __name__ == "__main__":
    main()
