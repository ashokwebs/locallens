#!/usr/bin/env python3
"""
sitecheck.py: non-intrusive website health check for the Norveth Website Fix Pack.

Only ordinary visitor requests: one GET of http://, one GET of the homepage, robots.txt,
sitemap.xml, HEAD (or single GET fallback) on at most 50 internal links and 30 images, run
sequentially with a small delay. No crawling beyond the homepage, no forms, no fuzzing, no
login attempts. Optional Lighthouse run (loads the page once in headless Chrome).

Usage:
  sitecheck.py https://example.com                       # writes reports/<host>-<date>/
  sitecheck.py https://example.com --no-lighthouse
  sitecheck.py https://example.com --before reports/x/findings.json   # before/after report
  sitecheck.py https://example.com --client "Sunrise Clinic" --pdf

Outputs: report.md, report.html, findings.json (+ report.pdf with --pdf, needs chromium).
Stdlib only (Python 3.9+).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (compatible; NorvethSiteCheck/1.0; +https://norveth.app)"
TIMEOUT = 15
DELAY = 0.15  # seconds between link/image checks: polite, sequential
MAX_LINKS = 50
MAX_IMAGES = 30
HERE = Path(__file__).resolve().parent.parent

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "pass": 5}
SEV_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "info": "Info", "pass": "Pass"}


# --------------------------------------------------------------------------- HTTP
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


class Resp:
    def __init__(self, url, status, headers, body=b"", elapsed=0.0, error=None):
        self.url, self.status, self.headers, self.body, self.elapsed, self.error = url, status, headers, body, elapsed, error

    def h(self, name, default=""):
        if self.headers is None:
            return default
        return self.headers.get(name, default) or default


def request(url, method="GET", read=True, max_bytes=5_000_000):
    """Single request, no redirect following."""
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-IN,en;q=0.9",
    })
    t0 = time.monotonic()
    try:
        r = _opener.open(req, timeout=TIMEOUT)
        body = r.read(max_bytes) if (read and method != "HEAD") else b""
        return Resp(url, r.status, r.headers, _decode(body, r.headers.get("Content-Encoding")), time.monotonic() - t0)
    except urllib.error.HTTPError as e:  # includes 3xx because redirects are not followed
        body = b""
        try:
            body = e.read(200_000) if read and method != "HEAD" else b""
        except Exception:
            pass
        return Resp(url, e.code, e.headers, _decode(body, e.headers.get("Content-Encoding") if e.headers else None), time.monotonic() - t0)
    except Exception as e:  # DNS, TLS, timeout, refused
        return Resp(url, None, None, b"", time.monotonic() - t0, error=f"{type(e).__name__}: {getattr(e, 'reason', e)}")


def _decode(body, enc):
    if not body or not enc:
        return body
    try:
        if "gzip" in enc:
            return gzip.decompress(body)
        if "deflate" in enc:
            return zlib.decompress(body)
    except Exception:
        pass
    return body


def follow(url, method="GET", hops=6):
    chain = []
    cur = url
    for _ in range(hops):
        r = request(cur, method=method)
        chain.append(r)
        if r.status in (301, 302, 303, 307, 308) and r.h("Location"):
            cur = urllib.parse.urljoin(cur, r.h("Location"))
            continue
        break
    return chain


# --------------------------------------------------------------------------- HTML parsing
class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self._in_title = "", False
        self.metas, self.links, self.anchors, self.images, self.scripts, self.h1 = [], [], [], [], [], 0
        self.html_lang, self.jsonld, self._in_jsonld, self.forms, self.iframes = None, 0, False, 0, []
        self.inline_styles = 0
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.html_lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append(a)
            if "stylesheet" in a.get("rel", "").lower():
                self.stylesheets.append(a.get("href", ""))
        elif tag == "a" and a.get("href"):
            self.anchors.append(a)
        elif tag == "img":
            self.images.append(a)
        elif tag == "script":
            self.scripts.append(a)
            if a.get("type", "").lower() == "application/ld+json":
                self.jsonld += 1
        elif tag == "h1":
            self.h1 += 1
        elif tag == "form":
            self.forms += 1
        elif tag == "iframe":
            self.iframes.append(a.get("src", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def meta(self, key):
        for m in self.metas:
            if m.get("name", "").lower() == key or m.get("property", "").lower() == key:
                return m.get("content", "")
        return None


# --------------------------------------------------------------------------- findings
class Report:
    def __init__(self):
        self.findings = []

    def add(self, fid, sev, title, found, why="", fix="", category="General", stack_fix=None, evidence=None):
        self.findings.append(dict(id=fid, severity=sev, title=title, found=found, why=why, fix=fix,
                                  category=category, stack_fix=stack_fix or {}, evidence=evidence or []))


STACK_HINTS = {
    "https_redirect": {
        "WordPress": "Settings → General: set both URLs to https://. Then Really Simple SSL, or a 301 rule in .htaccess / the host's 'Force HTTPS' toggle.",
        "Wix": "Settings → Domains → turn on HTTPS (Wix redirects automatically once enabled).",
        "Shopify": "Online Store → Domains: SSL is automatic; make sure the primary domain is set and 'Redirect all traffic' is on.",
        "Static/Next": "Enable 'Always use HTTPS' at the host/CDN (Cloudflare, Netlify and Vercel all have it).",
    },
    "hsts": {
        "WordPress": "Add the header at the host/CDN (Cloudflare: SSL/TLS → Edge Certificates → HSTS) or via a headers plugin.",
        "Wix": "Not configurable on Wix. Accept as a platform limitation.",
        "Shopify": "Set by Shopify on *.myshopify.com; custom domains through Cloudflare can add it.",
        "Static/Next": "Netlify _headers / vercel.json headers / Cloudflare HSTS setting.",
    },
    "images": {
        "WordPress": "Install an image optimiser (ShortPixel, Imagify or EWWW), bulk-optimise the library, and enable WebP delivery.",
        "Wix": "Re-upload large photos resized to ≤2000px; Wix converts to WebP automatically.",
        "Shopify": "Use the image_url filter with width= in the theme; re-upload oversized images.",
        "Static/Next": "Use next/image or pre-compress with sharp/squoosh to WebP/AVIF at display size.",
    },
    "seo_meta": {
        "WordPress": "Install Yoast or Rank Math; set the homepage SEO title and meta description.",
        "Wix": "Pages → Home → SEO basics: title tag and meta description.",
        "Shopify": "Online Store → Preferences: homepage title and meta description.",
        "Static/Next": "Set <title> and <meta name=description> in the layout / Next.js metadata export.",
    },
}


def check(url: str, run_lh: bool) -> dict:
    rep = Report()
    parsed = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host = parsed.hostname
    https_url = f"https://{parsed.netloc}{parsed.path or '/'}"
    http_url = f"http://{parsed.netloc}{parsed.path or '/'}"
    meta = {"input": url, "host": host, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}

    # ---- 1. HTTP -> HTTPS
    chain = follow(http_url)
    final = chain[-1]
    hops = [f"{r.status or r.error} {r.url}" for r in chain]
    if final.error and len(chain) == 1:
        rep.add("https_redirect", "info", "Plain http:// not reachable", f"http:// did not answer ({final.error}).",
                "Visitors typing the address without https may get an error instead of the site.",
                "Make sure port 80 answers with a 301 redirect to https://.", "Security", STACK_HINTS["https_redirect"], hops)
    elif urllib.parse.urlparse(final.url).scheme == "https" and final.status and final.status < 400:
        first = chain[0]
        if first.status == 301 or first.status == 308:
            rep.add("https_redirect", "pass", "http:// redirects to https://", f"Permanent redirect ({first.status}) in {len(chain) - 1} hop(s).", category="Security", evidence=hops)
        else:
            rep.add("https_redirect", "low", "HTTPS redirect is temporary", f"http:// redirects with a {first.status} (temporary) instead of 301.",
                    "Google treats temporary redirects as 'the old address may come back', which splits ranking signals.",
                    "Change the redirect to a permanent 301.", "Security", STACK_HINTS["https_redirect"], hops)
        if len(chain) > 3:
            rep.add("redirect_chain", "low", "Long redirect chain", f"{len(chain) - 1} redirects before the page loads.",
                    "Each hop adds delay, especially on mobile data.", "Redirect straight to the final https:// address in one hop.", "Speed", evidence=hops)
    else:
        https_ok = request(https_url, method="HEAD", read=False).status not in (None,)
        rep.add("https_redirect", "high" if https_ok else "critical", "Site does not force HTTPS", f"http:// ends at {final.url} (status {final.status})" + (", although https:// works." if https_ok else " and https:// does not work."),
                "Browsers show 'Not secure' next to your address, and anything typed into forms can be read on public Wi-Fi.",
                ("Add a permanent (301) redirect from every http:// address to https://." if https_ok else "Install a certificate (free with Let's Encrypt or your host) and 301-redirect all http:// traffic to https://."),
                "Security", STACK_HINTS["https_redirect"], hops)

    # ---- 2. TLS certificate
    cert_info = {}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, parsed.port or 443), timeout=TIMEOUT) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                c = ss.getpeercert()
                cert_info = {"tls_version": ss.version(), "not_after": c.get("notAfter"),
                             "issuer": dict(x[0] for x in c.get("issuer", [])).get("organizationName", "?")}
        exp = dt.datetime.strptime(cert_info["not_after"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
        days = (exp - dt.datetime.now(dt.timezone.utc)).days
        cert_info["days_left"] = days
        ev = [f"Issuer: {cert_info['issuer']}", f"Expires: {exp.date()} ({days} days)", f"Protocol: {cert_info['tls_version']}"]
        if days < 0:
            rep.add("tls_expiry", "critical", "SSL certificate has expired", f"Expired {-days} days ago.",
                    "Every visitor sees a full-page security warning; most will leave.", "Renew the certificate now and turn on auto-renewal.", "Security", evidence=ev)
        elif days < 14:
            rep.add("tls_expiry", "high", "SSL certificate expires very soon", f"Expires in {days} days.",
                    "If it lapses, visitors get a full-page security warning.", "Renew now and confirm auto-renewal is on.", "Security", evidence=ev)
        elif days < 30:
            rep.add("tls_expiry", "medium", "SSL certificate expires within a month", f"Expires in {days} days.",
                    "Short-lived certificates are normal if they auto-renew; if renewal is manual this will lapse.", "Confirm auto-renewal with the host.", "Security", evidence=ev)
        else:
            rep.add("tls_expiry", "pass", "SSL certificate valid", f"Valid for {days} more days ({cert_info['issuer']}).", category="Security", evidence=ev)
        if cert_info.get("tls_version") in ("TLSv1", "TLSv1.1"):
            rep.add("tls_version", "high", "Outdated TLS version", f"Server negotiated {cert_info['tls_version']}.",
                    "Old encryption that modern browsers are dropping.", "Enable TLS 1.2 and 1.3 only at the host/CDN.", "Security")
    except ssl.SSLCertVerificationError as e:
        rep.add("tls_expiry", "critical", "SSL certificate is invalid", f"Certificate check failed: {e.verify_message}.",
                "Browsers show a full-page warning ('Your connection is not private').", "Install a valid certificate for this exact domain (including www if used).", "Security")
    except Exception as e:
        rep.add("tls_expiry", "high", "Could not check the SSL certificate", f"{type(e).__name__}: {e}", "HTTPS may not be set up on this domain.", "Set up HTTPS.", "Security")

    # ---- 3. homepage
    page_chain = follow(https_url)
    page = page_chain[-1]
    if page.error or not page.status or page.status >= 400:
        rep.add("homepage", "critical", "Homepage did not load", f"{page.error or page.status} at {page.url}",
                "Nothing else can be checked, and customers can't reach the site.", "Check hosting, DNS and the domain's renewal status.", "Availability")
        return {"meta": meta, "findings": rep.findings, "lighthouse": None, "stack": "Unknown", "cert": cert_info}
    final_url = page.url
    meta["final_url"] = final_url
    body = page.body
    text = body.decode(_charset(page), errors="replace")
    p = PageParser()
    try:
        p.feed(text)
    except Exception:
        pass
    stack = detect_stack(text, page)
    meta["stack"] = stack
    meta["ttfb_s"] = round(page.elapsed, 2)
    meta["html_kb"] = round(len(body) / 1024, 1)

    # response basics
    if page.elapsed > 1.8:
        rep.add("ttfb", "medium", "Server responds slowly", f"The HTML took {page.elapsed:.1f}s to arrive (from our location).",
                "Slow servers delay everything else; Google recommends under 0.8s.", "Turn on page caching and a CDN; on WordPress use a caching plugin (WP Rocket, LiteSpeed Cache) or upgrade hosting.", "Speed")
    else:
        rep.add("ttfb", "pass", "Server response time OK", f"HTML arrived in {page.elapsed:.2f}s.", category="Speed")
    enc = page.h("Content-Encoding")
    if len(body) > 10_000 and not enc:
        rep.add("compression", "medium", "Text compression is off", f"Homepage HTML is {len(body) // 1024} KB and sent uncompressed.",
                "Compression typically makes text 70% smaller: faster loading on mobile data.", "Enable gzip or Brotli at the server/CDN (one toggle on Cloudflare; Apache mod_deflate; Nginx gzip on).", "Speed")
    elif enc:
        rep.add("compression", "pass", "Text compression on", f"Content-Encoding: {enc}", category="Speed")

    # ---- 4. security headers
    H = page.headers
    sec = [
        ("Strict-Transport-Security", "hsts", "medium", "HSTS header missing",
         "Tells browsers to always use HTTPS for this site, so a first visit over public Wi-Fi can't be downgraded.",
         "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains"),
        ("X-Content-Type-Options", "xcto", "low", "X-Content-Type-Options missing",
         "Stops browsers from guessing file types, which blocks a class of injection tricks.", "Add: X-Content-Type-Options: nosniff"),
        ("Referrer-Policy", "referrer", "low", "Referrer-Policy missing",
         "Controls how much of your page addresses leak to other sites your visitors click to.", "Add: Referrer-Policy: strict-origin-when-cross-origin"),
        ("Permissions-Policy", "permissions", "info", "Permissions-Policy missing",
         "Lets you switch off browser features (camera, microphone, location) the site never uses.", "Add: Permissions-Policy: camera=(), microphone=(), geolocation=()"),
    ]
    for hname, fid, sev, title, why, fix in sec:
        if H.get(hname):
            rep.add(fid, "pass", f"{hname} set", H.get(hname)[:120], category="Security")
        else:
            rep.add(fid, sev, title, f"The {hname} header is not sent.", why, fix, "Security", STACK_HINTS["hsts"] if fid == "hsts" else None)
    csp = H.get("Content-Security-Policy") or ""
    xfo = H.get("X-Frame-Options")
    if "frame-ancestors" in csp or xfo:
        rep.add("clickjacking", "pass", "Clickjacking protection set", xfo or "CSP frame-ancestors", category="Security")
    else:
        rep.add("clickjacking", "low", "No clickjacking protection", "Neither X-Frame-Options nor CSP frame-ancestors is set.",
                "Another site could load yours invisibly inside a frame to trick visitors into clicking.", "Add: X-Frame-Options: SAMEORIGIN (or CSP frame-ancestors 'self').", "Security")
    if not csp:
        rep.add("csp", "info", "No Content-Security-Policy", "No CSP header.",
                "A CSP limits which scripts can run, reducing the damage from a hacked plugin or injected script.",
                "Start with a report-only policy and tighten it; don't enable blindly on WordPress/Wix, it can break widgets.", "Security")
    leaks = [f"{k}: {H.get(k)}" for k in ("Server", "X-Powered-By", "X-AspNet-Version", "X-Generator") if H.get(k) and re.search(r"\d", H.get(k))]
    if leaks:
        rep.add("version_leak", "low", "Server software versions exposed", "; ".join(leaks),
                "Publishing exact versions helps attackers look up known holes.", "Hide version numbers (Nginx: server_tokens off; PHP: expose_php = Off).", "Security", evidence=leaks)

    # ---- 5. mobile + SEO basics
    vp = p.meta("viewport")
    if not vp:
        rep.add("viewport", "high", "Not set up for mobile", "No viewport meta tag.",
                "Phones show a shrunken desktop page that people have to pinch and zoom. Google ranks mobile-unfriendly pages lower.",
                'Add <meta name="viewport" content="width=device-width, initial-scale=1"> (or switch to a responsive theme).', "Mobile")
    elif "user-scalable=no" in vp.replace(" ", "") or re.search(r"maximum-scale\s*=\s*1(\.0)?\b", vp):
        rep.add("viewport", "low", "Zoom is disabled on mobile", f'viewport="{vp}"', "People with poor eyesight can't zoom in; it's also an accessibility failure.",
                "Remove user-scalable=no and maximum-scale=1.", "Mobile")
    else:
        rep.add("viewport", "pass", "Mobile viewport set", vp, category="Mobile")

    title = re.sub(r"\s+", " ", p.title).strip()
    if not title:
        rep.add("title", "high", "Page title missing", "The homepage has no <title>.", "The title is the blue link in Google results. Without one, Google invents it.",
                "Write a title like 'Business name | What you do in City' (50–60 characters).", "SEO", STACK_HINTS["seo_meta"])
    elif len(title) < 20 or len(title) > 65:
        rep.add("title", "low", "Page title length could be better", f'"{title}" ({len(title)} characters).',
                "Titles under ~20 characters waste the space; over ~60 get cut off in Google.", "Aim for 50–60 characters: business name, service and city.", "SEO", STACK_HINTS["seo_meta"])
    else:
        rep.add("title", "pass", "Page title OK", f'"{title}" ({len(title)} characters)', category="SEO")

    desc = (p.meta("description") or "").strip()
    if not desc:
        rep.add("description", "medium", "Meta description missing", "No meta description on the homepage.",
                "This is the grey text under your link in Google. Without it, Google picks random text from the page.",
                "Write 1–2 sentences (120–160 characters) saying what you do, where, and why to choose you.", "SEO", STACK_HINTS["seo_meta"])
    elif len(desc) < 70 or len(desc) > 170:
        rep.add("description", "low", "Meta description length could be better", f"{len(desc)} characters.", "Too short wastes the space; too long gets cut off.",
                "Aim for 120–160 characters.", "SEO", STACK_HINTS["seo_meta"])
    else:
        rep.add("description", "pass", "Meta description OK", f"{len(desc)} characters", category="SEO")

    if p.h1 == 0:
        rep.add("h1", "low", "No main heading (H1)", "The homepage has no <h1>.", "Search engines and screen readers use the main heading to understand the page.",
                "Make the main headline an H1 that says what you do.", "SEO")
    elif p.h1 > 1:
        rep.add("h1", "info", "Several H1 headings", f"{p.h1} <h1> tags.", "Not an error, but one clear main heading is easier for Google to read.", "Keep one H1; make the rest H2.", "SEO")
    if not p.html_lang:
        rep.add("lang", "low", "Page language not declared", "<html> has no lang attribute.", "Helps screen readers and Google pick the right language.", 'Add lang="en" (or the site language) to <html>.', "SEO")
    canonical = next((l.get("href") for l in p.links if "canonical" in l.get("rel", "").lower()), None)
    if not canonical:
        rep.add("canonical", "low", "No canonical URL", "No <link rel=canonical>.", "Stops Google splitting your ranking between www/non-www and URL variants.",
                "Add a canonical link pointing to the preferred https:// address.", "SEO")
    og = p.meta("og:title") and p.meta("og:image")
    if not og:
        rep.add("og", "low", "No link preview for WhatsApp/Facebook", "Open Graph title/image tags missing.",
                "When someone shares your site on WhatsApp, it shows a bare link instead of a picture and title.",
                "Add og:title, og:description and og:image (1200×630).", "SEO")
    else:
        rep.add("og", "pass", "Link previews set up", "og:title and og:image present", category="SEO")
    if p.jsonld == 0:
        rep.add("jsonld", "low", "No structured data", "No JSON-LD found.", "Structured data (LocalBusiness) helps Google show hours, address and ratings.",
                "Add LocalBusiness JSON-LD with name, address, phone, hours.", "SEO")
    if not any("icon" in l.get("rel", "").lower() for l in p.links):
        rep.add("favicon", "info", "No favicon declared", "No <link rel=icon>.", "The small logo in browser tabs and some Google results.", "Add a favicon.", "SEO")
    if p.meta("robots") and "noindex" in p.meta("robots").lower():
        rep.add("noindex", "critical", "Homepage is hidden from Google", f'meta robots = "{p.meta("robots")}"',
                "This tells Google not to list your site at all.", "Remove noindex (WordPress: Settings → Reading → uncheck 'Discourage search engines').", "SEO")

    # robots / sitemap (one request each)
    origin = f"{urllib.parse.urlparse(final_url).scheme}://{urllib.parse.urlparse(final_url).netloc}"
    rb = request(origin + "/robots.txt")
    time.sleep(DELAY)
    rb_text = rb.body.decode("utf-8", "replace") if rb.status == 200 else ""
    sm_url = next((m.group(1).strip() for m in re.finditer(r"(?im)^sitemap:\s*(\S+)", rb_text)), origin + "/sitemap.xml")
    sm = request(sm_url, max_bytes=300_000)
    if rb.status == 200 and re.search(r"(?im)^disallow:\s*/\s*$", rb_text) and re.search(r"(?im)^user-agent:\s*\*", rb_text):
        rep.add("robots", "high", "robots.txt blocks the whole site", "robots.txt contains 'Disallow: /' for all crawlers.",
                "Google may stop crawling your pages.", "Remove the 'Disallow: /' line unless the site is meant to be private.", "SEO")
    if sm.status == 200 and b"<urlset" in sm.body or (sm.status == 200 and b"<sitemapindex" in sm.body):
        rep.add("sitemap", "pass", "Sitemap found", sm_url, category="SEO")
    else:
        rep.add("sitemap", "medium", "No sitemap found", f"{sm_url} returned {sm.status or sm.error}.",
                "A sitemap tells Google every page that exists, so new pages get found faster.",
                "Generate a sitemap (Yoast/Rank Math on WordPress; automatic on Wix/Shopify) and submit it in Google Search Console.", "SEO")

    # mixed content
    if final_url.startswith("https://"):
        mixed = sorted({u for u in [i.get("src", "") for i in p.images] + [s.get("src", "") for s in p.scripts] + p.stylesheets + p.iframes if u.startswith("http://")})
        if mixed:
            rep.add("mixed_content", "high", "Insecure content on a secure page", f"{len(mixed)} resource(s) load over http://.",
                    "Browsers block or warn about these, which can break images or scripts and remove the padlock.",
                    "Change these links to https:// (WordPress: Better Search Replace http:// → https://).", "Security", evidence=mixed[:10])

    # ---- 6. internal links (HEAD, max 50)
    base_host = urllib.parse.urlparse(final_url).hostname
    internal, seen = [], set()
    for a in p.anchors:
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "whatsapp:", "sms:")):
            continue
        u = urllib.parse.urljoin(final_url, href).split("#")[0]
        pu = urllib.parse.urlparse(u)
        if pu.scheme not in ("http", "https") or (pu.hostname or "").removeprefix("www.") != (base_host or "").removeprefix("www."):
            continue
        if u not in seen:
            seen.add(u)
            internal.append(u)
    broken, checked = [], 0
    for u in internal[:MAX_LINKS]:
        r = request(u, method="HEAD", read=False)
        if r.status in (405, 501, 403) or r.status is None:
            time.sleep(DELAY)
            r = request(u, method="GET", max_bytes=1024)
        checked += 1
        if r.status is None or r.status >= 400:
            broken.append(f"{r.status or r.error}  {u}")
        time.sleep(DELAY)
    meta["links_checked"] = checked
    meta["links_found"] = len(internal)
    if broken:
        rep.add("broken_links", "high" if len(broken) > 2 else "medium", "Broken links on the homepage",
                f"{len(broken)} of {checked} internal links checked return an error.",
                "Visitors hit 'page not found' and leave; Google sees a neglected site.",
                "Fix the link or add a 301 redirect to the right page (WordPress: Redirection plugin).", "Links", evidence=broken[:20])
    elif checked:
        rep.add("broken_links", "pass", "No broken internal links", f"{checked} internal links on the homepage checked.", category="Links")

    # ---- 7. images (HEAD for size, max 30)
    imgs, seen_i = [], set()
    no_alt = no_dims = 0
    for im in p.images:
        src = im.get("src") or im.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        if "alt" not in im:
            no_alt += 1
        if not (im.get("width") and im.get("height")):
            no_dims += 1
        u = urllib.parse.urljoin(final_url, src)
        if u not in seen_i:
            seen_i.add(u)
            imgs.append(u)
    big, huge, total = [], [], 0
    for u in imgs[:MAX_IMAGES]:
        r = request(u, method="HEAD", read=False)
        size = int(r.h("Content-Length") or 0) if r.status and r.status < 400 else 0
        total += size
        if size > 500_000:
            huge.append(f"{size // 1024} KB  {u}")
        elif size > 200_000:
            big.append(f"{size // 1024} KB  {u}")
        time.sleep(DELAY)
    meta["images_found"] = len(imgs)
    meta["images_kb_checked"] = total // 1024
    if huge:
        rep.add("images_huge", "high", "Very large images", f"{len(huge)} image(s) over 500 KB ({total // 1024} KB across {min(len(imgs), MAX_IMAGES)} images checked).",
                "Large photos are the most common reason small-business sites are slow on mobile data.",
                "Resize to the size shown on screen (usually ≤1600px wide) and convert to WebP. Typical saving: 70–90%.", "Speed", STACK_HINTS["images"], huge[:15] + big[:5])
    elif big:
        rep.add("images_big", "medium", "Some images could be lighter", f"{len(big)} image(s) between 200 and 500 KB.",
                "Every extra 100 KB costs time on a 4G connection.", "Compress and convert to WebP.", "Speed", STACK_HINTS["images"], big[:15])
    elif imgs:
        rep.add("images", "pass", "Image sizes OK", f"{min(len(imgs), MAX_IMAGES)} images checked, {total // 1024} KB total.", category="Speed")
    if no_alt:
        rep.add("img_alt", "low", "Images without alt text", f"{no_alt} image(s) have no alt attribute.",
                "Alt text is read aloud to blind visitors and helps Google Images understand your photos.", "Add a short description to each image (decorative images: alt=\"\").", "Accessibility")
    if no_dims > 3:
        rep.add("img_dims", "low", "Images without width/height", f"{no_dims} image(s) have no width/height.",
                "The page jumps around while loading as images appear (layout shift).", "Set width and height attributes (or CSS aspect-ratio) on images.", "Speed")

    if not internal and not imgs:
        rep.add("js_rendered", "info", "Content is built by JavaScript",
                "The homepage HTML contains no links or images before JavaScript runs, so the link and image checks had nothing to test.",
                "Google can usually render JavaScript, but slower and less reliably; WhatsApp/Facebook previews and some crawlers see an empty page.",
                "Use server-side rendering or static generation for the homepage (Next.js: avoid 'use client' at the page level).", "SEO")

    # ---- 8. Lighthouse
    lh = run_lighthouse(final_url) if run_lh else None
    if lh and lh.get("scores"):
        perf = lh["scores"].get("performance")
        if perf is not None:
            sev = "pass" if perf >= 90 else "low" if perf >= 75 else "medium" if perf >= 50 else "high"
            rep.add("lh_perf", sev, f"Mobile speed score: {perf}/100",
                    f"Largest content shows at {lh['metrics'].get('LCP', '?')}; layout shift {lh['metrics'].get('CLS', '?')}; blocking time {lh['metrics'].get('TBT', '?')}.",
                    "Google's own mobile test (Lighthouse, simulated mid-range phone on 4G). Over half of visitors leave if a page takes more than 3 seconds.",
                    "See 'Biggest speed wins' below." if lh.get("opportunities") else "", "Speed",
                    evidence=[f"{o['title']}: {o['saving']}" for o in lh.get("opportunities", [])[:6]])
        a11y = lh["scores"].get("accessibility")
        if a11y is not None and a11y < 90:
            rep.add("lh_a11y", "medium" if a11y < 75 else "low", f"Accessibility score: {a11y}/100", "Lighthouse accessibility audit.",
                    "Low contrast, missing labels and tiny tap targets make the site hard to use, especially for older customers.", "Fix the listed items.", "Accessibility",
                    evidence=lh.get("a11y_fails", [])[:8])
    meta["cert"] = cert_info
    return {"meta": meta, "findings": rep.findings, "lighthouse": lh, "stack": stack}


def _charset(resp):
    ct = resp.h("Content-Type")
    m = re.search(r"charset=([\w-]+)", ct or "")
    return m.group(1) if m else "utf-8"


def detect_stack(text, resp):
    t = text[:400_000]
    gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', t, re.I)
    g = (gen.group(1) if gen else "").lower()
    if "wordpress" in g or "/wp-content/" in t or "/wp-includes/" in t:
        return "WordPress"
    if "wix.com" in g or "static.wixstatic.com" in t or resp.h("X-Wix-Request-Id"):
        return "Wix"
    if "cdn.shopify.com" in t or resp.h("X-ShopId") or "Shopify.theme" in t:
        return "Shopify"
    if "squarespace" in g or "static1.squarespace.com" in t:
        return "Squarespace"
    if "blogger" in g or "blogger.com" in g:
        return "Blogger"
    if "__NEXT_DATA__" in t or "/_next/static/" in t:
        return "Next.js"
    if "astro" in g:
        return "Astro"
    if "godaddy" in g or "img1.wsimg.com" in t:
        return "GoDaddy Website Builder"
    return "Static / custom"


def run_lighthouse(url):
    npx = shutil.which("npx")
    chrome = os.environ.get("CHROME_PATH") or shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chromium-browser")
    if not npx or not chrome:
        return {"error": "npx or Chrome not found; Lighthouse skipped"}
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"lh-{os.getpid()}.json"
    cmd = [npx, "-y", "lighthouse", url, "--quiet", "--form-factor=mobile", "--only-categories=performance,accessibility,best-practices,seo",
           "--chrome-flags=--headless=new --no-sandbox", "--output=json", f"--output-path={out}", "--max-wait-for-load=45000"]
    try:
        subprocess.run(cmd, env={**os.environ, "CHROME_PATH": chrome}, timeout=240, capture_output=True)
        r = json.loads(out.read_text())
    except Exception as e:
        return {"error": f"Lighthouse failed: {e}"}
    finally:
        out.unlink(missing_ok=True)
    au = r.get("audits", {})
    scores = {k: round((c.get("score") or 0) * 100) for k, c in r.get("categories", {}).items()}
    metrics = {k: au.get(a, {}).get("displayValue", "?") for k, a in
               [("FCP", "first-contentful-paint"), ("LCP", "largest-contentful-paint"), ("TBT", "total-blocking-time"), ("CLS", "cumulative-layout-shift"), ("SI", "speed-index")]}
    opps = []
    for a in au.values():
        d = a.get("details") or {}
        ms = d.get("overallSavingsMs") or 0
        if a.get("score") is not None and a["score"] < 0.9 and ms >= 150:
            opps.append({"title": a.get("title"), "saving": f"~{ms / 1000:.1f}s", "ms": ms})
    opps.sort(key=lambda o: -o["ms"])
    a11y_ids = set()
    for ref in r.get("categories", {}).get("accessibility", {}).get("auditRefs", []):
        a11y_ids.add(ref["id"])
    a11y_fails = [au[i]["title"] for i in a11y_ids if i in au and au[i].get("score") == 0]
    return {"scores": scores, "metrics": metrics, "opportunities": opps[:8], "a11y_fails": a11y_fails, "version": r.get("lighthouseVersion")}


# --------------------------------------------------------------------------- report
def health_score(findings):
    penalty = {"critical": 20, "high": 10, "medium": 5, "low": 2, "info": 0, "pass": 0}
    return max(0, 100 - sum(penalty[f["severity"]] for f in findings))


def render_md(res, client=None, before=None, studio="Norveth Studio", contact="norveth.app"):
    m, F = res["meta"], sorted([dict(f) for f in res["findings"]], key=lambda f: SEV_ORDER[f["severity"]])
    issues = [f for f in F if f["severity"] not in ("pass", "info")]
    notes = [f for f in F if f["severity"] == "info"]
    passes = [f for f in F if f["severity"] == "pass"]
    counts = {s: sum(1 for f in F if f["severity"] == s) for s in SEV_ORDER}
    score = health_score(F)
    date = m["checked_at"][:10]
    E = lambda x: str(x).replace("<", "&lt;").replace(">", "&gt;")
    for f in F:
        for k in ("found", "why", "fix", "title"):
            f[k] = E(f[k])
        f["stack_fix"] = {k: E(v) for k, v in f.get("stack_fix", {}).items()}
    L = []
    L.append(f"# Website health check: {m['host']}\n")
    L.append(f"**Prepared for:** {client or m['host']}  ")
    L.append(f"**Checked:** {date} · **Address:** {m.get('final_url', m['input'])} · **Built with:** {res.get('stack', 'Unknown')}  ")
    L.append(f"**Prepared by:** {studio} ({contact})\n")
    L.append("## Summary\n")
    grade = "Good" if score >= 85 else "Needs work" if score >= 60 else "Poor"
    L.append(f"**Health score: {score}/100 ({grade})**. {counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low-priority issues; {counts['pass']} checks passed.\n")
    lh = res.get("lighthouse") or {}
    if lh.get("scores"):
        s = lh["scores"]
        L.append("| Google Lighthouse (mobile) | Score |\n|---|---|")
        for k, lab in [("performance", "Speed"), ("accessibility", "Accessibility"), ("best-practices", "Best practices"), ("seo", "SEO")]:
            if k in s:
                L.append(f"| {lab} | {s[k]}/100 |")
        L.append("")
    elif lh.get("error"):
        L.append(f"_Lighthouse not run: {lh['error']}_\n")

    if before:
        L.append("## Before and after\n")
        bmap = {f["id"]: f for f in before["findings"]}
        amap = {f["id"]: f for f in F}
        L.append(f"| | Before ({before['meta']['checked_at'][:10]}) | After ({date}) |\n|---|---|---|")
        L.append(f"| **Health score** | {health_score(before['findings'])}/100 | **{score}/100** |")
        bl, al = (before.get("lighthouse") or {}).get("scores", {}), lh.get("scores", {})
        for k, lab in [("performance", "Mobile speed"), ("accessibility", "Accessibility"), ("seo", "SEO")]:
            if k in bl or k in al:
                L.append(f"| {lab} (Lighthouse) | {bl.get(k, '–')} | **{al.get(k, '–')}** |")
        for fid, bf in bmap.items():
            if bf["severity"] in ("pass", "info"):
                continue
            af = amap.get(fid)
            status = "✅ Fixed" if (af is None or af["severity"] == "pass") else ("Improved" if SEV_ORDER[af["severity"]] > SEV_ORDER[bf["severity"]] else "Still open")
            L.append(f"| {bf['title']} | {SEV_LABEL[bf['severity']]} | {status} |")
        L.append("")

    if issues:
        L.append("## Issues to fix (most important first)\n")
        L.append("| # | Severity | Issue | Area |\n|---|---|---|---|")
        for i, f in enumerate(issues, 1):
            L.append(f"| {i} | {SEV_LABEL[f['severity']]} | {f['title']} | {f['category']} |")
        L.append("")
        for i, f in enumerate(issues, 1):
            L.append(f"### {i}. {f['title']}\n")
            L.append(f"<span class=\"sev sev-{f['severity']}\">{SEV_LABEL[f['severity']]}</span> · {f['category']}\n")
            L.append(f"**What we found:** {f['found']}\n")
            if f["why"]:
                L.append(f"**Why it matters:** {f['why']}\n")
            if f["fix"]:
                L.append(f"**How to fix:** {f['fix']}\n")
            st = res.get("stack")
            sk = "Static/Next" if st in ("Next.js", "Astro", "Static / custom") else st
            if f.get("stack_fix", {}).get(sk):
                L.append(f"**On {st}:** {f['stack_fix'][sk]}\n")
            if f["evidence"]:
                L.append("<details><summary>Details</summary>\n\n```\n" + "\n".join(f["evidence"]) + "\n```\n</details>\n")
    if lh.get("opportunities"):
        L.append("## Biggest speed wins (from Lighthouse)\n")
        L.append("| Opportunity | Estimated saving |\n|---|---|")
        for o in lh["opportunities"]:
            L.append(f"| {o['title']} | {o['saving']} |")
        L.append("")
    if notes:
        L.append("## Good to have (optional)\n")
        for f in notes:
            L.append(f"- **{f['title']}.** {f['found']} {f['why']} _Fix:_ {f['fix']}")
        L.append("")
    if passes:
        L.append("## What's already working\n")
        for f in passes:
            L.append(f"- ✅ **{f['title']}**: {f['found']}")
        L.append("")
    L.append("## About this check\n")
    L.append(f"This was an outside-in check using ordinary visitor requests only: the homepage, robots.txt, sitemap, "
             f"and a single request to each of {m.get('links_checked', 0)} internal links and {min(m.get('images_found', 0), MAX_IMAGES)} images on the homepage"
             f"{', plus one Google Lighthouse mobile test' if lh.get('scores') else ''}. Nothing was logged into, submitted or scanned for vulnerabilities. "
             f"Speed results depend on network and location, so treat them as indicative. Timings measured from India.\n")
    L.append(f"**Want these fixed?** The Website Fix Pack covers HTTPS, speed, mobile layout, broken links and SEO basics for a fixed ₹2,999, "
             f"delivered in 48 hours with a before/after report. Reply on WhatsApp or visit {contact}.\n")
    return "\n".join(L)


CSS = Path(HERE / "templates" / "report.css")


def md_to_html(md, title):
    pandoc = shutil.which("pandoc")
    css = CSS.read_text() if CSS.exists() else ""
    if pandoc:
        body = subprocess.run([pandoc, "-f", "gfm", "-t", "html5"], input=md, capture_output=True, text=True).stdout
    else:
        body = "<pre>" + html.escape(md) + "</pre>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{css}</style></head><body><main class="report">{body}</main></body></html>"""


def to_pdf(html_path, pdf_path):
    chrome = os.environ.get("CHROME_PATH") or shutil.which("chromium") or shutil.which("google-chrome")
    if not chrome:
        return False
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", f"file://{Path(html_path).resolve()}"], capture_output=True, timeout=120)
    return Path(pdf_path).exists()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--client", help="Client/business name for the report header")
    ap.add_argument("--out", help="Output directory (default: reports/<host>-<date>)")
    ap.add_argument("--no-lighthouse", action="store_true")
    ap.add_argument("--before", help="findings.json from an earlier run, to produce a before/after report")
    ap.add_argument("--pdf", action="store_true", help="Also write report.pdf (needs chromium)")
    a = ap.parse_args()
    url = a.url if "://" in a.url else "https://" + a.url
    host = urllib.parse.urlparse(url).hostname
    out = Path(a.out or HERE / "reports" / f"{host}-{dt.date.today().isoformat()}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"Checking {url} …", file=sys.stderr)
    res = check(url, run_lh=not a.no_lighthouse)
    before = json.loads(Path(a.before).read_text()) if a.before else None
    md = render_md(res, client=a.client, before=before)
    (out / "findings.json").write_text(json.dumps(res, indent=2, default=str))
    (out / "report.md").write_text(md)
    (out / "report.html").write_text(md_to_html(md, f"Website health check: {host}"))
    if a.pdf:
        ok = to_pdf(out / "report.html", out / "report.pdf")
        print("PDF:", "written" if ok else "failed (no chromium?)", file=sys.stderr)
    F = res["findings"]
    c = {s: sum(1 for f in F if f["severity"] == s) for s in SEV_ORDER}
    print(f"Score {health_score(F)}/100 · critical {c['critical']} · high {c['high']} · medium {c['medium']} · low {c['low']} · pass {c['pass']}", file=sys.stderr)
    if (res.get("lighthouse") or {}).get("scores"):
        print("Lighthouse:", res["lighthouse"]["scores"], file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
