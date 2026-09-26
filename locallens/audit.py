"""Website health via the bundled audit engine (vendor/sitecheck.py: stdlib-only, homepage-only, non-intrusive).

This engine existed before the hackathon (disclosed in SUBMISSION.md); LocalLens wraps it.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .config import ROOT

SITECHECK = ROOT / "vendor" / "sitecheck.py"
PENALTY = {"critical": 20, "high": 10, "medium": 5, "low": 2}


def score_findings(findings: list[dict[str, Any]]) -> int:
    return max(0, 100 - sum(PENALTY.get(f.get("severity", ""), 0) for f in findings))


def audit_website(url: str | None, timeout: int = 90) -> dict[str, Any] | None:
    """Run the audit; returns {url, score, issues[...]} or None when there is no website."""
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                [sys.executable, str(SITECHECK), url, "--client", "LocalLens", "--out", tmp],
                capture_output=True, timeout=timeout, check=False,
            )
            data = json.loads((Path(tmp) / "findings.json").read_text())
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return {"url": url, "score": None, "issues": [], "error": "audit did not complete"}
    findings = data.get("findings") or []
    issues = [
        {"severity": f.get("severity"), "title": f.get("title"), "why": f.get("why"), "fix": f.get("fix"),
         "category": f.get("category")}
        for f in findings if f.get("severity") in PENALTY
    ]
    issues.sort(key=lambda i: -PENALTY[i["severity"]])
    unreachable = any("Name or service not known" in (f.get("found") or "") for f in findings)
    return {"url": url, "score": 0 if unreachable else score_findings(findings), "issues": issues,
            "unreachable": unreachable, "stack": data.get("stack")}
