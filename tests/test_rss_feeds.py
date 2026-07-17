"""Tests for NUCLEAR_RSS_FEEDS data-driven configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_news import NUCLEAR_RSS_FEEDS


def _feed_by_site(site_id: str) -> dict | None:
    return next((f for f in NUCLEAR_RSS_FEEDS if f["site_id"] == site_id), None)


def test_iaea_news_in_rss_feeds():
    """IAEA News must be registered in NUCLEAR_RSS_FEEDS for the pipeline to pick it up."""
    feed = _feed_by_site("iaea_news")
    assert feed is not None, "iaea_news missing from NUCLEAR_RSS_FEEDS"
    assert feed["site_name"] == "IAEA News"
    assert feed["xml_url"].startswith("https://www.iaea.org/")
    assert feed["html_url"].startswith("https://www.iaea.org/")


def test_iaea_official_tier_registered():
    """SOURCE_TIER_BY_SITE must classify iaea_news as 'official' for priority."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("iaea_news") == "official", \
        "iaea_news must be tier=official to rank above media sources"


def test_us_nrc_in_rss_feeds():
    """US NRC (regulator) must be registered for US regulatory signal coverage."""
    feed = _feed_by_site("us_nrc")
    assert feed is not None, "us_nrc missing from NUCLEAR_RSS_FEEDS"
    assert feed["site_name"] == "US NRC News"
    assert feed["xml_url"].startswith("https://www.nrc.gov/")
    assert feed["html_url"].startswith("https://www.nrc.gov/")
    assert feed.get("via_jina") is True, "us_nrc should have via_jina=True as Cloudflare-blocked insurance"


def test_us_nrc_regulator_tier_registered():
    """SOURCE_TIER_BY_SITE must classify us_nrc as 'regulator' for priority."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("us_nrc") == "regulator", \
        "us_nrc must be tier=regulator to rank above media sources"


def test_iter_org_in_rss_feeds_with_candidates():
    """ITER must be registered with the verified RSS path (https://www.iter.org/rss.xml)."""
    feed = _feed_by_site("iter_org")
    assert feed is not None, "iter_org missing from NUCLEAR_RSS_FEEDS"
    assert feed["xml_url"] == "https://www.iter.org/rss.xml", \
        f"iter_org primary xml_url must be the verified ITER RSS path, got {feed['xml_url']}"
    candidates = feed.get("xml_url_candidates")
    assert candidates and isinstance(candidates, list) and len(candidates) >= 2, \
        "iter_org must keep xml_url_candidates as fallback"
    assert "https://www.iter.org/rss.xml" in candidates, \
        "iter_org candidates must include the verified RSS path as first option"
    assert all(c.startswith("https://www.iter.org/") for c in candidates), \
        "All ITER candidate URLs must be HTTPS on iter.org"
    assert feed.get("via_jina") is True, "iter_org keeps via_jina fallback (Cloudflare-blocked)"


def test_iter_org_official_tier_registered():
    """SOURCE_TIER_BY_SITE must classify iter_org as 'official' (fusion project)."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("iter_org") == "official", \
        "iter_org must be tier=official to rank above media sources"


def test_edf_nuclear_in_rss_feeds():
    """EDF must be registered with the verified RSS path (https://www.edf.fr/rss.xml)."""
    feed = _feed_by_site("edf_nuclear")
    assert feed is not None, "edf_nuclear missing from NUCLEAR_RSS_FEEDS"
    assert feed["xml_url"] == "https://www.edf.fr/rss.xml", \
        f"edf_nuclear primary xml_url must be the verified EDF RSS path, got {feed['xml_url']}"
    candidates = feed.get("xml_url_candidates")
    assert candidates and "https://www.edf.fr/rss.xml" in candidates, \
        "edf_nuclear candidates must include the verified RSS path"
    assert feed.get("via_jina") is True, "edf_nuclear keeps via_jina fallback"


def test_edf_nuclear_industry_tier_registered():
    """SOURCE_TIER_BY_SITE must classify edf_nuclear as 'industry' (operator)."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("edf_nuclear") == "industry", \
        "edf_nuclear must be tier=industry for operator classification"


def test_doe_ne_in_rss_feeds():
    """DOE-NE must be registered with energy.gov whole-site RSS path."""
    feed = _feed_by_site("doe_ne")
    assert feed is not None, "doe_ne missing from NUCLEAR_RSS_FEEDS"
    assert feed["xml_url"] == "https://www.energy.gov/rss.xml", \
        f"doe_ne must use whole-site RSS (nuclear content filtered by keyword score), got {feed['xml_url']}"
    assert feed.get("via_jina") is True, "doe_ne needs via_jina fallback (energy.gov may rate-limit)"


def test_doe_ne_official_tier_registered():
    """SOURCE_TIER_BY_SITE must classify doe_ne as 'official' (US DOE)."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("doe_ne") == "official", \
        "doe_ne must be tier=official for US Department of Energy classification"


def test_oecd_nea_in_rss_feeds_with_candidates():
    """OECD-NEA must be registered with multiple RSS candidates (path unknown)."""
    feed = _feed_by_site("oecd_nea")
    assert feed is not None, "oecd_nea missing from NUCLEAR_RSS_FEEDS"
    candidates = feed.get("xml_url_candidates")
    assert candidates and isinstance(candidates, list) and len(candidates) >= 3, \
        "oecd_nea must declare xml_url_candidates for path discovery"
    assert all(c.startswith("https://www.oecd-nea.org/") for c in candidates), \
        "All OECD-NEA candidates must be HTTPS on oecd-nea.org"
    assert feed.get("via_jina") is True, "oecd_nea needs via_jina fallback (site often unreachable from mainline)"


def test_oecd_nea_official_tier_registered():
    """SOURCE_TIER_BY_SITE must classify oecd_nea as 'official' (international org)."""
    from nuclear_keywords import SOURCE_TIER_BY_SITE
    assert SOURCE_TIER_BY_SITE.get("oecd_nea") == "official", \
        "oecd_nea must be tier=official for international nuclear org classification"


def test_multi_candidate_fetcher_logic():
    """fetch_single_rss_feed must try each candidate until one succeeds."""
    from unittest.mock import MagicMock
    from update_news import fetch_single_rss_feed
    from datetime import datetime, UTC

    now = datetime.now(UTC)
    session = MagicMock()

    # Mock responses: first 2 fail with 403, 3rd succeeds with RSS XML
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = Exception("HTTP 403 Forbidden")
    ok_resp = MagicMock()
    ok_resp.raise_for_status.return_value = None
    ok_resp.content = b"<?xml version='1.0'?><rss><channel><title>x</title></channel></rss>"

    session.get.side_effect = [fail_resp, fail_resp, ok_resp]

    feed_def = {
        "site_id": "test_iter_probe",
        "site_name": "Test ITER Probe",
        "xml_url": "https://www.iter.org/rss",
        "html_url": "https://www.iter.org/news",
        "xml_url_candidates": [
            "https://www.iter.org/rss",
            "https://www.iter.org/news/rss",
            "https://www.iter.org/feed",
        ],
    }

    items = fetch_single_rss_feed(session, feed_def, now)
    assert session.get.call_count == 3, \
        f"Expected 3 candidates attempted, got {session.get.call_count}"
    urls_tried = [call.args[0] for call in session.get.call_args_list]
    assert urls_tried == feed_def["xml_url_candidates"], \
        f"Must try candidates in declared order, got {urls_tried}"


def test_multi_candidate_fetcher_raises_with_diagnostics():
    """When all candidates fail (no via_jina), error must include each candidate's failure."""
    from unittest.mock import MagicMock, patch
    from update_news import fetch_single_rss_feed
    from datetime import datetime, UTC

    now = datetime.now(UTC)
    session = MagicMock()
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = Exception("HTTP 403 Forbidden")
    session.get.return_value = fail_resp

    feed_def = {
        "site_id": "test_probe_fail",
        "site_name": "Test Probe Fail",
        "xml_url": "https://www.iter.org/rss",
        "html_url": "https://www.iter.org/news",
        "xml_url_candidates": ["https://www.iter.org/rss", "https://www.iter.org/feed"],
    }

    try:
        fetch_single_rss_feed(session, feed_def, now)
        assert False, "Expected RuntimeError when all candidates fail"
    except RuntimeError as e:
        msg = str(e)
        assert "all 2 RSS candidates failed" in msg, f"Missing summary: {msg}"
        assert "iter.org/rss" in msg, f"Missing first candidate URL: {msg}"
        assert "iter.org/feed" in msg, f"Missing second candidate URL: {msg}"


def test_all_feeds_have_required_keys():
    """Sanity: every feed must have site_id/site_name/xml_url/html_url."""
    required = {"site_id", "site_name", "xml_url", "html_url"}
    for feed in NUCLEAR_RSS_FEEDS:
        assert required.issubset(feed.keys()), f"Feed missing keys: {feed}"
