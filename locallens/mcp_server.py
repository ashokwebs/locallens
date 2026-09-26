"""LocalLens as an MCP server (Streamable HTTP, MCP spec 2025-11-25+), usable by any MCP client, e.g. Alexa+.

Run standalone:  python -m locallens.mcp_server            → http://127.0.0.1:8765/mcp
"""
from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from .engine import analyze_business, scan_area
from .serp import SerpClient


def _brief(a) -> dict[str, Any]:
    return {
        "business": a.business.name,
        "visibility_score": a.score,
        "competitor_scores": a.competitor_scores,
        "ranks": a.ranks,
        "top_fixes": [{"title": f.title, "why": f.why, "effort": f.effort, "impact": f.impact} for f in a.fixes[:5]],
        "summary": a.summary_en,
        "searches_used": a.searches_used,
        "data_mode": a.mode,
    }


def build_mcp() -> MCPServer:
    mcp = MCPServer(
        name="locallens",
        title="LocalLens",
        description="Local-search intelligence for small businesses: visibility score, competitors and a prioritised fix list.",
        instructions="Use analyze_business for one named business, compare_competitors to see who beats it and why, "
                     "and scan_area to find businesses in a category/area with the biggest fixable gaps.",
        version="0.1.0",
    )

    @mcp.tool(description="Analyse one local business (name + city): Visibility Score 0-100, map ranks, and top fixes.")
    def analyze_business_tool(business: str, city: str | None = None) -> dict[str, Any]:
        return _brief(analyze_business(business, city=city, client=SerpClient(), audit=False))

    @mcp.tool(description="Compare a business with its real Google Maps competitors: scores, ratings, reviews, ranks.")
    def compare_competitors(business: str, city: str | None = None) -> dict[str, Any]:
        a = analyze_business(business, city=city, client=SerpClient(), audit=False)
        return {
            "business": {"name": a.business.name, "score": a.score, "rating": a.business.rating,
                         "reviews": a.business.reviews, "ranks": a.ranks},
            "competitors": [{"name": c.name, "rating": c.rating, "reviews": c.reviews,
                             "score": a.competitor_scores.get(c.name), "ranks": a.competitor_ranks.get(c.name)}
                            for c in a.competitors],
        }

    @mcp.tool(description="Scan a category in an area and rank businesses by fixable gap (for agencies and consultants).")
    def scan_area_tool(category: str, area: str, limit: int = 10) -> dict[str, Any]:
        rows = scan_area(category, area, limit=limit)
        return {"results": [{"name": r["business"]["name"], "position": r["position"], "quick_score": r["quick_score"],
                             "gaps": r["gaps"]} for r in rows]}

    return mcp


def main() -> None:
    import uvicorn
    app = build_mcp().streamable_http_app(streamable_http_path="/mcp")
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "8765")))


if __name__ == "__main__":
    main()
