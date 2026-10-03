# SerpApi India Hackathon 2026: submission text (paste into the dashboard)

**Project:** LocalLens
**Track:** AI Agents
**Repository:** https://github.com/ashokwebs/locallens
**Demo video:** <YouTube URL: upload `~/videos/out/locallens-serpapi-live.mp4` (2:45, live data), unlisted is fine>

## Description (≈250 words)
India has 60M+ small businesses, and for clinics, gyms, coaching centres and shops, Google Maps "near me" searches decide
who gets the customer. Owners can see they're behind the shop down the road, but not why, or what to fix first.

LocalLens is an AI agent that plans, searches, compares and acts on live SerpApi data. Given "Sunrise Dental Care,
Mangalagiri", it resolves the business on Google Maps, discovers the competitors Google actually ranks around its
coordinates, tracks its map rank for three real intent searches, reads the latest reviews of the business and its top three
competitors (velocity, owner-reply rate, unanswered negatives, praise/complaint themes) and audits its website. It turns all
of that into a transparent Visibility Score (0–100) next to each competitor's, and a prioritised fix list where every fix
cites the evidence ("you reply to 5% of reviews; competitors reply to 60%"). Output: a shareable report and a WhatsApp-ready
summary in English and Telugu, the way owners in Andhra Pradesh actually communicate.

A Scan-an-area mode ranks every business in a category and area by fixable gap (for web agencies), and an MCP server
(Streamable HTTP, spec 2025-11-25) exposes the agent to any AI assistant. SerpApi engines: google_maps (search, place
details, location-biased search) and google_maps_reviews; ≈9 searches per analysis with on-disk caching and a hard budget.

## Disclosures
- **Prior work:** the website-audit module (`vendor/sitecheck.py`) existed before the hackathon and is reused as a component.
  Everything else (the SerpApi agent, scoring, fixes, reviews analysis, UI, MCP server) was built for this hackathon.
- **AI tools used:** Claude (Anthropic) for coding assistance.
- **Data:** the demo video runs on live SerpApi results (Mangalagiri dental clinics, 03 Oct 2026; 7 searches per analysis, cached on disk).
  Without a key, the app falls back to fixtures: fictional businesses in SerpApi's response format, labelled DEMO DATA in the UI.
