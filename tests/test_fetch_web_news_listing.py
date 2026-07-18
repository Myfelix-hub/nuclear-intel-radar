"""Tests for the generic news-listing scraper used by Rosatom (and future
enterprise sites whose news is rendered as a structured HTML listing rather
than RSS).

Contract under test:
    1. fetch_web_news_listing probes start_urls sequentially; first URL with
       parseable items wins.
    2. When all start_urls return 200 HTML but no items parse → silent zero
       (return []); the wrapper records ok=True + warning field.
    3. When all start_urls hard-fail (4xx/5xx/network err) and via_jina=False →
       raise RuntimeError so wrapper records ok=False + error field.
    4. When via_jina=True and direct fails, fall back to Jina markdown reader;
       markdown items are extracted via regex (CSS selectors do not survive
       HTML→markdown conversion).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from datetime import datetime, timezone

from update_news import (
    RawItem,
    WEB_SOURCES_NEWS_LISTING,
    fetch_web_news_listing,
    fetch_web_news_listing_sources,
    _parse_news_listing_html,
)
from nuclear_keywords import SOURCE_TIER_BY_SITE

NOW = datetime.now(timezone.utc)

# A Rosatom-flavored src_def used by most tests. Selectors here are Drupal
# guesses; tests construct their own HTML to match.
ROSATOM_DEF = {
    "site_id": "rosatom",
    "site_name": "Rosatom",
    "start_urls": [
        "https://en.rosatom.ru/news/",
        "https://en.rosatom.ru/",
    ],
    "container_selector": "article.node--type-news",
    "title_selector": "h2.node__title a",
    "link_selector": "h2.node__title a",
    "time_selector": "time",
    "time_attr": "datetime",
    "max_items": 20,
    "via_jina": True,
}


def _build_html_resp(html: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.headers = {"content-type": "text/html; charset=utf-8"}
    resp.raise_for_status.return_value = None
    return resp


def _build_failing_resp(status: int = 404) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    resp.headers = {"content-type": "text/plain"}
    resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


def _build_news_listing_html(items: list[tuple[str, str, str]]) -> str:
    """items = [(title, href, datetime_iso), ...]"""
    blocks = "\n".join(
        f'<article class="node--type-news">'
        f'<h2 class="node__title"><a href="{href}">{title}</a></h2>'
        f'<time datetime="{iso}">{iso[:10]}</time>'
        f'</article>'
        for title, href, iso in items
    )
    return f"<html><body>{blocks}</body></html>"


# ─────────────────────────────────────────────────────────────────────────────
# 1. happy path — first start_url returns parseable HTML
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_happy_path():
    sess = MagicMock(spec=requests.Session)
    html = _build_news_listing_html([
        ("Rosatom commissions new reactor unit", "/news/abc/", "2026-07-15T10:00:00+00:00"),
        ("IAEA mission completes at Leningrad", "/news/def/", "2026-07-14T10:00:00+00:00"),
    ])
    sess.get.return_value = _build_html_resp(html)

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)

    assert len(items) == 2
    assert items[0].site_id == "rosatom"
    assert "Leningrad" in items[0].title or "Rosatom" in items[0].title
    assert items[0].url.startswith("http")
    # second probe URL NOT called because first returned items
    assert sess.get.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. fallback chain — first start_url fails, second succeeds
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_first_url_fails_second_succeeds():
    sess = MagicMock(spec=requests.Session)

    html = _build_news_listing_html([
        ("Press release from Rosatom", "/news/xyz/", "2026-07-13T10:00:00+00:00"),
    ])

    def side_effect(url, **kwargs):
        if "news/" in url:
            return _build_failing_resp(404)
        return _build_html_resp(html)

    sess.get.side_effect = side_effect

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)

    assert len(items) == 1
    assert "Press release" in items[0].title
    assert sess.get.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. silent zero — all start_urls 200 but 0 items parse
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_all_200_but_zero_items():
    sess = MagicMock(spec=requests.Session)
    empty_html = "<html><body><p>no news here</p></body></html>"
    sess.get.return_value = _build_html_resp(empty_html)

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)

    assert items == [], "silent zero must return [] for wrapper to warn"
    # Both start_urls probed
    assert sess.get.call_count == len(ROSATOM_DEF["start_urls"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. all hard-fail, via_jina=False → raise
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_all_fail_no_jina_raises():
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_failing_resp(500)

    def_no_jina = {**ROSATOM_DEF, "via_jina": False}

    with pytest.raises(RuntimeError) as excinfo:
        fetch_web_news_listing(sess, def_no_jina, NOW)
    msg = str(excinfo.value)
    assert "rosatom" in msg
    assert "all" in msg.lower() or "fail" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 5. all hard-fail, via_jina=True → Jina success
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_jina_fallback_when_direct_fails():
    sess = MagicMock(spec=requests.Session)

    direct_html = "<html></html>"  # any direct response (will fail parse)
    jina_md = (
        "Some intro text\n\n"
        "[Rosatom ships fuel to India](https://en.rosatom.ru/news/aaa/)\n\n"
        "[More text here about nuclear](https://en.rosatom.ru/news/bbb/)\n"
    )

    def side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            r = MagicMock()
            r.status_code = 200
            r.text = jina_md
            return r
        return _build_failing_resp(503)

    sess.get.side_effect = side_effect

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)

    # Jina items surface; via_jina path returns them
    assert len(items) >= 1
    assert any("Rosatom ships fuel" in it.title for it in items)


# ─────────────────────────────────────────────────────────────────────────────
# 6. all hard-fail + Jina also fails → combined raise
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_combined_raise_when_direct_and_jina_fail():
    sess = MagicMock(spec=requests.Session)

    def side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            r = MagicMock()
            r.status_code = 403
            r.text = ""
            return r
        return _build_failing_resp(502)

    sess.get.side_effect = side_effect

    with pytest.raises(RuntimeError) as excinfo:
        fetch_web_news_listing(sess, ROSATOM_DEF, NOW)
    msg = str(excinfo.value)
    # Both phases must be mentioned so operators see what failed
    assert "rosatom" in msg
    assert "Jina" in msg or "jina" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 7. wrapper silent-zero visibility
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_sources_records_warning_on_silent_zero(monkeypatch):
    """Wrapper layer: when the inner fetcher returns [], the wrapper must
    populate 'warning' on the status entry — NOT bare ok=True / item_count=0
    / error=null. Same contract as test_silent_zero.py."""
    def _fake_inner(session, src_def, now):
        return []

    monkeypatch.setattr("update_news.fetch_web_news_listing", _fake_inner)
    sess = requests.Session()
    items, statuses = fetch_web_news_listing_sources(sess, NOW)

    assert items == []
    assert len(statuses) == len(WEB_SOURCES_NEWS_LISTING)
    for s in statuses:
        assert s["ok"] is True
        assert s.get("warning"), (
            f"silent zero must surface via 'warning' field: {s}"
        )
        assert s.get("error") is None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Kairos Power — Webflow CMS, /updates page
#    Selectors: container `div.news_item.w-dyn-item`,
#               title `div.news_title_wrap div`,
#               link   `a` (relative href like `/updates/<slug>`).
#    Confirmed by direct local HTML probe 2026-07-18.
# ─────────────────────────────────────────────────────────────────────────────


KAIROS_HTML = """<!DOCTYPE html><html><body>
<div class="news_cards_content u-grid-autofill w-dyn-items">
  <div class="news_item w-dyn-item">
    <a href="/updates/kairos-power-completes-key-fuel-performance-milestone">
      <div class="news_meta_wrap">
        <div class="news_meta_full-date">
          <div class="news_meta_date">Jul</div>
          <div class="news_meta_dot">. </div>
          <div class="news_meta_date">16</div>
          <div class="news_meta_dot">.</div>
          <div class="news_meta_date">2026</div>
        </div>
      </div>
      <div class="news_title_wrap"><div>Kairos Power Completes Key Fuel Performance Milestone for Future Reactor Licensing</div></div>
    </a>
  </div>
  <div class="news_item w-dyn-item">
    <a href="/updates/kairos-power-breaks-ground-on-hermes-2">
      <div class="news_title_wrap"><div>Kairos Power Breaks Ground on Hermes 2 Demonstration Plant</div></div>
    </a>
  </div>
</div>
</body></html>"""


def _kairos_entry() -> dict:
    return next(e for e in WEB_SOURCES_NEWS_LISTING if e["site_id"] == "kairos")


def test_kairos_entry_is_registered():
    """Kairos must be in WEB_SOURCES_NEWS_LISTING so fetch_web_news_listing
    iterates over it. Tier must be 'industry' so it ranks above aggregators."""
    e = _kairos_entry()
    assert e["start_urls"], "kairos must have at least one start_url"
    assert e["via_jina"] is True, "kairos needs Jina fallback for resilience"
    assert SOURCE_TIER_BY_SITE.get("kairos") == "industry"


def test_kairos_selectors_parse_real_html_structure():
    """The HTML mock matches Kairos' actual /updates page DOM (verified by
    local probe 2026-07-18). Selectors must extract: container,
    relative → absolute URL, title text."""
    from datetime import datetime, timezone

    items = _parse_news_listing_html(
        KAIROS_HTML, _kairos_entry(), datetime.now(timezone.utc)
    )
    assert len(items) == 2, f"expected 2 news items, got {len(items)}: {items}"
    # First item: full URL composed from relative href
    assert items[0].url == "https://www.kairospower.com/updates/kairos-power-completes-key-fuel-performance-milestone"
    assert "Fuel Performance Milestone" in items[0].title
    # Second item: title extracted from nested div
    assert "Hermes 2" in items[1].title
    # Date was fragmented across 3 divs → time_selector=None → published_at is None
    assert items[0].published_at is None
    # All items carry nuclear_keyword_score meta so composite scoring can rank them
    assert "nuclear_relevance" in items[0].meta


# ─────────────────────────────────────────────────────────────────────────────
# 9. New SMR / advanced reactor developers — TerraPower & Oklo
#    Cloudflare / managed challenge means direct fetch fails in production too
#    sometimes; via_jina=True is the primary reliable path. These tests verify
#    registration + Jina flag + tier, not the selector specifics (selectors
#    are best-effort guesses; production logs will tell us when to tune).
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("site_id", ["terrapower", "oklo"])
def test_new_smr_source_registered_and_tiered(site_id):
    e = next((s for s in WEB_SOURCES_NEWS_LISTING if s["site_id"] == site_id), None)
    assert e is not None, f"{site_id} missing from WEB_SOURCES_NEWS_LISTING"
    assert e["start_urls"], f"{site_id} must have start_urls"
    assert e["via_jina"] is True, f"{site_id} needs Jina fallback (Cloudflare / SPA)"
    assert SOURCE_TIER_BY_SITE.get(site_id) == "industry"


@pytest.mark.parametrize("site_id", ["terrapower", "oklo"])
def test_new_smr_source_selectors_nonempty(site_id):
    """Selectors are best-effort guesses — production Actions logs will tell
    us when to tune. We at least require them to be present so the fetcher
    doesn't blow up at runtime on missing keys."""
    e = next(s for s in WEB_SOURCES_NEWS_LISTING if s["site_id"] == site_id)
    assert e["container_selector"].strip()
    assert e["title_selector"].strip()
    # link_selector may fall back to title_selector at runtime, so we don't
    # require it — but if present, it must be non-empty.
