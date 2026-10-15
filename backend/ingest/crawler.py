"""Polite crawler for official PAN sources: allow-listed domains, robots.txt, rate limit, change detection."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .chunker import html_to_sections

log = logging.getLogger(__name__)
USER_AGENT = "CivicRouteBot/1.0 (citizen-help RAG; respects robots.txt)"
ALLOWED_DOMAINS = ("incometax.gov.in", "incometaxindia.gov.in", "proteantech.in", "protean-tinpan.com", "utiitsl.com",
                   "pib.gov.in", "uidai.gov.in", "egazette.gov.in")
DELAY_S = 1.5


def source_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


class Crawler:
    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = raw_dir / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.8"},
                                   follow_redirects=True, timeout=30)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _robots_ok(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt", timeout=10)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[base] = rp
                else:
                    self._robots[base] = None  # no robots.txt => allowed
            except httpx.HTTPError:
                self._robots[base] = None
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> dict:
        sid = source_id(url)
        prev = self.manifest.get(url, {})
        rec = {"url": url, "source_id": sid, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if not allowed(url):
            return {**prev, **rec, "status": "blocked-domain", "changed": False}
        if not self._robots_ok(url):
            return {**prev, **rec, "status": "blocked-robots", "changed": False}
        try:
            r = self.client.get(url)
        except httpx.HTTPError as exc:
            log.warning("fetch failed %s: %s", url, exc)
            return {**prev, **rec, "status": f"error: {type(exc).__name__}", "changed": False}
        time.sleep(DELAY_S)
        if not allowed(str(r.url)):  # a redirect must not take us off the official allow-list
            log.warning("redirected off allow-list: %s -> %s", url, r.url)
            return {**prev, **rec, "status": "blocked-redirect", "changed": False}
        if len(r.content) > 15 * 1024 * 1024:
            return {**prev, **rec, "status": "too-large", "changed": False}
        if r.status_code != 200:
            return {**prev, **rec, "status": f"http {r.status_code}", "changed": False}
        is_pdf = "pdf" in r.headers.get("content-type", "") or url.lower().endswith(".pdf")
        ext = "pdf" if is_pdf else "html"
        path = self.raw_dir / f"{sid}.{ext}"
        path.write_bytes(r.content)
        # Hash the *visible text*, not raw HTML, so rotating tokens/ads don't count as changes.
        if is_pdf:
            text_hash = hashlib.sha1(r.content).hexdigest()
        else:
            text_hash = hashlib.sha1("\n".join(t for _, t in html_to_sections(r.text)).encode()).hexdigest()
        changed = bool(prev.get("text_hash")) and prev.get("text_hash") != text_hash
        return {**rec, "status": "ok", "file": path.name, "type": ext, "text_hash": text_hash,
                "changed": changed, "first_seen": prev.get("first_seen", rec["fetched_at"]),
                "last_changed": rec["fetched_at"] if changed or not prev else prev.get("last_changed")}

    def crawl(self, sources: list[dict]) -> list[dict]:
        results = []
        for s in sources:
            rec = self.fetch(s["url"])
            self.manifest[s["url"]] = rec
            results.append(rec)
            log.info("%-14s %s%s", rec["status"], s["url"], "  <-- CHANGED" if rec.get("changed") else "")
        self.manifest_path.write_text(json.dumps(self.manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        return results
