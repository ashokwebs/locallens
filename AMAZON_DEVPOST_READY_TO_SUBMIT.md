# 🚀 Amazon "Build, Ship, Shape" (Alexa+ Track) — Ready to Submit

**Platform:** Devpost ([amazonappdev2026.devpost.com](https://amazonappdev2026.devpost.com/))  
**Deadline:** October 24, 2026 at 00:30 IST (Oct 23, 12:00 PT)  
**Track:** Alexa+ (Self-hosted MCP Server, Streamable HTTP)  
**Cash Prizes:** 1st: $25,000 · 2nd: $15,000 · 3rd: $4,000 · Mini Challenges: 5 × $1,000  
**Project Name:** LocalLens  
**Repository:** https://github.com/ashokwebs/locallens  
**Pre-Rendered Demo Video:** `/home/charizard/videos/out/locallens-alexa.mp4` (Ready to upload to YouTube as Unlisted)  
**Video Thumbnail:** `/home/charizard/videos/out/locallens-alexa-thumb.png`  

---

## 1. Project Tagline / One-Liner (100 characters max)
> Self-hosted MCP intelligence server giving Alexa+ real-time Google Maps competitive audits for SMBs.

---

## 2. Description (Devpost Overview Field)

### What it does
LocalLens is an autonomous AI agent and Model Context Protocol (MCP) server that equips Alexa+ with real-time competitive intelligence for local small businesses. 

When a user asks:
> *"Alexa, ask LocalLens how Sunrise Dental Care in Mangalagiri is doing against competitors."*

LocalLens performs a multi-step audit across live search data:
1. **Maps Entity Resolution:** Pins the business coordinates and extracts category-specific attributes.
2. **Competitor Discovery:** Discovers the businesses Google actually ranks nearby for competitive intent queries.
3. **Reputation & Velocity Auditing:** Analyzes review velocity, owner-reply percentages, negative sentiment patterns, and rating gaps.
4. **Three-Sentence Spoken Intelligence:** Generates an immediate, voice-friendly summary:
   * Current Visibility Score (0–100) vs the local category benchmark.
   * The critical operational gap to the #1 competitor.
   * The single highest-ROI action to take today.

The agent simultaneously streams structured telemetry to the companion web dashboard (`/alexa`), allowing users to inspect deep audit cards, competitor matrices, and shareable WhatsApp summaries in English and regional languages.

---

## 3. How we built it
- **MCP Server:** Implemented using Model Context Protocol (Streamable HTTP, Spec 2025-11-25) with tools: `analyze_business_tool`, `compare_competitors`, and `scan_area_tool`.
- **Search Engine:** Integrates SerpApi Google Maps and Maps Reviews endpoints with SQLite persistent caching to protect API quotas.
- **Voice Synthesis & UI:** FastAPI backend exposing `/alexa` voice simulator with browser-native Web Speech API synthesis and speech recognition.
- **Testing:** 9 passing regression and unit test suites covering scoring algorithms, review velocity metrics, and MCP protocol transport.

---

## 4. Challenges we ran into & Developer Feedback (Required Field)
- **Voice Response Formatting:** Initial LLM outputs frequently included parentheses, formatting characters, and markdown tables which sound unnatural when spoken by text-to-speech engines. We built a dedicated voice-sanitization pipeline (`spoken_summary`) that expands abbreviations and normalizes conversational flow into clean spoken dialogue.
- **MCP Protocol Migration:** Migrated from FastMCP v1 conventions to the updated MCP Python SDK v2 (`MCPServer` over Streamable HTTP). The specification standardizes tool discovery and structured parameter serialization cleanly.

---

## 5. What's next for LocalLens
- Deploying the MCP server to AWS Lambda via AWS Serverless Application Model (SAM) with Amazon Bedrock agent integration.
- Automated daily scheduled competitor rank alerts sent directly to SMB owners via Telegram and WhatsApp bots.

---

## 6. How to Run (Instructions for Judges)
```bash
git clone https://github.com/ashokwebs/locallens.git
cd locallens
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Start the MCP Server (Streamable HTTP on port 8765)
python -m locallens.mcp_server

# 2. Run the MCP client verification test
python examples/mcp_client.py

# 3. Launch the Alexa+ Voice Simulator Web UI
uvicorn locallens.web.app:app --port 8000
# Open http://localhost:8000/alexa in Chrome/Brave
```
