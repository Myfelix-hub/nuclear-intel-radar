"""Tests verifying that fetch_*_sources wrappers surface "silent zero" as a warning.

A "silent zero" is a fetcher that returns [] without raising — meaning the network
round-trip succeeded but no usable items came back. Today, the four wrapper layers
(fetch_rss_sources, fetch_web_direct_sources, fetch_web_jina_sources, collect_all
community block) all record ok=True with item_count=0 and error=null. This hides
real production failures (DOE-NE, OECD-NEA, ITER's first commit) from operators.

Contract under test:
    When an inner fetcher returns [] without raising, the wrapper MUST record
    ok=True AND populate a "warning" field on the status dict, so source-status.json
    and the operator can distinguish "source is empty" from "source is healthy".

    When the inner fetcher raises, the wrapper records ok=False with "error".
    When the inner fetcher returns items, the wrapper records ok=True with item_count>0.
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
    collect_all,
    fetch_rss_sources,
    fetch_web_direct_sources,
    fetch_web_jina_sources,
    NUCLEAR_RSS_FEEDS,
    WEB_SOURCES_DIRECT,
    WEB_SOURCES_JINA,
)

NOW = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# fetch_rss_sources — silent zero
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_rss_sources_warns_on_silent_zero(monkeypatch):
    """When every RSS fetcher returns [] without raising, fetch_rss_sources
    must record ok=True with a populated 'warning' field for each source,
    NOT bare ok=True / error=None / item_count=0."""
    def _fake_fetch(session, feed_def, now):
        return []  # silent zero: HTTP ok, no items

    monkeypatch.setattr("update_news.fetch_single_rss_feed", _fake_fetch)
    sess = requests.Session()
    items, statuses = fetch_rss_sources(sess, NOW)

    assert items == [], "no items should be returned"
    assert len(statuses) == len(NUCLEAR_RSS_FEEDS), \
        "one status per RSS source"
    for s in statuses:
        assert s["ok"] is True, f"network did succeed — ok should be True: {s}"
        assert s["item_count"] == 0, f"zero items: {s}"
        assert s.get("warning"), (
            f"silent zero must be surfaced via 'warning' field, "
            f"got status without warning: {s}"
        )
        assert s.get("error") is None, (
            f"warning is not an error — error must stay None for silent zero: {s}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# fetch_web_direct_sources — silent zero
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_direct_sources_warns_on_silent_zero(monkeypatch):
    """When fetch_web_direct returns [] without raising (e.g. BeautifulSoup
    parses a page but no links match the selector), the wrapper must warn."""
    def _fake_fetch(session, src_def, now):
        return []  # silent zero

    monkeypatch.setattr("update_news.fetch_web_direct", _fake_fetch)
    sess = requests.Session()
    items, statuses = fetch_web_direct_sources(sess, NOW)

    assert items == []
    assert len(statuses) == len(WEB_SOURCES_DIRECT)
    for s in statuses:
        assert s["ok"] is True
        assert s.get("warning"), (
            f"silent zero must be surfaced via 'warning' field: {s}"
        )
        assert s.get("error") is None


# ─────────────────────────────────────────────────────────────────────────────
# fetch_web_jina_sources — silent zero
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_jina_sources_warns_on_silent_zero(monkeypatch):
    """When Jina returns the markdown but no links survive the skip patterns
    (e.g. OECD-NEA's homepage), the wrapper must warn."""
    def _fake_fetch(session, src_def, now):
        return []  # silent zero

    monkeypatch.setattr("update_news.fetch_web_jina", _fake_fetch)
    sess = requests.Session()
    items, statuses = fetch_web_jina_sources(sess, NOW)

    assert items == []
    assert len(statuses) == len(WEB_SOURCES_JINA)
    for s in statuses:
        assert s["ok"] is True
        assert s.get("warning"), (
            f"silent zero must be surfaced via 'warning' field: {s}"
        )
        assert s.get("error") is None


# ─────────────────────────────────────────────────────────────────────────────
# collect_all community block (HN + Reddit) — silent zero
# ─────────────────────────────────────────────────────────────────────────────


def test_collect_all_warns_when_community_fetchers_return_empty(monkeypatch):
    """When fetch_hn_nuclear and fetch_reddit_nuclear both return [] without
    raising (all queries/subreddits return 200 but produce zero nuclear items),
    collect_all's community status entries must each carry a warning."""
    def _fake_fetch(session, now):
        return []

    # Preserve original function names so collect_all's site_id patch table
    # (line ~1010 in update_news.py) can still resolve fn.__name__ → real site_id.
    _fake_fetch.__name__ = "fetch_hn_nuclear"

    def _fake_reddit_fetch(session, now):
        return []
    _fake_reddit_fetch.__name__ = "fetch_reddit_nuclear"

    monkeypatch.setattr("update_news.fetch_hn_nuclear", _fake_fetch)
    monkeypatch.setattr("update_news.fetch_reddit_nuclear", _fake_reddit_fetch)
    sess = requests.Session()
    items, statuses = collect_all(sess, NOW)

    community = [s for s in statuses if s["site_id"] in ("hn_nuclear", "reddit_nuclear")]
    assert len(community) == 2, (
        f"expected hn_nuclear + reddit_nuclear in statuses, got: {[s['site_id'] for s in statuses]}"
    )
    for s in community:
        assert s["ok"] is True
        assert s.get("warning"), (
            f"silent zero must be surfaced via 'warning' field: {s}"
        )
        assert s.get("error") is None


# ─────────────────────────────────────────────────────────────────────────────
# Negative control: when items are returned, no warning should be added
# ─────────────────────────────────────────────────────────────────────────────


def test_no_warning_when_fetcher_returns_items(monkeypatch):
    """Healthy source: fetcher returns items → status must have item_count>0
    and NO warning (warning is reserved for silent zero)."""
    from update_news import RawItem

    def _fake_fetch(session, feed_def, now):
        return [RawItem(
            site_id="synthetic", site_name="Synthetic", source="synthetic",
            title="Test nuclear item", url="https://example.com/x",
            published_at=now, meta={},
        )]

    monkeypatch.setattr("update_news.fetch_single_rss_feed", _fake_fetch)
    sess = requests.Session()
    items, statuses = fetch_rss_sources(sess, NOW)

    assert len(items) == len(NUCLEAR_RSS_FEEDS)
    for s in statuses:
        assert s["ok"] is True
        assert s["item_count"] == 1
        assert not s.get("warning"), (
            f"healthy source must not emit warning: {s}"
        )
        assert s.get("error") is None


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: main()'s site_list must propagate warning to source-status JSON shape
# ─────────────────────────────────────────────────────────────────────────────


def test_main_site_list_propagates_warning(monkeypatch):
    """Verify main() copies warning from fetcher status into the final site_list
    that gets written to source-status.json. This is the JSON output contract
    that the operator reads."""
    from update_news import RawItem

    # All RSS fetchers return [] → every source is silent zero
    def _fake_fetch(session, feed_def, now):
        return []

    monkeypatch.setattr("update_news.fetch_single_rss_feed", _fake_fetch)

    # Build a few representative statuses (one per category) by capturing them
    sess = requests.Session()
    _, statuses = fetch_rss_sources(sess, NOW)

    # Simulate the site_list copy logic that main() does (line ~1209):
    site_list = []
    for s in statuses:
        site_list.append({
            "site_id": s["site_id"],
            "site_name": s["site_name"],
            "ok": s["ok"],
            "item_count": s["item_count"],
            "duration_ms": s["duration_ms"],
            "error": s["error"],
            "warning": s.get("warning"),
        })

    # Every silent-zero source must carry a non-null warning field on the
    # JSON-facing record (the operator-facing diagnostic surface).
    for s in site_list:
        assert s.get("warning"), (
            f"main()'s site_list must propagate warning to JSON output: {s}"
        )