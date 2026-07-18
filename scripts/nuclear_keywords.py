"""Nuclear energy domain keywords and classification rules."""

from typing import Any

# ── Core nuclear keywords (hit in title or body → mark as nuclear-related) ──
NUCLEAR_CORE_KEYWORDS: list[str] = [
    # English
    "nuclear", "reactor", "uranium", "plutonium", "fission", "fusion",
    "radionuclide", "radioactive", "radiation", "coolant", "moderator",
    "SMR", "small modular reactor", "advanced reactor", "Generation IV",
    "HALEU", "TRISO", "fast reactor", "molten salt", "pebble bed",
    "ITER", "tokamak", "stellarator", "deuterium", "tritium",
    "NRC", "IAEA", "WANO", "INPO", "NEA", "DOE nuclear",
    "fuel cycle", "enrichment", "reprocessing", "decommissioning",
    "safeguards", "non-proliferation", "nuclear safety", "emergency preparedness",
    "Hualong One", "AP1000", "APR1400", "VVER", "EPR", "ABWR",
    "NuScale", "TerraPower", "Kairos", "Oklo",
    "CANDU", "RBMK", "BWR", "PWR", "PHWR", "HTGR",
    "isotope", "actinide", "transuranic", "spent fuel", "dry cask",
    "criticality", "subcritical", "neutron flux", "burnup",
    # Chinese
    "核能", "核电", "核电站", "核反应堆", "核聚变", "核裂变",
    "铀矿", "铀浓缩", "核燃料", "核废料", "核安全", "辐射",
    "华龙一号", "国和一号", "高温气冷堆", "快堆", "小堆",
    "托卡马克", "聚变堆", "等离子体",
    "中核", "中广核", "国家电投", "华能核电",
    "核管会", "核安全局", "原子能机构", "核动力",
    "核电机组", "并网发电", "临界", "换料",
    "辐射防护", "放射性废物", "退役",
    "玲龙一号", "燕龙", "CAP1400", "CAP1000",
]

# ── Tech / engineering keywords (broader match, lower weight) ──
NUCLEAR_TECH_KEYWORDS: list[str] = [
    "energy", "power plant", "electricity generation", "clean energy",
    "decarbonization", "baseload", "grid stability", "capacity factor",
    "thermal efficiency", "steam cycle", "cooling tower",
    "能源", "发电", "清洁能源", "碳中和", "基荷",
    "turbine", "steam generator", "pressure vessel", "containment",
    "汽轮机", "蒸汽发生器", "压力容器", "安全壳",
    "control rod", "boron", "zirconium", "hafnium",
    "控制棒", "硼酸", "锆合金",
]

# ── Noise keywords (penalize — likely non-nuclear or weapons-only content) ──
NUCLEAR_NOISE_KEYWORDS: list[str] = [
    "nuclear weapon", "nuclear bomb", "nuclear war", "atomic bomb",
    "nuclear strike", "nuclear deterrence", "ICBM", "warhead",
    "核武器", "核弹", "核战争", "原子弹", "核威慑",
    "核打击", "战略核", "战术核",
]

# ── Vendor / company aliases (normalize names for dedup) ──
VENDOR_ALIASES: dict[str, str] = {
    "cnnc": "中核集团",
    "cgn": "中广核",
    "cgnpc": "中广核",
    "spic": "国家电投",
    "chn energy": "华能",
    "china national nuclear": "中核集团",
    "china general nuclear": "中广核",
    "edf": "法国电力",
    "khnp": "韩国水力原子力",
    "kepco": "韩国电力",
    "rosatom": "俄罗斯原子能",
    "nuscale": "NuScale",
    "terrapower": "TerraPower",
    "kairos": "Kairos Power",
    "x-energy": "X-energy",
    "oklo": "Oklo",
    "iter": "ITER",
    "cfs": "Commonwealth Fusion",
    "helion": "Helion Energy",
    "tae": "TAE Technologies",
    "general fusion": "General Fusion",
    "cameco": "Cameco",
    "kazatomprom": "Kazatomprom",
}

# ── Source tier mapping ──
SOURCE_TIER_BY_SITE: dict[str, str] = {
    # Tier 0 — Official primary sources
    "iaea_news": "official",
    "oecd_nea": "official",
    "doe_ne": "official",
    "iter_org": "official",
    # Tier 0 — Regulators
    "us_nrc": "regulator",
    "asn_fr": "regulator",
    # Tier 1 — Nuclear vertical media
    "wnn": "nuclear_media",
    "nucnet": "nuclear_media",
    "ans_newswire": "nuclear_media",
    "nei_magazine": "nuclear_media",
    "neutronbytes": "nuclear_media",
    # Tier 2 — Nuclear operators / industry
    "rosatom": "industry",
    "cnnc_news": "industry",
    "cgn_news": "industry",
    "edf_nuclear": "industry",
    "oklo": "industry",
    "terrapower": "industry",
    "kairos": "industry",
    "wechat_cnnp": "industry",
    "wechat_cnnc": "industry",
    "wechat_cnji": "industry",
    "wechat_energy_research": "industry",
    "wechat_nuclearnet": "industry",
    "wechat_nuclear_story": "industry",
    "wechat_nsa": "industry",
    "wechat_sh_nuclear": "industry",
    "wechat_npdi": "industry",
    # Tier 3 — Research / academic
    "arxiv_nuclex": "research",
    "arxiv_nuclth": "research",
    "arxiv_insdet": "research",
    "eurofusion": "research",
    # Tier 4 — Aggregators / community / general media
    "powermag": "general_media",
    "bjx_nuclear": "aggregator",
    "nucleartownhall": "aggregator",
    "nuclear_net_cn": "aggregator",
    "hn_nuclear": "community",
    "reddit_nuclear": "community",
}

SOURCE_TIER_RANK: dict[str, int] = {
    "official": 0,
    "regulator": 0,
    "nuclear_media": 1,
    "industry": 2,
    "research": 2,
    "aggregator": 3,
    "general_media": 4,
    "community": 5,
}

SOURCE_TIER_IMPORTANCE: dict[str, float] = {
    "official": 1.0,
    "regulator": 0.95,
    "nuclear_media": 0.85,
    "industry": 0.70,
    "research": 0.65,
    "aggregator": 0.45,
    "general_media": 0.30,
    "community": 0.25,
    "unknown": 0.30,
}

# ── Nuclear relevance score thresholds ──
NUCLEAR_MIN_KEYWORD_SCORE: float = 0.30
NUCLEAR_CORE_KW_WEIGHT: float = 15.0
NUCLEAR_TECH_KW_WEIGHT: float = 5.0
NUCLEAR_NOISE_KW_PENALTY: float = 30.0
NUCLEAR_TITLE_BONUS: float = 2.0

# ── Section classification rules ──
# Rules are evaluated in this order; the first matching rule becomes primary_section.
# Matching uses three phases of decreasing signal strength:
#   1. title_keywords (strongest)
#   2. source_ids
#   3. tier_map + summary_keywords
# A later phase is only considered when no earlier phase matched any rule.
# All matching rules are collected into sections[].
NUCLEAR_SECTION_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "policy",
        "label": "政策法规",
        "source_ids": {"us_nrc", "asn_fr", "doe_ne", "oecd_nea"},
        "tier_map": {"regulator": "policy", "official": "policy"},
        "title_keywords": [
            "regulation", "regulatory", "license", "licensing", "permit", "approval", "approved",
            "policy", "framework", "directive", "safeguards", "non-proliferation",
            "nuclear safety", "emergency preparedness", "oversight",
            "监管", "许可证", "执照", "审批", "批准", "法规", "政策", "核安全局",
            "核管会", "安全监管", "防扩散", "保障监督", "条例", "法令",
        ],
        "summary_keywords": [
            "regulation", "regulatory", "license", "licensing", "permit", "approval",
            "safeguards", "non-proliferation", "oversight",
            "监管", "许可证", "审批", "核安全局", "防扩散",
        ],
    },
    {
        "id": "safety",
        "label": "核安全",
        "source_ids": set(),
        "tier_map": dict(),
        "title_keywords": [
            "incident", "accident", "event", "INES", "radiation", "radioactive",
            "containment", "emergency", "coolant", "leak", "shutdown", "scram",
            "事件", "事故", "辐射", "放射性", "应急", "安全壳", "冷却剂", "泄漏",
            "停堆", "紧急停堆", "核安全", "防护", "熔毁",
        ],
        "summary_keywords": [
            "incident", "accident", "INES", "radiation", "radioactive", "leak",
            "shutdown", "事件", "事故", "辐射", "应急", "停堆",
        ],
    },
    {
        "id": "china",
        "label": "国内核电",
        "source_ids": {
            "cnnc_news", "cgn_news",
            "wechat_cnnp", "wechat_cnnc", "wechat_cnji", "wechat_energy_research",
            "wechat_nuclearnet", "wechat_nuclear_story", "wechat_nsa",
            "wechat_sh_nuclear", "wechat_npdi",
            "bjx_nuclear", "nuclear_net_cn",
        },
        "tier_map": dict(),
        "title_keywords": [
            "CNNC", "CGN", "CNEC", "SPIC", "CHN Energy", "Huaneng",
            "中核", "中广核", "中国核建", "国家电投", "华能核电", "华能集团",
            "华龙一号", "国和一号", "玲龙一号", "燕龙", "CAP1400", "CAP1000",
            "高温气冷堆", "石岛湾", "田湾", "三门", "海阳", "台山", "阳江",
            "防城港", "红沿河", "宁德", "福清", "秦山", "大亚湾", "岭澳",
        ],
        "summary_keywords": [
            "CNNC", "CGN", "中核", "中广核", "国家电投", "华能",
            "华龙一号", "国和一号", "玲龙一号",
        ],
    },
    {
        "id": "newbuild",
        "label": "新项目",
        "source_ids": set(),
        "tier_map": dict(),
        "title_keywords": [
            "construction", "building", "new reactor", "new unit", "new plant",
            "FCD", "first concrete", "grid connection", "commissioning", "startup",
            "operation", "commercial operation", "construction permit",
            "建设", "新建", "开工", "浇注", "并网", "调试", "投运", "商运",
            "机组", "核电站", "核岛", "常规岛", "里程碑",
        ],
        "summary_keywords": [
            "construction", "FCD", "grid connection", "commissioning", "startup",
            "建设", "并网", "调试", "投运", "商运",
        ],
    },
    {
        "id": "fuel",
        "label": "铀矿燃料",
        "source_ids": set(),
        "tier_map": dict(),
        "title_keywords": [
            "uranium", "enrichment", "HALEU", "fuel", "reprocessing", "conversion",
            "fabrication", "fuel cycle", "yellowcake", "centrifuge", "yellow cake",
            "cameco", "kazatomprom", "urenco", "nuclear fuel",
            "铀", "浓缩", "燃料", "乏燃料", "后处理", "转化", "制造", "离心机",
            "黄饼", "铀矿", "核燃料", "燃料循环",
        ],
        "summary_keywords": [
            "uranium", "enrichment", "HALEU", "fuel cycle", "reprocessing",
            "铀", "浓缩", "燃料", "乏燃料", "后处理",
        ],
    },
    {
        "id": "tech",
        "label": "技术进展",
        "source_ids": set(),
        "tier_map": dict(),
        "title_keywords": [
            "SMR", "small modular reactor", "advanced reactor", "Generation IV",
            "fusion", "fission", "ITER", "tokamak", "stellarator", "molten salt",
            "fast reactor", "pebble bed", "HTGR", "HTR-PM", "design", "technology",
            "R&D", "research and development", "breakthrough", "milestone",
            "demonstration reactor", "test reactor", "prototype reactor", "reactor design",
            "小堆", "模块堆", "聚变", "托卡马克", "快堆", "高温气冷堆", "四代堆",
            "技术", "研发", "设计", "突破", "等离子体", "氚", "氘", "示范堆", "试验堆",
        ],
        "summary_keywords": [
            "SMR", "advanced reactor", "fusion", "tokamak", "molten salt",
            "fast reactor", "小堆", "聚变", "快堆", "技术", "研发",
        ],
    },
    {
        "id": "research",
        "label": "学术前沿",
        "source_ids": {"arxiv_nuclex", "arxiv_nuclth", "arxiv_insdet", "eurofusion"},
        "tier_map": {"research": "research"},
        "title_keywords": [
            "paper", "study", "experiment", "prototype", "preprint", "thesis",
            "publication", "journal", "conference", "symposium",
            "论文", "实验", "研究", "预印本", "期刊", "会议", "研讨会",
        ],
        "summary_keywords": [
            "paper", "study", "experiment", "preprint", "publication",
            "论文", "实验", "研究", "预印本",
        ],
    },
    {
        "id": "community",
        "label": "社区讨论",
        "source_ids": {"hn_nuclear", "reddit_nuclear", "nucleartownhall"},
        "tier_map": {"community": "community"},
        "title_keywords": [
            "discussion", "forum", "ask", "opinion", "community",
            "讨论", "论坛", "观点", "社区",
        ],
        "summary_keywords": [
            "discussion", "forum", "讨论",
        ],
    },
    {
        "id": "hot",
        "label": "热点",
        "source_ids": set(),
        "tier_map": dict(),
        "title_keywords": [],
        "summary_keywords": [],
    },
)

SECTION_ORDER: tuple[str, ...] = tuple(rule["id"] for rule in NUCLEAR_SECTION_RULES)
