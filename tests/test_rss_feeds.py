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


def test_all_feeds_have_required_keys():
    """Sanity: every feed must have site_id/site_name/xml_url/html_url."""
    required = {"site_id", "site_name", "xml_url", "html_url"}
    for feed in NUCLEAR_RSS_FEEDS:
        assert required.issubset(feed.keys()), f"Feed missing keys: {feed}"
