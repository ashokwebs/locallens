# Next Founders Hackathon: 5-minute video (due Oct 15, 5 PM EDT = Oct 16 02:30 IST)

Judged 25% each: technical execution · innovation & UX · **business & finance** · communication.

| Time | Section | What to show / say |
|---|---|---|
| 0:00–0:40 | **Problem** | Google Maps on a phone in Mangalagiri: "dentist near me". India has 60M+ small businesses; for clinics, gyms and shops, this search decides who gets the customer. Owners see they're behind but not *why*. Agencies waste hours auditing each prospect by hand. |
| 0:40–2:10 | **Live demo** | LocalLens: type the business → score vs the competitors Google actually ranks → evidence-backed fix list → Telugu WhatsApp summary → Scan-an-area for agencies → the `/alexa` voice demo. |
| 2:10–3:10 | **Architecture & stack** | Diagram from README: FastAPI + a SerpApi agent (google_maps, google_maps_reviews) with disk cache and a hard search budget (≈9 searches per report) → scoring → fixes → report / WhatsApp / MCP server (Streamable HTTP) for any AI assistant. Python, tests, clean install in 5 commands. |
| 3:10–4:10 | **Business & finance** | See model below. |
| 4:10–4:40 | **Scalability** | Caching makes repeat reports free; per-report cost is fixed (≈9 API calls ≈ ₹6 at SerpApi's entry tier); stateless API scales horizontally; MCP lets assistants distribute it. |
| 4:40–5:00 | **Close** | "See why you're losing, fix it first." Ask: pilot with 10 local agencies. |

## Business model (numbers are assumptions, stated as such)
- **Owners, ₹499 one-off report** (sent on WhatsApp) → upsell **₹1,999 fix-it service** (listing + WhatsApp setup) or **₹1,499/month care plan**.
- **Agencies, ₹2,999/month**: 100 area scans + 30 full reports; they resell the fixes. Area scan = 1 search → a ranked lead list.
- **Unit cost:** ≈9 SerpApi searches per full report. On SerpApi's $75/5,000-search plan that's ≈$0.14 (≈₹12) per report, so gross margin > 95% on the ₹499 report.
- **Go-to-market:** Norveth (the founder's studio) already walks into clinics in Vijayawada/Guntur; the report is the opener. Then WhatsApp referral from each fixed business.
- **Year-1 target (assumption):** 30 agencies × ₹2,999 + 200 owner reports/month ≈ ₹1.9L MRR.
