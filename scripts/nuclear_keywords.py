"""Nuclear energy domain keywords and classification rules."""

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
