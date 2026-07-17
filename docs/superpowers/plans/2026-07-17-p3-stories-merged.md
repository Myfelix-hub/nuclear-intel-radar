# P3 stories-merged / daily-brief 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `data/stories-merged.json` 与 `data/daily-brief.json` 真正落地（不是 71B/75B 空壳），解锁 3 个测试文件的 import 失败，emit 两个 payload 到 main pipeline。

**Architecture:** 三函数 + 两 payload + main() wire-up。`merge_story_items` 在 `dedupe_items_by_title_url` 之后跑，先按 canonical url 精确归并，再按标题相似度 ≥ 0.86 跨组合并。`build_daily_brief_payload` 选 top 10 stories by composite score（`nuclear_score × source_tier_rank × (1 + log(duplicate_count))`）。

**Tech Stack:** Python 3.14, pytest, stdlib `xml.etree.ElementTree`, stdlib `difflib.SequenceMatcher` (已有)

## Global Constraints

- TDD discipline: failing test → implementation → passing test → commit
- 既有 13 个测试零 regression
- 三个目标测试文件 import 不能继续失败：`tests/test_story_merge.py`, `tests/test_utils.py`, `tests/test_source_overlap.py`
- 新增函数签名: `merge_story_items(items: list[dict], now: datetime, window_hours: int) -> tuple[list[dict], list[dict]]`
- 新增函数签名: `event_time(record: dict | None, now: datetime) -> datetime | None`
- 新增函数签名: `parse_opml_subscriptions(path: Path) -> list[dict[str, str]]` 返回 keys `["title","xml_url","html_url"]`
- 新增 schema：`story["story_id"]`, `story["title"]`, `story["representative_url"]`, `story["first_published_at"]`, `story["sources"]`, `story["items"]`, `story["duplicate_count"]`
- 新增 schema：top story extra fields `["nuclear_score","source_tier","score"]`
- daily-brief top 10 排序键: `(score desc, first_published_at desc)` 平局取新
- test 文件 retrofit: `aihot` → `nuclear_news`, `ai_score` → `nuclear_score`, `ai_is_related` → `nuclear_is_related`
- main() 必须 emit `data/stories-merged.json` + `data/daily-brief.json`,失败不阻塞其他输出文件

---

## Task 1: backfill `event_time` helper + activate 3 test files

**Files:**
- Modify: `scripts/update_news.py:31+` (insert helper near `parse_iso`/`iso`,line ~213)
- Modify: `tests/test_source_overlap.py` (already imports — verify collection now succeeds)
- Modify: `tests/test_utils.py` (already imports — verify collection now succeeds)

**Interfaces:**
- Consumes: `record: dict | None`, `now: datetime`
- Produces: `datetime | None` — `record.published_at` → `record.added_at` → `None`
- Consumed by: `scripts/evaluate_source_overlap.py:132,133,220`

- [ ] **Step 1: Run failing collections**

Run: `cd "C:/Users/Myfelix/RR/nuclear-intel-radar" && PYTHONPATH=scripts python -m pytest tests/test_source_overlap.py tests/test_utils.py tests/test_story_merge.py -v 2>&1 | tail -25`
Expected: 3 collection errors (`event_time` / `parse_opml_subscriptions` / `merge_story_items` not found)

- [ ] **Step 2: Implement `event_time`**

Location: in `scripts/update_news.py` after `parse_iso` (line ~213) and before `normalize_url`.

```python
def event_time(record: dict | None, now: datetime) -> datetime | None:
    """Extract the most relevant timestamp from an item record.
    Returns published_at if parseable, else added_at, else None.
    Used by evaluate_source_overlap for look-back logic.
    """
    if not isinstance(record, dict):
        return None
    for key in ("published_at", "added_at"):
        v = record.get(key)
        if not v:
            continue
        if isinstance(v, str):
            dt = parse_iso(v)
            if dt is not None:
                return dt
        elif isinstance(v, datetime):
            return v
    return None
```

- [ ] **Step 3: Re-run collection**

Run: `PYTHONPATH=scripts python -m pytest tests/test_source_overlap.py 2>&1 | tail -10`
Expected: collection no longer errors on `event_time` import; remaining import errors for `classify_overlap` etc. mean evaluation still has gaps but **the import works**.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/Myfelix/RR/nuclear-intel-radar"
git add scripts/update_news.py
git commit -m "P3: backfill event_time helper (used by evaluate_source_overlap)"
```

---

## Task 2: implement `merge_story_items` + retrofit `test_story_merge.py` (TDD)

**Files:**
- Modify: `scripts/update_news.py` (insert after `event_time`)
- Modify: `tests/test_story_merge.py` (retrofit ai_* → nuclear_*)

**Interfaces:**
- `merge_story_items(items: list[dict], now: datetime, window_hours: int) -> tuple[list[dict], list[dict]]`
- Item shape that must be accepted: `{site_id, site_name, source, title, url, published_at, nuclear_is_related: True, nuclear_score: float}` (plus whatever `add_source_tier_fields` adds, i.e. `source_tier`, `source_tier_rank`)

- [ ] **Step 1: Inspect the test (already read)**

The test file expects:
- `make_item(idx, *, title, url, hours_ago, site_id)` returns dict with `id, site_id, site_name, source, title, url, published_at, nuclear_is_related: True, nuclear_score: 0.9` then `add_source_tier_fields(item)` applied.
- 3 tests:
  1. `test_url_params_are_ignored_for_canonical_merge` — utm/rss params 去掉后两 URL identical → 1 story, dup_count=2, event reason=`canonical_url` similarity=1.0
  2. `test_similar_titles_within_window_merge` — slightly different titles → 1 story, dup_count=2, event reason=`title_similarity` similarity≥0.86
  3. `test_different_model_vendor_events_do_not_merge` — different words → 2 stories, events=[]

- [ ] **Step 2: Retrofit `tests/test_story_merge.py`**

Replace:
- `"aihot"` → `"nuclear_news"` in `site_id` default
- `"ai_is_related": True` → `"nuclear_is_related": True`
- `"ai_score": 0.9` → `"nuclear_score": 0.9`
- `site_id` parameter default value updated likewise

Title examples are AI-flavored ("OpenAI releases a Codex update"). They still serve as test data — leave them as-is. The merge function will operate on any title, so the AI vocabulary doesn't matter for behavior tests.

- [ ] **Step 3: Run test to verify 3 failures (RED)**

Run: `PYTHONPATH=scripts python -m pytest tests/test_story_merge.py -v 2>&1 | tail -20`
Expected: `ImportError: cannot import name 'merge_story_items'`

- [ ] **Step 4: Implement `merge_story_items`**

Location: after `event_time` block in `scripts/update_news.py`.

```python
import difflib  # at top of file

def _merge_title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def merge_story_items(items: list[dict], now: datetime, window_hours: int) -> tuple[list[dict], list[dict]]:
    """Merge raw items into stories by canonical URL then by title similarity.

    Returns (stories, events).
    - stories: each has title, representative_url, first_published_at, sources, items, duplicate_count
    - events: merge events with reason "canonical_url" or "title_similarity", similarity float
    """
    if not items:
        return [], []

    cutoff = now - timedelta(hours=window_hours)

    # Keep only items inside window that have a parseable published_at
    in_window: list[dict] = []
    for it in items:
        ts = event_time(it, now)
        if ts is None:
            continue
        if ts < cutoff:
            continue
        in_window.append(it)

    stories: list[dict] = []
    events: list[dict] = []

    # First pass: canonical_url exact groups
    canonical_groups: dict[str, list[dict]] = {}
    for it in in_window:
        key = normalize_url(str(it.get("url") or ""))
        canonical_groups.setdefault(key, []).append(it)

    # Second pass: across canonical groups, merge by title similarity >= 0.86
    for key, group in canonical_groups.items():
        # group is already one canonical story; cross-group merge below
        pass

    # Use union-find by canonical_url key + title similarity
    canonical_keys = list(canonical_groups.keys())
    parent: dict[str, str] = {k: k for k in canonical_keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    representative_title: dict[str, str] = {
        k: (canonical_groups[k][0].get("title") or "") for k in canonical_keys
    }

    for i, ki in enumerate(canonical_keys):
        for kj in canonical_keys[i + 1:]:
            sim = _merge_title_similarity(representative_title[ki], representative_title[kj])
            if sim >= 0.86:
                union(ki, kj)

    grouped: dict[str, list[dict]] = {}
    for k in canonical_keys:
        grouped.setdefault(find(k), []).extend(canonical_groups[k])

    # Build stories and events
    for root, group_items in grouped.items():
        dates: list[datetime] = []
        for it in group_items:
            ts = event_time(it, now)
            if ts is not None:
                dates.append(ts)
        first = min(dates) if dates else now
        rep = group_items[0]
        seen_site: list[str] = []
        for it in group_items:
            sid = it.get("site_id") or ""
            if sid and sid not in seen_site:
                seen_site.append(sid)
        story_id = "story-" + make_item_id(root, "story", representative_title[root], root)
        story = {
            "story_id": story_id,
            "title": rep.get("title") or "",
            "representative_url": rep.get("url") or "",
            "first_published_at": iso(first) or iso(now),
            "sources": seen_site,
            "items": group_items,
            "duplicate_count": len(group_items),
        }
        stories.append(story)

        # Emit merge events for this story when it represents >1 distinct canonical URLs
        canonical_in_story = {
            normalize_url(str(it.get("url") or "")) for it in group_items
        }
        if len(canonical_in_story) > 1:
            # Determine similarity reason vs URL exact reason
            sim = _merge_title_similarity(representative_title[root], representative_title[root])
            # If all canonical in this story share same URL → canonical_url event with 1.0
            events.append({
                "items": group_items,
                "reason": "canonical_url",
                "similarity": 1.0,
            })
        elif len(group_items) > 1 and len(canonical_keys) > 1:
            events.append({
                "items": group_items,
                "reason": "title_similarity",
                "similarity": 0.86,
            })

    # Sort stories newest first
    def _sort_key(s: dict):
        ts = parse_iso(str(s.get("first_published_at") or "")) or now
        return ts

    stories.sort(key=_sort_key, reverse=True)
    return stories, events
```

Note: The test asserts events[0]["similarity"] == 1.0 for canonical URL and `events[0]["similarity"] >= 0.86` for title similarity. To match the **existing test assertions exactly**, the events must be scoped per underlying merge pair, not per story. Easier: re-scope events as the union-find merges that produced cross-group merges.

- [ ] **Step 5: Refine event emission to match test contract**

Re-shape event emission to assert per-merge, not per-story. Replace the event-emission block above with:

```python
        # Emit per-canonical-URL merge events when a story spans >1 canonical URL
        seen_pairs: set[tuple[str, str]] = set()
        canonical_in_story = {
            normalize_url(str(it.get("url") or "")) for it in group_items
        }
        canonical_list = sorted(canonical_in_story)
        for i, ki in enumerate(canonical_list):
            for kj in canonical_list[i + 1:]:
                pair = (ki, kj) if ki < kj else (kj, ki)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if ki == kj:
                    events.append({
                        "items": [it for it in group_items if normalize_url(str(it.get("url") or "")) == ki],
                        "reason": "canonical_url",
                        "similarity": 1.0,
                    })
                else:
                    sim = _merge_title_similarity(representative_title.get(ki, ""), representative_title.get(kj, ""))
                    if sim >= 0.86:
                        events.append({
                            "items": [it for it in group_items if normalize_url(str(it.get("url") or "")) in (ki, kj)],
                            "reason": "title_similarity",
                            "similarity": sim,
                        })
```

Test contract assertion (from `test_similar_titles_within_window_merge`):
- `events[0]["similarity"] >= 0.86` — yes if same canonical URL → 0.86 only if different. Adjust: the test uses `https://example.com/a` and `https://example.org/b` — **different URLs, different domains → so two canonical URLs, similarity ≥ 0.86 triggers.** ✓

- [ ] **Step 6: Re-run tests**

Run: `PYTHONPATH=scripts python -m pytest tests/test_story_merge.py -v 2>&1 | tail -20`
Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add scripts/update_news.py tests/test_story_merge.py
git commit -m "P3: implement merge_story_items (canonical URL + title similarity)"
```

---

## Task 3: implement `parse_opml_subscriptions`

**Files:**
- Modify: `scripts/update_news.py` (insert near other feed utilities, after `make_item_id`)

**Interfaces:**
- `parse_opml_subscriptions(path: Path) -> list[dict[str, str]]`
- Each dict: `{"title": ..., "xml_url": ..., "html_url": ...}`
- Dedupe by `xml_url` (first wins)
- Skip entries without `xmlUrl`

- [ ] **Step 1: Run failing test**

Run: `PYTHONPATH=scripts python -m pytest tests/test_utils.py::UtilsTests::test_parse_opml_subscriptions -v 2>&1 | tail -10`
Expected: `ImportError: cannot import name 'parse_opml_subscriptions'`

- [ ] **Step 2: Implement `parse_opml_subscriptions`**

```python
def parse_opml_subscriptions(path: Path) -> list[dict[str, str]]:
    """Parse an OPML subscription file exported from a feed reader.

    Returns a list of {title, xml_url, html_url} dicts, deduplicated by xml_url.
    Silently returns [] if path is missing or malformed.
    """
    if not isinstance(path, Path):
        path = Path(path)
    if not path.exists():
        return []
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(path))
    except Exception:
        return []
    root = tree.getroot()
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for outline in root.iter("outline"):
        xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
        if not xml_url:
            continue
        if xml_url in seen:
            continue
        seen.add(xml_url)
        out.append({
            "title": (outline.get("title") or outline.get("text") or "").strip(),
            "xml_url": xml_url,
            "html_url": outline.get("htmlUrl") or outline.get("htmlurl") or "",
        })
    return out
```

- [ ] **Step 3: Re-run test**

Run: `PYTHONPATH=scripts python -m pytest tests/test_utils.py -v 2>&1 | tail -15`
Expected: all `UtilsTests` passing

- [ ] **Step 4: Run silent_zero + news_listing regression**

Run: `PYTHONPATH=scripts python -m pytest tests/test_silent_zero.py tests/test_fetch_web_news_listing.py -q 2>&1 | tail -10`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/update_news.py
git commit -m "P3: implement parse_opml_subscriptions (OPML import utility)"
```

---

## Task 4: build_stories_payload + build_daily_brief_payload + main wire-up

**Files:**
- Modify: `scripts/update_news.py` (add two new build_* functions, modify main() to emit two new files)
- Test: `tests/test_p3_stories.py` (new file)

**Interfaces:**
- `build_stories_payload(items, now, window_hours) -> dict` returns `{generated_at, window_hours, total_stories, stories, merge_events}`
- `build_daily_brief_payload(stories, now, window_hours) -> dict` returns `{generated_at, window_hours, total_items, items}`, where `items` is top 10 stories by composite score

- [ ] **Step 1: Write the new test file `tests/test_p3_stories.py`**

```python
"""Tests for build_stories_payload and build_daily_brief_payload."""
from datetime import datetime, timedelta, timezone

from scripts.update_news import (
    add_source_tier_fields,
    add_nuclear_relevance_fields,
    build_daily_brief_payload,
    build_stories_payload,
)

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def make_item(idx, *, title, url, site_id="nuclear_news", hours_ago=1, nuclear_score=0.9, tier_rank=2):
    base = {
        "id": f"item-{idx}",
        "site_id": site_id,
        "site_name": site_id.title(),
        "source": "Test",
        "title": title,
        "url": url,
        "published_at": (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z"),
        "nuclear_is_related": True,
        "nuclear_score": nuclear_score,
    }
    base = add_nuclear_relevance_fields(base)
    base = add_source_tier_fields(base)
    base["source_tier_rank"] = tier_rank
    return base


def test_build_stories_payload_wellformed():
    items = [
        make_item(1, title="IAEA approves safeguards in Ukraine", url="https://iaea.org/news/a"),
        make_item(2, title="NRC issues new reactor guidance", url="https://nrc.gov/news/b"),
    ]
    payload = build_stories_payload(items, NOW, 24)
    assert payload["window_hours"] == 24
    assert payload["total_stories"] == 2
    assert isinstance(payload["stories"], list)
    assert all("story_id" in s for s in payload["stories"])
    assert payload["generated_at"]


def test_build_daily_brief_top_10_orders_by_composite_score():
    items = [
        make_item(i, title=f"Story {i}", url=f"https://example.com/{i}",
                  nuclear_score=0.1 * (10 - i), tier_rank=2)
        for i in range(1, 13)
    ]
    stories, _ = __import__("scripts.update_news", fromlist=["merge_story_items"]).merge_story_items(items, NOW, 24)
    brief = build_daily_brief_payload(stories, NOW, 24)
    assert brief["total_items"] == 10
    scores = [it["score"] for it in brief["items"]]
    assert scores == sorted(scores, reverse=True)
    # All top 10 carry composite score fields
    for it in brief["items"]:
        assert "nuclear_score" in it
        assert "source_tier" in it
        assert "score" in it
```

- [ ] **Step 2: Run test to confirm RED**

Run: `PYTHONPATH=scripts python -m pytest tests/test_p3_stories.py -v 2>&1 | tail -15`
Expected: `ImportError: cannot import name 'build_stories_payload'`

- [ ] **Step 3: Implement `build_stories_payload`**

Location: after `build_slim_and_all` in `update_news.py`.

```python
def build_stories_payload(items: list[dict], now: datetime, window_hours: int) -> dict[str, Any]:
    stories, events = merge_story_items(items, now, window_hours)
    return {
        "generated_at": iso(now),
        "window_hours": window_hours,
        "total_stories": len(stories),
        "stories": stories,
        "merge_events": events,
    }
```

- [ ] **Step 4: Implement `build_daily_brief_payload`**

```python
import math  # at top with other stdlib

def _story_composite_score(story: dict) -> float:
    rep = story["items"][0] if story.get("items") else {}
    nuc = float(rep.get("nuclear_score") or 0.0)
    tier = int(rep.get("source_tier_rank") or 0)
    dup = int(story.get("duplicate_count") or 1)
    return nuc * (tier + 1) * (1.0 + math.log(max(dup, 1)))


def build_daily_brief_payload(stories: list[dict], now: datetime, window_hours: int, top_n: int = 10) -> dict[str, Any]:
    scored: list[dict] = []
    for s in stories:
        rep = s.get("items", [{}])[0] if s.get("items") else {}
        score = _story_composite_score(s)
        scored.append({
            "story_id": s.get("story_id"),
            "title": s.get("title", ""),
            "representative_url": s.get("representative_url", ""),
            "first_published_at": s.get("first_published_at"),
            "sources": s.get("sources", []),
            "duplicate_count": s.get("duplicate_count", 1),
            "nuclear_score": rep.get("nuclear_score", 0.0),
            "source_tier": rep.get("source_tier", "unknown"),
            "score": score,
        })
    scored.sort(key=lambda x: (-float(x["score"]), str(x.get("first_published_at") or "")), reverse=False)
    scored = scored[:max(0, top_n)]
    return {
        "generated_at": iso(now),
        "window_hours": window_hours,
        "total_items": len(scored),
        "items": scored,
    }
```

Sort key fix: `(-score, -first_published_at)` → use tuple `(score desc, first_published_at desc)`. Replace with:
```python
scored.sort(key=lambda x: (float(x["score"]), str(x.get("first_published_at") or "")), reverse=True)
```
Wait — reverse=True on a tuple sorts by first element desc. To get score desc + date desc:
```python
scored.sort(key=lambda x: (float(x["score"]), -(int(__import__('datetime').datetime.fromisoformat(x.get("first_published_at","1970-01-01T00:00:00+00:00").replace('Z','+00:00'))).timestamp()) if x.get("first_published_at") else 0)), reverse=True)
```
Simpler — sort twice:
```python
scored.sort(key=lambda x: str(x.get("first_published_at") or ""), reverse=True)
scored.sort(key=lambda x: float(x["score"]), reverse=True)
```
Stable sort: secondary sort by date desc, primary by score desc. ✓

- [ ] **Step 5: Re-run tests**

Run: `PYTHONPATH=scripts python -m pytest tests/test_p3_stories.py -v 2>&1 | tail -15`
Expected: `2 passed`

- [ ] **Step 6: Wire into main()**

Location: in `main()`, after `(out / "waytoagi-7d.json").write_text(...)`, before `save_archive`.

```python
    # Stories + daily brief
    stories_payload = build_stories_payload(
        payload.get("items", []), now, args.window_hours
    )
    (out / "stories-merged.json").write_text(
        json.dumps(stories_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    brief_payload = build_daily_brief_payload(
        stories_payload.get("stories", []), now, args.window_hours, top_n=10
    )
    (out / "daily-brief.json").write_text(
        json.dumps(brief_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

Add `stories_data_url` to slim payload so app.js picks the URL:
In `build_latest_payload`'s payload dict, add `"stories_data_url": "data/stories-merged.json"`. Or set it after the fact in main():
```python
    slim["stories_data_url"] = "data/stories-merged.json"
    (out / "latest-24h.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
```
(app.js line 2833 reads `payload.stories_data_url` — already uses state default `data/stories-merged.json`, so this is belt-and-braces.)

- [ ] **Step 7: Run the full regression**

Run: `PYTHONPATH=scripts python -m pytest tests/ --ignore=tests/test_reddit_partial_failure.py -q 2>&1 | tail -20`
Expected: 18 passed (was 13; +5 from new + retrofit

- [ ] **Step 8: Commit**

```bash
git add scripts/update_news.py tests/test_p3_stories.py
git commit -m "P3: build_stories_payload + build_daily_brief_payload + main wire-up"
```

---

## Task 5: live verification — push to Actions

**Files:** none (operations only)

- [ ] **Step 1: Push to origin**

```bash
cd "C:/Users/Myfelix/RR/nuclear-intel-radar"
git push origin master 2>&1 | tail -5
```
Expected: push success

- [ ] **Step 2: Wait for Actions run**

```bash
sleep 90
curl -s "https://api.github.com/repos/Myfelix-hub/nuclear-intel-radar/actions/runs?per_page=1" | python -c "..."
```
Expected: latest run status=`completed` conclusion=`success`

- [ ] **Step 3: Inspect emitted files**

```bash
curl -s "https://raw.githubusercontent.com/Myfelix-hub/nuclear-intel-radar/master/data/stories-merged.json" | python -c "import sys,json; d=json.load(sys.stdin); print('total_stories=', d.get('total_stories'))"
curl -s "https://raw.githubusercontent.com/Myfelix-hub/nuclear-intel-radar/master/data/daily-brief.json" | python -c "import sys,json; d=json.load(sys.stdin); print('total_items=', d.get('total_items'), 'first story=', d.get('items',[{}])[0].get('title'))"
```
Expected: `total_stories > 0` and `total_items > 0`, first story title non-empty

- [ ] **Step 4: Commit no-op + update memory**

If all data verified, no commit. Update `MEMORY.md` and `nuclear-intel-radar-project.md` to reflect "P3 stories-merged / daily-brief 完成".

---

## Verification (final)

- [ ] All 18+ tests pass under pytest
- [ ] `data/stories-merged.json` and `data/daily-brief.json` non-empty after Actions run
- [ ] No regression in silent_zero / news-listing tests
- [ ] Memory updated
