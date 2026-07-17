"""Tests for build_stories_payload and build_daily_brief_payload."""
from datetime import datetime, timedelta, timezone

from scripts.update_news import (
    add_nuclear_relevance_fields,
    add_source_tier_fields,
    build_daily_brief_payload,
    build_stories_payload,
    merge_story_items,
)

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def make_item(idx, *, title, url, site_id="nuclear_news", hours_ago=1,
              nuclear_score=0.9, tier_rank=2):
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
    titles = [
        "IAEA approves Ukraine safeguards report",
        "NRC issues AP1000 design amendment",
        "ITER reports first plasma milestone",
        "EDF restarts Civaux unit reactor",
        "Cameco announces uranium production forecast",
        "Kazatomprom signs fuel supply contract",
        "Helion completes fusion prototype test",
        "CFS achieves tokamak net energy record",
        "DoE funds advanced reactor demonstration",
        "Urenco expands enrichment capacity",
        "Westinghouse submits eVinci licensing",
        "BWXT receives microreactor contract",
    ]
    items = [
        make_item(i, title=titles[i - 1], url=f"https://example.com/news/{i}",
                  nuclear_score=0.1 * (10 - i), tier_rank=2)
        for i in range(1, 13)
    ]
    stories, _ = merge_story_items(items, NOW, 24)
    brief = build_daily_brief_payload(stories, NOW, 24)
    assert brief["total_items"] == 10
    scores = [it["score"] for it in brief["items"]]
    assert scores == sorted(scores, reverse=True)
    for it in brief["items"]:
        assert "nuclear_score" in it
        assert "source_tier" in it
        assert "score" in it


def test_build_stories_payload_empty_on_no_items():
    payload = build_stories_payload([], NOW, 24)
    assert payload["total_stories"] == 0
    assert payload["stories"] == []
    assert payload["merge_events"] == []
