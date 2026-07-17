"""Tests verifying that fetchers DO NOT silently swallow exceptions.

A silent except that returns [] makes a fetcher appear successful (ok=True,
item_count=0) in source-status.json even when the source is unreachable.
This hides production failures (nucnet, nucleartownhall, reddit_nuclear)
from the operator.

These tests assert that fetchers propagate their failures so the
fetch_*_sources wrapper can record ok=False with a meaningful error.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from datetime import datetime, timezone

from update_news import (
    fetch_web_direct,
    fetch_single_rss_feed,
    fetch_web_jina,
    NUCLEAR_RSS_FEEDS,
    WEB_SOURCES_DIRECT,
    WEB_SOURCES_JINA,
)

NOW = datetime.now(timezone.utc)


def test_fetch_web_direct_raises_on_unreachable_host():
    """fetch_web_direct must NOT silently swallow ConnectionError.

    Currently it does: `except Exception: return items` at line ~545.
    This test pins the bug. When fixed, it will pass.
    """
    sess = requests.Session()
    bad = {
        "site_id": "fake_unreachable",
        "site_name": "Fake Unreachable",
        "url": "http://this-host-does-not-exist.invalid",
        "link_selector": "a",
        "time_selector": None,
        "time_attr": None,
    }
    with pytest.raises(Exception):
        fetch_web_direct(sess, bad, NOW)


def test_fetch_single_rss_feed_raises_on_unreachable_host():
    """fetch_single_rss_feed must NOT silently swallow ConnectionError.

    Currently it does: `except Exception: return items` at line ~446.
    """
    sess = requests.Session()
    bad = {
        "site_id": "fake_rss",
        "site_name": "Fake RSS",
        "xml_url": "http://this-host-does-not-exist.invalid/feed",
        "html_url": "http://this-host-does-not-exist.invalid",
    }
    with pytest.raises(Exception):
        fetch_single_rss_feed(sess, bad, NOW)


def test_fetch_web_jina_raises_on_unreachable_host():
    """fetch_web_jina must NOT silently swallow HTTP errors.

    Currently it does: `except Exception: return items` at line ~633
    plus an early return on non-200 status at line ~631.
    Both swallow real failures.
    """
    sess = requests.Session()
    bad = {
        "site_id": "fake_jina",
        "site_name": "Fake Jina",
        "url": "http://this-host-does-not-exist.invalid",
    }
    with pytest.raises(Exception):
        fetch_web_jina(sess, bad, NOW)


def test_fetch_web_direct_sources_records_failure_status():
    """End-to-end: when a direct source is unreachable, fetch_web_direct_sources
    must record ok=False with the error message — NOT ok=True cnt=0."""
    sess = requests.Session()
    # Replace WEB_SOURCES_DIRECT with a single bad source for this test
    import update_news
    original = update_news.WEB_SOURCES_DIRECT
    try:
        update_news.WEB_SOURCES_DIRECT = ({
            "site_id": "fake_e2e",
            "site_name": "Fake E2E",
            "url": "http://this-host-does-not-exist.invalid",
            "link_selector": "a",
            "time_selector": None,
            "time_attr": None,
        },)
        from update_news import fetch_web_direct_sources
        items, statuses = fetch_web_direct_sources(sess, NOW)
        assert items == [], "no items should be returned"
        assert len(statuses) == 1, "exactly one status entry"
        s = statuses[0]
        assert s["ok"] is False, (
            f"sinkable failure: unreachable source reported ok=True. "
            f"status={s}"
        )
        assert s["error"], f"error message must be populated, got: {s}"
    finally:
        update_news.WEB_SOURCES_DIRECT = original