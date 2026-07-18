# P3 WeChat RSSHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 9 Chinese 微信公众号 (WeChat public accounts) to the nuclear-intel-radar pipeline via an RSSHub bridge hosted on Tencent Serverless Cloud Function (SCF), so maintainers can subscribe to high-signal Chinese nuclear industry sources without needing a first-party WeChat API.

**Architecture:** Add 9 entries to existing `NUCLEAR_RSS_FEEDS` whose `xml_url` is a template `{RSSHUB_BASE}/wechat/{mpID}` resolved at fetch time. A standalone `discover_wechat_mpids.py` script (run by maintainer locally once) resolves公众号 names → mpIDs via RSSHub `/newwechat` and caches them in `data/wechat_mpids.json` (git-tracked). When `RSSHUB_BASE` GitHub secret or the mpID cache is missing, the 9 wechat entries fall through to silent-zero (matches existing TerraPower / Oklo pattern) so the pipeline never crashes on bridge absence.

**Tech Stack:** Python 3.11 + feedparser (existing); Tencent SCF (RSSHub official scf-template); RSSHub `/wechat/:mpID` and `/newwechat/:name` routes; GitHub Actions secrets for `RSSHUB_BASE` injection; existing `fetch_single_rss_feed` RSS path (no new fetch code).

**Reference spec:** `docs/superpowers/specs/2026-07-18-p3-wechat-rsshub-design.md`

## Global Constraints

- **9 公众号 names** (from spreadsheet rows 60-68, hardcode in `WECHAT_ACCOUNTS`):
  1. 中国核电网 (CNNP) → `wechat_cnnp`
  2. 中核集团 → `wechat_cnnc`
  3. 中国核建 → `wechat_cnji`
  4. 中国能源研究 → `wechat_energy_research`
  5. 核闻 (NuclearNet) → `wechat_nuclearnet`
  6. 核电那些事 → `wechat_nuclear_story`
  7. 国家核安全局 → `wechat_nsa`
  8. 上海核电 → `wechat_sh_nuclear`
  9. 中国核动力研究设计院 → `wechat_npdi`

- **Tier for all 9**: `industry` (in `scripts/nuclear_keywords.py` `SOURCE_TIER_BY_SITE`)

- **Existing silent-zero contract** (from `tests/test_silent_zero.py` + TerraPower/Oklo precedent):
  When fetcher returns `[]` but `ok=True`, wrapper MUST record `warning` field and `error=null`. Pipeline does not crash.

- **Existing hard-fail contract** (from `tests/test_silent_failure.py`):
  When fetcher raises, wrapper MUST record `ok=False, error=...`. Per-entry (not pipeline-wide).

- **`RSSHUB_BASE` injection**: GitHub Actions secret, read via `os.environ.get("RSSHUB_BASE", "")`. Empty string = silent zero for all 9 wechat entries.

- **GitHub Actions runner**: `ubuntu-latest`. WeChat is blocked from overseas IPs — RSSHub MUST be on a domestic IP surface (Tencent SCF). Maintainer deploys separately; workflow only consumes the URL.

- **mpID cache**: `data/wechat_mpids.json` is git-tracked; structure `[{name, mpID, fetched_at}, ...]` matching 9 entries above. Maintainer runs `discover_wechat_mpids.py` locally once after SCF deploy, commits the JSON.

- **No new fetch code**: Wechat entries use the existing `fetch_single_rss_feed` path via `_fetch_rss_xml` (defined `update_news.py:820`). Only addition is `_resolve_wechat_xml_url` helper + 9 entries with `xml_url` as a template string.

- **No new dependencies**: `requirements.txt` unchanged. RSSHub deployment uses `serverless` framework + `node` runtime (separate from Python pipeline).

- **DRY**: All 9 entries share helpers (`_resolve_wechat_xml_url`, `_load_wechat_mpids`); do not duplicate URL/path construction per entry.

- **YAGNI**: No multi-cloud / multi-instance RSSHub; no auto-rotation of mpIDs; no per-entry discovery fallback; no transformation of RSSHub output beyond what the existing RSS parser does.

- **Frequent commits**: Each task ends with a `git commit`. Never bundle multiple tasks into one commit.

- **Tests use mocks**: No real RSSHub instance required to run any test. All tests offline-deterministic.

---

## File Structure

### Files created

| Path | Responsibility |
|---|---|
| `scripts/discover_wechat_mpids.py` | One-time CLI: name → RSSHub /newwechat → mpID → write JSON |
| `scripts/deploy_rsshub_scf/serverless.yml` | SCF config (region, memory, timeout, env) |
| `scripts/deploy_rsshub_scf/package.json` | RSSHub version pin |
| `scripts/deploy_rsshub_scf/deploy.sh` | Wrapper invoking `sls deploy` |
| `data/wechat_mpids.json` | Cache: 9 rows `{name, mpID, fetched_at}` (created by discover script) |
| `tests/test_discover_wechat_mpids.py` | mpID discovery correctness (mocked) |
| `tests/test_wechat_rss_entries.py` | entry registration + tier + path construction |
| `tests/test_wechat_silent_zero.py` | missing bridge → silent zero |
| `tests/test_wechat_rsshub_failure.py` | per-entry hard fail |

### Files modified

| Path | Change |
|---|---|
| `scripts/update_news.py` | Add `WECHAT_ACCOUNTS` constant; add `_resolve_wechat_xml_url`, `_load_wechat_mpids`, `_fetch_wechat_rss` helpers; add 9 entries to `NUCLEAR_RSS_FEEDS` |
| `scripts/nuclear_keywords.py` | Add 9 tier mappings |
| `.github/workflows/update-news.yml` | Inject `RSSHUB_BASE` from secrets into "Update data" step env |
| `CLAUDE.md` | Remove WeChat exclusion line; add note about P3 / RSSHub bridge |
| `README.md` | Add "Adding WeChat 公众号" setup section |

---

## Task 1: WeChat helpers + entries + tier mapping (foundation)

This task establishes all the building blocks. Tests at the end verify silent-zero and registration. Later tasks layer on top.

**Files:**
- Modify: `scripts/update_news.py:1-30` (imports), `scripts/update_news.py:56-101` (NUCLEAR_RSS_FEEDS), add new section after NUCLEAR_RSS_FEEDS for helpers
- Modify: `scripts/nuclear_keywords.py:79-110` (SOURCE_TIER_BY_SITE)
- Create: `tests/test_wechat_rss_entries.py`
- Create: `tests/test_wechat_silent_zero.py`

**Interfaces:**
- Consumes: `requests.Session`, `data/wechat_mpids.json` (path: `data/wechat_mpids.json` relative to repo root), `os.environ["RSSHUB_BASE"]`
- Produces:
  - `WECHAT_ACCOUNTS: tuple[dict[str, str], ...]` — 9 entries, each `{mpID_key, site_id, site_name, display_name}`
  - `_resolve_wechat_xml_url(site_id: str, mpids_map: dict[str, str], rsshub_base: str) -> str | None` — returns full URL or None if either side missing
  - `_load_wechat_mpids(path: Path) -> dict[str, str] | None` — returns `{mpID_key: mpID}` map or None on any error
  - `_fetch_wechat_rss(session, feed_def, now) -> list[RawItem]` — wrapper around `_fetch_rss_xml` with silent-zero on missing bridge

### Step 1.1: Add tier mappings (write failing test)

In `tests/test_wechat_rss_entries.py`:

```python
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
```

### Step 1.2: Run test — verify it fails

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_rss_entries.py -v
```

Expected: `ImportError: cannot import name 'WECHAT_ACCOUNTS' from 'update_news'`

### Step 1.3: Add `WECHAT_ACCOUNTS` constant + tier mappings + 9 NUCLEAR_RSS_FEEDS entries

In `scripts/update_news.py`, add imports near the top (after `import os`):

```python
import os
from pathlib import Path
```

(Skip if already imported — check existing imports first.)

After the closing `)` of `NUCLEAR_RSS_FEEDS` (line 101), add:

```python
# ═══════════════════════════════════════════════════════════════════
# WeChat 公众号 — bridged via RSSHub (deployed to Tencent SCF by maintainer)
# xml_url is a template resolved at fetch time; missing bridge → silent zero.
# ═══════════════════════════════════════════════════════════════════

WECHAT_ACCOUNTS: tuple[dict[str, str], ...] = (
    {"mpID_key": "cnnp",             "site_id": "wechat_cnnp",             "site_name": "中国核电网 (CNNP)",      "display_name": "中国核电网"},
    {"mpID_key": "cnnc",             "site_id": "wechat_cnnc",             "site_name": "中核集团",                 "display_name": "中核集团"},
    {"mpID_key": "cnji",             "site_id": "wechat_cnji",             "site_name": "中国核建",                 "display_name": "中国核建"},
    {"mpID_key": "energy_research",  "site_id": "wechat_energy_research",  "site_name": "中国能源研究",             "display_name": "中国能源研究"},
    {"mpID_key": "nuclearnet",       "site_id": "wechat_nuclearnet",       "site_name": "核闻 NuclearNet",        "display_name": "核闻"},
    {"mpID_key": "nuclear_story",    "site_id": "wechat_nuclear_story",    "site_name": "核电那些事",               "display_name": "核电那些事"},
    {"mpID_key": "nsa",              "site_id": "wechat_nsa",              "site_name": "国家核安全局",             "display_name": "国家核安全局"},
    {"mpID_key": "sh_nuclear",       "site_id": "wechat_sh_nuclear",       "site_name": "上海核电",                 "display_name": "上海核电"},
    {"mpID_key": "npdi",             "site_id": "wechat_npdi",             "site_name": "中国核动力研究设计院",     "display_name": "中国核动力研究设计院"},
)

WECHAT_MPIDS_PATH = Path("data/wechat_mpids.json")
```

Then append 9 entries to `NUCLEAR_RSS_FEEDS` (before its closing `)`):

```python
    # WeChat 公众号 via RSSHub (deployed to Tencent SCF, see deploy_rsshub_scf/).
    # xml_url is a template resolved at fetch time by _resolve_wechat_xml_url.
    # Missing bridge (no RSSHUB_BASE secret / no mpID cache) → silent zero.
    *({{
        "site_id": acct["site_id"],
        "site_name": acct["site_name"],
        "xml_url": "{{RSSHUB_BASE}}/wechat/{{mpID}}",
        "html_url": "https://mp.weixin.qq.com/",
        "via_jina": False,
        "_mpID_key": acct["mpID_key"],
    }} for acct in WECHAT_ACCOUNTS),
```

NOTE: tuple-of-dicts concatenation — modify if NUCLEAR_RSS_FEEDS becomes a list. Adjust syntax to match (tuple → use `*` unpacking; list → use `.extend()`).

In `scripts/nuclear_keywords.py`, inside `SOURCE_TIER_BY_SITE` dict (around line 79-110), add after the existing `kairos: "industry"` line:

```python
    "wechat_cnnp": "industry",
    "wechat_cnnc": "industry",
    "wechat_cnji": "industry",
    "wechat_energy_research": "industry",
    "wechat_nuclearnet": "industry",
    "wechat_nuclear_story": "industry",
    "wechat_nsa": "industry",
    "wechat_sh_nuclear": "industry",
    "wechat_npdi": "industry",
```

### Step 1.4: Run test — verify it passes

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_rss_entries.py -v
```

Expected: All 19 tests pass (9 + 9 + 1).

### Step 1.5: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add scripts/update_news.py scripts/nuclear_keywords.py tests/test_wechat_rss_entries.py
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 foundation: register 9 wechat entries + tier mapping"
```

---

## Task 2: WeChat helpers implementation + silent-zero tests

**Files:**
- Modify: `scripts/update_news.py` — add `_resolve_wechat_xml_url`, `_load_wechat_mpids`, `_fetch_wechat_rss` helpers
- Create: `tests/test_wechat_silent_zero.py`

**Interfaces:**
- `_resolve_wechat_xml_url(site_id: str, mpids_map: dict[str, str] | None, rsshub_base: str) -> str | None`
  - Returns `None` if `mpids_map is None` or `not rsshub_base.strip()` or `site_id` not in `mpids_map`
  - Returns `f"{rsshub_base.rstrip('/')}/wechat/{mpids_map[site_id]}"` otherwise
- `_load_wechat_mpids(path: Path) -> dict[str, str] | None`
  - Returns `None` if file missing / malformed JSON / not a list
  - Returns `{"<site_id>": "<mpID>", ...}` keyed by `site_id` (not `mpID_key`) for direct lookup
  - Schema expected per row: `{"name": str, "mpID": str, "site_id": str (optional), "fetched_at": str}`
- `_fetch_wechat_rss(session: requests.Session, feed_def: dict, now: datetime) -> list[RawItem]`
  - If `RSSHUB_BASE` env empty → return `[]` (silent zero, wrapper will warn)
  - If mpID cache missing/empty → return `[]`
  - If `site_id` not in cache → return `[]`
  - Else call existing `_fetch_rss_xml(session, resolved_url, site_id, site_name, html_url, now, feed_def)`

### Step 2.1: Write failing test for silent-zero path

In `tests/test_wechat_silent_zero.py`:

```python
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
                        published_at=now, summary="")]

    monkeypatch.setattr(update_news, "_fetch_rss_xml", fake_fetch_rss_xml)
    sess = MagicMock(spec=requests.Session)
    items = _fetch_wechat_rss(sess, _wechat_def(), NOW)
    assert len(items) == 1
    assert captured["url"] == "https://r.example/release/rsshub/wechat/Mp-abc"
    assert captured["site_id"] == "wechat_cnnp"
```

### Step 2.2: Run test — verify it fails

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_silent_zero.py -v
```

Expected: `ImportError: cannot import name '_resolve_wechat_xml_url' from 'update_news'`

### Step 2.3: Add helpers to `scripts/update_news.py`

After `WECHAT_MPIDS_PATH` definition (added in Task 1), append:

```python
def _resolve_wechat_xml_url(
    site_id: str, mpids_map: dict[str, str] | None, rsshub_base: str
) -> str | None:
    """Resolve template `{RSSHUB_BASE}/wechat/{mpID}` to a real URL.

    Returns None when bridge is missing in any way:
      - rsshub_base is empty/whitespace
      - mpids_map is None
      - site_id not in mpids_map

    Caller (typically _fetch_wechat_rss) must translate None into silent-zero.
    """
    if not rsshub_base or not rsshub_base.strip():
        return None
    if not mpids_map:
        return None
    mpID = mpids_map.get(site_id)
    if not mpID:
        return None
    return f"{rsshub_base.rstrip('/')}/wechat/{mpID}"


def _load_wechat_mpids(path: Path) -> dict[str, str] | None:
    """Load data/wechat_mpids.json and return {site_id: mpID} map.

    Returns None if file missing, malformed JSON, not a list, or empty.
    Skips individual rows with empty mpID / missing site_id.
    """
    try:
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list):
        return None
    result: dict[str, str] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        site_id = row.get("site_id")
        mpID = row.get("mpID")
        if isinstance(site_id, str) and isinstance(mpID, str) and site_id and mpID.strip():
            result[site_id] = mpID
    return result or None


def _fetch_wechat_rss(
    session: requests.Session, feed_def: dict[str, Any], now: datetime
) -> list[RawItem]:
    """Fetch one wechat entry's RSS via RSSHub bridge.

    Silent-zero contract (matches TerraPower / Oklo):
      - RSSHUB_BASE env unset/empty → return []
      - mpID cache missing/malformed → return []
      - site_id not in cache → return []
      - any HTTP failure → raise (per-entry hard fail; wrapper records ok=False)
    """
    site_id = feed_def["site_id"]
    site_name = feed_def["site_name"]
    html_url = feed_def.get("html_url", "https://mp.weixin.qq.com/")

    rsshub_base = os.environ.get("RSSHUB_BASE", "")
    mpids_map = _load_wechat_mpids(WECHAT_MPIDS_PATH)

    xml_url = _resolve_wechat_xml_url(site_id, mpids_map, rsshub_base)
    if xml_url is None:
        return []

    return _fetch_rss_xml(session, xml_url, site_id, site_name, html_url, now, feed_def)
```

### Step 2.4: Run test — verify it passes

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_silent_zero.py -v
```

Expected: All 13 tests pass.

### Step 2.5: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add scripts/update_news.py tests/test_wechat_silent_zero.py
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 helpers: resolve + load + fetch with silent-zero on missing bridge"
```

---

## Task 3: Wire wechat entries into the fetch pipeline

Currently the 9 wechat entries have `xml_url = "{RSSHUB_BASE}/wechat/{mpID}"` which is not a valid URL. The fetch pipeline calls `fetch_single_rss_feed` which calls `_fetch_rss_xml` directly with `xml_url`. We need to dispatch wechat entries to `_fetch_wechat_rss` instead.

**Files:**
- Modify: `scripts/update_news.py:761-820` (`fetch_single_rss_feed` function — add dispatch at top)

**Decision**: Add a check at the top of `fetch_single_rss_feed`:

```python
if feed_def.get("_mpID_key"):
    return _fetch_wechat_rss(session, feed_def, now)
```

This keeps the rest of `fetch_single_rss_feed` untouched.

### Step 3.1: Verify existing pipeline test still passes (sanity)

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/ -v --tb=no -q 2>&1 | tail -20
```

Expected: All previous tests still pass (this task should not change them).

### Step 3.2: Modify `fetch_single_rss_feed`

In `scripts/update_news.py`, at the top of `fetch_single_rss_feed` (after `site_id = feed_def["site_id"]` line, before `xml_url = feed_def["xml_url"]`), add:

```python
    # WeChat 公众号 entries have a template xml_url resolved at fetch time.
    # Dispatch to _fetch_wechat_rss which handles RSSHub bridge resolution.
    if feed_def.get("_mpID_key"):
        return _fetch_wechat_rss(session, feed_def, now)
```

### Step 3.3: Run all tests — verify everything still passes

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All tests pass. The 9 wechat entries will be exercised; with no `RSSHUB_BASE` env + no `data/wechat_mpids.json`, they fall through to silent-zero via the new dispatch path. The pre-existing pipeline test (which iterates over all entries) will see silent-zero for wechat and either pass or skip them gracefully.

If any test fails because of the 9 new entries breaking an enumeration assumption (e.g. test counted "9 wechat entries produce no items"), that's expected and acceptable — only fail if a non-wechat test breaks.

### Step 3.4: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add scripts/update_news.py
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 dispatch: route wechat entries through _fetch_wechat_rss"
```

---

## Task 4: Per-entry hard-fail tests for RSSHub errors

When RSSHUB_BASE is set but the specific mpID call fails (404 / 503), the wrapper must record `ok=False, error=...`. This proves the per-entry error visibility.

**Files:**
- Create: `tests/test_wechat_rsshub_failure.py`

### Step 4.1: Write failing tests

```python
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
```

### Step 4.2: Run test — verify it fails (or the second integration test fails)

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_rsshub_failure.py -v
```

Expected: First two tests pass (RuntimeError raised correctly). Third test (integration) may fail if `fetch_rss_sources` doesn't include wechat entries in its iteration; that proves Task 3 dispatch is missing — fix and re-run.

### Step 4.3: Run test — verify it passes (after any Task 3 fix)

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_wechat_rsshub_failure.py -v
```

Expected: All 3 tests pass.

### Step 4.4: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add tests/test_wechat_rsshub_failure.py
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 tests: per-entry hard fail when RSSHub returns 4xx/5xx"
```

---

## Task 5: GitHub Actions workflow injects `RSSHUB_BASE` env

**Files:**
- Modify: `.github/workflows/update-news.yml:44-47`

### Step 5.1: Add `RSSHUB_BASE` env to "Update data" step

Find the existing step:
```yaml
      - name: Update data
        run: |
          python scripts/update_news.py --output-dir data --window-hours 72 --archive-days 21
```

Change to:
```yaml
      - name: Update data
        env:
          RSSHUB_BASE: ${{ secrets.RSSHUB_BASE }}
        run: |
          python scripts/update_news.py --output-dir data --window-hours 72 --archive-days 21
```

### Step 5.2: Validate workflow YAML

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -c "import yaml; yaml.safe_load(open('.github/workflows/update-news.yml'))" && echo OK
```

Expected: `OK`

### Step 5.3: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add .github/workflows/update-news.yml
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 workflow: inject RSSHUB_BASE from GitHub secret"
```

---

## Task 6: `discover_wechat_mpids.py` discover script

Standalone CLI for maintainer to run locally once after SCF deploy.

**Files:**
- Create: `scripts/discover_wechat_mpids.py`

### Step 6.1: Write failing test

`tests/test_discover_wechat_mpids.py`:

```python
"""Tests for the one-time mpID discovery CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import discover_wechat_mpids  # noqa: E402


def _build_rsshub_resp(mpID: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    # RSSHub /newwechat response shape varies; parser must handle common ones.
    # Most common: redirect to /wechat/:mpID with body containing the mpID link.
    resp.text = f'<html><body><a href="/wechat/{mpID}">link</a></body></html>'
    resp.headers = {"content-type": "text/html"}
    resp.raise_for_status.return_value = None
    return resp


def test_discover_writes_json_with_resolved_mpids(tmp_path, monkeypatch):
    """End-to-end: mock RSSHub /newwechat, verify JSON output."""
    output = tmp_path / "mpids.json"
    sess = MagicMock(spec=requests.Session)
    sess.get.return_value = _build_rsshub_resp("Mp-test-cnnp")

    # Map name → mpID by returning different mpIDs per call
    expected_mpids = {
        "cnnp": "Mp-cnnp-1",
        "cnnc": "Mp-cnnc-1",
        "cnji": "Mp-cnji-1",
        "energy_research": "Mp-energy-1",
        "nuclearnet": "Mp-nuclearnet-1",
        "nuclear_story": "Mp-story-1",
        "nsa": "Mp-nsa-1",
        "sh_nuclear": "Mp-sh-1",
        "npdi": "Mp-npdi-1",
    }
    counter = {"i": 0}

    def side_effect(url, **kwargs):
        idx = counter["i"]
        counter["i"] += 1
        # Resolve mpID from the URL or iterate by index
        key = list(expected_mpids.keys())[idx]
        return _build_rsshub_resp(expected_mpids[key])

    sess.get.side_effect = side_effect

    exit_code = discover_wechat_mpids.run(
        session=sess,
        rsshub_base="https://r.example/release/rsshub",
        output_path=output,
    )
    assert exit_code == 0
    assert output.exists()
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 9
    assert {r["mpID_key"] for r in rows} == set(expected_mpids.keys())
    for r in rows:
        assert r["mpID"] == expected_mpids[r["mpID_key"]]
        assert r["fetched_at"]


def test_discover_exits_1_when_some_names_fail(tmp_path):
    output = tmp_path / "mpids.json"
    sess = MagicMock(spec=requests.Session)

    def side_effect(url, **kwargs):
        # First call succeeds, second fails with 503
        if "fail" in url:
            r = MagicMock()
            r.status_code = 503
            r.text = ""
            r.raise_for_status.side_effect = requests.HTTPError("HTTP 503")
            return r
        return _build_rsshub_resp("Mp-ok")

    sess.get.side_effect = side_effect
    # Monkeypatch the names list to inject a guaranteed failure
    with patch.object(discover_wechat_mpids, "NAMES", [("ok", "ok"), ("fail", "fail")]):
        exit_code = discover_wechat_mpids.run(
            session=sess,
            rsshub_base="https://r.example/release/rsshub",
            output_path=output,
        )
    assert exit_code == 1
    assert output.exists(), "partial JSON must be written for ops to inspect"
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["mpID_key"] == "ok"


def test_discover_resolves_mpid_from_response_html():
    """Unit test for the mpID extraction logic."""
    html = '<html><body><a href="/wechat/Mp-abc123">中国核电网</a></body></html>'
    assert discover_wechat_mpids._extract_mpid_from_html(html) == "Mp-abc123"


def test_discover_resolves_mpid_from_response_html_alternate_shape():
    """Some RSSHub versions embed mpID in JSON or in a different tag."""
    html = '<html><body><div data-mpid="Mp-xyz789">x</div></body></html>'
    assert discover_wechat_mpids._extract_mpid_from_html(html) == "Mp-xyz789"


def test_discover_returns_none_when_no_mpid_in_html():
    html = "<html><body><p>no match</p></body></html>"
    assert discover_wechat_mpids._extract_mpid_from_html(html) is None
```

### Step 6.2: Run test — verify it fails

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_discover_wechat_mpids.py -v
```

Expected: `ModuleNotFoundError: No module named 'discover_wechat_mpids'`

### Step 6.3: Write `scripts/discover_wechat_mpids.py`

```python
"""One-time mpID discovery CLI for WeChat 公众号 sources.

Resolves公众号 names to mpIDs via RSSHub /newwechat and writes
data/wechat_mpids.json. Run locally by maintainer after deploying RSSHub
to Tencent SCF; never run in CI.

Usage:
    RSSHUB_BASE=https://service-xxxx.gz.apigw.tencentcs.com/release/rsshub \\
        python scripts/discover_wechat_mpids.py

Exit codes:
    0 — all 9 names resolved
    1 — some names failed; partial JSON still written for inspection
    2 — RSSHUB_BASE env not set
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

# 9 公众号 from spreadsheet rows 60-68. (mpID_key, RSSHub /newwechat query string)
NAMES: tuple[tuple[str, str], ...] = (
    ("cnnp",             "中国核电网"),
    ("cnnc",             "中核集团"),
    ("cnji",             "中国核建"),
    ("energy_research",  "中国能源研究"),
    ("nuclearnet",       "核闻"),
    ("nuclear_story",    "核电那些事"),
    ("nsa",              "国家核安全局"),
    ("sh_nuclear",       "上海核电"),
    ("npdi",             "中国核动力研究设计院"),
)

SITE_ID_BY_KEY = {
    "cnnp": "wechat_cnnp",
    "cnnc": "wechat_cnnc",
    "cnji": "wechat_cnji",
    "energy_research": "wechat_energy_research",
    "nuclearnet": "wechat_nuclearnet",
    "nuclear_story": "wechat_nuclear_story",
    "nsa": "wechat_nsa",
    "sh_nuclear": "wechat_sh_nuclear",
    "npdi": "wechat_npdi",
}

OUTPUT_PATH = Path("data/wechat_mpids.json")
RSSHUB_NEW_WECHAT = "/newwechat"  # RSSHub route; appended with query string

MPID_RE = re.compile(r"(/wechat/|mpid=|data-mpid=)(Mp-[A-Za-z0-9_-]+)")


def _extract_mpid_from_html(html: str) -> str | None:
    """Extract the first mpID from a RSSHub /newwechat response body.

    Supports two common response shapes:
      1. Anchor href like /wechat/Mp-xxx
      2. data-mpid="Mp-xxx" attribute
    """
    m = MPID_RE.search(html)
    return m.group(2) if m else None


def _discover_one(
    session: requests.Session, rsshub_base: str, mpID_key: str, name: str
) -> str | None:
    """Resolve one name to mpID via RSSHub /newwechat/:name. Returns None on failure."""
    base = rsshub_base.rstrip("/")
    url = f"{base}{RSSHUB_NEW_WECHAT}/{requests.utils.quote(name)}"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  FAIL {mpID_key} ({name}): {type(e).__name__}: {e}", file=sys.stderr)
        return None
    mpID = _extract_mpid_from_html(resp.text)
    if not mpID:
        print(f"  FAIL {mpID_key} ({name}): no mpID parsed from response", file=sys.stderr)
        return None
    return mpID


def run(
    session: requests.Session,
    rsshub_base: str,
    output_path: Path,
    names: Iterable[tuple[str, str]] = NAMES,
) -> int:
    """Resolve names → mpIDs and write JSON. Returns exit code."""
    if not rsshub_base or not rsshub_base.strip():
        print("ERROR: RSSHUB_BASE env not set", file=sys.stderr)
        return 2

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    failures: list[str] = []

    for mpID_key, name in names:
        print(f"Probing {mpID_key} ({name})...", file=sys.stderr)
        mpID = _discover_one(session, rsshub_base, mpID_key, name)
        if mpID:
            rows.append({
                "name": name,
                "mpID_key": mpID_key,
                "site_id": SITE_ID_BY_KEY[mpID_key],
                "mpID": mpID,
                "fetched_at": fetched_at,
            })
        else:
            failures.append(mpID_key)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {len(rows)}/{len(NAMES)} entries to {output_path}", file=sys.stderr)
    if failures:
        print(f"FAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    rsshub_base = os.environ.get("RSSHUB_BASE", "")
    session = requests.Session()
    session.headers.update({"User-Agent": "nuclear-intel-radar-mpID-discover/1.0"})
    return run(session, rsshub_base, OUTPUT_PATH)


if __name__ == "__main__":
    sys.exit(main())
```

### Step 6.4: Run test — verify it passes

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/test_discover_wechat_mpids.py -v
```

Expected: All 5 tests pass.

### Step 6.5: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add scripts/discover_wechat_mpids.py tests/test_discover_wechat_mpids.py
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 discover: mpID discovery CLI via RSSHub /newwechat"
```

---

## Task 7: SCF deploy bundle (RSSHub on Tencent Serverless)

**Files:**
- Create: `scripts/deploy_rsshub_scf/serverless.yml`
- Create: `scripts/deploy_rsshub_scf/package.json`
- Create: `scripts/deploy_rsshub_scf/deploy.sh`

This bundle is based on the RSSHub official scf-template
(https://github.com/rsscloud/RSSHub/tree/master/scf). It is documentation +
scripts only; no test (deploy is a manual maintainer action).

### Step 7.1: `scripts/deploy_rsshub_scf/serverless.yml`

```yaml
# Tencent SCF config for RSSHub.
# Maintainer runs: ./deploy.sh
# Reference: https://github.com/RSSHub/RSSHub/tree/master/scf

service:
  name: rsshub-nuclear-intel

provider:
  name: tencent
  region: ap-guangzhou       # Guangzhou; nearest to WeChat origin
  runtime: Nodejs12.16
  credentials: ~/credentials  # maintainer must create this file

functions:
  rsshub:
    handler: serverless.handler
    memorySize: 256
    timeout: 30
    environment:
      TZ: Asia/Shanghai
    events:
      - apigw:
          name: rsshub
          parameters:
            protocols:
              - https
            serviceName: scf
            description: RSSHub for nuclear-intel-radar
            environment: release
            endpoints:
              - path: /wechat/{mpID}
                apiName: rsshub-wechat
                serviceTimeout: 30
                function:
                  isIntegratedResponse: TRUE
              - path: /newwechat/{name}
                apiName: rsshub-newwechat
                serviceTimeout: 30
                function:
                  isIntegratedResponse: TRUE
              - path: /
                apiName: rsshub-root
                serviceTimeout: 30
                function:
                  isIntegratedResponse: TRUE
```

### Step 7.2: `scripts/deploy_rsshub_scf/package.json`

```json
{
  "name": "rsshub-nuclear-intel-scf",
  "version": "1.0.0",
  "description": "RSSHub deployed on Tencent SCF for nuclear-intel-radar WeChat 公众号 bridge",
  "scripts": {
    "deploy": "sls deploy"
  },
  "dependencies": {},
  "devDependencies": {
    "serverless": "^3.0.0",
    "serverless-tencent-scf": "^1.0.0"
  },
  "private": true
}
```

### Step 7.3: `scripts/deploy_rsshub_scf/deploy.sh`

```bash
#!/usr/bin/env bash
# One-shot deploy of RSSHub to Tencent SCF.
# Maintainer runs this once after cloning the repo and setting up
# ~/credentials (serverless framework auth).

set -euo pipefail

cd "$(dirname "$0")"

echo "Installing serverless framework + plugins..."
npm install

echo "Deploying RSSHub to Tencent SCF (region: ap-guangzhou)..."
npx sls deploy

echo ""
echo "Deploy complete. Copy the API Gateway URL from the output above."
echo "Set it as the GitHub Actions secret: RSSHUB_BASE"
echo ""
echo "Next step:"
echo "  RSSHUB_BASE=<URL> python ../../scripts/discover_wechat_mpids.py"
echo "  git add ../../data/wechat_mpids.json"
echo "  git commit -m 'chore: populate wechat mpID cache'"
```

Make executable:

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
# On Windows / Git Bash: use bash to chmod
chmod +x scripts/deploy_rsshub_scf/deploy.sh 2>/dev/null || true
```

### Step 7.4: Add a README in `scripts/deploy_rsshub_scf/`

`scripts/deploy_rsshub_scf/README.md`:

```markdown
# RSSHub SCF Deploy Bundle

Deploys RSSHub to Tencent Serverless Cloud Function so the nuclear-intel-radar
GitHub Actions runner can fetch WeChat 公众号 articles from a domestic IP
surface.

## Why

- WeChat blocks overseas IPs. RSSHub must run on a mainland China IP surface.
- Tencent SCF is pay-per-call (~¥10/mo at 48 fetches/day × 9 sources × 30 days)
  and requires no persistent infra.

## Prerequisites (one-time, on maintainer's local machine)

1. Install Node.js 16+ and npm.
2. Install serverless framework:
   ```
   npm install -g serverless
   ```
3. Set up Tencent Cloud credentials:
   ```
   sls credentials create --provider tencent --key-id <YOUR_SECRET_ID> --secret-key <YOUR_SECRET_KEY> --overwrite
   ```
   (This creates `~/credentials` referenced by serverless.yml.)

## Deploy

```
cd scripts/deploy_rsshub_scf
./deploy.sh
```

The output includes an API Gateway URL like:
```
https://service-xxxx.gz.apigw.tencentcs.com/release/rsshub
```

Copy that URL → set it as the GitHub Actions secret `RSSHUB_BASE`
(Settings → Secrets and variables → Actions → New repository secret).

## Populate mpID cache

```
cd ../..
RSSHUB_BASE=https://service-xxxx.gz.apigw.tencentcs.com/release/rsshub \
    python scripts/discover_wechat_mpids.py
git add data/wechat_mpids.json
git commit -m "chore: populate wechat mpID cache"
```

The next scheduled workflow run picks up the 9 new sources automatically.

## Re-deploy (when RSSHub version updates)

```
cd scripts/deploy_rsshub_scf
npx sls deploy
```

## Tear down

```
cd scripts/deploy_rsshub_scf
npx sls remove
```

## Reference

- RSSHub official scf-template: https://github.com/RSSHub/RSSHub/tree/master/scf
- Serverless Tencent plugin: https://github.com/serverless-components/tencent-scf
```

### Step 7.5: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add scripts/deploy_rsshub_scf/
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 deploy: Tencent SCF bundle for RSSHub"
```

---

## Task 8: Update CLAUDE.md and README.md

**Files:**
- Modify: `C:\Users\Myfelix\.claude\CLAUDE.md` (this is the user's GLOBAL claude, NOT the project — DO NOT modify)
- Modify: `C:\Users\Myfelix\RR\nuclear-intel-radar\CLAUDE.md`
- Modify: `C:\Users\Myfelix\RR\nuclear-intel-radar\README.md`

**NOTE**: The user's private global CLAUDE.md at `C:\Users\Myfelix\.claude\CLAUDE.md` is OUT OF SCOPE for this plan. Only the project's own CLAUDE.md is modified.

### Step 8.1: Modify project CLAUDE.md

In `C:\Users\Myfelix\RR\nuclear-intel-radar\CLAUDE.md`, find the line:

```
- WeChat public accounts have no public API and are out of scope for MVP.
```

Replace with:

```
- WeChat 公众号 (公众号) require an RSSHub bridge (see P3 design
  `docs/superpowers/specs/2026-07-18-p3-wechat-rsshub-design.md`). The
  bridge is a domestic RSSHub instance (Tencent SCF recommended); deploy
  via `scripts/deploy_rsshub_scf/deploy.sh`. The 9 entries fall through
  to silent-zero if `RSSHUB_BASE` secret or `data/wechat_mpids.json`
  cache is missing, so the pipeline never crashes on bridge absence.
```

### Step 8.2: Modify project README.md — add WeChat section

Read `README.md` first to find the right insertion point (after "Adding a new source" or similar maintenance section).

Append a new section at the end:

````markdown
## Adding WeChat 公众号

The 9 Chinese 公众号 sources (中国核电网 / 中核集团 / etc.) are routed through
an RSSHub bridge hosted on Tencent Serverless Cloud Function. This avoids
WeChat's overseas-IP block and the lack of a public WeChat API.

Setup (one-time, maintainer):

1. **Deploy RSSHub to SCF** — see `scripts/deploy_rsshub_scf/README.md`.
   Outputs an API Gateway URL.
2. **Set the GitHub Actions secret `RSSHUB_BASE`** to that URL.
3. **Run mpID discovery** locally:
   ```
   RSSHUB_BASE=<URL> python scripts/discover_wechat_mpids.py
   git add data/wechat_mpids.json
   git commit -m "chore: populate wechat mpID cache"
   ```
4. **Next workflow run** picks up all 9 entries automatically.

When an mpID goes stale (a single entry repeatedly shows `ok=False` in
`data/source-status.json`):

```
RSSHUB_BASE=<URL> python scripts/discover_wechat_mpids.py
# edit data/wechat_mpids.json to keep only the refreshed row, OR re-run for all 9
git add data/wechat_mpids.json && git commit -m "chore: refresh wechat mpID cache"
```

If `RSSHUB_BASE` secret is unset or mpID cache is missing, the 9 wechat
entries produce silent-zero (no items, no crash). The wrapper records a
warning in `source-status.json` so maintainers can see the bridge state.
````

### Step 8.3: Commit

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git add CLAUDE.md README.md
git -c user.name="Claude" -c user.email="claude@anthropic.com" commit -m "P3 docs: remove wechat exclusion; add SCF setup instructions"
```

---

## Task 9: Full validation pass

### Step 9.1: Run full test suite

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -m pytest tests/ -v --tb=short 2>&1 | tail -60
```

Expected: All tests pass (existing ~70 + new ~30 = ~100). Pre-existing reddit failure is expected and acceptable.

### Step 9.2: Run pipeline smoke test (no real fetch — verify silent-zero path)

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
unset RSSHUB_BASE  # ensure bridge is "missing"
python scripts/update_news.py --output-dir data --window-hours 72 --archive-days 21 2>&1 | tail -20
```

Expected: Pipeline runs to completion. `data/source-status.json` shows 9 wechat entries with `ok=True, warning=..., items=0` (silent-zero). All other sources behave as before.

### Step 9.3: Verify source-status.json shape for wechat entries

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
python -c "
import json
data = json.load(open('data/source-status.json'))
wechat = [s for s in data if s.get('site_id', '').startswith('wechat_')]
print(f'wechat entries in source-status: {len(wechat)}')
for s in wechat:
    print(f\"  {s['site_id']}: ok={s.get('ok')}, warning={s.get('warning')!r}, error={s.get('error')!r}\")
"
```

Expected: 9 wechat entries all show `ok=True`, `warning=<non-empty string>`, `error=None`.

### Step 9.4: Commit (no code change — only a sanity tag if you want)

Skip if no changes from Tasks 1-8. If you tweaked something during validation:

```bash
cd C:/Users/Myfelix/RR/nuclear-intel-radar
git status  # check what's dirty
# if anything: git add <those files> && git commit -m "P3: validation tweaks"
```

---

## Task 10: Update memory

### Step 10.1: Update project memory

Edit `C:\Users\Myfelix\.claude\projects\C--Users-Myfelix-RR\memory\nuclear-intel-radar-project.md`:

- Add to "Production 状态" table: row "7-18 P3 后" with sources=33 (+9 wechat_xxx), OK rate showing 9 silent-zero
- Update "如何运行" section to mention SCF deploy + mpID discovery
- Add a new entry under "✅ 已完成" list: P3 wechat RSSHub bridge
- Update "🚧 仍待办": remove P3 (now done)

### Step 10.2: Update MEMORY.md index

Edit `C:\Users\Myfelix\.claude\projects\C--Users-Myfelix-RR\memory\MEMORY.md`:

Update the one-liner for `nuclear-intel-radar-project.md` to reflect P3 completion + 33 sources + RSSHub bridge.

### Step 10.3: No git commit (memory lives outside project repo)

Memory files are outside the project; no commit needed.

---

## Self-Review

After writing the complete plan, check:

**1. Spec coverage:**

| Spec requirement | Implemented in task |
|---|---|
| C1 `discover_wechat_mpids.py` | Task 6 |
| C2 `deploy_rsshub_scf/` bundle | Task 7 |
| C3 `data/wechat_mpids.json` cache | Task 6 (written) + Tasks 2/4 (read) |
| C4 9 `NUCLEAR_RSS_FEEDS` entries | Task 1 |
| C5 `_resolve_wechat_xml_url`, `_load_wechat_mpids`, `_fetch_wechat_rss` | Task 2 |
| C5 dispatch in `fetch_single_rss_feed` | Task 3 |
| C6 workflow env injection | Task 5 |
| C7 tier mapping | Task 1 |
| C8 CLAUDE.md change | Task 8 |
| C9 README.md change | Task 8 |
| 12 tests across 4 modules | Tasks 1 (3 test files partial), 2, 4, 6 |
| Silent-zero contract | Tasks 2, 4 |
| Per-entry hard-fail contract | Task 4 |
| Memory update | Task 10 |

**2. Placeholder scan:** Search plan for "TBD", "TODO", "implement later" — none. All steps contain concrete code.

**3. Type consistency:**
- `WECHAT_ACCOUNTS: tuple[dict[str, str], ...]` — defined Task 1 Step 1.3, used Task 1 Step 1.1 test (imports it)
- `_resolve_wechat_xml_url(site_id, mpids_map, rsshub_base) -> str | None` — defined Task 2 Step 2.3, used in Task 2 Step 2.3 itself and Task 3 dispatch
- `_load_wechat_mpids(path) -> dict[str, str] | None` — defined Task 2 Step 2.3, used Task 2 Step 2.3 itself and Task 6 test via `_extract_mpid_from_html` (different function — careful)
- `_fetch_wechat_rss(session, feed_def, now) -> list[RawItem]` — defined Task 2 Step 2.3, used Task 3 dispatch + Task 4 tests
- `WECHAT_MPIDS_PATH: Path` — defined Task 1, used Task 2/4 tests via monkeypatch
- mpID cache schema `{name, mpID, site_id, fetched_at}` — written Task 6, read Task 2 `_load_wechat_mpids`

**Consistency check**: All function signatures match across tasks. Tests reference functions that are defined in earlier tasks. ✅

**4. Ambiguity check:** Plan is concrete enough for a zero-context engineer.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-18-p3-wechat-rsshub.md`.

10 tasks, ~30 new tests, 9 new sources, deploy bundle + discover script + workflow env + docs. Frequent commits per task.