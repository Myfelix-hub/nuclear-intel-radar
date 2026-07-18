"""Per-entry hard-fail tests when RSSHub returns 4xx/5xx for a specific mpID."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from datetime import datetime, timezone

from update_news import _fetch_wechat_rss, fetch_rss_sources

NOW = datetime.now(timezone.utc)


def _wechat_def(site_id: str = "wechat_cnnp") -> dict:
    return {
        "site_id": site_id,
        "site_name": "中国核电网",
        "xml_url": "{RSSHUB_BASE}/wechat/{mpID}",
        "html_url": "https://mp.weixin.qq.com/",
        "via_jina": False,
        "_mpID_key": "cnnp",
    }


def _build_failing_resp(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    resp.headers = {"content-type": "text/html"}
    resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


@pytest.fixture
def rsshub_bridge(monkeypatch, tmp_path):
    """Set RSSHUB_BASE + write mpID cache so the bridge is 'present'."""
    monkeypatch.setenv("RSSHUB_BASE", "https://r.example/release/rsshub")
    import update_news
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps([
        {"name": "中国核电网", "mpID": "Mp-abc", "site_id": "wechat_cnnp",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]), encoding="utf-8")
    monkeypatch.setattr(update_news, "WECHAT_MPIDS_PATH", f)
    return tmp_path


def test_fetch_wechat_rss_raises_on_404(rsshub_bridge):
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_failing_resp(404)
    with pytest.raises(RuntimeError) as excinfo:
        _fetch_wechat_rss(sess, _wechat_def(), NOW)
    msg = str(excinfo.value)
    assert "wechat_cnnp" in msg, \
        f"error must name the source for ops; got: {msg}"


def test_fetch_wechat_rss_raises_on_503(rsshub_bridge):
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_failing_resp(503)
    with pytest.raises(RuntimeError):
        _fetch_wechat_rss(sess, _wechat_def(), NOW)


def test_fetch_rss_sources_records_per_entry_error_for_wechat(monkeypatch, tmp_path):
    """Integration: when fetch_rss_sources iterates NUCLEAR_RSS_FEEDS, a wechat
    entry whose underlying call raises must surface as ok=False with error."""
    monkeypatch.setenv("RSSHUB_BASE", "https://r.example/release/rsshub")
    import update_news
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps([
        {"name": "中国核电网", "mpID": "Mp-abc", "site_id": "wechat_cnnp",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]), encoding="utf-8")
    monkeypatch.setattr(update_news, "WECHAT_MPIDS_PATH", f)

    # Force _fetch_wechat_rss to raise for wechat_cnnp; succeed (return []) for others
    def fake_fetch(session, feed_def, now):
        if feed_def.get("site_id") == "wechat_cnnp":
            raise RuntimeError("wechat_cnnp: RSSHub 404")
        return []

    monkeypatch.setattr(update_news, "_fetch_wechat_rss", fake_fetch)
    # Also need to ensure dispatch hits _fetch_wechat_rss for wechat entries
    # (Task 3 already adds the dispatch; this test assumes Task 3 is in place.)

    # Keep the test offline-deterministic: make every non-wechat feed fail fast
    # instead of doing real network fetches.
    def _fast_fail(*args, **kwargs):
        raise RuntimeError("offline test stub")

    monkeypatch.setattr(update_news, "_fetch_rss_xml", _fast_fail)
    monkeypatch.setattr(update_news, "_fetch_via_jina", _fast_fail)

    sess = requests.Session()
    items, statuses = update_news.fetch_rss_sources(sess, NOW)
    assert items == []

    # Find wechat_cnnp status
    wechat_status = next((s for s in statuses if s["site_id"] == "wechat_cnnp"), None)
    assert wechat_status is not None, "wechat_cnnp must appear in statuses"
    assert wechat_status["ok"] is False, \
        f"per-entry hard fail must surface ok=False; got: {wechat_status}"
    assert wechat_status.get("error"), \
        f"per-entry hard fail must include error field; got: {wechat_status}"
    assert "404" in wechat_status["error"] or "RSSHub" in wechat_status["error"]
