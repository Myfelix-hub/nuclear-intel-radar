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
    _maybe_dump_probe,
    _PROBE_ENABLED,
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
    """with via_jina=False, silent zero must short-circuit and return [] —
    no Jina probe attempted. Wrapper layer then records the warning field."""
    sess = MagicMock(spec=requests.Session)
    empty_html = "<html><body><p>no news here</p></body></html>"
    sess.get.return_value = _build_html_resp(empty_html)

    def_no_jina = {**ROSATOM_DEF, "via_jina": False}
    items = fetch_web_news_listing(sess, def_no_jina, NOW)

    assert items == [], "silent zero must return [] for wrapper to warn"
    # Both start_urls probed, no Jina call (via_jina=False)
    assert sess.get.call_count == len(def_no_jina["start_urls"])


def test_fetch_web_news_listing_silent_zero_falls_through_to_jina():
    """with via_jina=True and direct path producing 0 items, the fetcher must
    try Jina before giving up. If Jina yields items, those surface; if not,
    return []. This is the OKLO / TerraPower path — direct HTML loads but
    our BeautifulSoup selectors don't match the post-JS DOM, while Jina's
    markdown regex sweep still extracts titles."""
    sess = MagicMock(spec=requests.Session)
    direct_html = "<html><body><div class='spinner'>Loading...</div></body></html>"
    jina_md = (
        "Some intro\n\n"
        "[Oklo announces Aurora powerhouse milestone](https://oklo.com/newsroom/news/aurora-milestone/)\n\n"
    )

    def side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            r = MagicMock()
            r.status_code = 200
            r.text = jina_md
            return r
        return _build_html_resp(direct_html)

    sess.get.side_effect = side_effect

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)  # via_jina=True

    assert len(items) == 1, f"Jina fallback should surface 1 item, got {items}"
    assert "Aurora" in items[0].title
    assert items[0].site_id == "rosatom"  # src_def controls site_id even via Jina path


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


# ─────────────────────────────────────────────────────────────────────────────
# 10. Probe mode — NUCLEAR_PROBE=1 dumps news-listing HTML to
#     data/.probe-{site_id}.html so an operator can inspect selectors
#     offline. Default-off so it never affects production runs.
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_mode_default_off_does_not_write(tmp_path, monkeypatch):
    """Without NUCLEAR_PROBE=1, probe mode is a no-op even if a probe file
    path is set. Confirms the production default is safe."""
    monkeypatch.delenv("NUCLEAR_PROBE", raising=False)
    monkeypatch.setenv("NUCLEAR_PROBE_DIR", str(tmp_path))
    assert _PROBE_ENABLED is False
    _maybe_dump_probe("oklo", "<html>real page</html>")
    assert not (tmp_path / ".probe-oklo.html").exists()


def test_probe_mode_dumps_html_when_enabled(tmp_path, monkeypatch):
    import update_news
    monkeypatch.setattr(update_news, "_PROBE_ENABLED", True)
    monkeypatch.setattr(update_news, "_PROBE_DIR", tmp_path)
    update_news._maybe_dump_probe("terrapower", "<html>cloudflare page</html>")
    probe_file = tmp_path / ".probe-terrapower.html"
    assert probe_file.exists()
    assert "cloudflare page" in probe_file.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 11. All-200-zero + Jina fallback raises → hard error, NOT silent zero
#     (Oklo / TerraPower failure mode: Cloudflare serves a 200 HTML shell,
#     our selectors match nothing, and Jina is 403 — operators must see
#     ok=False with the Jina error, not a misleading "no containers matched"
#     silent-zero warning).
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_web_news_listing_raises_when_jina_fails_after_200_zero():
    sess = MagicMock(spec=requests.Session)
    shell_html = "<html><body><div class='cf-shell'>Loading...</div></body></html>"

    def side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            r = MagicMock()
            r.status_code = 403
            r.text = ""
            return r
        return _build_html_resp(shell_html)

    sess.get.side_effect = side_effect

    with pytest.raises(RuntimeError) as excinfo:
        fetch_web_news_listing(sess, ROSATOM_DEF, NOW)  # via_jina=True
    msg = str(excinfo.value)
    assert "rosatom" in msg
    assert "no containers matched" in msg, f"must explain the direct-path failure: {msg}"
    assert "Jina" in msg, f"must surface the Jina failure: {msg}"


def test_fetch_web_news_listing_silent_zero_when_jina_also_returns_nothing():
    """All-200-zero + Jina reachable but 0 extracted links → genuine silent
    zero (return []); the wrapper's warning path covers this case."""
    sess = MagicMock(spec=requests.Session)
    shell_html = "<html><body><p>no news here</p></body></html>"

    def side_effect(url, **kwargs):
        if "r.jina.ai" in url:
            r = MagicMock()
            r.status_code = 200
            r.text = "no markdown links at all"
            return r
        return _build_html_resp(shell_html)

    sess.get.side_effect = side_effect

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)
    assert items == [], "Jina 200 with 0 links must remain a silent zero"


# ─────────────────────────────────────────────────────────────────────────────
# 12. OECD-NEA — no real RSS exists (all candidate paths 404 or serve HTML,
#     verified 2026-07-30). Moved from NUCLEAR_RSS_FEEDS to
#     WEB_SOURCES_NEWS_LISTING against the Jalios news search endpoint
#     (types=generated.NewsItem&sort=pdate). Article hrefs are RELATIVE and
#     must resolve via the page's <base href> tag.
# ─────────────────────────────────────────────────────────────────────────────

NEA_HTML = """<!DOCTYPE html><html><head>
<base href="https://www.oecd-nea.org/"   />
</head><body>
<div class="app-cards-horizontal-wrapper">
  <div class="search-result-item-container">
    <div class="search-result-item-title custom-padding-bottom">
      <a href="jcms/pl_119771/deadline-extended-for-nea-survey-on-the-role-of-women-in-the-nuclear-sector" data-jalios-id='pl_119771'>Deadline extended for NEA survey on the role of women in the nuclear sector</a>
    </div>
    <div class="search-published-date">Published date: <span>29 June 2026</span></div>
  </div>
  <div class="search-result-item-container">
    <div class="search-result-item-title custom-padding-bottom">
      <a href="jcms/pl_120580/inaugural-nextgen-nuclear-leaders-summer-school-held" data-jalios-id='pl_120580'>Inaugural NextGen Nuclear Leaders Summer School held</a>
    </div>
    <div class="search-published-date">Published date: <span>23 July 2026</span></div>
  </div>
</div>
</body></html>"""


def _listing_entry(site_id: str) -> dict:
    return next(e for e in WEB_SOURCES_NEWS_LISTING if e["site_id"] == site_id)


def test_oecd_nea_listing_entry_registered():
    e = _listing_entry("oecd_nea")
    assert e["start_urls"], "oecd_nea must have start_urls"
    assert any("oecd-nea.org" in u for u in e["start_urls"])
    assert e["via_jina"] is True, "oecd_nea keeps Jina as last-resort fallback"
    assert SOURCE_TIER_BY_SITE.get("oecd_nea") == "official"


def test_oecd_nea_selectors_parse_real_html_structure():
    """HTML mock mirrors the Jalios customQuery result card (verified by
    direct probe 2026-07-30). Relative hrefs must resolve against the
    document <base href>, NOT against the long start_url path."""
    items = _parse_news_listing_html(NEA_HTML, _listing_entry("oecd_nea"), NOW)

    assert len(items) == 2, f"expected 2 items, got {len(items)}: {items}"
    assert items[0].url == (
        "https://www.oecd-nea.org/jcms/pl_119771/"
        "deadline-extended-for-nea-survey-on-the-role-of-women-in-the-nuclear-sector"
    ), f"relative href must resolve via <base href>, got {items[0].url}"
    assert "Deadline extended" in items[0].title
    # "29 June 2026" parsed by dateutil fallback
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026 and items[0].published_at.month == 6
    assert items[1].published_at is not None and items[1].published_at.month == 7


def test_base_href_absent_falls_back_to_start_url():
    """Without a <base> tag, relative hrefs must still resolve against
    start_urls[0] — pre-existing behavior must not regress."""
    src = {
        "site_id": "t", "site_name": "T",
        "start_urls": ["https://example.com/news/index.html"],
        "container_selector": "article",
        "title_selector": "h2 a",
        "link_selector": "h2 a",
        "time_selector": None,
        "max_items": 20,
        "via_jina": False,
    }
    html = ('<html><body><article><h2><a href="/news/story-1">'
            "Example nuclear story title</a></h2></article></body></html>")
    items = _parse_news_listing_html(html, src, NOW)
    assert len(items) == 1
    assert items[0].url == "https://example.com/news/story-1"


# ─────────────────────────────────────────────────────────────────────────────
# 13. CGN (中广核) + 中国核网 — Jina returns a stable 403 for both, but the
#     listing pages are static HTML (verified by direct probe 2026-07-30), so
#     they moved from WEB_SOURCES_JINA to WEB_SOURCES_NEWS_LISTING.
# ─────────────────────────────────────────────────────────────────────────────

CGN_HTML = """<!DOCTYPE html><html><body>
<div class="col-xs-12 culture mtb" style="margin:10px auto 40px"><span id="comp_920181">
<ul>
  <li><a href="/cgn/c100944/2026-07/21/content_3316286d6da540168feb58a45594e6b2.shtml">
    <h4 class="blue">中广核“元曜一号”光热熔盐槽式集热器型号在青海西宁发布</h4>
    <small>2026-07-16</small><p> </p></a></li>
  <li><a href="/cgn/c100944/2026-07/13/content_b8bb1c1d1f3c455fb3a69423e060a79b.shtml">
    <h4 class="blue">纳米比亚总统恩代特瓦到中广核大亚湾核电基地参访</h4>
    <small>2026-07-07</small><p> </p></a></li>
</ul></span></div>
</body></html>"""

NUCLEAR_NET_CN_HTML = """<!DOCTYPE html><html><body>
<div class="bm_c xld zxlblb">
  <div class="top_new cl newss_1"><div class="box01 cl"><div class="rig">
    <h2><a href="http://www.nuclear.net.cn/portal.php?mod=view&aid=17554" target="_blank" class="xi2">这家核电机组FCD正式开工！</a></h2>
    <span class="xg1 time">发表：2026-5-15 17:24</span>
    <a href="http://www.nuclear.net.cn/portal.php?mod=view&aid=17554" target="_blank" class="readmore">查看全文 &gt;&gt;</a>
  </div></div></div>
  <div class="top_new cl newss_2"><div class="box01 cl"><div class="rig">
    <h2><a href="http://www.nuclear.net.cn/portal.php?mod=view&aid=17551" target="_blank" class="xi2">核武器专家赵宪庚等3名工程院院士被除名</a></h2>
    <span class="xg1 time">发表：2026-5-14 09:10</span>
    <a href="http://www.nuclear.net.cn/portal.php?mod=view&aid=17551" target="_blank" class="readmore">查看全文 &gt;&gt;</a>
  </div></div></div>
</div>
</body></html>"""


def test_cgn_news_listing_entry_registered():
    e = _listing_entry("cgn_news")
    assert e["start_urls"] == ["https://www.cgnpc.com.cn/cgn/c100944/jtyw_all.shtml"]
    assert e["via_jina"] is True
    assert SOURCE_TIER_BY_SITE.get("cgn_news") == "industry"


def test_cgn_news_selectors_parse_real_html_structure():
    """HTML mock mirrors the 集团要闻 list (verified by direct probe
    2026-07-30): <li><a><h4 class="blue">title</h4><small>YYYY-MM-DD</small>."""
    items = _parse_news_listing_html(CGN_HTML, _listing_entry("cgn_news"), NOW)

    assert len(items) == 2, f"expected 2 items, got {len(items)}: {items}"
    assert items[0].url == (
        "https://www.cgnpc.com.cn/cgn/c100944/2026-07/21/"
        "content_3316286d6da540168feb58a45594e6b2.shtml"
    )
    assert "元曜一号" in items[0].title
    assert items[0].published_at is not None
    assert (items[0].published_at.year, items[0].published_at.month,
            items[0].published_at.day) == (2026, 7, 16)


def test_nuclear_net_cn_listing_entry_registered():
    e = _listing_entry("nuclear_net_cn")
    assert e["start_urls"] == ["http://www.nuclear.net.cn/portal.php?mod=list&catid=94"]
    assert e["via_jina"] is True
    assert SOURCE_TIER_BY_SITE.get("nuclear_net_cn") == "aggregator"


def test_nuclear_net_cn_selectors_parse_real_html_structure():
    """HTML mock mirrors the Discuz-style `div.top_new` cards (verified by
    direct probe 2026-07-30). The '查看全文 >>' anchor shares the h2 href, so
    each card must yield exactly ONE item. The '发表：' date prefix is
    unparseable → published_at falls back to None (same as Kairos)."""
    items = _parse_news_listing_html(NUCLEAR_NET_CN_HTML, _listing_entry("nuclear_net_cn"), NOW)

    assert len(items) == 2, f"expected 2 items (one per card), got {len(items)}: {items}"
    assert items[0].url == "http://www.nuclear.net.cn/portal.php?mod=view&aid=17554"
    assert "FCD" in items[0].title
    assert "查看全文" not in items[0].title
    assert items[0].published_at is None


# ─────────────────────────────────────────────────────────────────────────────
# 14. _parse_news_listing_jina URL filter must accept the link shapes of the
#     newly-added listing sources (NEA /jcms/, 核网 portal.php, CGN .shtml),
#     otherwise the Jina fallback can never surface anything for them.
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_news_listing_jina_accepts_new_source_link_shapes():
    from update_news import _parse_news_listing_jina

    sess = MagicMock(spec=requests.Session)
    r = MagicMock()
    r.status_code = 200
    r.text = (
        "[Deadline extended for NEA survey on the role of women in the nuclear sector]"
        "(https://www.oecd-nea.org/jcms/pl_119771/deadline-extended-for-nea-survey)\n"
        "[这家核电机组FCD正式开工建造啦](http://www.nuclear.net.cn/portal.php?mod=view&aid=17554)\n"
        "[中广核与内蒙古自治区人民政府签署战略合作协议](https://www.cgnpc.com.cn/cgn/c100944/2026-07/13/content_15be98b214004f15b88522e8b853445b.shtml)\n"
        "[About us page link](https://www.oecd-nea.org/jcms/tro_5705/about-us)\n"
    )
    sess.get.return_value = r

    items = _parse_news_listing_jina(sess, ROSATOM_DEF, NOW)
    urls = {it.url for it in items}
    assert any("/jcms/pl_119771/" in u for u in urls), f"NEA /jcms/ link dropped: {urls}"
    assert any("portal.php?mod=view" in u for u in urls), f"portal.php link dropped: {urls}"
    assert any(u.endswith(".shtml") for u in urls), f".shtml link dropped: {urls}"
    assert len(items) == 4  # about-us also passes via /jcms/ — acceptable, relevance scoring filters later
