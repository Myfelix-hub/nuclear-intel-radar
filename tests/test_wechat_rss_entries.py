"""Tests for wechat_xxx entries in NUCLEAR_RSS_FEEDS + SOURCE_TIER_BY_SITE."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from update_news import NUCLEAR_RSS_FEEDS, WECHAT_ACCOUNTS  # noqa: E402
from nuclear_keywords import SOURCE_TIER_BY_SITE  # noqa: E402


WECHAT_SITE_IDS = [
    "wechat_cnnp", "wechat_cnnc", "wechat_cnji", "wechat_energy_research",
    "wechat_nuclearnet", "wechat_nuclear_story", "wechat_nsa",
    "wechat_sh_nuclear", "wechat_npdi",
]


@pytest.mark.parametrize("site_id", WECHAT_SITE_IDS)
def test_wechat_entry_registered_in_nuclear_rss_feeds(site_id):
    matches = [e for e in NUCLEAR_RSS_FEEDS if e.get("site_id") == site_id]
    assert len(matches) == 1, f"{site_id} must be registered exactly once"
    entry = matches[0]
    assert entry["site_name"], f"{site_id} must have a display site_name"
    # xml_url is a template string at registration; resolution happens at fetch time
    assert "{RSSHUB_BASE}" in entry["xml_url"], \
        f"{site_id} xml_url must contain {{RSSHUB_BASE}} template"
    assert "{mpID}" in entry["xml_url"], \
        f"{site_id} xml_url must contain {{mpID}} template"
    assert entry["via_jina"] is False, \
        f"{site_id} must NOT use Jina (RSSHub emits proper RSS)"


@pytest.mark.parametrize("site_id", WECHAT_SITE_IDS)
def test_wechat_entry_tier_is_industry(site_id):
    assert SOURCE_TIER_BY_SITE.get(site_id) == "industry", \
        f"{site_id} tier must be 'industry'"


def test_wechat_accounts_constant_has_nine_entries():
    assert len(WECHAT_ACCOUNTS) == 9, \
        f"WECHAT_ACCOUNTS must have exactly 9 entries, got {len(WECHAT_ACCOUNTS)}"
    keys = {a["mpID_key"] for a in WECHAT_ACCOUNTS}
    expected_keys = {
        "cnnp", "cnnc", "cnji", "energy_research", "nuclearnet",
        "nuclear_story", "nsa", "sh_nuclear", "npdi",
    }
    assert keys == expected_keys, \
        f"mpID_key mismatch. missing={expected_keys - keys}, extra={keys - expected_keys}"
