const $ = (s) => document.querySelector(s);
const esc = (x) => String(x ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const LABELS = {map_visibility: "Map visibility", reputation: "Reputation", profile: "Profile completeness",
  momentum: "Review momentum", engagement: "Owner replies", website: "Website health"};

fetch("/api/health").then((r) => r.json()).then((h) => {
  const m = $("#mode");
  m.textContent = h.mode === "live" ? "LIVE · SerpApi" : "DEMO DATA";
  m.className = "mode " + h.mode;
  if (h.mode === "live") {  // the default examples are fictional fixture businesses; swap in real ones for live data
    const real = [["Siri Dental, Mangalagiri", "Siri Dental"], ["Trident Super Speciality Dental Hospital, Mangalagiri", "Trident Dental"]];
    document.querySelectorAll(".ex").forEach((b, i) => { if (real[i]) { b.dataset.q = real[i][0]; b.textContent = real[i][1]; } });
    $("#q").placeholder = "Business name, city (e.g. Siri Dental, Mangalagiri)";
  }
}).catch(() => {});

document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", x === b));
  $("#tab-analyze").hidden = b.dataset.tab !== "analyze";
  $("#tab-scan").hidden = b.dataset.tab !== "scan";
}));

document.querySelectorAll(".ex").forEach((b) => b.addEventListener("click", () => {
  $("#q").value = b.dataset.q; $("#f-analyze").requestSubmit();
}));

function gauge(score) {
  const color = score < 50 ? "var(--bad)" : score < 75 ? "var(--mid)" : "var(--good)";
  const dash = (251.3 * score / 100).toFixed(1);
  return `<svg viewBox="0 0 100 100" class="gauge" role="img" aria-label="Score ${score}"><circle cx="50" cy="50" r="40" fill="none" stroke="var(--line)" stroke-width="10"/>
  <circle cx="50" cy="50" r="40" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${dash} 251.3" transform="rotate(-90 50 50)"/>
  <text x="50" y="56" text-anchor="middle" class="gnum">${score}</text></svg>`;
}

const rank = (p) => (p == null ? "—" : `#${p}`);

function render(a) {
  const b = a.business, scores = Object.values(a.competitor_scores);
  const avg = scores.length ? Math.round(scores.reduce((x, y) => x + y, 0) / scores.length) : null;
  const qs = Object.keys(a.ranks);
  const bars = Object.entries(a.breakdown).map(([k, v]) =>
    `<div class="bar"><span>${LABELS[k]}</span><div class="track"><i style="width:${Math.round(100 * v.points / v.max)}%"></i></div><b>${v.points}/${v.max}</b></div>`).join("");
  const row = (name, score, c, ranks, me) => `<tr class="${me ? "me" : ""}"><td>${esc(name)}${me ? " <em>(you)</em>" : ""}</td><td>${score ?? "—"}</td>
    <td>${esc(c.rating)}</td><td>${c.reviews}</td>${qs.map((q) => `<td>${rank((ranks || {})[q])}</td>`).join("")}<td>${c.website ? "✓" : "✗"}</td></tr>`;
  const rows = [row(b.name, a.score, b, a.ranks, true)].concat(a.competitors.map((c) => row(c.name, a.competitor_scores[c.name], c, a.competitor_ranks[c.name], false))).join("");
  const fixes = a.fixes.map((f) => `<li><strong>${esc(f.title)}</strong><span class="tag ${f.impact}">${f.impact}</span><span class="tag">${esc(f.effort)}</span>
    <span class="tag">+${f.points} pts</span><p>${esc(f.why)}</p></li>`).join("");
  const r = a.reviews;
  $("#result").innerHTML = `
  <div class="card hero">${gauge(a.score)}<div><h2>${esc(b.name)}</h2><div class="muted">${esc(b.category)} · ${esc(b.address)}</div>
    <div>Google Visibility Score <strong>${a.score}/100</strong>${avg != null ? ` · nearby competitors average <strong>${avg}</strong>` : ""}</div>
    <div class="muted">${a.searches_used} live searches · ${a.mode === "live" ? "live data" : "demo data"}</div></div></div>
  <div class="card"><h3>Where the points go</h3>${bars}</div>
  <div class="card"><h3>You vs your real competitors</h3><div class="scroll"><table><thead><tr><th>Business</th><th>Score</th><th>★</th><th>Reviews</th>
    ${qs.map((q) => `<th>${esc(q)}</th>`).join("")}<th>Site</th></tr></thead><tbody>${rows}</tbody></table></div></div>
  <div class="card"><h3>Fix these first</h3><ol class="fixes">${fixes}</ol></div>
  <div class="two"><div class="card"><h3>What customers say</h3><p><strong>Praise:</strong> ${esc(r.praise.join(", ") || "not enough reviews")}</p>
    <p><strong>Complaints:</strong> ${esc(r.complaints.join(", ") || "none in recent reviews")}</p>
    <p class="muted">${r.recent_90d} reviews in 90 days · owner replies to ${Math.round(100 * (r.reply_rate || 0))}% · ${r.unanswered_negative} unanswered negative</p></div>
  <div class="card"><h3>WhatsApp summary</h3><pre id="sum-en">${esc(a.summary_en)}</pre><pre id="sum-te" lang="te">${esc(a.summary_te)}</pre>
    <div class="row"><button class="btn" data-copy="sum-en">Copy English</button><button class="btn" data-copy="sum-te">Copy Telugu</button>
    <a class="btn" href="/report" target="_blank" rel="noopener">Open shareable report</a></div></div></div>`;
  $("#result").hidden = false;
  document.querySelectorAll("[data-copy]").forEach((btn) => btn.addEventListener("click", () => {
    navigator.clipboard.writeText($("#" + btn.dataset.copy).textContent).then(() => { btn.textContent = "Copied ✓"; });
  }));
}

$("#f-analyze").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.submitter || $("#f-analyze button"); btn.disabled = true;
  const steps = ["Resolving the business on Google Maps", "Finding its real competitors nearby", "Checking map rank for 3 real searches",
    "Reading recent reviews (theirs and competitors')", $("#audit").checked ? "Auditing the website" : "Skipping website audit", "Scoring and writing the fix list"];
  const ol = $("#steps"); ol.innerHTML = steps.map((s) => `<li>${s}</li>`).join(""); ol.hidden = false; $("#result").hidden = true;
  let i = 0; const tick = setInterval(() => { if (i < steps.length - 1) ol.children[i++].className = "done"; }, 700);
  try {
    const res = await fetch(`/api/analyze?q=${encodeURIComponent($("#q").value)}&audit=${$("#audit").checked}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    [...ol.children].forEach((li) => (li.className = "done")); render(data);
  } catch (err) {
    $("#result").innerHTML = `<div class="err">${esc(err.message)}</div>`; $("#result").hidden = false;
  } finally { clearInterval(tick); btn.disabled = false; }
});

$("#f-scan").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = $("#scan-result"); out.innerHTML = '<div class="card muted">Scanning…</div>';
  try {
    const res = await fetch(`/api/scan?category=${encodeURIComponent($("#cat").value)}&area=${encodeURIComponent($("#area").value)}`);
    const data = await res.json(); if (!res.ok) throw new Error(data.detail || res.statusText);
    out.innerHTML = `<div class="card"><div class="scroll"><table><thead><tr><th>Business</th><th>Map #</th><th>★</th><th>Reviews</th><th>Quick score</th><th>Gaps</th></tr></thead><tbody>
      ${data.results.map((r) => `<tr><td>${esc(r.business.name)}</td><td>#${r.position}</td><td>${esc(r.business.rating)}</td><td>${r.business.reviews}</td>
      <td>${r.quick_score}</td><td>${esc(r.gaps.join(", ") || "—")}</td></tr>`).join("")}</tbody></table></div>
      <p class="muted">Sorted by opportunity (gaps + score deficit). ${data.mode === "live" ? "" : "Demo data."}</p></div>`;
  } catch (err) { out.innerHTML = `<div class="err">${esc(err.message)}</div>`; }
});
