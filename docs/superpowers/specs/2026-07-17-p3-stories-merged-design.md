# P3 — stories-merged / daily-brief 实现 设计

**日期：** 2026-07-17
**状态：** Approved
**关联：** Memory `nuclear-intel-radar-project.md` 后续路线第 4 项
**前置：** silent zero fix（commit `950f9bd`）、Rosatom 范式 + collect_all wiring（commit `9b7265f`）

## 背景

两个长期空壳:
- `data/stories-merged.json` 71 字节 — `{"generated_at":"","window_hours":72,"total_stories":0,"stories":[]}`
- `data/daily-brief.json` 75 字节 — `{"generated_at":"","window_hours":72,"total_items":0,"items":[]}`

`scripts/update_news.py:main()` 不 emit 这两个文件,只跑到 waytoagi-7d.json 就 return。
但 `assets/app.js` 已经把它们读进 state（line 2787, 2792）,line 2833 还要读 `payload.stories_data_url`。

3 个测试文件 import 失败（保持 fork-from-ai 残留语义,fields 没 retrofit）:
- `tests/test_story_merge.py` → `merge_story_items` 不存在
- `tests/test_utils.py` → `parse_opml_subscriptions` 不存在
- `tests/test_source_overlap.py` → 链入 `event_time` 不存在

## 范围

**本轮 = 让 stories-merged + daily-brief 真正落地 + 解锁 3 个测试文件 + emit 数据文件**。

不重做现有 dedupe（`dedupe_items_by_title_url` 已够强）。不写故事摘要（LLM 工作,超 MVP）。
不动 `assets/app.js`,因为前端 read interface 已对齐我们要 emit 的 schema。

## 设计

### 三个新函数（scripts/update_news.py）

**1. `event_time(record: dict | None, now: datetime) -> datetime | None`**
```python
def event_time(record, now):
    if not isinstance(record, dict): return None
    for key in ("published_at", "added_at"):
        v = record.get(key)
        if not v: continue
        dt = parse_iso(v) if isinstance(v, str) else v
        if dt: return dt
    return None
```
被 `scripts/evaluate_source_overlap.py` import,本轮解锁它。

**2. `merge_story_items(items, now, window_hours) -> tuple[list[dict], list[dict]]`**

输入是 raw items（含 `site_id` / `site_name` / `title` / `url` / `published_at`）。流程:
```
1. 过滤 window_hours 内 + 跳过 published_at 缺失
2. 按 canonical_url 精确 normalize 后分组（redirect 命中 → 同一个故事）
3. 跨组：标题相似度 >= 0.86 → 合并
4. 输出 (stories, events)
```

story schema:
```python
{
    "story_id": "story-<hash>",
    "title": "<代表标题>",
    "representative_url": "<representative.item.url>",
    "first_published_at": iso(min(dates)),
    "sources": [item.site_id list, unique, preserve order],
    "items": [原始 items],
    "duplicate_count": len(items),
}
```

events schema（保留测试 contract）:
```python
{
    "items": [item refs],
    "reason": "canonical_url" | "title_similarity",
    "similarity": float,  # canonical_url = 1.0, title_similarity = SequenceMatcher ratio
}
```

**3. `parse_opml_subscriptions(path) -> list[dict]`**

```python
{
    "title": outline.get("title") or outline.get("text"),
    "xml_url": outline.get("xmlUrl"),
    "html_url": outline.get("htmlUrl"),  # 可选
}
```

- dedupe by `xml_url`
- skip entries without `xmlUrl`
- return list[dict]

### 两个新 payload 构造 + emit

**4. `build_stories_payload(items, now, window_hours) -> dict`**

```python
{
    "generated_at": iso(now),
    "window_hours": window_hours,
    "total_stories": len(stories),
    "stories": stories,
    "merge_events": events,  # 兼容 events 字段
}
```

**5. `build_daily_brief_payload(stories, now, window_hours) -> dict`**

top 10 selection (用户决策):
```
score = nuclear_score × source_tier_rank × (1 + log(duplicate_count))
取 score 最高的 10 个 story
```

tier_rank: `SOURCE_TIER_RANK` 已存在 (regulator=4, official=3, industry=2, media=1, research=0)。
代表 score = 代表 item 的 `nuclear_score`。

```python
{
    "generated_at": iso(now),
    "window_hours": window_hours,
    "total_items": len(top),
    "items": top_story_dicts,
}
```

top story dict:
```python
{
    "story_id": s["story_id"],
    "title": s["title"],
    "representative_url": s["representative_url"],
    "first_published_at": s["first_published_at"],
    "sources": s["sources"],
    "duplicate_count": s["duplicate_count"],
    "nuclear_score": <代表 item 字段>,
    "source_tier": <代表 item 的 tier>,
    "score": <复合 score>,
}
```

**6. main() 调用 wire-up**

`update_news.py` main() 顺序:
```
build_latest_payload → slim/all
[waytoagi] (existing)
[NEW: merge_story_items over nuclear_deduped] → build_stories_payload → write stories-merged.json
[NEW: same stories list] → build_daily_brief_payload → write daily-brief.json
```

payload slim 也加 `stories_data_url`（app.js 已经在读）。

### Test 改造 — retrofit AI → nuclear

`tests/test_story_merge.py`:
- `make_item`: `ai_is_related` → `nuclear_is_related`, `ai_score` → `nuclear_score`, `aihot` → `nuclear_news`
- 测试本身（结构、assertions）保留

`tests/test_utils.py`: 无 AI 字段,只缺 `parse_opml_subscriptions`,测试保留。

`tests/test_source_overlap.py`: imports 没动,只是 module 级 `event_time` 解锁。

## 复用现有组件

- `parse_iso`, `iso`, `now`, `add_source_tier_fields`, `nuclear_relevance_score`, `nuclear_keyword_score`
- `SOURCE_TIER_RANK` 已有
- `add_nuclear_relevance_fields`（line 443）确保 item 有 `nuclear_score`
- `dedupe_items_by_title_url` 已经在 build_latest_payload 跑过 → `merge_story_items` 输入是其输出

## 数据流

```
collect_all → raw_items
  build_latest_payload → all_payload["items"] (nuclear_deduped)
    ↓
    merge_story_items(items, now, window_hours)
      ├─ canonical URL exact match → 合并
      └─ title_similarity ≥ 0.86 → 合并
        ↓
        build_stories_payload → write data/stories-merged.json
        ↓
        build_daily_brief_payload (Top 10 by composite score) → write data/daily-brief.json
```

## 错误处理

| 场景 | 行为 |
|---|---|
| 全 0 nuclear items | stories-merged 与 daily-brief 也空对象（与现有 stub 兼容） |
| nuclear_score 缺失 | 用 0.0 fallback（已经被核能 filter 过） |
| OPML 文件不存在 / 解析失败 | `parse_opml_subscriptions` 返回 `[]`,**不 raise**（maintainer 脚本容忍） |
| window_hours 内 0 items | stories 列表空, generated_at 写入,total_stories=0 |

## 测试覆盖

新建 + retrofit:

**`tests/test_story_merge.py`** — retrofit ai_* → nuclear_*,function 不变,5 个测试保持。

**`tests/test_utils.py`** — 已有 OPML 测试,补 `event_time` 测试案例（parse_iso 路径 / 缺失 published_at fallback / 不存在 key）。

**`tests/test_p3_stories.py`**（新）:
1. `test_merge_story_items_groups_by_canonical_url`: 2 个 item 同一 url 不同 utm 参数 → 1 story
2. `test_merge_story_items_merges_similar_titles_in_window`: 2 个相似标题 + 在 24h 内 → 1 story
3. `test_merge_story_items_filters_outside_window`: 一个 in 一个 out → 2 stories
4. `test_build_daily_brief_top_10_by_composite_score`: 构造 12 个 stories,assert top 10 ordering + composite score 字段
5. `test_main_writes_stories_merged_and_daily_brief`: mock collect_all → check 两个文件写入

## 成功标准

- [ ] `event_time`, `merge_story_items`, `parse_opml_subscriptions` 三个函数实现
- [ ] `build_stories_payload`, `build_daily_brief_payload` 实现
- [ ] main() emit `data/stories-merged.json` 和 `data/daily-brief.json`
- [ ] 5 个新/retrofit 测试通过
- [ ] 既有 13 测试无 regression
- [ ] 海外 Actions runner 跑后 `data/stories-merged.json` 含真实 stories,`data/daily-brief.json` 含 top 10

## 不做的事

- 不写 LLM story summary（超 MVP,留给未来 task）
- 不改 dedupe_items_by_title_url（保留,作为底层基线）
- 不改 app.js 的 stories_data_url,只 emit `data/stories-merged.json`
- 不重写 evaluate_source_overlap（maintainer 脚本本轮只需 event_time 能 import）
- 不发 OPML 到 main pipeline（OPML 只是 utilities,留着给 maintainer 仪表盘用）

## 后续

- 实施计划 docs/superpowers/plans/2026-07-17-p3-stories-merged.md
- 实施完成后跑回归 + push 到 Actions 验证产物
