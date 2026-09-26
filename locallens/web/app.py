"""LocalLens web app (FastAPI): JSON API + a single-page UI. The MCP server runs separately (locallens.mcp_server)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..engine import analyze_business, scan_area
from ..report import render_report
from ..serp import BudgetExceeded, SerpClient, SerpError

STATIC = Path(__file__).parent / "static"
_last: dict[str, Any] = {}


def create_app() -> FastAPI:
    app = FastAPI(title="LocalLens", version="0.1.0",
                  description="Why does a local business lose to its neighbours on Google, and what should it fix first?")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        s = get_settings()
        return {"ok": True, "mode": s.mode, "llm": s.llm_provider}

    @app.get("/api/analyze")
    def analyze(q: str = Query(..., min_length=3, description="Business name and city"),
                city: str | None = None, audit: bool = True) -> dict[str, Any]:
        client = SerpClient()
        try:
            a = analyze_business(q, city=city, client=client, audit=audit)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except (BudgetExceeded, SerpError) as exc:
            raise HTTPException(502, str(exc)) from None
        data = a.to_dict()
        data["log"] = client.log
        _last["analysis"] = a
        return data

    @app.get("/api/scan")
    def scan(category: str, area: str, limit: int = 20) -> dict[str, Any]:
        try:
            rows = scan_area(category, area, limit=limit)
        except (BudgetExceeded, SerpError) as exc:
            raise HTTPException(502, str(exc)) from None
        return {"category": category, "area": area, "results": rows, "mode": get_settings().mode}

    @app.get("/report", response_class=HTMLResponse)
    def report(q: str | None = None, audit: bool = False) -> str:
        a = analyze_business(q, audit=audit) if q else _last.get("analysis")
        if not a:
            raise HTTPException(404, "Run an analysis first or pass ?q=")
        return render_report(a)

    @app.get("/api/voice")
    def voice(q: str = Query(..., min_length=3)) -> dict[str, Any]:
        """Voice endpoint for the Alexa+ simulation: short spoken answer + card data."""
        from statistics import mean
        from ..summary import spoken_summary
        try:
            a = analyze_business(q, client=SerpClient(), audit=False)
        except LookupError as exc:
            return {"spoken": f"Sorry, I couldn't find {q} on Google Maps.", "error": str(exc)}
        avg = round(mean(a.competitor_scores.values())) if a.competitor_scores else None
        _last["analysis"] = a
        return {"spoken": spoken_summary(a.business, a.score, avg, a.fixes, a.ranks), "score": a.score,
                "competitor_average": avg, "business": a.business.name,
                "fixes": [f.title for f in a.fixes[:3]], "mode": a.mode}

    @app.get("/alexa")
    def alexa() -> FileResponse:
        return FileResponse(STATIC / "alexa.html")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    return app


app = create_app()
