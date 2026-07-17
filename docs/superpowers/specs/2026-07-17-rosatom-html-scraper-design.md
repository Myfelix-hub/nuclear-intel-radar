# P1.2 — Rosatom HTML Scraper 设计

**日期：** 2026-07-17
**状态：** Approved（设计阶段）
**关联：** Memory `nuclear-intel-radar-project.md` 后续路线第 2 项
**前置：** silent zero fix（commit `950f9bd`，P1）— selectors 不命中时给运维可见信号

## 背景

`SOURCE_TIER_BY_SITE`（`scripts/nuclear_keywords.py`）已声明 `rosatom: industry`，但 `update_news.py` **未实现 fetcher**。

**Rosatom 探测结果**（2026-07-17 P2.3）：
- 主页 `https://en.rosatom.ru/` 无 RSS 引用
- 常见 RSS 路径全 404：`/rss` / `/feed` / `/rss.xml` / `/news/rss`
- **结论**：Rosatom 没 RSS，必须走 HTML scraper 路径

`nucleartownhall`（已实现）走 BeautifulSoup 直接抓取范式，但那是"全页 a tag"抓链接堆，**不适合企业站 news listing**（结构化容器：每个 article 容器内含 title/link/time）。

## 范围

**本轮 = Rosatom 闭环 + 通用 news listing scraper 范式**。

理由：
1. Rosatom 是行业 tier，一手源价值高
2. 通用范式可复用于未来其他企业站（OKLO / TerraPower / Kairos 等）
3. silent zero fix 已就位，调试成本接近 0

## 设计

### 改动（4 个部分）

**1. 数据结构**：`scripts/update_news.py` 顶部新增 `WEB_SOURCES_NEWS_LISTING` 元组（与 `WEB_SOURCES_DIRECT` / `WEB_SOURCES_JINA` 并列）。

```python
WEB_SOURCES_NEWS_LISTING = (
    {
        "site_id": "rosatom",
        "site_name": "Rosatom",
        "start_urls": [
            "https://en.rosatom.ru/news/",
            "https://en.rosatom.ru/press-centre/news/",
            "https://en.rosatom.ru/",
        ],
        "container_selector": "article.node--type-news",   # Drupal 推测
        "title_selector": "h2.node__title a",
        "link_selector": "h2.node__title a[href]",
        "time_selector": "time[datetime]",
        "time_attr": "datetime",
        "max_items": 20,
        "via_jina": True,
    },
)
```

**2. 主入口函数**：`fetch_web_news_listing(session, src_def, now)`

逻辑：
```
for url in start_urls:
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200 or 'text/html' not in content-type:
            continue
        items = _parse_news_listing_html(resp.text, src_def, now)
        if items:
            return items   # 成功就停
    except Exception:
        continue

if via_jina and direct_all_hard_fail:
    try: return _parse_news_listing_jina(session, src_def, now)
    except: raise RuntimeError("all start_urls + Jina failed — ...")

if direct_all_200_but_zero_items:
    return []   # silent zero → wrapper 记 warning

raise RuntimeError("no usable news listing found")
```

**3. 辅助函数**：
- `_parse_news_listing_html(html, src_def, now)` — BeautifulSoup 提取
- `_parse_news_listing_jina(session, src_def, now)` — Jina markdown → regex extract

**4. Wrapper 层**：`fetch_web_news_listing_sources(session, now)`
- 与 `fetch_web_direct_sources` / `fetch_web_jina_sources` 完全相同的 silent zero 模式
- 0 items → warning 字段填充

### 复用现有组件

- `BeautifulSoup`（已 import，line 26）
- `parse_date_any`（line 256）— 英文 ISO/RFC822 已支持
- `maybe_fix_mojibake`（line 219）— 英文不需要，但保留无害
- `normalize_url`（line 202）
- `compact_title`（line 244）
- `nuclear_keyword_score`（line 375）
- `RawItem` dataclass（line 164）
- `collect_all`（line 974）— 加一行调用 `fetch_web_news_listing_sources`

### 数据流

```
collect_all()
  └─ fetch_web_news_listing_sources()       # 新 wrapper（silent zero 内建）
      └─ fetch_web_news_listing(src_def)     # 新主入口
          ├─ for url in start_urls:
          │     session.get(url)
          │     _parse_news_listing_html(BeautifulSoup)
          └─ if via_jina and all fail:
                _parse_news_listing_jina(Jina markdown + regex)
                                ↓
                RawItem list → items.extend()
                                ↓
                statuses 记录（ok / warning / error）
```

### 错误处理（与 silent zero fix 对齐）

| 场景 | fetcher 行为 | wrapper status |
|---|---|---|
| start_urls 中至少 1 个有 items | return items | ok=true, item_count>0 |
| start_urls 都 200 但 0 items | return [] | **silent zero warning** |
| start_urls 都 4xx/5xx/network err + via_jina=False | raise RuntimeError | ok=false, error="all start_urls failed — ..." |
| start_urls 都 fail + via_jina=True + Jina 成功 | return Jina items | ok=true |
| start_urls 都 fail + via_jina=True + Jina 0 items | return [] | silent zero warning |
| start_urls 都 fail + via_jina=True + Jina 也 fail | raise RuntimeError | ok=false, error="all start_urls + Jina failed" |

### Selectors 迭代策略

**en.rosatom.ru 是 Drupal-based 站**（俄罗斯政府/国企常见），Selectors 是推测：
- `article.node--type-news` — Drupal news node 容器
- `h2.node__title a` — Drupal title 元素
- `time[datetime]` — HTML5 time 元素

**迭代流程**：
1. 第一次 commit 用推测 selectors → push → Actions 海外 runner 跑
2. 大概率 silent zero（selectors 错或页结构变了）
3. 看 `data/source-status.json` 的 warning + 直接 fetch en.rosatom.ru/news/ 的 HTML 调 selectors
4. 再 push → 直到有 items
5. 估计 1-2 次迭代收敛

**为什么接受迭代**：silent zero warning 现在可见，调试成本接近 0（一次 push 看 1 个字段）。不浪费本地 GFW 时间。

### 测试覆盖

`tests/test_fetch_web_news_listing.py`（7 个 case）：

1. **happy path**：mock HTML 含 article.node--type-news 节点 → 验证 items 字段正确提取
2. **first start_url fail, second success**：验证 fallback 链
3. **all start_urls 200 but 0 items**：验证 silent zero（return []）
4. **all start_urls fail, via_jina=False**：验证 raise RuntimeError
5. **all start_urls fail, via_jina=True, Jina success**：验证 Jina path
6. **all start_urls fail, via_jina=True, Jina fail**：验证 combined raise
7. **wrapper 层 silent zero**：`fetch_web_news_listing_sources` 验证 status 含 warning

测试用 `MagicMock(spec=requests.Session)` + `_build_html_resp(items_html)`，不依赖真网络。

## 成功标准

- [ ] `WEB_SOURCES_NEWS_LISTING` 追加 Rosatom 1 条
- [ ] `fetch_web_news_listing` + `_parse_news_listing_html` + `_parse_news_listing_jina` + `fetch_web_news_listing_sources` 4 个函数实现
- [ ] `collect_all` 调用 wrapper
- [ ] 7 个新测试全 pass，原有测试无破坏
- [ ] 海外 Actions runner 跑 pipeline 后 `data/source-status.json` 含 `rosatom`（本地 GFW 阻断严重，不作为验证手段）
- [ ] 第一次跑可能 silent zero，迭代 selectors 后产出 items > 0

## 不做的事

- 不写 Rosatom-specific fetcher（保持通用）
- 不写自定义 markdown parser（复用现有 Jina regex 范式）
- 不改 `fetch_web_direct`（保持单职责）
- 不改 `SOURCE_TIER_BY_SITE`（已含 `rosatom: industry`）
- 不写 RSS 探测（已确认 Rosatom 无 RSS）

## 后续

- 实施完成后 invoke `writing-plans` skill 写实施计划
- Rosatom 闭环后考虑：OKLO / TerraPower / Kairos（同样是企业站 news listing，复用本范式只改 src_def）