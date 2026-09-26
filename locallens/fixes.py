"""Turn score gaps into a prioritised, concrete fix list (rules first; every fix cites the evidence behind it)."""
from __future__ import annotations

from statistics import median
from typing import Any

from .models import Business, Fix, ReviewStats

TE = {
    "hours": "ప్రారంభ, మూసివేత సమయాలను గూగుల్ లిస్టింగ్‌లో జోడించండి",
    "photos": "15కి పైగా తాజా ఫోటోలు (లోపల, బయట, సిబ్బంది, సేవలు) అప్‌లోడ్ చేయండి",
    "website": "మొబైల్‌లో బాగా కనిపించే ఒక పేజీ వెబ్‌సైట్ పెట్టి, గూగుల్ లిస్టింగ్‌కు లింక్ చేయండి",
    "website_down": "మీ వెబ్‌సైట్ పని చేయడం లేదు. వెంటనే సరిచేయండి లేదా లిస్టింగ్ నుండి తీసేయండి",
    "replies": "జవాబు ఇవ్వని రివ్యూలకు స్పందించండి (ముందుగా ప్రతికూల రివ్యూలకు)",
    "ask_reviews": "సంతృప్తి చెందిన ప్రతి కస్టమర్‌ను రివ్యూ అడగండి (వాట్సాప్ లింక్ + కౌంటర్ వద్ద QR)",
    "complaint": "ఎక్కువగా వచ్చిన ఫిర్యాదును సరిచేసి, ఆ రివ్యూలకు జవాబు ఇవ్వండి",
    "rank": "సెర్చ్‌లో ముందుకు రావడానికి వివరణలో మీ సేవలు, ప్రాంతం పేర్లు జోడించండి",
    "description": "మీ సేవలు, ప్రాంతం పేర్లతో బిజినెస్ వివరణ రాయండి",
    "phone": "సరైన ఫోన్ నంబర్ జోడించండి, కాల్స్ మిస్ కాకుండా చూసుకోండి",
    "site_issue": "వెబ్‌సైట్ సమస్యను సరిచేయండి",
}


def build_fixes(b: Business, ranks: dict[str, int | None], rs: ReviewStats, website: dict[str, Any] | None,
                competitors: list[Business], comp_reviews: dict[str, ReviewStats]) -> list[tuple[Fix, str]]:
    fixes: list[tuple[Fix, str]] = []
    peers_reply = [s.reply_rate for s in comp_reviews.values() if s.reply_rate is not None]
    peer_recent = [s.recent_90d for s in comp_reviews.values()]
    peer_photos = [c.photos for c in competitors if c.photos]

    if not b.has_hours:
        fixes.append((Fix("Add opening hours to your Google listing",
                          "Google hides or down-ranks listings without hours for 'open now' searches.",
                          "high", "10 min", 3, "profile"), TE["hours"]))
    if (b.photos or 0) < 10:
        target = int(median(peer_photos)) if peer_photos else 15
        fixes.append((Fix(f"Upload at least {max(15, target)} recent photos",
                          f"You have {b.photos or 0}; competitors have a median of {target}.",
                          "medium", "1 hour", 3, "profile"), TE["photos"]))
    if not b.phone:
        fixes.append((Fix("Add a phone number that is answered", "Calls are the main conversion for local search.",
                          "high", "10 min", 3, "profile"), TE["phone"]))
    if not b.description:
        fixes.append((Fix("Write a business description with your services and area names",
                          "Descriptions feed Google's relevance matching for service searches.",
                          "medium", "10 min", 2, "profile"), TE["description"]))
    if website and website.get("unreachable"):
        fixes.append((Fix("Your website is down: fix it or remove the link",
                          f"{website['url']} does not resolve, so every visitor who taps it gets an error.",
                          "high", "1 hour", 6, "website"), TE["website_down"]))
    elif not b.website:
        with_site = sum(1 for c in competitors if c.website)
        fixes.append((Fix("Get a fast one-page website and link it from your listing",
                          f"{with_site} of {len(competitors)} competitors link a website; you don't.",
                          "high", "1 day", 8, "website"), TE["website"]))
    elif website and website.get("issues"):
        for issue in website["issues"][:2]:
            fixes.append((Fix(f"Website: {issue['title']}", issue.get("why") or "",
                              "high" if issue["severity"] in ("critical", "high") else "medium", "1 hour", 2,
                              "website"), f"{TE['site_issue']}: {issue['title']}"))
    if rs.count_sampled:
        peer = median(peers_reply) if peers_reply else 0.5
        if (rs.reply_rate or 0) < max(0.3, peer):
            fixes.append((Fix(f"Reply to reviews, starting with the {rs.unanswered_negative} unanswered negative ones",
                              f"You reply to {round(100 * (rs.reply_rate or 0))}% of recent reviews; "
                              f"competitors reply to {round(100 * peer)}%.",
                              "high", "1 hour", round(10 * max(0, peer - (rs.reply_rate or 0))) + 2, "engagement"),
                          TE["replies"]))
        peer_r = median(peer_recent) if peer_recent else 0
        if rs.recent_90d < peer_r:
            fixes.append((Fix("Ask every happy customer for a review (WhatsApp link + counter QR)",
                              f"{rs.recent_90d} reviews in the last 90 days vs a competitor median of {peer_r}.",
                              "high", "10 min", 6, "momentum"), TE["ask_reviews"]))
        if rs.complaints:
            fixes.append((Fix(f"Fix the top complaint: {rs.complaints[0].split(' (')[0]}",
                              f"Mentioned in recent low-rated reviews: {', '.join(rs.complaints[:2])}.",
                              "medium", "1 week", 4, "reputation"), f"{TE['complaint']}: {rs.complaints[0]}"))
    weak = [q for q, pos in ranks.items() if pos is None or pos > 3]
    if weak:
        q = weak[0]
        pos = ranks[q]
        fixes.append((Fix(f"Rank higher for '{q}'",
                          f"You are {'not in the top 20' if pos is None else f'#{pos}'} on Google Maps for it. Add the "
                          "service name and your area to your description and services, and ask for reviews that "
                          "mention them.", "high", "1 hour", 6, "visibility"), TE["rank"]))
    order = {"high": 0, "medium": 1, "low": 2}
    fixes.sort(key=lambda ft: (order[ft[0].impact], -ft[0].points))
    return fixes
