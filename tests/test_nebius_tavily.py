import os
import pytest
from locallens.tavily import search_tavily, extract_reputation_signals
from locallens.nebius import synthesize_competitor_analysis, DEFAULT_NEBIUS_MODEL
from locallens.config import get_settings


def test_tavily_search_offline_mode():
    data = search_tavily("dental clinic visakhapatnam")
    assert "query" in data
    assert "results" in data
    assert len(data["results"]) >= 1

    signals = extract_reputation_signals(data)
    assert signals["source_count"] >= 1
    assert "sentiment_keywords" in signals


def test_nebius_synthesis_telemetry():
    competitors = [
        {"name": "Apollo Clinic", "score": 88},
        {"name": "Care Diagnostics", "score": 79},
    ]
    res = synthesize_competitor_analysis(
        business_name="Vijaya Diagnostics",
        business_score=68,
        competitors=competitors,
        web_signals={"sentiment": ["wait", "delay"]},
    )
    assert res["ok"] is True
    assert "NVIDIA" in res["hardware"]
    assert res["tokens_per_sec"] > 50.0
    assert "competitive_gap" in res
    assert len(res["critical_fixes"]) >= 1


def test_config_nebius_provider(monkeypatch):
    monkeypatch.setenv("LOCALLENS_LLM", "on")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-nebius-key")
    settings = get_settings()
    assert settings.llm_provider == "nebius"
