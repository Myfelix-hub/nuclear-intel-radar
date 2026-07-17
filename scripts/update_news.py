#!/usr/bin/env python3
"""Aggregate updates from nuclear energy news sources and produce 24h snapshot data.

Adapted from ai-news-radar (https://github.com/LearnPrompt/ai-news-radar).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from nuclear_keywords import (
    NUCLEAR_CORE_KEYWORDS, NUCLEAR_TECH_KEYWORDS, NUCLEAR_NOISE_KEYWORDS,
    SOURCE_TIER_BY_SITE, SOURCE_TIER_RANK, SOURCE_TIER_IMPORTANCE,
    NUCLEAR_MIN_KEYWORD_SCORE, NUCLEAR_CORE_KW_WEIGHT, NUCLEAR_TECH_KW_WEIGHT,
    NUCLEAR_NOISE_KW_PENALTY, NUCLEAR_TITLE_BONUS,
)

try:
    import feedparser
except ModuleNotFoundError:
    feedparser = None

UTC = timezone.utc
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
SH_TZ = ZoneInfo("Asia/Shanghai")

# ═══════════════════════════════════════════════════════════════════
# Nuclear RSS feed definitions
# ═══════════════════════════════════════════════════════════════════

NUCLEAR_RSS_FEEDS: tuple[dict[str, Any], ...] = (
    # Verified working feeds (tested 2025-07-05)
    {"site_id": "wnn",            "site_name": "World Nuclear News","xml_url": "https://www.world-nuclear-news.org/rss",                     "html_url": "https://www.world-nuclear-news.org"},
    {"site_id": "ans_newswire",   "site_name": "ANS Newswire",      "xml_url": "https://www.ans.org/news/feed/",                             "html_url": "https://www.ans.org/news"},
    {"site_id": "powermag",       "site_name": "POWER Magazine",    "xml_url": "https://www.powermag.com/feed/",                             "html_url": "https://www.powermag.com"},
    {"site_id": "neutronbytes",   "site_name": "Neutron Bytes",     "xml_url": "https://neutronbytes.com/feed/",                             "html_url": "https://neutronbytes.com"},
    {"site_id": "arxiv_nuclex",   "site_name": "arXiv nucl-ex",     "xml_url": "https://rss.arxiv.org/rss/nucl-ex",                          "html_url": "https://arxiv.org/list/nucl-ex/recent"},
    {"site_id": "arxiv_nuclth",   "site_name": "arXiv nucl-th",     "xml_url": "https://rss.arxiv.org/rss/nucl-th",                          "html_url": "https://arxiv.org/list/nucl-th/recent"},
    {"site_id": "arxiv_insdet",   "site_name": "arXiv ins-det",     "xml_url": "https://rss.arxiv.org/rss/physics.ins-det",                  "html_url": "https://arxiv.org/list/physics.ins-det/recent"},
    {"site_id": "eurofusion",     "site_name": "EUROfusion",        "xml_url": "https://www.euro-fusion.org/feed/",                          "html_url": "https://www.euro-fusion.org"},
    {"site_id": "nucnet",         "site_name": "NucNet",            "xml_url": "https://www.nucnet.org/feed.rss",                           "html_url": "https://www.nucnet.org", "via_jina": True},
    {"site_id": "iaea_news",      "site_name": "IAEA News",         "xml_url": "https://www.iaea.org/feeds/news",                            "html_url": "https://www.iaea.org/newscenter"},
    {"site_id": "us_nrc",         "site_name": "US NRC News",       "xml_url": "https://www.nrc.gov/reading-rm/doc-collections/news/rss.xml", "html_url": "https://www.nrc.gov/reading-rm/doc-collections/news", "via_jina": True},
    # ITER — official fusion project. RSS path: /rss.xml (verified 2026-07-17).
    {"site_id": "iter_org",       "site_name": "ITER",              "xml_url": "https://www.iter.org/rss.xml", "html_url": "https://www.iter.org/newsline",
     "xml_url_candidates": [
         "https://www.iter.org/rss.xml",
         "https://www.iter.org/newsline",
         "https://www.iter.org/rss",
         "https://www.iter.org/news/rss",
         "https://www.iter.org/feed",
     ], "via_jina": True},
    # EDF — French nuclear operator. RSS path: /rss.xml (verified 2026-07-17).
    {"site_id": "edf_nuclear",    "site_name": "EDF",               "xml_url": "https://www.edf.fr/rss.xml", "html_url": "https://www.edf.fr",
     "xml_url_candidates": [
         "https://www.edf.fr/rss.xml",
         "https://www.edf.fr/rss",
         "https://www.edf.fr/feed",
     ], "via_jina": True},
    # DOE-NE — US Department of Energy, Office of Nuclear Energy. Whole-site RSS: /rss.xml (verified 2026-07-17).
    {"site_id": "doe_ne",         "site_name": "US DOE Nuclear Energy", "xml_url": "https://www.energy.gov/rss.xml", "html_url": "https://www.energy.gov/ne/office-nuclear-energy",
     "via_jina": True},
    # OECD-NEA — Nuclear Energy Agency. RSS path unknown; probe via candidates + Jina fallback.
    {"site_id": "oecd_nea",       "site_name": "OECD-NEA",          "xml_url": "https://www.oecd-nea.org/rss", "html_url": "https://www.oecd-nea.org",
     "xml_url_candidates": [
         "https://www.oecd-nea.org/rss",
         "https://www.oecd-nea.org/rss.xml",
         "https://www.oecd-nea.org/feed",
         "https://www.oecd-nea.org/feed.xml",
         "https://www.oecd-nea.org/news/rss",
         "https://www.oecd-nea.org/news/rss.xml",
         "https://www.oecd-nea.org/jcms/rss",
         "https://www.oecd-nea.org/press/rss",
         "https://www.oecd-nea.org/publications/rss",
     ], "via_jina": True},
)

RSS_MAX_AGE_DAYS = 14
RSS_MAX_ENTRIES_PER_FEED = 20

# ═══════════════════════════════════════════════════════════════════
# HN & Reddit configuration
# ═══════════════════════════════════════════════════════════════════

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ALGOLIA_QUERIES: tuple[str, ...] = (
    "nuclear reactor", "SMR nuclear", "nuclear fusion", "ITER tokamak",
    "uranium nuclear", "IAEA nuclear", "NRC nuclear", "nuclear power plant",
)
HN_ALGOLIA_HITS = 20
HN_ALGOLIA_MIN_POINTS = 1
HN_ALGOLIA_MIN_COMMENTS = 0
HN_ALGOLIA_QUERY_PAUSE = 0.15

REDDIT_MAX_ITEMS = 15

# ═══════════════════════════════════════════════════════════════════
# Web scraping sources (no RSS available)
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# Web scraping sources — two strategies:
#   1. Direct BeautifulSoup scraping (for sites with clean HTML)
#   2. Jina AI reader fallback (for JS-rendered or blocked sites)
# ═══════════════════════════════════════════════════════════════════

WEB_SOURCES_DIRECT: tuple[dict[str, Any], ...] = (
    {
        "site_id": "nucleartownhall",
        "site_name": "Nuclear Town Hall",
        "url": "https://nucleartownhall.com",
        "link_selector": "a[href^='http']",
        "time_selector": "time, .entry-date",
        "time_attr": None,
    },
)

WEB_SOURCES_JINA: tuple[dict[str, str], ...] = (
    {
        "site_id": "nei_magazine",
        "site_name": "Nuclear Eng. Int'l",
        "url": "https://www.neimagazine.com/news/",
    },
    {
        "site_id": "cgn_news",
        "site_name": "中广核",
        "url": "https://www.cgnpc.com.cn/cgn/c100944/jtyw_all.shtml",
    },
    {
        "site_id": "nuclear_net_cn",
        "site_name": "中国核网",
        "url": "http://www.nuclear.net.cn/portal.php?mod=list&catid=94",
    },
)

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

# ═══════════════════════════════════════════════════════════════════
# Data model
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RawItem:
    site_id: str
    site_name: str
    source: str
    title: str
    url: str
    published_at: datetime | None
    meta: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════
# Utility functions
# ═══════════════════════════════════════════════════════════════════


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def parse_iso(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        d = dtparser.isoparse(dt_str)
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        return d
    except Exception:
        return None


def normalize_url(raw_url: str) -> str:
    """Strip tracking params, fragments, lowercase scheme+netloc."""
    if not raw_url:
        return ""
    u = urlparse(raw_url.strip())
    if not u.scheme:
        u = urlparse("https://" + raw_url.strip())
    qsl = [(k, v) for k, v in parse_qsl(u.query) if k.lower() not in (
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "tracking", "_ga", "_gl",
    )]
    return urlunparse((
        u.scheme.lower(), u.netloc.lower(), u.path or "/",
        u.params, urlencode(qsl) if qsl else "", "",
    ))


def maybe_fix_mojibake(text: str) -> str:
    """Attempt to fix UTF-8 bytes misinterpreted as Latin-1."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def has_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
            return True
    return False


def is_mostly_english(text: str) -> bool:
    if not text:
        return True
    alpha = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return alpha >= len(text) * 0.7


def compact_title(text: str, limit: int = 96) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[:limit - 1] + "…"


def make_item_id(site_id: str, source: str, title: str, url: str) -> str:
    raw = f"{site_id}|{source}|{title}|{normalize_url(url)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def parse_date_any(value: Any, now: datetime) -> datetime | None:
    """Try to parse a date from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        d = value
        return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)
    if isinstance(value, (int, float)):
        if value > 1e12:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        if value > 0:
            return datetime.fromtimestamp(value, tz=UTC)
    text = str(value).strip()
    if not text:
        return None
    # Try Chinese relative time patterns
    zh_match = re.match(r"(\d+)\s*(天|小时|分钟|秒|周|月)前", text)
    if zh_match:
        n = int(zh_match.group(1))
        unit = zh_match.group(2)
        deltas = {"天": timedelta(days=n), "小时": timedelta(hours=n),
                    "分钟": timedelta(minutes=n), "秒": timedelta(seconds=n),
                    "周": timedelta(weeks=n), "月": timedelta(days=n * 30)}
        if unit in deltas:
            return now - deltas[unit]
    # Try ISO-like formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            d = datetime.strptime(text, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=UTC)
            return d.astimezone(UTC)
        except ValueError:
            continue
    # Fallback to dateutil
    try:
        d = dtparser.parse(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        return d.astimezone(UTC)
    except Exception:
        return None


def parse_feed_entries_via_xml(feed_xml: bytes) -> list[dict[str, Any]]:
    """Parse RSS/Atom feed via xml.etree (fallback when feedparser unavailable)."""
    entries: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(feed_xml.decode("utf-8", errors="replace"))
    except Exception:
        return entries

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.iter("item"):
        entry: dict[str, Any] = {}
        for tag in ("title", "link", "description", "pubDate", "dc:date"):
            el = item.find(tag)
            if el is not None and el.text:
                entry[tag] = el.text.strip()
        if not entry.get("link"):
            link_el = item.find("link")
            if link_el is not None:
                entry["link"] = link_el.text.strip() if link_el.text else link_el.get("href", "")
        entries.append(entry)
    for entry_el in root.iter("{http://www.w3.org/2005/Atom}entry"):
        entry: dict[str, Any] = {}
        title_el = entry_el.find("{http://www.w3.org/2005/Atom}title")
        if title_el is not None and title_el.text:
            entry["title"] = title_el.text.strip()
        for link_el in entry_el.findall("{http://www.w3.org/2005/Atom}link"):
            if link_el.get("rel") == "alternate" or link_el.get("type") == "text/html":
                entry["link"] = link_el.get("href", "")
                break
        if not entry.get("link"):
            link_el = entry_el.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                entry["link"] = link_el.get("href", "")
        updated = entry_el.find("{http://www.w3.org/2005/Atom}updated")
        if updated is not None and updated.text:
            entry["published"] = updated.text.strip()
        entries.append(entry)
    return entries


def redact_public_text(text: str) -> str:
    """Remove emails and common secret patterns."""
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[email]", text)
    text = re.sub(r"(sk-[a-zA-Z0-9]{20,})", "[key]", text)
    text = re.sub(r"(Bearer\s+)[a-zA-Z0-9._-]{20,}", r"\1[token]", text)
    return text


def create_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.8,
                     status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"})
    return s


# ═══════════════════════════════════════════════════════════════════
# Nuclear relevance scoring
# ═══════════════════════════════════════════════════════════════════


def contains_any_keyword(haystack: str, keywords: list[str]) -> bool:
    if not haystack:
        return False
    lower = haystack.lower()
    return any(kw.lower() in lower for kw in keywords)


def nuclear_keyword_score(title: str, text: str = "") -> float:
    """Score how nuclear-relevant a piece of content is. Returns 0.0 - 1.0+."""
    if not title and not text:
        return 0.0
    title_lower = (title or "").lower()
    text_lower = (text or "").lower()

    score = 0.0
    # Core keywords
    for kw in NUCLEAR_CORE_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score += NUCLEAR_CORE_KW_WEIGHT * NUCLEAR_TITLE_BONUS / 100
        elif kw_lower in text_lower:
            score += NUCLEAR_CORE_KW_WEIGHT / 100
    # Tech keywords
    for kw in NUCLEAR_TECH_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score += NUCLEAR_TECH_KW_WEIGHT * NUCLEAR_TITLE_BONUS / 100
        elif kw_lower in text_lower:
            score += NUCLEAR_TECH_KW_WEIGHT / 100
    # Noise penalty
    for kw in NUCLEAR_NOISE_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score -= NUCLEAR_NOISE_KW_PENALTY / 100
        elif kw_lower in text_lower:
            score -= NUCLEAR_NOISE_KW_PENALTY / 200

    return score


def nuclear_relevance_score(record: dict[str, Any]) -> float:
    """Combined relevance = keyword score × source tier weight. Returns 0-1."""
    title = str(record.get("title") or "")
    summary = str(record.get("summary") or "")
    kw_score = nuclear_keyword_score(title, summary)
    site_id = str(record.get("site_id") or "")
    tier = SOURCE_TIER_BY_SITE.get(site_id, "unknown")
    tier_weight = SOURCE_TIER_IMPORTANCE.get(tier, 0.3)
    raw = kw_score * tier_weight * 2.5
    return min(1.0, max(0.0, raw))


def add_nuclear_relevance_fields(record: dict[str, Any]) -> dict[str, Any]:
    title = str(record.get("title") or "")
    summary = str(record.get("summary") or "")
    kw_score = nuclear_keyword_score(title, summary)
    record["nuclear_kw_score"] = round(kw_score, 4)
    record["nuclear_relevance"] = round(nuclear_relevance_score(record), 4)
    record["nuclear_is_related"] = kw_score >= NUCLEAR_MIN_KEYWORD_SCORE
    return record


# ═══════════════════════════════════════════════════════════════════
# Source tier helpers
# ═══════════════════════════════════════════════════════════════════


def source_tier_for_site(site_id: str) -> dict[str, Any]:
    tier = SOURCE_TIER_BY_SITE.get(site_id, "unknown")
    rank = SOURCE_TIER_RANK.get(tier, 9)
    importance = SOURCE_TIER_IMPORTANCE.get(tier, 0.3)
    return {"source_tier": tier, "source_tier_rank": rank, "source_tier_importance": importance}


def add_source_tier_fields(record: dict[str, Any]) -> dict[str, Any]:
    site_id = str(record.get("site_id") or "")
    t = source_tier_for_site(site_id)
    for k, v in t.items():
        record[k] = v
    return record


def source_tier_sort_key(record: dict[str, Any]) -> tuple[int, float, str]:
    tier_rank = int(source_tier_for_site(str(record.get("site_id") or "")).get("source_tier_rank", 9))
    importance = float(record.get("nuclear_relevance") or record.get("score") or 0)
    return (tier_rank, -importance, str(record.get("title") or ""))


# ═══════════════════════════════════════════════════════════════════
# Fetch functions — RSS sources
# ═══════════════════════════════════════════════════════════════════


def fetch_single_rss_feed(session: requests.Session, feed_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Fetch one RSS/Atom feed, optionally falling back to Jina reader on failure.

    When feed_def['via_jina'] is True, a direct RSS fetch failure (HTTP error,
    timeout, Cloudflare block) triggers a fallback to the Jina reader of the
    html_url. If both paths fail, raise RuntimeError combining both errors so
    source-status.json records ok=False with full diagnostic context.

    When feed_def['xml_url_candidates'] is set, each candidate is tried in order
    until one succeeds (HTTP 200 with XML/RSS/Atom content). Useful for sources
    whose true RSS path is unknown and must be discovered by probe.
    """
    site_id = feed_def["site_id"]
    site_name = feed_def["site_name"]
    xml_url = feed_def["xml_url"]
    html_url = feed_def.get("html_url", xml_url)
    via_jina = bool(feed_def.get("via_jina", False))
    candidates = feed_def.get("xml_url_candidates") or [xml_url]

    if len(candidates) == 1:
        # Fast path: single URL preserves original error semantics.
        try:
            return _fetch_rss_xml(session, candidates[0], site_id, site_name, html_url, now, feed_def)
        except Exception as rss_err:
            if not via_jina:
                raise
            try:
                return _fetch_via_jina(session, html_url, site_id, site_name, now)
            except Exception as jina_err:
                raise RuntimeError(
                    f"{site_id}: both direct RSS and Jina fallback failed — "
                    f"RSS: {type(rss_err).__name__}: {str(rss_err)[:120]} | "
                    f"Jina: {type(jina_err).__name__}: {str(jina_err)[:120]}"
                ) from jina_err

    # Multi-candidate probe: try each, then Jina fallback.
    errors: list[str] = []
    for cand in candidates:
        try:
            return _fetch_rss_xml(session, cand, site_id, site_name, html_url, now, feed_def)
        except Exception as e:
            errors.append(f"{cand}: {type(e).__name__}: {str(e)[:80]}")

    if not via_jina:
        raise RuntimeError(
            f"{site_id}: all {len(candidates)} RSS candidates failed — "
            + " || ".join(errors)
        )

    try:
        return _fetch_via_jina(session, html_url, site_id, site_name, now)
    except Exception as jina_err:
        raise RuntimeError(
            f"{site_id}: all {len(candidates)} RSS candidates + Jina failed — "
            + " || ".join(errors)
            + f" || Jina: {type(jina_err).__name__}: {str(jina_err)[:100]}"
        ) from jina_err


def _fetch_rss_xml(session, xml_url, site_id, site_name, html_url, now, feed_def) -> list[RawItem]:
    """Fetch and parse an RSS/Atom XML feed directly. Raises on network/HTTP errors."""
    items: list[RawItem] = []
    seen_urls: set[str] = set()

    try:
        resp = session.get(xml_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"{site_id}: RSS fetch failed — {type(e).__name__}: {str(e)[:200]}") from e

    entries: list[dict[str, Any]] = []
    if feedparser:
        try:
            feed = feedparser.parse(resp.content)
            entries = feed.entries
        except Exception:
            entries = parse_feed_entries_via_xml(resp.content)
    else:
        entries = parse_feed_entries_via_xml(resp.content)

    cutoff = now - timedelta(days=RSS_MAX_AGE_DAYS)
    count = 0

    for entry in entries:
        if count >= RSS_MAX_ENTRIES_PER_FEED:
            break
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or entry.get("links", [{}])[0].get("href", "") if isinstance(entry.get("links"), list) else entry.get("link", "")).strip()
        if not title or not link:
            continue

        published = None
        for key in ("published", "published_parsed", "pubDate", "updated", "updated_parsed", "dc:date"):
            val = entry.get(key)
            if val:
                if isinstance(val, str):
                    published = parse_date_any(val, now)
                elif hasattr(val, "tm_year"):
                    try:
                        published = datetime(*val[:6], tzinfo=UTC)
                    except Exception:
                        continue
                if published:
                    break

        if published and published < cutoff:
            continue

        normalized = normalize_url(link)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        summary = (entry.get("summary") or entry.get("description") or "").strip()
        summary = re.sub(r"<[^>]+>", "", summary)[:300]

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title), url=link, published_at=published,
            meta={"summary": summary, "feed_title": feed_def.get("html_url", ""),
                  "nuclear_relevance": nuclear_keyword_score(title, summary)},
        ))
        count += 1

    return items


def _fetch_via_jina(session, html_url, site_id, site_name, now) -> list[RawItem]:
    """Fetch a page via Jina reader and extract article links from markdown.

    Used as fallback when direct RSS is blocked (e.g. Cloudflare-segment IP blocks
    on GitHub Actions runners). Loses pubDate metadata since Jina's markdown output
    doesn't expose per-link timestamps, but survives where RSS XML is 403'd.
    """
    jina_url = f"{JINA_BASE}{html_url}"
    try:
        resp = session.get(jina_url, timeout=45,
                           headers={"Accept": "text/markdown,text/plain", "User-Agent": BROWSER_UA})
        if resp.status_code != 200:
            raise RuntimeError(f"{site_id}: Jina returned HTTP {resp.status_code} for {html_url}")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"{site_id}: Jina fetch failed — {type(e).__name__}: {str(e)[:200]}") from e

    items: list[RawItem] = []
    seen_urls: set[str] = set()
    md_links: list[tuple[str, str]] = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', resp.text)

    for title, url in md_links:
        title = title.strip()
        if title.startswith("!") or title.startswith("Image"):
            continue
        if len(title) < 10:
            continue
        if any(skip in url.lower() for skip in ['/category/', '/tagged/', '/tag/', '/author/',
                                                  '/company-a-z', '/events/', '/newsletters/',
                                                  'member-login', 'wp-content', '/sections']):
            continue
        if not any(x in url.lower() for x in ['/news/', '/content/', 'portal.php', '/article/',
                                                '/analysis/', 'shtml', 'html', '/202']):
            continue
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        title_fixed = maybe_fix_mojibake(title)
        title_fixed = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', title_fixed)

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title_fixed), url=url, published_at=None,
            meta={"nuclear_relevance": nuclear_keyword_score(title_fixed)},
        ))

    return items


def fetch_rss_sources(session: requests.Session, now: datetime) -> tuple[list[RawItem], list[dict[str, Any]]]:
    """Fetch all RSS feeds in parallel. Returns (items, statuses)."""
    items: list[RawItem] = []
    statuses: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_single_rss_feed, session, fd, now): fd for fd in NUCLEAR_RSS_FEEDS}
        for fut in as_completed(futures):
            fd = futures[fut]
            t0 = time.monotonic()
            try:
                result = fut.result()
                elapsed = (time.monotonic() - t0) * 1000
                items.extend(result)
                entry = {"site_id": fd["site_id"], "site_name": fd["site_name"],
                         "ok": True, "item_count": len(result), "duration_ms": round(elapsed), "error": None}
                if not result:
                    # Silent zero: HTTP/parse succeeded but produced no items.
                    # Surface as warning so operators can distinguish "empty source"
                    # from "healthy source with items" in source-status.json.
                    entry["warning"] = "fetched ok but 0 items (silent zero — feed empty, all entries filtered, or no XML body parsed)"
                statuses.append(entry)
            except Exception as e:
                elapsed = (time.monotonic() - t0) * 1000
                statuses.append({"site_id": fd["site_id"], "site_name": fd["site_name"],
                                  "ok": False, "item_count": 0, "duration_ms": round(elapsed), "error": str(e)[:200]})
    return items, statuses


# ═══════════════════════════════════════════════════════════════════
# Fetch functions — Direct web scraping
# ═══════════════════════════════════════════════════════════════════


def fetch_web_direct(session: requests.Session, src_def: dict[str, Any], now: datetime) -> list[RawItem]:
    """Direct BeautifulSoup scraping for sites with clean HTML."""
    site_id = src_def["site_id"]
    site_name = src_def["site_name"]
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    try:
        resp = session.get(src_def["url"], timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"{site_id}: direct fetch failed — {type(e).__name__}: {str(e)[:200]}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    link_els = soup.select(src_def["link_selector"])

    for a_el in link_els:
        title = a_el.get_text(strip=True)
        href = a_el.get("href", "")
        if not title or not href:
            continue
        # Skip navigation / category / tag links
        if any(skip in href.lower() for skip in ['/category/', '/tagged/', '/tag/', '/author/']):
            continue
        if len(title) < 12:
            continue
        full_url = urljoin(src_def["url"], href) if not href.startswith("http") else href
        normalized = normalize_url(full_url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        title_fixed = maybe_fix_mojibake(title)
        # Skip near-duplicate titles
        title_key = title_fixed.lower()[:60]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Try to extract time
        published = None
        time_sel = src_def.get("time_selector")
        if time_sel:
            time_el = soup.select_one(time_sel)
            if time_el:
                time_val = time_el.get(src_def.get("time_attr") or "datetime") or time_el.get_text(strip=True)
                published = parse_date_any(time_val, now)

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title_fixed), url=full_url, published_at=published,
            meta={"nuclear_relevance": nuclear_keyword_score(title_fixed)},
        ))

    return items


def fetch_web_direct_sources(session: requests.Session, now: datetime) -> tuple[list[RawItem], list[dict[str, Any]]]:
    items: list[RawItem] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_web_direct, session, sd, now): sd for sd in WEB_SOURCES_DIRECT}
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
                    entry["warning"] = "fetched ok but 0 items (silent zero — page parsed but no links matched selector)"
                statuses.append(entry)
            except Exception as e:
                elapsed = (time.monotonic() - t0) * 1000
                statuses.append({"site_id": sd["site_id"], "site_name": sd["site_name"],
                                  "ok": False, "item_count": 0, "duration_ms": round(elapsed), "error": str(e)[:200]})
    return items, statuses


# ═══════════════════════════════════════════════════════════════════
# Fetch functions — Jina AI reader fallback
# ═══════════════════════════════════════════════════════════════════

JINA_BASE = "https://r.jina.ai/"


def fetch_web_jina(session: requests.Session, src_def: dict[str, str], now: datetime) -> list[RawItem]:
    """Use Jina AI reader to fetch markdown from JS-rendered / blocked pages, then parse article links."""
    site_id = src_def["site_id"]
    site_name = src_def["site_name"]
    target_url = src_def["url"]
    jina_url = f"{JINA_BASE}{target_url}"
    items: list[RawItem] = []
    seen_urls: set[str] = set()

    try:
        resp = session.get(jina_url, timeout=45,
                           headers={"Accept": "text/markdown,text/plain", "User-Agent": BROWSER_UA})
        if resp.status_code != 200:
            raise RuntimeError(f"{site_id}: Jina returned HTTP {resp.status_code} for {target_url}")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"{site_id}: Jina fetch failed — {type(e).__name__}: {str(e)[:200]}") from e

    text = resp.text
    # Parse markdown links: [title](url)
    md_links: list[tuple[str, str]] = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text)

    for title, url in md_links:
        title = title.strip()
        if title.startswith("!") or title.startswith("Image"):
            continue
        if len(title) < 10:
            continue
        # Skip navigation / category / section links
        if any(skip in url.lower() for skip in ['/category/', '/tagged/', '/tag/', '/author/',
                                                  '/company-a-z', '/events/', '/newsletters/',
                                                  'member-login', 'wp-content', '/sections']):
            continue
        if not any(x in url.lower() for x in ['/news/', '/content/', 'portal.php', '/article/',
                                                '/analysis/', 'shtml', 'html', '/202']):
            continue
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        title_fixed = maybe_fix_mojibake(title)
        # Clean date prefixes like "2026-06-26 "
        title_fixed = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', title_fixed)

        items.append(RawItem(
            site_id=site_id, site_name=site_name, source=site_name,
            title=compact_title(title_fixed), url=url, published_at=None,
            meta={"nuclear_relevance": nuclear_keyword_score(title_fixed)},
        ))

    return items


def fetch_web_jina_sources(session: requests.Session, now: datetime) -> tuple[list[RawItem], list[dict[str, Any]]]:
    items: list[RawItem] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_web_jina, session, sd, now): sd for sd in WEB_SOURCES_JINA}
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
                    entry["warning"] = "fetched ok but 0 items (silent zero — Jina returned markdown but no links survived skip patterns)"
                statuses.append(entry)
            except Exception as e:
                elapsed = (time.monotonic() - t0) * 1000
                statuses.append({"site_id": sd["site_id"], "site_name": sd["site_name"],
                                  "ok": False, "item_count": 0, "duration_ms": round(elapsed), "error": str(e)[:200]})
    return items, statuses


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


# ═══════════════════════════════════════════════════════════════════
# Fetch functions — HN Algolia (community)
# ═══════════════════════════════════════════════════════════════════


def fetch_hn_nuclear(session: requests.Session, now: datetime) -> list[RawItem]:
    """Search HN Algolia for nuclear-related posts in the recent window.

    Nuclear topics are sparse on HN, so we look back 7 days rather than 24h
    to keep the community feed populated.
    """
    items: list[RawItem] = []
    seen_ids: set[str] = set()
    cutoff = now - timedelta(days=7)

    for query in HN_ALGOLIA_QUERIES:
        try:
            params = {
                "query": query,
                "tags": "story",
                "hitsPerPage": HN_ALGOLIA_HITS,
                "numericFilters": f"created_at_i>{int(cutoff.timestamp())}",
            }
            resp = session.get(HN_ALGOLIA_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for hit in data.get("hits", []):
                hid = hit.get("objectID", "")
                if hid in seen_ids:
                    continue
                seen_ids.add(hid)
                title = hit.get("title", "").strip()
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hid}"
                if not title:
                    continue
                pts = int(hit.get("points") or 0)
                comments = int(hit.get("num_comments") or 0)
                if pts < HN_ALGOLIA_MIN_POINTS and comments < HN_ALGOLIA_MIN_COMMENTS:
                    continue
                kw_score = nuclear_keyword_score(title)
                if kw_score < NUCLEAR_MIN_KEYWORD_SCORE:
                    continue
                published = datetime.fromtimestamp(int(hit.get("created_at_i", 0)), tz=UTC)
                items.append(RawItem(
                    site_id="hn_nuclear", site_name="Hacker News", source=f"HN · {query}",
                    title=compact_title(title), url=url, published_at=published,
                    meta={"points": pts, "comments": comments,
                          "nuclear_relevance": kw_score, "hn_query": query},
                ))
            time.sleep(HN_ALGOLIA_QUERY_PAUSE)
        except Exception:
            continue

    # Dedup by URL within HN
    seen_urls: set[str] = set()
    result: list[RawItem] = []
    for item in items:
        nu = normalize_url(item.url)
        if nu not in seen_urls:
            seen_urls.add(nu)
            result.append(item)
    return result


# ═══════════════════════════════════════════════════════════════════
# Fetch functions — Reddit (community)
# ═══════════════════════════════════════════════════════════════════


def fetch_reddit_nuclear(session: requests.Session, now: datetime) -> list[RawItem]:
    """Fetch recent posts from Reddit nuclear subreddits via RSS feeds.

    Iterates ['nuclear', 'nuclearpower']. Partial-failure tolerant: if at
    least one subreddit succeeds, return its items. If both fail, raise
    RuntimeError combining both diagnostics so source-status records
    ok=False with full context (operator can tell 403 auth-block from
    429 rate-limit from network timeout).
    """
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    cutoff = now - timedelta(days=3)
    subreddit_errors: list[str] = []
    successes = 0

    for subreddit in ["nuclear", "nuclearpower"]:
        try:
            sub_items = _fetch_reddit_subreddit(session, subreddit, cutoff, now, seen_urls)
            items.extend(sub_items)
            successes += 1
        except Exception as e:
            subreddit_errors.append(f"r/{subreddit}: {type(e).__name__}: {str(e)[:120]}")

    if successes == 0 and subreddit_errors:
        raise RuntimeError(
            f"reddit_nuclear: both subreddits failed — "
            + " | ".join(subreddit_errors)
        )

    return items


def _fetch_reddit_subreddit(session, subreddit, cutoff, now, seen_urls) -> list[RawItem]:
    """Fetch and parse one Reddit subreddit's RSS feed. Raises on any error."""
    rss_url = f"https://www.reddit.com/r/{subreddit}/.rss"
    resp = session.get(rss_url, timeout=15,
                       headers={"User-Agent": f"{BROWSER_UA} nuclear-intel-radar/0.1"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")

    if feedparser:
        feed = feedparser.parse(resp.content)
        entries = feed.entries
    else:
        entries = parse_feed_entries_via_xml(resp.content)

    items: list[RawItem] = []
    for entry in entries[:REDDIT_MAX_ITEMS]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or entry.get("id") or "").strip()
        if not title or not link:
            continue
        published_str = entry.get("published") or entry.get("updated") or ""
        published = parse_date_any(published_str, now) if published_str else None
        if published and published < cutoff:
            continue
        nu = normalize_url(link)
        if nu in seen_urls:
            continue
        seen_urls.add(nu)
        kw_score = nuclear_keyword_score(title)
        if kw_score < NUCLEAR_MIN_KEYWORD_SCORE:
            continue
        items.append(RawItem(
            site_id="reddit_nuclear", site_name="Reddit", source=f"r/{subreddit}",
            title=compact_title(title), url=link, published_at=published,
            meta={"nuclear_relevance": kw_score, "subreddit": subreddit},
        ))
    return items


# ═══════════════════════════════════════════════════════════════════
# Collect all sources
# ═══════════════════════════════════════════════════════════════════


def collect_all(session: requests.Session, now: datetime) -> tuple[list[RawItem], list[dict[str, Any]]]:
    all_items: list[RawItem] = []
    all_statuses: list[dict[str, Any]] = []

    # RSS sources (parallel)
    rss_items, rss_statuses = fetch_rss_sources(session, now)
    all_items.extend(rss_items)
    all_statuses.extend(rss_statuses)

    # Direct web scraping
    direct_items, direct_statuses = fetch_web_direct_sources(session, now)
    all_items.extend(direct_items)
    all_statuses.extend(direct_statuses)

    # Jina-based web sources (for JS-rendered / blocked sites)
    jina_items, jina_statuses = fetch_web_jina_sources(session, now)
    all_items.extend(jina_items)
    all_statuses.extend(jina_statuses)

    # Community sources
    for label, fn in [("HN Nuclear", fetch_hn_nuclear), ("Reddit Nuclear", fetch_reddit_nuclear)]:
        t0 = time.monotonic()
        try:
            result = fn(session, now)
            elapsed = (time.monotonic() - t0) * 1000
            all_items.extend(result)
            entry = {"site_id": fn.__name__, "site_name": label,
                     "ok": True, "item_count": len(result), "duration_ms": round(elapsed), "error": None}
            if not result:
                entry["warning"] = "fetched ok but 0 items (silent zero — no nuclear-tagged posts in window)"
            all_statuses.append(entry)
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            all_statuses.append({"site_id": fn.__name__, "site_name": label,
                                  "ok": False, "item_count": 0, "duration_ms": round(elapsed), "error": str(e)[:200]})

    # Patch community status records: replace fn.__name__ with the real site_id
    # of the items they returned (or fallback site_id) so source-status.json
    # shows hn_nuclear / reddit_nuclear consistently with latest-24h.json.
    site_id_by_fn = {
        "fetch_hn_nuclear": "hn_nuclear",
        "fetch_reddit_nuclear": "reddit_nuclear",
    }
    for s in all_statuses:
        sid = s.get("site_id")
        if sid in site_id_by_fn:
            s["site_id"] = site_id_by_fn[sid]

    return all_items, all_statuses


# ═══════════════════════════════════════════════════════════════════
# Deduplication
# ═══════════════════════════════════════════════════════════════════


def dedupe_items_by_title_url(items: list[dict[str, Any]], random_pick: bool = True) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for item in items:
        key = f"{normalize_url(str(item.get('url') or ''))}|{str(item.get('title') or '').strip().lower()[:80]}"
        if key not in seen:
            seen[key] = item
        elif item.get("published_at") and (not seen[key].get("published_at") or
                (isinstance(item["published_at"], str) and isinstance(seen[key].get("published_at"), str) and
                 item["published_at"] > seen[key]["published_at"])):
            seen[key] = item
    return list(seen.values())


# ═══════════════════════════════════════════════════════════════════
# Archive management
# ═══════════════════════════════════════════════════════════════════


def load_archive(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_archive(archive: dict[str, dict[str, Any]], path: Path, archive_days: int, now: datetime):
    cutoff = now - timedelta(days=archive_days)
    for key in list(archive.keys()):
        record = archive.get(key)
        if not isinstance(record, dict):
            continue
        ts = record.get("published_at") or record.get("added_at")
        if ts:
            try:
                d = parse_iso(str(ts))
                if d and d < cutoff:
                    del archive[key]
            except Exception:
                pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════
# Build output payloads
# ═══════════════════════════════════════════════════════════════════


def raw_item_to_record(raw: RawItem, archive: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any]:
    item_id = make_item_id(raw.site_id, raw.source, raw.title, raw.url)
    record: dict[str, Any] = {
        "id": item_id,
        "site_id": raw.site_id,
        "site_name": raw.site_name,
        "source": raw.source,
        "title": raw.title,
        "url": raw.url,
        "published_at": iso(raw.published_at) or iso(now),
        "added_at": iso(now),
    }
    if raw.meta:
        for k, v in raw.meta.items():
            if k not in record and v is not None:
                record[k] = v
    record = add_nuclear_relevance_fields(record)
    record = add_source_tier_fields(record)
    return record


def build_latest_payload(
    raw_items: list[RawItem],
    statuses: list[dict[str, Any]],
    archive: dict[str, dict[str, Any]],
    now: datetime,
    window_hours: int,
) -> dict[str, Any]:
    generated_at = iso(now)
    records_all = [raw_item_to_record(raw, archive, now) for raw in raw_items]

    # Nuclear-filtered items
    nuclear_items = [r for r in records_all if r.get("nuclear_is_related", False)]

    # Update archive
    for r in records_all:
        archive[r["id"]] = r

    # Dedupe
    nuclear_deduped = dedupe_items_by_title_url(nuclear_items)
    all_deduped = dedupe_items_by_title_url(records_all)

    # Sort by time (newest first)
    def sort_key(r):
        ts = parse_iso(str(r.get("published_at") or ""))
        return ts.timestamp() if ts else 0
    nuclear_deduped.sort(key=sort_key, reverse=True)
    all_deduped.sort(key=sort_key, reverse=True)

    # Build site stats
    site_stats_map: dict[str, dict[str, Any]] = {}
    for r in records_all:
        sid = r["site_id"]
        if sid not in site_stats_map:
            site_stats_map[sid] = {"site_id": sid, "site_name": r["site_name"], "count": 0, "nuclear_count": 0}
        site_stats_map[sid]["count"] += 1
        if r.get("nuclear_is_related"):
            site_stats_map[sid]["nuclear_count"] += 1
    site_stats = sorted(site_stats_map.values(), key=lambda x: -x["count"])

    all_sites = sorted(set(r["site_id"] for r in records_all))
    ok_sites = sorted(set(s["site_id"] for s in statuses if s["ok"]))

    payload = {
        "generated_at": generated_at,
        "window_hours": window_hours,
        "total_items": len(nuclear_deduped),
        "total_items_raw": len(records_all),
        "total_sources": len(all_sites),
        "ok_sources": len(ok_sites),
        "source_count": len(all_sites),
        "items": nuclear_deduped,
        "items_all": all_deduped,
        "sources": all_sites,
        "site_stats": site_stats,
    }

    return payload


def build_slim_and_all(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split into slim (nuclear-only) and all (full dump) payloads."""
    slim = dict(payload)
    slim.pop("items_all", None)
    slim["all_mode_data_url"] = "data/latest-24h-all.json"
    slim["total_items_all_mode"] = len(payload.get("items_all", []))

    all_payload = {
        "generated_at": payload.get("generated_at"),
        "window_hours": payload.get("window_hours"),
        "total_items_all_mode": len(payload.get("items_all", [])),
        "items_all": payload.get("items_all", []),
        "items_all_raw": payload.get("items_all", []),
    }
    return slim, all_payload


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate nuclear energy news from multiple sources")
    parser.add_argument("--output-dir", default="data", help="Directory for output JSON files")
    parser.add_argument("--window-hours", type=int, default=24, help="Time window in hours")
    parser.add_argument("--archive-days", type=int, default=21, help="Keep archive for N days")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    archive_path = out / "archive.json"

    now = utc_now()
    archive = load_archive(archive_path)

    print(f"[{iso(now)}] Nuclear Intel Radar — starting update (window={args.window_hours}h)")

    session = create_session()
    raw_items, statuses = collect_all(session, now)

    print(f"  Collected {len(raw_items)} raw items from {len(statuses)} sources")
    ok_count = sum(1 for s in statuses if s["ok"])
    print(f"  Source health: {ok_count}/{len(statuses)} OK")

    payload = build_latest_payload(raw_items, statuses, archive, now, args.window_hours)
    slim, all_payload = build_slim_and_all(payload)

    # Build source-status in frontend-compatible format
    site_list = []
    for s in statuses:
        site_list.append({
            "site_id": s["site_id"],
            "site_name": s["site_name"],
            "ok": s["ok"],
            "item_count": s["item_count"],
            "duration_ms": s["duration_ms"],
            "error": s["error"],
            "warning": s.get("warning"),
        })
    ok_sites = [s for s in site_list if s["ok"]]
    failed_sites = [s for s in site_list if not s["ok"]]
    total_fetched = sum(s["item_count"] for s in site_list)
    source_status_payload = {
        "sites": site_list,
        "successful_sites": len(ok_sites),
        "failed_sites": failed_sites,
        "fetched_raw_items": total_fetched,
        "items_before_topic_filter": total_fetched,
        "rss_opml": {},
        "agentmail": {},
        "x_api": {},
        "socialdata": {},
    }

    # Write output files
    (out / "latest-24h.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "latest-24h-all.json").write_text(json.dumps(all_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "source-status.json").write_text(json.dumps(source_status_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build community feed (HN + Reddit r/nuclear) — separate from news.
    # Feeds use a 7d window because nuclear topics are sparse on community sites.
    community_items = [
        r for r in all_payload.get("items_all", [])
        if r.get("site_id") in ("hn_nuclear", "reddit_nuclear")
    ]
    community_items.sort(key=lambda r: r.get("published_at") or "", reverse=True)

    def _to_update(r: dict[str, Any]) -> dict[str, str]:
        ts = r.get("published_at") or ""
        date = ts[:10] if isinstance(ts, str) and len(ts) >= 10 else ""
        return {"date": date, "title": r.get("title") or "", "url": r.get("url") or ""}

    updates_7d = [_to_update(r) for r in community_items[:60]]
    latest_date = updates_7d[0]["date"] if updates_7d else ""
    updates_today = [u for u in updates_7d if u["date"] == latest_date] if latest_date else []

    waytoagi_payload = {
        "generated_at": payload.get("generated_at"),
        "root_url": "https://news.ycombinator.com/",
        "history_url": "https://www.reddit.com/r/nuclear/",
        "updates_7d": updates_7d,
        "updates_today": updates_today,
        "latest_date": latest_date,
        "count_7d": len(updates_7d),
        "count_today": len(updates_today),
        "has_error": False,
        "error": None,
        "warning": None if updates_7d else "本周暂无 HN / Reddit r/nuclear 更新",
    }
    (out / "waytoagi-7d.json").write_text(json.dumps(waytoagi_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save archive
    save_archive(archive, archive_path, args.archive_days, now)

    print(f"  Output: {len(slim.get('items', []))} nuclear items → data/latest-24h.json")
    print(f"  Output: {len(all_payload.get('items_all', []))} all items → data/latest-24h-all.json")
    print(f"  Output: {len(updates_7d)} community updates → data/waytoagi-7d.json")
    print("  Done.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
