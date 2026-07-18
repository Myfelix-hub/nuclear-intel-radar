"""Tests for wechat_xxx silent-zero behavior when bridge is missing."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from datetime import datetime, timezone

from update_news import (
    WECHAT_ACCOUNTS,
    _resolve_wechat_xml_url,
    _load_wechat_mpids,
    _fetch_wechat_rss,
)
from update_news import RawItem  # noqa: F401  (sanity import)

NOW = datetime.now(timezone.utc)


def _wechat_def(site_id: str = "wechat_cnnp") -> dict:
    return {
        "site_id": site_id,
        "site_name": "中国核电网 (CNNP)",
        "xml_url": "{RSSHUB_BASE}/wechat/{mpID}",
        "html_url": "https://mp.weixin.qq.com/",
        "via_jina": False,
        "_mpID_key": "cnnp",
    }


def test_resolve_wechat_xml_url_returns_none_when_rsshub_base_empty():
    mpids_map = {"wechat_cnnp": "Mp-abc123"}
    assert _resolve_wechat_xml_url("wechat_cnnp", mpids_map, "") is None
    assert _resolve_wechat_xml_url("wechat_cnnp", mpids_map, "   ") is None


def test_resolve_wechat_xml_url_returns_none_when_mpids_map_none():
    assert _resolve_wechat_xml_url("wechat_cnnp", None, "https://r.example") is None


def test_resolve_wechat_xml_url_returns_none_when_site_id_not_in_map():
    mpids_map = {"wechat_other": "Mp-xyz"}
    assert _resolve_wechat_xml_url("wechat_cnnp", mpids_map, "https://r.example") is None


def test_resolve_wechat_xml_url_composes_correct_url():
    mpids_map = {"wechat_cnnp": "Mp-abc123"}
    url = _resolve_wechat_xml_url("wechat_cnnp", mpids_map, "https://r.example.com/release/rsshub")
    assert url == "https://r.example.com/release/rsshub/wechat/Mp-abc123"


def test_resolve_wechat_xml_url_strips_trailing_slash_from_base():
    mpids_map = {"wechat_cnnp": "Mp-abc123"}
    url = _resolve_wechat_xml_url("wechat_cnnp", mpids_map, "https://r.example.com/release/rsshub/")
    assert url == "https://r.example.com/release/rsshub/wechat/Mp-abc123"


def test_load_wechat_mpids_returns_none_when_file_missing(tmp_path):
    assert _load_wechat_mpids(tmp_path / "nope.json") is None


def test_load_wechat_mpids_returns_none_when_malformed(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json{{{", encoding="utf-8")
    assert _load_wechat_mpids(f) is None


def test_load_wechat_mpids_returns_none_when_not_list(tmp_path):
    f = tmp_path / "dict.json"
    f.write_text(json.dumps({"k": "v"}), encoding="utf-8")
    assert _load_wechat_mpids(f) is None


def test_load_wechat_mpids_returns_site_id_keyed_map(tmp_path):
    rows = [
        {"name": "中国核电网 (CNNP)", "mpID": "Mp-abc", "site_id": "wechat_cnnp",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
        {"name": "中核集团", "mpID": "Mp-def", "site_id": "wechat_cnnc",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    result = _load_wechat_mpids(f)
    assert result == {"wechat_cnnp": "Mp-abc", "wechat_cnnc": "Mp-def"}


def test_load_wechat_mpids_skips_rows_missing_mpid(tmp_path):
    rows = [
        {"name": "中国核电网 (CNNP)", "mpID": "Mp-abc", "site_id": "wechat_cnnp",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
        {"name": "中核集团", "mpID": "", "site_id": "wechat_cnnc",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    result = _load_wechat_mpids(f)
    assert result == {"wechat_cnnp": "Mp-abc"}, \
        "empty mpID row must be skipped, not included as empty string"


def test_fetch_wechat_rss_silent_zero_when_rsshub_base_unset(monkeypatch):
    monkeypatch.delenv("RSSHUB_BASE", raising=False)
    sess = MagicMock(spec=requests.Session)
    items = _fetch_wechat_rss(sess, _wechat_def(), NOW)
    assert items == [], "missing RSSHUB_BASE must produce silent zero, not crash"
    sess.get.assert_not_called(), \
        "must not even attempt HTTP when bridge is unset"


def test_fetch_wechat_rss_silent_zero_when_mpids_cache_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("RSSHUB_BASE", "https://r.example/release/rsshub")
    # Point WECHAT_MPIDS_PATH at a nonexistent file
    import update_news
    monkeypatch.setattr(update_news, "WECHAT_MPIDS_PATH", tmp_path / "missing.json")
    sess = MagicMock(spec=requests.Session)
    items = _fetch_wechat_rss(sess, _wechat_def(), NOW)
    assert items == [], "missing mpID cache must produce silent zero"
    sess.get.assert_not_called()


def test_fetch_wechat_rss_silent_zero_when_site_id_not_in_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("RSSHUB_BASE", "https://r.example/release/rsshub")
    import update_news
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps([
        {"name": "x", "mpID": "Mp-other", "site_id": "wechat_other",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]), encoding="utf-8")
    monkeypatch.setattr(update_news, "WECHAT_MPIDS_PATH", f)
    sess = MagicMock(spec=requests.Session)
    items = _fetch_wechat_rss(sess, _wechat_def("wechat_cnnp"), NOW)
    assert items == []
    sess.get.assert_not_called()


def test_fetch_wechat_rss_calls_real_path_when_bridge_ok(monkeypatch, tmp_path):
    """Happy path: RSSHUB_BASE set + mpID cache has site_id → fetches via existing RSS path."""
    monkeypatch.setenv("RSSHUB_BASE", "https://r.example/release/rsshub")
    import update_news
    f = tmp_path / "mpids.json"
    f.write_text(json.dumps([
        {"name": "中国核电网", "mpID": "Mp-abc", "site_id": "wechat_cnnp",
         "fetched_at": "2026-07-18T00:00:00+08:00"},
    ]), encoding="utf-8")
    monkeypatch.setattr(update_news, "WECHAT_MPIDS_PATH", f)

    # Mock the underlying _fetch_rss_xml to assert the resolved URL is right
    captured = {}

    def fake_fetch_rss_xml(session, xml_url, site_id, site_name, html_url, now, feed_def):
        captured["url"] = xml_url
        captured["site_id"] = site_id
        return [RawItem(site_id=site_id, site_name=site_name, source=site_name,
                        title="Test article", url="https://mp.weixin.qq.com/s/x",
                        published_at=now, meta={"summary": ""})]

    monkeypatch.setattr(update_news, "_fetch_rss_xml", fake_fetch_rss_xml)
    sess = MagicMock(spec=requests.Session)
    items = _fetch_wechat_rss(sess, _wechat_def(), NOW)
    assert len(items) == 1
    assert captured["url"] == "https://r.example/release/rsshub/wechat/Mp-abc"
    assert captured["site_id"] == "wechat_cnnp"
