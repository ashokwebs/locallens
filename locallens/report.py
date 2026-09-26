"""Self-contained, printable HTML report (no external assets; prints cleanly to PDF from any browser)."""
from __future__ import annotations

import html
from datetime import date

from .models import Analysis

LABELS = {"map_visibility": "Map visibility", "reputation": "Reputation", "profile": "Profile completeness",
          "momentum": "Review momentum", "engagement": "Owner replies", "website": "Website health"}


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _gauge(score: int) -> str:
    color = "#d64545" if score < 50 else "#e0a526" if score < 75 else "#2e9e5b"
    dash = 251.3 * score / 100
    return (f'<svg viewBox="0 0 100 100" class="gauge" role="img" aria-label="Score {score} of 100">'
            f'<circle cx="50" cy="50" r="40" fill="none" stroke="var(--track)" stroke-width="10"/>'
            f'<circle cx="50" cy="50" r="40" fill="none" stroke="{color}" stroke-width="10" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.1f} 251.3" transform="rotate(-90 50 50)"/>'
            f'<text x="50" y="55" text-anchor="middle" class="gnum">{score}</text></svg>')


def _rank(pos) -> str:
    return "—" if pos is None else f"#{pos}"


def render_report(a: Analysis) -> str:
    b = a.business
    avg = round(sum(a.competitor_scores.values()) / len(a.competitor_scores)) if a.competitor_scores else None
    bars = "".join(
        f'<div class="bar"><span>{LABELS[k]}</span><div class="track"><i style="width:{100 * v["points"] / v["max"]:.0f}%"></i>'
        f'</div><b>{v["points"]:g}/{v["max"]}</b></div>' for k, v in a.breakdown.items())
    queries = list(a.ranks)
    head = "".join(f"<th>{_e(q)}</th>" for q in queries)
    rows = [f'<tr class="me"><td>{_e(b.name)} <em>(you)</em></td><td>{a.score}</td><td>{_e(b.rating)}</td><td>{b.reviews}</td>'
            + "".join(f"<td>{_rank(a.ranks[q])}</td>" for q in queries)
            + f'<td>{"✓" if b.website else "✗"}</td></tr>']
    for c in a.competitors:
        rows.append(f"<tr><td>{_e(c.name)}</td><td>{a.competitor_scores.get(c.name, '—')}</td><td>{_e(c.rating)}</td>"
                    f"<td>{c.reviews}</td>" + "".join(f"<td>{_rank(a.competitor_ranks.get(c.name, {}).get(q))}</td>"
                                                      for q in queries)
                    + f'<td>{"✓" if c.website else "✗"}</td></tr>')
    fixes = "".join(
        f'<li><div class="fx"><strong>{_e(f.title)}</strong><span class="tag {f.impact}">{f.impact}</span>'
        f'<span class="tag">{_e(f.effort)}</span><span class="pts">+{f.points} pts</span></div><p>{_e(f.why)}</p></li>'
        for f in a.fixes)
    rs = a.reviews
    web = ""
    if a.website:
        issues = "".join(f"<li>{_e(i['title'])}</li>" for i in a.website.get("issues", [])[:5]) or "<li>No major issues.</li>"
        status = ("<strong>does not load</strong>" if a.website.get("unreachable")
                  else "audit score " + _e(a.website.get("score")) + "/100")
        web = (f'<section><h2>Website check</h2><p>{_e(a.website["url"])}: {status}</p>'
               f"<ul>{issues}</ul></section>")
    demo = ('<div class="demo">Demo data: fictional businesses in SerpApi\'s response format. '
            "Set SERPAPI_KEY for live Google results.</div>") if a.mode == "fixtures" else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LocalLens · {_e(b.name)}</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#16202b;--muted:#5d6b7a;--track:#e6e9ee;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f141a;--card:#171e26;--ink:#e8edf2;--muted:#9aa7b4;--track:#2a333d}}}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}}
main{{max-width:960px;margin:0 auto;padding:24px 16px}}header{{display:flex;gap:20px;align-items:center;flex-wrap:wrap}}
.gauge{{width:120px;height:120px}}.gnum{{font:700 26px system-ui;fill:var(--ink)}}h1{{margin:0;font-size:24px}}
.sub{{color:var(--muted)}}section{{background:var(--card);border-radius:14px;padding:18px;margin:16px 0;box-shadow:0 1px 3px #0001}}
h2{{margin:0 0 12px;font-size:17px}}.bar{{display:grid;grid-template-columns:160px 1fr 60px;gap:10px;align-items:center;margin:6px 0}}
.track{{height:10px;background:var(--track);border-radius:6px;overflow:hidden}}.track i{{display:block;height:100%;background:var(--acc)}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:8px 6px;border-bottom:1px solid var(--track);text-align:left}}
tr.me td{{font-weight:600}}.scroll{{overflow-x:auto}}ol{{padding-left:20px}}li p{{margin:4px 0 12px;color:var(--muted)}}
.fx{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}.tag{{font-size:12px;padding:2px 8px;border-radius:10px;background:var(--track)}}
.tag.high{{background:#d6454522;color:#d64545}}.tag.medium{{background:#e0a52622;color:#b3831a}}.pts{{font-size:12px;color:var(--muted)}}
pre{{white-space:pre-wrap;background:var(--bg);padding:12px;border-radius:10px;font:14px/1.5 system-ui}}
.demo{{background:#e0a52622;border:1px solid #e0a52666;padding:10px 14px;border-radius:10px;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media (max-width:640px){{.grid{{grid-template-columns:1fr}}.bar{{grid-template-columns:110px 1fr 52px}}}}
footer{{color:var(--muted);font-size:13px;text-align:center;margin:24px 0}}
</style></head><body><main>{demo}
<header>{_gauge(a.score)}<div><h1>{_e(b.name)}</h1><div class="sub">{_e(b.category)} · {_e(b.address)}</div>
<div class="sub">Google Visibility Score <strong>{a.score}/100</strong>{f" · competitor average {avg}/100" if avg is not None else ""}</div></div></header>
<section><h2>Where the points go</h2>{bars}</section>
<section><h2>You vs your real competitors</h2><div class="scroll"><table><thead><tr><th>Business</th><th>Score</th><th>★</th><th>Reviews</th>{head}<th>Site</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div><p class="sub">Map positions are Google Maps ranks near the business for each search.</p></section>
<section><h2>Fix these first</h2><ol>{fixes}</ol></section>
<div class="grid"><section><h2>What customers say</h2><p><strong>Praise:</strong> {_e(", ".join(rs.praise) or "not enough reviews")}</p>
<p><strong>Complaints:</strong> {_e(", ".join(rs.complaints) or "none in recent reviews")}</p>
<p class="sub">{rs.recent_90d} reviews in the last 90 days · owner replies to {round(100 * (rs.reply_rate or 0))}% · {rs.unanswered_negative} unanswered negative</p></section>
<section><h2>WhatsApp summary</h2><pre>{_e(a.summary_en)}</pre><pre lang="te">{_e(a.summary_te)}</pre></section></div>
{web}
<footer>LocalLens · {date.today().isoformat()} · {a.searches_used} live searches · data: Google Maps via SerpApi</footer>
</main></body></html>"""
