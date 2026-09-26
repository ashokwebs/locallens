# Amazon "Build, Ship, Shape": Alexa+ track submission (Ashok submits on Devpost by Oct 23, 12:00 PT)

**Track:** Alexa+ (self-hosted MCP server, Streamable HTTP, spec 2025-11-25) + simulated Alexa+ experience (`/alexa`).
**Mini challenge:** AWS Builder, only if the MCP server is deployed on AWS (Lambda/Bedrock) with the hackathon credits. Otherwise skip.

## What it does (for the description field)
"Alexa, ask LocalLens how Sunrise Dental Care in Mangalagiri is doing." LocalLens is a self-hosted MCP server that gives
Alexa+ local-search intelligence for small businesses: it resolves the business on Google Maps, finds the competitors Google
actually ranks nearby, checks its map rank for real searches, reads recent reviews and owner-reply rates, and answers in
three spoken sentences: the score, the gap to competitors, and the single first fix. The same tools (`analyze_business_tool`,
`compare_competitors`, `scan_area_tool`) return structured data for the card, and a web simulation (`/alexa`) shows the
voice flow with browser speech recognition and synthesis.

## How to run (judges)
```bash
pip install -r requirements.txt
python -m locallens.mcp_server                 # MCP at http://127.0.0.1:8765/mcp
python examples/mcp_client.py                  # proves the MCP round trip
uvicorn locallens.web.app:app --port 8000      # simulation at http://localhost:8000/alexa
```

## What was built during the submission window (started Aug 31)
The whole project was built in September 2026. MCP server, voice layer (`spoken_summary`, `/api/voice`, `/alexa`) and tests
were added specifically for Alexa+. Pre-existing component: the website-audit module (`vendor/sitecheck.py`).

## Product feedback (required field): fill after testing with the Alexa+ tools
- MCP spec 2025-11-25 via the Python SDK v2 (`MCPServer`, Streamable HTTP): worked first time; the v1→v2 rename (FastMCP → MCPServer) was the only friction.
- Voice design: spoken answers must avoid parentheses/abbreviations ("10 min" → "10 minutes"); we added a speech-cleaning step.
- Friction log (up to 10% bonus): record each onboarding step with the Alexa+ developer tools when you connect the MCP server.

## Video (<3 min)
Reuse DEMO_SCRIPT.md, but lead with the voice flow on `/alexa` (0:00–1:00), then the MCP client in a terminal, then the full report.
