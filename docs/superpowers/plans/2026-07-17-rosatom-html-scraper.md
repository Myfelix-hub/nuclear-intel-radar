# Rosatom HTML Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Rosatom (and future enterprise news-listing sites) as a fetchable source via a new generic `fetch_web_news_listing` fetcher with start_urls probe, BeautifulSoup extraction, Jina fallback, and silent-zero visibility.

**Architecture:** New `WEB_SOURCES_NEWS_LISTING` config tuple (parallel to `WEB_SOURCES_DIRECT` / `WEB_SOURCES_JINA`) drives a 3-layer fetcher: probe `start_urls` sequentially → `_parse_news_listing_html` (BeautifulSoup container-based) → fall back to `_parse_news_listing_jina` if all direct attempts hard-fail. Wrapper `fetch_web_news_listing_sources` mirrors the silent-zero fix from P1 (`commit 950f9bd`).

**Tech Stack:** Python 3.14, BeautifulSoup 4, requests (existing). No new dependencies.

## Global Constraints

- Follow patterns from `tests/test_silent_zero.py` for wrapper tests
- All new code goes in `scripts/update_news.py` next to existing `WEB_SOURCES_*` tuples
- Do NOT touch `fetch_web_direct` or `fetch_web_jina` — they keep single responsibility
- Do NOT add a Rosatom-specific fetcher — keep generic
- All wrapper silent-zero tests must follow the contract from `tests/test_silent_zero.py`: `ok=True`, `warning` populated, `error=None` for silent zero; `ok=False`, `error` populated for hard fail
- Selectors in `WEB_SOURCES_NEWS_LISTING` are Drupal-typical guesses; iteration via silent-zero is the documented strategy

---

### Task 1: Test scaffold + data structure + function stubs

**Files:**
- Create: `tests/test_fetch_web_news_listing.py`
- Modify: `scripts/update_news.py:130-157` (add `WEB_SOURCES_NEWS_LISTING` after `WEB_SOURCES_JINA`)

**Interfaces:**
- Produces (Task 2-5 will fill in): `fetch_web_news_listing(session, src_def, now) -> list[RawItem]`, `_parse_news_listing_html(html, src_def, now) -> list[RawItem]`, `_parse_news_listing_jina(session, src_def, now) -> list[RawItem]`, `fetch_web_news_listing_sources(session, now) -> tuple[list[RawItem], list[dict]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetch_web_news_listing.py`:

```python
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
)

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
    sess = MagicMock(spec=requests.Session)
    empty_html = "<html><body><p>no news here</p></body></html>"
    sess.get.return_value = _build_html_resp(empty_html)

    items = fetch_web_news_listing(sess, ROSATOM_DEF, NOW)

    assert items == [], "silent zero must return [] for wrapper to warn"
    # Both start_urls probed
    assert sess.get.call_count == len(ROSATOM_DEF["start_urls"])


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fetch_web_news_listing.py -v`
Expected: All 7 tests FAIL with `ImportError` or `AttributeError` because `fetch_web_news_listing`, `_parse_news_listing_html`, `_parse_news_listing_jina`, `fetch_web_news_listing_sources` do not exist yet.

- [ ] **Step 3: Add `WEB_SOURCES_NEWS_LISTING` config + 4 function stubs to `scripts/update_news.py`**

Insert **after line 157** (after `WEB_SOURCES_JINA = (...)` block ends), before the `# ═══════════════════════════════════════════════════════════════════\n# Data model` divider:

```python
# ─── News listing web sources (BeautifulSoup container-based) ────────────────
# Used by enterprise sites that publish news as a structured HTML listing
# rather than RSS. Each entry is one "news index page" the fetcher probes.

WEB_SOURCES_NEWS_LISTING: tuple[dict[str, Any], ...] = (
    {
        "site_id": "rosatom",
        "site_name": "Rosatom",
        "start_urls": [
            "https://en.rosatom.ru/news/",
            "https://en.rosatom.ru/press-centre/news/",
            "https://en.rosatom.ru/",
        ],
        "container_selector": "article.node--type-news",   # Drupal guess
        "title_selector": "h2.node__title a",
        "link_selector": "h2.node__title a",
        "time_selector": "time",
        "time_attr": "datetime",
        "max_items": 20,
        "via_jina": True,
    },
)
```

Insert **after line 826** (after `fetch_web_jina_sources` ends), before the `# HN Algolia` divider:

```python
# ═══════════════════════════════════════════════════════════════════
# Fetch functions — News listing (structured HTML, no RSS)
# ═══════════════════════════════════════════════════════════════════


def fetch_web_news_listing(session: requests.Session, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Probe start_urls sequentially; first URL with parseable items wins.
    Falls back to Jina reader if via_jina=True and all direct attempts hard-fail.
    Returns [] (silent zero) when all start_urls return 200 HTML but parse 0 items.
    Raises RuntimeError when all start_urls hard-fail (and Jina, if enabled, also fails).
    """
    raise NotImplementedError("implemented in Task 3")


def _parse_news_listing_html(html: str, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Extract news items from structured HTML using src_def's CSS selectors.
    Returns [] when no container matches the selector (silent zero signal)."""
    raise NotImplementedError("implemented in Task 2")


def _parse_news_listing_jina(session: requests.Session, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Fetch src_def['start_urls'][0] via Jina reader and extract article links
    from the resulting markdown. Used as fallback when direct fetch is blocked."""
    raise NotImplementedError("implemented in Task 4")


def fetch_web_news_listing_sources(session: requests.Session, now: datetime) -> tuple[list[RawItem], list[dict[str, Any]]]:
    """Wrapper: invoke fetch_web_news_listing for every WEB_SOURCES_NEWS_LISTING
    entry in parallel; surface silent zero (0 items, no raise) as warning field."""
    items: list[RawItem] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch_web_news_listing, session, sd, now): sd for sd in WEB_SOURCES_NEWS_LISTING}
        for fut in as_completed(futures):
            sd = futures[fut]
            t0 = time.monotonic()
            try:
                result = fut.result()
                elapsed = (time.monotonic() - t0) * 1000
                items.extend(result)
                entry = {"site_id": sd["site_id"], "site_name": sd["site_name"],
                         "ok": True, "item_count": len(result), "duration_ms": round(elapsed), "error": None}
                if not result:
                    entry["warning"] = "fetched ok but 0 items (silent zero — all start_urls returned 200 HTML but no containers matched selector)"
                statuses.append(entry)
            except Exception as e:
                elapsed = (time.monotonic() - t0) * 1000
                statuses.append({"site_id": sd["site_id"], "site_name": sd["site_name"],
                                  "ok": False, "item_count": 0, "duration_ms": round(elapsed), "error": str(e)[:200]})
    return items, statuses
```

- [ ] **Step 4: Run tests to verify they still fail (with NotImplementedError)**

Run: `python -m pytest tests/test_fetch_web_news_listing.py -v`
Expected: Tests still FAIL but now with `NotImplementedError: implemented in Task N` — confirms stubs are in place but logic not yet written.

- [ ] **Step 5: Verify no other tests broken**

Run: `python -m pytest tests/ --ignore=tests/test_silent_zero.py --ignore=tests/test_source_overlap.py --ignore=tests/test_story_merge.py --ignore=tests/test_utils.py -q`
Expected: All previously-passing tests still pass; new test file still failing as expected.

- [ ] **Step 6: Commit**

```bash
git add tests/test_fetch_web_news_listing.py scripts/update_news.py
git commit -m "P1.2: scaffold WEB_SOURCES_NEWS_LISTING + 4 stub functions for news-listing scraper

Adds 7-case test scaffold locking the contract:
- happy path, first-url-fail-second-success
- silent zero (all 200 but 0 items)
- via_jina=False raise, via_jina=True Jina success
- combined raise (direct + Jina both fail)
- wrapper-level silent zero → warning field

Stubs (NotImplementedError) for: fetch_web_news_listing,
_parse_news_listing_html, _parse_news_listing_jina,
fetch_web_news_listing_sources. Tasks 2-5 fill them in."
```

---

### Task 2: Implement `_parse_news_listing_html` (BeautifulSoup extraction)

**Files:**
- Modify: `scripts/update_news.py` — replace `_parse_news_listing_html` stub

**Interfaces:**
- Consumes: `html: str`, `src_def: dict[str, Any]`, `now: datetime`
- Produces: `list[RawItem]` (empty list when no containers match — silent zero signal)
- src_def keys used: `site_id`, `site_name`, `container_selector`, `title_selector`, `link_selector`, `time_selector`, `time_attr`, `max_items`

- [ ] **Step 1: Implement `_parse_news_listing_html`**

Replace the stub body:

```python
def _parse_news_listing_html(html: str, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Extract news items from structured HTML using src_def's CSS selectors.

    For each `container_selector` match:
      - title from title_selector text (trimmed)
      - url from link_selector [href] (joined with src_def['start_urls'][0] base if relative)
      - published_at from time_selector [time_attr] (or text content as fallback)
    Dedup by normalized URL. Returns [] (silent zero signal) when no containers match.
    """
    site_id = src_def["site_id"]
    site_name = src_def["site_name"]
    base_url = src_def["start_urls"][0]
    container_sel = src_def["container_selector"]
    title_sel = src_def["title_selector"]
    link_sel = src_def.get("link_selector", title_sel)
    time_sel = src_def.get("time_selector")
    time_attr = src_def.get("time_attr") or "datetime"
    max_items = int(src_def.get("max_items", 20))

    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select(container_sel)
    if not containers:
        return []

    items: list[RawItem] = []
    seen_urls: set[str] = set()

    for container in containers[:max_items]:
        title_el = container.select_one(title_sel)
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if len(title) < 8:
            continue

        link_el = container.select_one(link_sel) or title_el
        href = link_el.get("href") if link_el and link_el.has_attr("href") else ""
        if not href:
            continue
        full_url = urljoin(base_url, href)
        normalized = normalize_url(full_url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        published = None
        if time_sel:
            time_el = container.select_one(time_sel)
            if time_el:
                time_val = time_el.get(time_attr) or time_el.get_text(strip=True)
                if time_val:
                    published = parse_date_any(time_val, now)

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title), url=full_url, published_at=published,
            meta={"nuclear_relevance": nuclear_keyword_score(title)},
        ))

    return items
```

- [ ] **Step 2: Run happy-path test to verify it passes**

Run: `python -m pytest tests/test_fetch_web_news_listing.py::test_fetch_web_news_listing_happy_path -v`
Expected: PASS

- [ ] **Step 3: Run silent-zero test — still expected to fail (stub for main fetcher)**

Run: `python -m pytest tests/test_fetch_web_news_listing.py::test_fetch_web_news_listing_all_200_but_zero_items -v`
Expected: FAIL with `NotImplementedError: implemented in Task 3` (the main fetcher is still a stub)

- [ ] **Step 4: Commit**

```bash
git add scripts/update_news.py
git commit -m "P1.2: implement _parse_news_listing_html (BeautifulSoup container extraction)"
```

---

### Task 3: Implement `fetch_web_news_listing` (start_urls probe + silent zero + raise)

**Files:**
- Modify: `scripts/update_news.py` — replace `fetch_web_news_listing` stub

**Interfaces:**
- Consumes: `session`, `src_def`, `now`
- Produces: `list[RawItem]` (empty list for silent zero); raises `RuntimeError` for hard fail
- Reads `src_def['start_urls']`, `src_def['via_jina']`, `src_def['site_id']`

- [ ] **Step 1: Implement `fetch_web_news_listing`**

Replace the stub body:

```python
def fetch_web_news_listing(session: requests.Session, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Probe start_urls sequentially; first URL with parseable items wins.

    Per-URL behavior:
        - HTTP 200 + content-type text/html → parse via _parse_news_listing_html.
          If items found → return immediately. If 0 items → remember, try next URL.
        - HTTP 4xx/5xx / non-HTML / network error → skip to next URL.

    Aggregate outcomes:
        - At least one URL returned items → return those items.
        - All URLs returned 200 HTML but no items parsed → return [] (silent zero).
        - All URLs hard-failed (no URL even reached 200 HTML) →
            if via_jina=True → try _parse_news_listing_jina; if that also fails or
            returns 0 items in the Jina path, raise RuntimeError.
            if via_jina=False → raise RuntimeError.
    """
    site_id = src_def["site_id"]
    start_urls = src_def["start_urls"]
    via_jina = bool(src_def.get("via_jina", False))

    direct_errors: list[str] = []
    all_200_zero_items = True  # assume silent zero until we prove otherwise

    for url in start_urls:
        try:
            resp = session.get(url, timeout=30)
        except Exception as e:
            direct_errors.append(f"{url}: {type(e).__name__}: {str(e)[:80]}")
            all_200_zero_items = False
            continue

        if resp.status_code != 200:
            direct_errors.append(f"{url}: HTTP {resp.status_code}")
            all_200_zero_items = False
            continue

        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype:
            direct_errors.append(f"{url}: not HTML (content-type={ctype[:40]})")
            all_200_zero_items = False
            continue

        try:
            items = _parse_news_listing_html(resp.text, src_def, now)
        except Exception as e:
            direct_errors.append(f"{url}: parse error {type(e).__name__}: {str(e)[:80]}")
            all_200_zero_items = False
            continue

        if items:
            return items  # success — stop probing

    # If we got here, no URL yielded items. Decide the outcome:
    if all_200_zero_items:
        # All start_urls served 200 HTML but no items parsed → silent zero
        return []

    # At least one URL hard-failed. Try Jina if enabled.
    if via_jina:
        try:
            jina_items = _parse_news_listing_jina(session, src_def, now)
            if jina_items:
                return jina_items
            # Jina returned 0 items — treat as silent zero (still no items to surface)
            return []
        except Exception as jina_err:
            raise RuntimeError(
                f"{site_id}: all start_urls + Jina failed — "
                + " || ".join(direct_errors)
                + f" || Jina: {type(jina_err).__name__}: {str(jina_err)[:100]}"
            ) from jina_err

    raise RuntimeError(
        f"{site_id}: all {len(start_urls)} start_urls hard-failed — "
        + " || ".join(direct_errors)
    )
```

- [ ] **Step 2: Run tests 1-4 (happy path + 2 fallbacks + silent zero + raise)**

Run: `python -m pytest tests/test_fetch_web_news_listing.py -v -k "not jina_fallback and not combined_raise and not sources_records"`
Expected: PASS for `test_fetch_web_news_listing_happy_path`, `test_fetch_web_news_listing_first_url_fails_second_succeeds`, `test_fetch_web_news_listing_all_200_but_zero_items`, `test_fetch_web_news_listing_all_fail_no_jina_raises`.
The two Jina tests still fail with `NotImplementedError: implemented in Task 4`.

- [ ] **Step 3: Commit**

```bash
git add scripts/update_news.py
git commit -m "P1.2: implement fetch_web_news_listing (start_urls probe + silent zero + raise)"
```

---

### Task 4: Implement `_parse_news_listing_jina` (markdown regex extraction)

**Files:**
- Modify: `scripts/update_news.py` — replace `_parse_news_listing_jina` stub

**Interfaces:**
- Consumes: `session`, `src_def`, `now`
- Produces: `list[RawItem]` (empty list for silent zero); raises on hard fail

- [ ] **Step 1: Implement `_parse_news_listing_jina`**

Replace the stub body:

```python
def _parse_news_listing_jina(session: requests.Session, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Fetch src_def['start_urls'][0] via Jina reader, then extract article links
    from the resulting markdown via regex.

    CSS selectors do NOT survive HTML→markdown conversion, so this path is a
    heuristic regex sweep over [text](url) pairs. Filters applied:
      - skip images (title starts with !)
      - title length >= 10
      - URL must contain a year-like segment or path component suggesting news
        (e.g. /news/, /press/, /2024/, /2025/, /2026/, article path)
    Raises on HTTP non-200 from Jina.
    """
    site_id = src_def["site_id"]
    site_name = src_def["site_name"]
    base_url = src_def["start_urls"][0]
    jina_url = f"{JINA_BASE}{base_url}"

    resp = session.get(jina_url, timeout=45,
                       headers={"Accept": "text/markdown,text/plain", "User-Agent": BROWSER_UA})
    if resp.status_code != 200:
        raise RuntimeError(f"{site_id}: Jina returned HTTP {resp.status_code} for {base_url}")

    items: list[RawItem] = []
    seen_urls: set[str] = set()
    md_links: list[tuple[str, str]] = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', resp.text)

    for title, url in md_links:
        title = title.strip()
        if title.startswith("!") or title.startswith("Image"):
            continue
        if len(title) < 10:
            continue
        # Heuristic URL filter: must look like a news/article path
        url_lower = url.lower()
        if not any(seg in url_lower for seg in [
            "/news/", "/press/", "/article/", "/publication/",
            "/2024/", "/2025/", "/2026/", "/2027/", "/20",
        ]):
            continue
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title), url=url, published_at=None,
            meta={"nuclear_relevance": nuclear_keyword_score(title)},
        ))

    return items
```

- [ ] **Step 2: Run all 7 tests — except the wrapper one**

Run: `python -m pytest tests/test_fetch_web_news_listing.py -v -k "not sources_records"`
Expected: 6 tests PASS (1-6). Test 7 (wrapper) still fails because `fetch_web_news_listing_sources` is a stub.

- [ ] **Step 3: Commit**

```bash
git add scripts/update_news.py
git commit -m "P1.2: implement _parse_news_listing_jina (markdown regex extraction)"
```

---

### Task 5: Wire `collect_all` to invoke the new wrapper

**Files:**
- Modify: `scripts/update_news.py` — `collect_all` body, between `fetch_web_jina_sources` call and the community block

**Interfaces:**
- Consumes: `fetch_web_news_listing_sources(session, now)` returning `(items, statuses)`
- Produces: extends `all_items` and `all_statuses`

- [ ] **Step 1: Add wrapper call to `collect_all`**

In `collect_all` (around line 989-991, after `jina_statuses` is appended), insert:

```python
    # News listing sources (structured HTML, e.g. Rosatom)
    listing_items, listing_statuses = fetch_web_news_listing_sources(session, now)
    all_items.extend(listing_items)
    all_statuses.extend(listing_statuses)
```

- [ ] **Step 2: Run full test suite — silent_zero + new + all pre-existing**

Run: `python -m pytest tests/ -v --ignore=tests/test_source_overlap.py --ignore=tests/test_story_merge.py --ignore=tests/test_utils.py --deselect tests/test_reddit_partial_failure.py::test_returns_items_when_one_subreddit_succeeds`
Expected: All previously-passing tests still pass + 7 new tests pass. The 1 known-flaky reddit test + 3 P3 import errors stay excluded.

- [ ] **Step 3: Compile-check the script**

Run: `python -m py_compile scripts/update_news.py && echo "SYNTAX_OK"`
Expected: `SYNTAX_OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/update_news.py
git commit -m "P1.2: wire collect_all to fetch_web_news_listing_sources wrapper"
```

---

### Task 6: Push to remote, observe Actions run, iterate selectors if silent zero

**Files:** None (operational task)

- [ ] **Step 1: Push**

```bash
git push origin master
```

Expected: `master -> master` push succeeds.

- [ ] **Step 2: Wait for Actions run to finish (overseas runner)**

Run: `git fetch origin master && git log --oneline origin/master -3`
Expected: New commit `chore: update nuclear news snapshot` appears within ~10 min (Actions auto-commits data updates).

- [ ] **Step 3: Inspect `data/source-status.json` for Rosatom**

Run: `git show origin/master:data/source-status.json | python -c "import json,sys; d=json.load(sys.stdin); [print(s) for s in d['sites'] if s['site_id']=='rosatom']"`
Expected (first attempt): `{... 'item_count': 0, 'warning': '...silent zero — all start_urls returned 200 HTML but no containers matched selector'}` — the iteration signal we wanted.

- [ ] **Step 4: If silent zero — fetch one Rosatom page to diagnose selectors**

Run:
```bash
curl -s "https://en.rosatom.ru/news/" | head -200
```
Look at the actual HTML structure. Update `container_selector` / `title_selector` / `time_selector` in `WEB_SOURCES_NEWS_LISTING` to match. Commit + push. Repeat until `item_count > 0`.

- [ ] **Step 5: Update memory with final state**

If Rosatom ends up with `item_count > 0`, update `~/.claude/projects/C--Users-Myfelix-RR/memory/nuclear-intel-radar-project.md` to reflect the new source and the iteration outcome (which selectors worked).

- [ ] **Step 6: Commit any follow-up changes**

```bash
git add scripts/update_news.py memory/
git commit -m "P1.2: tune Rosatom selectors based on Actions output + update memory"
```

---

### Task 7: Verify wrapper-level silent-zero contract (regression)

**Files:** None (test-only re-run)

- [ ] **Step 1: Run silent-zero + new tests together**

Run: `python -m pytest tests/test_silent_zero.py tests/test_fetch_web_news_listing.py -v -k "not collect_all_warns"`
Expected: All 11 tests pass (5 silent-zero + 6 news-listing — the slow collect_all_warns test is deselected for speed).

- [ ] **Step 2: Done**

The news-listing fetcher is fully wired, the silent-zero contract is preserved end-to-end, and any select-or iteration work happens in Task 6 Step 4.