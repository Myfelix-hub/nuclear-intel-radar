# P2 — IAEA News RSS 接入设计

**日期：** 2026-07-16
**状态：** Approved (设计阶段)
**关联：** Memory `nuclear-intel-radar-project.md` 后续路线第 4 项

## 背景

`SOURCE_TIER_BY_SITE`（`scripts/nuclear_keywords.py:79-111`）已声明 9 个未实现的官方 / 监管 tier 信源：
- `iaea_news`（official）
- `oecd_nea`（official）
- `doe_ne`（official）
- `iter_org`（official）
- `us_nrc`（regulator）
- `asn_fr`（regulator）
- `rosatom`（industry）
- `cnnc_news`（industry）
- `edf_nuclear`（industry）

但 `update_news.py` 里**一个 fetcher 都没写**。原 memory 把这归因为"被 Cloudflare / GFW 阻断"，**未实测**。

## 实测结果（2026-07-16 本地探测）

| 信源 | 探测 RSS URL | 状态 |
|------|--------------|------|
| IAEA News | `https://www.iaea.org/feeds/news` | **200 OK** — RSS 完整，含 Press Release / News Story / Statement |
| OECD-NEA | 多 URL（rss/feed/news.rss/news/feed） | 000 timeout（GFW 阻断 / 真无 RSS） |
| DOE-NE | 多 URL | 000 timeout |
| ITER | 多 URL | 404（路径不存在） |
| Rosatom | 多 URL | 404 |
| EDF | 多 URL | 404 |
| CNNC | 多 URL | 412 Precondition Failed |
| NRC | 多 URL | 403 Cloudflare 阻断 |
| ASN | `french-nuclear-safety.fr/rss` → `asnr.fr` | 站已重构，RSS 不存在 |

**关键发现**：memory 的 "Cloudflare / GFW 阻断" 假设**只对 NRC / OECD-NEA / DOE-NE 部分成立**，对其他 5 个是错的（其实是 RSS 路径不存在或站死了）。**IAEA 完全可用**，立即可接入。

## 范围（重新定义 P2）

**本轮 P2 = 只 IAEA 闭环**。理由：
1. 8 个源只有 IAEA 立即可用（200 + RSS 完整）
2. 其他 7 个需要后续 P2.x 单独处理（探测真实 RSS URL / 适配 Cloudflare / 处理站重构）
3. IAEA 一手源价值最高，先闭环验证 fetcher 流程

**后续 P2.x 单独会话处理**：
- P2.1: NRC（GitHub Actions 境外 runner 验证可达性）
- P2.2: OECD-NEA / DOE-NE（GFW 阻断，需探测镜像或放弃）
- P2.3: ITER / Rosatom / EDF（探测首页找真实 RSS URL）
- P2.4: ASN / CNNC（站死，放弃）

## 设计

### 改动

**单文件 1 行配置**：`scripts/update_news.py` 的 `NUCLEAR_RSS_FEEDS` 元组追加：

```python
{"site_id": "iaea_news", "site_name": "IAEA News",
 "xml_url": "https://www.iaea.org/feeds/news",
 "html_url": "https://www.iaea.org/newscenter"},
```

### 复用现有组件

- `fetch_single_rss_feed`（line 434）— 已通用，只需 `site_id/site_name/xml_url/html_url`
- `fetch_rss_sources`（line 505）— 数据驱动 wrapper，遍历 `NUCLEAR_RSS_FEEDS`
- `SOURCE_TIER_BY_SITE`（nuclear_keywords.py:79）— 已含 `iaea_news → "official"`，tier 自动生效
- `collect_all`（line 818）— 已调用 `fetch_rss_sources`，新条目自动覆盖

### 数据流

```
collect_all()
  └─ fetch_rss_sources()                # 现有
       └─ for feed in NUCLEAR_RSS_FEEDS:    # IAEA 在此
            fetch_single_rss_feed(feed) → RawItem list
                                          ↓
                add_nuclear_relevance_fields() → 加 score / is_related
                                          ↓
                add_source_tier_fields()    → 加 tier=official
                                          ↓
            all_items (进入 latest-24h.json)
```

### 错误处理

`fetch_single_rss_feed`（line 442-446）已 try/except 包住 `session.get(xml_url)`：
- 失败返回空 items
- `fetch_rss_sources` 记 `ok=False, error=str(e)[:200]`
- 不影响其他 RSS 源

**降级策略**：无。失败只记录，不重试不降级（用户选择，保持 fetcher 简洁）。

### 测试

1. **本地**：`python scripts/update_news.py --output-dir data/test-run --window-hours 72`
   - 验证 `source-status.json` 含 `iaea_news` 且 `item_count > 0`
   - 验证 `latest-24h.json` 含 IAEA 条目且 `nuclear_is_related=true`

2. **GitHub Actions**：push 后查看
   - https://github.com/Myfelix-hub/nuclear-intel-radar/actions 最新 run success
   - https://myfelix-hub.github.io/nuclear-intel-radar/data/source-status.json 含 iaea_news

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| IAEA 站结构变化（RSS 路径失效） | fetch_rss_sources 失败记录，未来 1 行修复 |
| IAEA 新闻核能相关性低（如 Rainbow Trout） | `nuclear_keyword_score` 会过滤低分条目，nuclear_is_related=false 仍可能保留（按现有策略） |
| 24h 窗口过滤掉早期 IAEA | RSS_MAX_AGE_DAYS=14d 默认值，不会丢 |
| RSS XML 解析失败 | fetchparser + parse_feed_entries_via_xml 双 fallback（line 449-456） |

## 成功标准

- [ ] `NUCLEAR_RSS_FEEDS` 追加 IAEA 1 条
- [ ] 本地 `data/test-run/source-status.json` 含 `iaea_news` 且 item_count > 0
- [ ] 本地 `data/test-run/latest-24h.json` 至少 1 条 IAEA 条目
- [ ] GitHub Actions run success
- [ ] 线上 `source-status.json` 含 `iaea_news` 真实条目
- [ ] 改动 < 10 行（仅配置 + commit）

## 不做的事

- 不写新 fetcher（复用 fetch_single_rss_feed）
- 不新加 NUCLEAR_OFFICIAL_FEEDS 元组（与 NUCLEAR_RSS_FEEDS 重复）
- 不写 Jina / Wayback Machine 降级（用户选择保持简洁）
- 不处理其他 7 个未实现源（P2.x 单独会话）
- 不改 SOURCE_TIER_BY_SITE（已含 iaea_news）

## 后续

- 实施完成后 invoke `writing-plans` skill 写实施计划
- P2 闭环后进入 P3（stories-merged / daily-brief 生成逻辑）