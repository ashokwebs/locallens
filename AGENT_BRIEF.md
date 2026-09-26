# AGENT BRIEF: LocalLens (SerpApi India Hackathon 2026)

You are an autonomous engineering agent. Your supervisor is **Claude** (another AI agent). Ashok (the human) is busy selling and does
not want questions. Work through **every milestone below in one continuous run**, without stopping to ask. Read `PROTOCOL.md` first
and follow it exactly: it is how Claude supervises you.

## Deadline and target
- **SerpApi India Hackathon 2026**: submission closes **Oct 10, 2026, 23:59 IST**. Track: **AI Agents**.
- Judging (no fixed weights): idea strength, originality, technical complexity, usefulness, **meaningful SerpApi usage** (search data must
  be core to the product). AI-assisted development is allowed (disclose it). Prizes ₹1L / ₹40k / ₹20k.
- Required for submission: public GitHub repo with setup instructions, **demo video under 3 minutes**, description, track.
  You prepare everything; **Claude/Ashok publish and submit**.

## The product: LocalLens, an agent that tells a small business exactly why it loses to its neighbours, and what to fix first
Problem (India, tier-2 cities): clinics, coaching centres, gyms, bakeries and boutiques lose walk-ins because their Google presence is
weaker than the shop down the road, and they can't tell *what* is weaker or what to fix first.

**Input:** a business name + city (e.g. "Sri Sai Dental Clinic, Mangalagiri"), or a category + area for **prospect mode**.
**The agent (plan → search → compare → act):**
1. **Resolve the business** with SerpApi `google_maps` (type=search, then place details): rating, review count, category, hours,
   phone, website, photos count, attributes, and coordinates.
2. **Find the real competitors**: the top 5 results for its category near those coordinates (`google_maps` with `ll`), plus the
   organic/local pack for "<category> in <city>" (`google` engine, `local_results`).
3. **Rank tracking**: where the business ranks for 3–5 intent queries ("best dentist near <area>", "<category> <city>") vs competitors.
4. **Reviews intelligence** (`google_maps_reviews`): volume, recency/velocity, owner-reply rate, and themes customers praise or
   complain about. Use an LLM on the review text to extract themes, and compare them with competitors' themes.
5. **Website audit**: reuse Ashok's audit engine at `~/kits/fix-pack/bin/sitecheck.py` (stdlib Python: HTTPS, mobile, SEO, speed).
   Copy what you need into this repo (don't modify the original).
6. **Output**: a **Visibility Score (0–100)** with a transparent breakdown, a side-by-side competitor table, and a **prioritised fix
   list** ("Reply to 23 unanswered reviews: competitors reply to 80%"; "Add opening hours"; "Website fails on mobile"), each with
   effort and expected impact. Export as a clean shareable HTML/PDF and a short **WhatsApp-ready summary in English and Telugu**.
7. **Prospect mode (for agencies):** scan "<category> in <area>", score every business, and rank them by fixable gap. This is
   lead generation for web agencies, and it shows the search data is the core of the product.
8. **MCP server**: expose the core as tools (`analyze_business`, `compare_competitors`, `scan_area`) over **MCP Streamable HTTP
   (spec 2025-11-25+)**. It will be reused for an Amazon Alexa+ entry later, so keep it clean.

**Stack:** Python 3.11+ (FastAPI or similar) + a simple, fast web UI (plain HTML/HTMX or a small React/Vite app, your call; it must
look polished and work on mobile). LLM: free tiers only, via a provider switch: Gemini (`GEMINI_API_KEY`), Groq (`GROQ_API_KEY`),
OpenRouter (`OPENROUTER_API_KEY`). The LLM is optional: a deterministic rule engine must work without it. **Cost: ₹0.**

**Secrets:** read keys only from `~/.config/hackstack/.env` (via env vars). Never print, log or commit a key. `.env*` goes in `.gitignore`.
If `SERPAPI_KEY` is empty, build and test against **recorded fixtures** (write realistic sample JSON matching SerpApi's documented
response shapes) and set `needs_human` in STATUS.json. Don't stop working.

**SerpApi budget:** the free plan has **250 searches/month**. Cache every response on disk (keyed by params); never re-query in tests.
One full analysis should cost ≤ 12 searches. Log the search count per analysis.

## Milestones (do them in order, commit after each, and report per PROTOCOL.md)
- **M1**: repo scaffold, README skeleton, `.gitignore`, config and env loading, SerpApi client with disk cache + fixtures, tests running.
- **M2**: business resolution + competitor discovery + rank tracking (working on fixtures; live if a key exists).
- **M3**: reviews intelligence + website audit integration + Visibility Score with breakdown.
- **M4**: fix-list generator (rules + optional LLM), EN/Telugu WhatsApp summary, HTML/PDF report.
- **M5**: web UI (polished, mobile-friendly): analyze page, competitor table, fix list, prospect-mode scan.
- **M6**: MCP server (Streamable HTTP) with the 3 tools + a tested client example.
- **M7**: README for judges (problem, architecture diagram, SerpApi engines used, setup in ≤5 commands, screenshots),
  `DEMO_SCRIPT.md` (a 2:45 video script, shot by shot), `SUBMISSION.md` (description ≤ 300 words, track, AI tools disclosure,
  "prior project" disclosure: the website audit engine existed before; everything else is new).
- **M8**: hardening: error handling, rate limits, a 3-business end-to-end demo run recorded to `demo/`, and tests green.

## Hard rules
- Stay inside `~/first`. Don't touch other folders except reading `~/kits/fix-pack`.
- **Never** push to GitHub, publish, deploy, post, email, or sign up for anything. Commit locally only.
- No fake data presented as real: fixtures are labelled as fixtures. No invented metrics in the README.
- Don't mention crypto, trading or wallet projects anywhere.
