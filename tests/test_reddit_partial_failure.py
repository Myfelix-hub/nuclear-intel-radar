"""Tests for fetch_reddit_nuclear partial-failure handling.

Background: fetch_reddit_nuclear iterates two subreddits
('nuclear', 'nuclearpower'). Each iteration had `except Exception:
continue`, so even when both subreddits' RSS endpoints failed, the
function returned [] without raising. The collect_all wrapper then
recorded ok=True cnt=0 — a silent failure hidden by design.

These tests pin the new contract: at least one subreddit must produce
items OR no errors; if every subreddit raises, fetch_reddit_nuclear
must raise so the wrapper records ok=False with the diagnostic.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from datetime import datetime, timezone
from update_news import fetch_reddit_nuclear

NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)


def _build_rss_resp(items_xml: str) -> MagicMock:
    """Build a mock Response whose .content parses as a feedparser-compatible RSS."""
    resp = MagicMock()
    resp.status_code = 200
    body = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
{items_xml}
</channel></rss>""".encode("utf-8")
    resp.content = body
    return resp


def _build_failing_resp(status: int = 403) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


def _item_xml(title: str, link: str, date: str = "Mon, 14 Jul 2026 12:00:00 +0000") -> str:
    return f'<item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate></item>'


def test_raises_when_both_subreddits_fail():
    """Both subreddits return 403 → fetch_reddit_nuclear must raise RuntimeError
    combining both errors, NOT return [] silently."""
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_failing_resp(403)

    with pytest.raises(RuntimeError) as excinfo:
        fetch_reddit_nuclear(sess, NOW)
    msg = str(excinfo.value)
    assert "reddit_nuclear" in msg or "nuclear" in msg
    # Both subreddit names should appear in the combined error
    assert "nuclear" in msg
    assert "nuclearpower" in msg, f"both subreddits must be mentioned: {msg}"


def test_returns_items_when_one_subreddit_succeeds():
    """One subreddit returns items, the other 403 → return the items,
    do NOT raise (partial-failure is acceptable)."""
    sess = MagicMock(spec=requests.Session)

    good_xml = _item_xml(
        "Test post about SMR nuclear reactor",
        "https://www.reddit.com/r/nuclear/comments/abc/test/",
    )

    def side_effect(url, **kwargs):
        if "/r/nuclearpower/" in url:
            return _build_failing_resp(503)
        return _build_rss_resp(good_xml)

    sess.get.side_effect = side_effect

    items = fetch_reddit_nuclear(sess, NOW)
    assert len(items) >= 1, f"expected at least one item from 'nuclear' subreddit, got {items}"
    assert any("SMR" in it.title for it in items)


def test_returns_empty_list_when_all_succeed_but_no_recent_items():
    """Both subreddits return 200 with empty feeds (no recent items) →
    return [] without raising. This is a 'fetched successfully but empty'
    state, distinct from 'fetch failed'."""
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_rss_resp("")  # valid RSS, no items

    items = fetch_reddit_nuclear(sess, NOW)
    assert items == []


def test_combined_error_mentions_http_status_from_both_subreddits():
    """The combined RuntimeError must include diagnostic detail from BOTH
    failed subreddits so operators can tell them apart in source-status."""
    sess = MagicMock(spec=requests.Session)

    def side_effect(url, **kwargs):
        if "/r/nuclear/" in url and "/r/nuclearpower/" not in url:
            return _build_failing_resp(403)
        if "/r/nuclearpower/" in url:
            return _build_failing_resp(429)
        raise AssertionError(f"unexpected URL: {url}")

    sess.get.side_effect = side_effect

    with pytest.raises(RuntimeError) as excinfo:
        fetch_reddit_nuclear(sess, NOW)
    msg = str(excinfo.value)
    # Either include the status codes or exception names — operators need to
    # tell 403 from 429 to know if it's auth-block vs rate-limit.
    assert "403" in msg or "Forbidden" in msg, msg
    assert "429" in msg or "rate" in msg.lower() or "Too" in msg, msg