"""Tests for Jina fallback mechanism in fetch_single_rss_feed.

Background: Several RSS endpoints (notably NucNet /feed.rss) are
blocked by Cloudflare for GitHub Actions runner IPs but work from
unmarked IPs. Direct RSS fetch then raises RuntimeError (silent-
failure fix). The Jina reader uses different infrastructure that
isn't Cloudflare-flagged, so it can fetch the page HTML→markdown and
extract article links even when the RSS endpoint itself is 403.

When via_jina=True on a feed entry, fetch_single_rss_feed should:
1. Try the direct RSS URL first.
2. If that raises, fall back to Jina reader of the html_url.
3. If both fail, raise RuntimeError combining both errors.
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
from update_news import (
    fetch_single_rss_feed,
    NUCLEAR_RSS_FEEDS,
)

NOW = datetime.now(timezone.utc)


def _rss_by_site(site_id: str) -> dict | None:
    return next((f for f in NUCLEAR_RSS_FEEDS if f["site_id"] == site_id), None)


def test_nucnet_marked_with_via_jina():
    """nucnet must be configured via_jina=True because /feed.rss is 403
    on Actions runner IPs but the homepage works via Jina."""
    feed = _rss_by_site("nucnet")
    assert feed is not None
    assert feed.get("via_jina") is True, (
        f"nucnet must declare via_jina=True, got {feed}"
    )


def test_falls_back_to_jina_when_direct_rss_fails():
    """via_jina=True: RSS fetch raises → Jina fetch is attempted → items returned."""
    sess = MagicMock(spec=requests.Session)

    # Direct RSS endpoint: 403 Forbidden
    rss_resp = MagicMock()
    rss_resp.status_code = 403
    rss_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    # Jina reader: returns markdown with article links
    jina_resp = MagicMock()
    jina_resp.status_code = 200
    jina_resp.text = (
        "Some intro text.\n"
        "\n"
        "[Russia's Nuclear Regulator Issues Site Licences](https://www.nucnet.org/news/russia-s-nuclear-regulator)\n"
        "\n"
        "[US Triso Fuel Manufacturer Gets Grant](https://www.nucnet.org/news/us-triso-grant)\n"
        "\n"
        "Footer links:\n"
        "[About](https://www.nucnet.org/about)\n"
        "[Contact](https://www.nucnet.org/contact)\n"
    )

    def get_side_effect(url, **kwargs):
        if "/feed.rss" in url or url.endswith(".rss") or url.endswith(".xml"):
            return rss_resp
        if "r.jina.ai" in url:
            return jina_resp
        raise AssertionError(f"unexpected URL fetched: {url}")

    sess.get.side_effect = get_side_effect

    feed_def = {
        "site_id": "test_fallback",
        "site_name": "Test Fallback",
        "xml_url": "https://example.test/feed.rss",
        "html_url": "https://example.test/",
        "via_jina": True,
    }
    items = fetch_single_rss_feed(sess, feed_def, NOW)
    # Must have skipped the footer "About" / "Contact" links (no /news/ in URL)
    # and kept the two news items.
    assert len(items) == 2, f"expected 2 items, got {len(items)}: {items}"
    titles = {it.title for it in items}
    assert any("Russia" in t for t in titles)
    assert any("Triso" in t for t in titles)


def test_raises_when_via_jina_false_and_rss_fails():
    """via_jina=False (or absent): RSS failure must raise, no fallback."""
    sess = MagicMock(spec=requests.Session)
    rss_resp = MagicMock()
    rss_resp.status_code = 403
    rss_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    sess.get.return_value = rss_resp

    feed_def = {
        "site_id": "test_no_fallback",
        "site_name": "Test No Fallback",
        "xml_url": "https://example.test/feed.rss",
        "html_url": "https://example.test/",
        # via_jina absent → False
    }
    with pytest.raises(RuntimeError, match="test_no_fallback"):
        fetch_single_rss_feed(sess, feed_def, NOW)
    # Jina must NOT have been tried
    for call in sess.get.call_args_list:
        assert "r.jina.ai" not in call.args[0], "Jina must not be tried when via_jina=False"


def test_raises_combined_error_when_both_rss_and_jina_fail():
    """via_jina=True with both RSS and Jina failing: RuntimeError must mention BOTH errors."""
    sess = MagicMock(spec=requests.Session)
    rss_resp = MagicMock()
    rss_resp.status_code = 403
    rss_resp.raise_for_status.side_effect = requests.HTTPError("403 from RSS")
    jina_resp = MagicMock()
    jina_resp.status_code = 500
    jina_resp.raise_for_status.side_effect = requests.HTTPError("500 from Jina")

    def get_side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            return jina_resp
        return rss_resp

    sess.get.side_effect = get_side_effect

    feed_def = {
        "site_id": "test_both_fail",
        "site_name": "Test Both Fail",
        "xml_url": "https://example.test/feed.rss",
        "html_url": "https://example.test/",
        "via_jina": True,
    }
    with pytest.raises(RuntimeError) as excinfo:
        fetch_single_rss_feed(sess, feed_def, NOW)
    msg = str(excinfo.value)
    assert "test_both_fail" in msg
    assert "RSS" in msg and "Jina" in msg, f"error must mention both: {msg}"