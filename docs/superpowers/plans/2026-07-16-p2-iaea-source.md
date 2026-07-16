# P2 IAEA News RSS 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 IAEA News RSS 加入 `NUCLEAR_RSS_FEEDS` 一行配置，让 pipeline 自动采集 IAEA 一手新闻。

**Architecture:** 复用现有数据驱动架构 `NUCLEAR_RSS_FEEDS` + `fetch_single_rss_feed`（已通用）+ `SOURCE_TIER_BY_SITE`（已含 `iaea_news → "official"`）。改动 1 行配置 + 1 个测试 + 1 次本地验证。

**Tech Stack:** Python 3.x / feedparser / requests / GitHub Actions cron

## Global Constraints

- 改动文件 ≤ 2 个：`scripts/update_news.py`（1 行配置）+ `tests/test_rss_feeds.py`（新建测试）
- 测试必须 TDD：先写失败测试 → 加 1 行 → 测试通过
- commit 粒度：1 行配置 1 个 commit，测试 1 个 commit（或合并为 1 个 commit）
- 不得修改 `nuclear_keywords.py`（`SOURCE_TIER_BY_SITE` 已含 `iaea_news`）
- 不得新增 fetcher（复用 `fetch_single_rss_feed`）
- 数据驱动：`NUCLEAR_RSS_FEEDS` 是单一配置源，新条目按现有 schema 写

---

### Task 1: 添加 IAEA News 到 NUCLEAR_RSS_FEEDS

**Files:**
- Modify: `scripts/update_news.py:54-64`（NUCLEAR_RSS_FEEDS 元组）
- Create: `tests/test_rss_feeds.py`

**Interfaces:**
- Consumes: 现有 `fetch_single_rss_feed(session, feed_def, now) -> list[RawItem]`（`scripts/update_news.py:434`）
- Consumes: 现有 `SOURCE_TIER_BY_SITE["iaea_news"] = "official"`（`scripts/nuclear_keywords.py:81`）
- Produces: `data/latest-24h.json` 含 site_id=`iaea_news` 条目，`data/source-status.json` 含 iaea_news 状态

- [ ] **Step 1: 写失败测试**

Create `tests/test_rss_feeds.py`：

```python
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


def test_all_feeds_have_required_keys():
    """Sanity: every feed must have site_id/site_name/xml_url/html_url."""
    required = {"site_id", "site_name", "xml_url", "html_url"}
    for feed in NUCLEAR_RSS_FEEDS:
        assert required.issubset(feed.keys()), f"Feed missing keys: {feed}"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
python -m pytest tests/test_rss_feeds.py -v
```

Expected: `test_iaea_news_in_rss_feeds` **FAIL** with `assert feed is not None, "iaea_news missing from NUCLEAR_RSS_FEEDS"`。其他两个 PASS（tier 已声明、所有 feed 都有 keys）。

- [ ] **Step 3: 加 IAEA 条目到 NUCLEAR_RSS_FEEDS**

在 `scripts/update_news.py` 的 `NUCLEAR_RSS_FEEDS` 元组（约 line 54-64）末尾追加：

```python
    {"site_id": "iaea_news",   "site_name": "IAEA News",       "xml_url": "https://www.iaea.org/feeds/news",          "html_url": "https://www.iaea.org/newscenter"},
```

完整最终列表（line 54-65）：

```python
NUCLEAR_RSS_FEEDS: tuple[dict[str, str], ...] = (
    {"site_id": "wnn",            "site_name": "World Nuclear News","xml_url": "https://www.world-nuclear-news.org/rss",                     "html_url": "https://www.world-nuclear-news.org"},
    {"site_id": "ans_newswire",   "site_name": "ANS Newswire",      "xml_url": "https://www.ans.org/news/feed/",                             "html_url": "https://www.ans.org/news"},
    {"site_id": "powermag",       "site_name": "POWER Magazine",    "xml_url": "https://www.powermag.com/feed/",                             "html_url": "https://www.powermag.com"},
    {"site_id": "neutronbytes",   "site_name": "Neutron Bytes",     "xml_url": "https://neutronbytes.com/feed/",                             "html_url": "https://neutronbytes.com"},
    {"site_id": "arxiv_nuclex",   "site_name": "arXiv nucl-ex",     "xml_url": "https://rss.arxiv.org/rss/nucl-ex",                          "html_url": "https://arxiv.org/list/nucl-ex/recent"},
    {"site_id": "arxiv_nuclth",   "site_name": "arXiv nucl-th",     "xml_url": "https://rss.arxiv.org/rss/nucl-th",                          "html_url": "https://arxiv.org/list/nucl-th/recent"},
    {"site_id": "arxiv_insdet",   "site_name": "arXiv ins-det",     "xml_url": "https://rss.arxiv.org/rss/physics.ins-det",                  "html_url": "https://arxiv.org/list/physics.ins-det/recent"},
    {"site_id": "eurofusion",     "site_name": "EUROfusion",        "xml_url": "https://www.euro-fusion.org/feed/",                          "html_url": "https://www.euro-fusion.org"},
    {"site_id": "iaea_news",      "site_name": "IAEA News",         "xml_url": "https://www.iaea.org/feeds/news",                            "html_url": "https://www.iaea.org/newscenter"},
)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
python -m pytest tests/test_rss_feeds.py -v
```

Expected: 3 个测试全部 PASS。

- [ ] **Step 5: 跑 pipeline 验证 IAEA 真实抓取**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
rm -rf data/test-run
mkdir -p data/test-run
python scripts/update_news.py --output-dir data/test-run --window-hours 72 --archive-days 21 2>&1 | tail -5
```

Expected output 末行含：`Output: N nuclear items → data/latest-24h.json` 和 `Output: N community updates → data/waytoagi-7d.json`。

- [ ] **Step 6: 验证 IAEA 数据进入 latest-24h 和 source-status**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
python -X utf8 -c "
import json
with open('data/test-run/source-status.json', encoding='utf-8') as f:
    s = json.load(f)
iaea = [x for x in s['sites'] if x['site_id'] == 'iaea_news']
print('iaea_news status:', iaea[0] if iaea else 'MISSING')
with open('data/test-run/latest-24h.json', encoding='utf-8') as f:
    d = json.load(f)
iaea_items = [i for i in d['items'] if i.get('site_id') == 'iaea_news']
print(f'iaea_news items in latest-24h: {len(iaea_items)}')
for it in iaea_items[:3]:
    print(f\"  - {it['title'][:75]}\")
"
```

Expected:
- `iaea_news status: {'site_id': 'iaea_news', 'site_name': 'IAEA News', 'ok': True, 'item_count': N>=1, ...}`
- `iaea_news items in latest-24h: N>=1`，含真新闻标题（如 "IAEA Director General Statement" / "IAEA Draws Safeguards Conclusions" / "Nuclear Science is Transforming Rainbow Trout Farming"）

- [ ] **Step 7: 清理 + commit**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
rm -rf data/test-run
git add scripts/update_news.py tests/test_rss_feeds.py
git commit -m "feat(pipeline): add IAEA News RSS to NUCLEAR_RSS_FEEDS

- NUCLEAR_RSS_FEEDS append iaea_news entry (https://www.iaea.org/feeds/news)
- Reuses fetch_single_rss_feed (already data-driven) + SOURCE_TIER_BY_SITE
  (iaea_news -> official already declared at nuclear_keywords.py:81)
- tests/test_rss_feeds.py: verify iaea_news registered with correct tier"
```

- [ ] **Step 8: push 触发 GitHub Actions**

```bash
cd "C:\Users\Myfelix\RR\nuclear-intel-radar"
git push origin master
```

Expected: push 成功，Actions run `in_progress`（3-5 分钟完成）。

- [ ] **Step 9: 验证线上 IAEA 数据**

```bash
sleep 90 && curl -s --max-time 15 "https://myfelix-hub.github.io/nuclear-intel-radar/data/source-status.json" | python -X utf8 -c "
import sys, json
s = json.load(sys.stdin)
iaea = [x for x in s['sites'] if x['site_id'] == 'iaea_news']
print('Live iaea_news:', iaea[0] if iaea else 'MISSING')
"
curl -s --max-time 15 "https://myfelix-hub.github.io/nuclear-intel-radar/data/latest-24h.json" | python -X utf8 -c "
import sys, json
d = json.load(sys.stdin)
iaea = [i for i in d['items'] if i.get('site_id') == 'iaea_news']
print(f'Live iaea_news items: {len(iaea)}')
for it in iaea[:3]:
    print(f\"  - {it['title'][:75]}\")
"
```

Expected:
- `Live iaea_news: {'site_id': 'iaea_news', ..., 'item_count': N>=1, 'ok': True}`
- `Live iaea_news items: N>=1` 列出真新闻标题

## Self-Review Checklist

- [x] Spec coverage: 全部 spec 成功标准都对应 task 步骤（1 行配置 / 本地验证 / Actions 验证）
- [x] No placeholders: 所有命令、代码、预期输出完整
- [x] Type consistency: 使用现有 `NUCLEAR_RSS_FEEDS` schema / `fetch_single_rss_feed` 签名 / `SOURCE_TIER_BY_SITE` 字段名
- [x] TDD: 3 个测试先失败再通过
- [x] Frequent commits: 1 个 commit（配置 + 测试同 commit，1 行改动）