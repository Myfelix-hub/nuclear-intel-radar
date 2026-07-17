"""Tests for NucNet source migration from direct scraping to RSS.

Background: NucNet's homepage scraping was returning HTTP 403 from
Cloudflare-protected Actions runner IPs. The site exposes a real RSS
feed at /feed.rss that returns 14.9KB of clean Atom/RSS content.

These tests pin the configuration migration so the pipeline picks up
NucNet via RSS, not BeautifulSoup scraping of the homepage.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from update_news import NUCLEAR_RSS_FEEDS, WEB_SOURCES_DIRECT


def _rss_by_site(site_id: str) -> dict | None:
    return next((f for f in NUCLEAR_RSS_FEEDS if f["site_id"] == site_id), None)


def _direct_by_site(site_id: str) -> dict | None:
    return next((f for f in WEB_SOURCES_DIRECT if f["site_id"] == site_id), None)


def test_nucnet_registered_in_rss_feeds():
    """nucnet must be in NUCLEAR_RSS_FEEDS — homepage scraping is dead (HTTP 403)."""
    feed = _rss_by_site("nucnet")
    assert feed is not None, "nucnet missing from NUCLEAR_RSS_FEEDS"
    assert feed["site_name"] == "NucNet"
    assert feed["xml_url"] == "https://www.nucnet.org/feed.rss", (
        f"xml_url must be the real NucNet RSS endpoint, got {feed['xml_url']!r}"
    )
    assert feed["html_url"] == "https://www.nucnet.org"


def test_nucnet_removed_from_web_direct_sources():
    """nucnet must NOT be in WEB_SOURCES_DIRECT — homepage scraping is unreliable
    (Cloudflare 403 on production runner IPs)."""
    direct = _direct_by_site("nucnet")
    assert direct is None, (
        f"nucnet must be removed from WEB_SOURCES_DIRECT, still found: {direct}"
    )


def test_nucnet_rss_endpoint_reachable():
    """End-to-end: the registered XML URL must actually return a feed (>=1KB)."""
    import requests
    feed = _rss_by_site("nucnet")
    assert feed is not None
    r = requests.get(feed["xml_url"], timeout=15,
                     headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 200, f"NucNet RSS returned HTTP {r.status_code}"
    assert len(r.content) > 1024, f"NucNet RSS body too small: {len(r.content)}B"
    body = r.content[:200].lower()
    assert b"<rss" in body or b"<feed" in body, (
        f"NucNet RSS doesn't look like an RSS/Atom feed: {r.content[:200]!r}"
    )