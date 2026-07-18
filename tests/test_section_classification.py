from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from update_news import classify_item_sections


def make_record(**kwargs):
    defaults = {
        "site_id": "wnn",
        "site_name": "World Nuclear News",
        "source": "World Nuclear News",
        "title": "Nuclear energy update",
        "summary": "A general update about the nuclear industry.",
    }
    defaults.update(kwargs)
    return defaults


def test_regulator_item_classified_as_policy():
    record = make_record(
        site_id="us_nrc",
        site_name="US NRC",
        title="NRC issues new reactor licensing guidance",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "policy"
    assert "policy" in sections


def test_official_source_with_safety_keywords_classified_as_safety():
    record = make_record(
        site_id="iaea_news",
        site_name="IAEA News",
        title="IAEA reports radiation incident at research facility",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "safety"
    assert sections == ["safety"]  # title keyword wins; context phase not evaluated


def test_official_source_without_specific_title_defaults_to_policy():
    record = make_record(
        site_id="iaea_news",
        site_name="IAEA News",
        title="IAEA Board of Governors meeting concludes",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "policy"
    assert "policy" in sections


def test_arxiv_item_classified_as_research():
    record = make_record(
        site_id="arxiv_nuclex",
        site_name="arXiv nucl-ex",
        title="Experimental study of nuclear structure",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "research"


def test_chinese_operator_classified_as_china():
    record = make_record(
        site_id="cgn_news",
        site_name="中广核",
        title="中广核台山核电站 1 号机组并网发电",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "china"


def test_fuel_keywords_classified_as_fuel():
    record = make_record(
        site_id="wnn",
        title="Cameco expands uranium enrichment capacity",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "fuel"


def test_tech_keywords_classified_as_tech():
    record = make_record(
        site_id="wnn",
        title="Kairos Power advances Hermes low-power demonstration reactor",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "tech"


def test_newbuild_keywords_classified_as_newbuild():
    record = make_record(
        site_id="wnn",
        title="Grid connection achieved for new VVER-1200 unit",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "newbuild"


def test_community_source_classified_as_community():
    record = make_record(
        site_id="reddit_nuclear",
        site_name="Reddit",
        title="What do you think about nuclear energy's future?",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "community"


def test_generic_nuclear_item_falls_back_to_hot():
    record = make_record(
        site_id="wnn",
        title="Nuclear industry overview",
        summary="A broad look at nuclear developments this quarter.",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "hot"
    assert "hot" in sections


def test_multi_section_collects_all_matches():
    record = make_record(
        site_id="cgn_news",
        site_name="中广核",
        title="中广核新建核电机组采用高温气冷堆技术",
    )
    sections, primary = classify_item_sections(record)
    assert primary == "china"
    assert "china" in sections
    assert "tech" in sections
