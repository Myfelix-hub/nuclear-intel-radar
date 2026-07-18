/* ── Pure utilities for Nuclear Intel Radar ── */

function getSections() {
  return [
    { id: "hot", label: t("section.hot"), description: t("sectionDesc.hot") },
    { id: "policy", label: t("section.policy"), description: t("sectionDesc.policy") },
    { id: "newbuild", label: t("section.newbuild"), description: t("sectionDesc.newbuild") },
    { id: "tech", label: t("section.tech"), description: t("sectionDesc.tech") },
    { id: "fuel", label: t("section.fuel"), description: t("sectionDesc.fuel") },
    { id: "safety", label: t("section.safety"), description: t("sectionDesc.safety") },
    { id: "research", label: t("section.research"), description: t("sectionDesc.research") },
    { id: "china", label: t("section.china"), description: t("sectionDesc.china") },
    { id: "community", label: t("section.community"), description: t("sectionDesc.community") },
  ];
}

function getSourceTierLabels() {
  return {
    official: t("tierOfficial"),
    regulator: t("tierRegulator"),
    nuclear_media: t("tierMedia"),
    industry: t("tierIndustry"),
    research: t("tierResearch"),
    aggregator: t("tierAggregator"),
    general_media: t("tierGeneral"),
    community: t("tierCommunity"),
    unknown: t("tierUnknown"),
  };
}

const NIR_SOURCE_KINDS = {
  iaea_news: { label: "IAEA", tier: "official" },
  oecd_nea: { label: "OECD/NEA", tier: "official" },
  us_nrc: { label: "US NRC", tier: "regulator" },
  asn_fr: { label: "ASN", tier: "regulator" },
  doe_ne: { label: "DOE-NE", tier: "official" },
  iter_org: { label: "ITER", tier: "official" },
  wnn: { label: "WNN", tier: "nuclear_media" },
  nucnet: { label: "NucNet", tier: "nuclear_media" },
  ans_newswire: { label: "ANS", tier: "nuclear_media" },
  nei_magazine: { label: "NEI", tier: "nuclear_media" },
  neutronbytes: { label: "NeutronBytes", tier: "nuclear_media" },
  powermag: { label: "POWER", tier: "general_media" },
  cnnc_news: { label: "中核", tier: "industry" },
  cgn_news: { label: "中广核", tier: "industry" },
  rosatom: { label: "Rosatom", tier: "industry" },
  edf_nuclear: { label: "EDF", tier: "industry" },
  oklo: { label: "Oklo", tier: "industry" },
  terrapower: { label: "TerraPower", tier: "industry" },
  kairos: { label: "Kairos", tier: "industry" },
  arxiv_nuclex: { label: "arXiv", tier: "research" },
  arxiv_nuclth: { label: "arXiv", tier: "research" },
  arxiv_insdet: { label: "arXiv", tier: "research" },
  eurofusion: { label: "EUROfusion", tier: "research" },
  bjx_nuclear: { label: "北极星", tier: "aggregator" },
  nucleartownhall: { label: "Town Hall", tier: "aggregator" },
  nuclear_net_cn: { label: "中国核网", tier: "aggregator" },
  hn_nuclear: { label: "HN", tier: "community" },
  reddit_nuclear: { label: "Reddit", tier: "community" },
};

const NIR_TIER_CHIP_CLASS = {
  official: "nir-chip--official",
  regulator: "nir-chip--regulator",
  nuclear_media: "nir-chip--media",
  industry: "nir-chip--industry",
  research: "nir-chip--research",
  aggregator: "nir-chip--aggregator",
  general_media: "nir-chip--general",
  community: "nir-chip--community",
  unknown: "nir-chip--general",
};

/* ── Date / time ── */
function fmtDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const locale = NIRI18n.getLocale() === "zh" ? "zh-CN" : "en-US";
  return d.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const locale = NIRI18n.getLocale() === "zh" ? "zh-CN" : "en-US";
  return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

function fmtRelative(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.round(diffMs / 60000);
  if (diffMins < 1) return t("justNow");
  if (diffMins < 60) return t("minutesAgo", { n: diffMins });
  const diffHours = Math.round(diffMins / 60);
  if (diffHours < 24) return t("hoursAgo", { n: diffHours });
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return t("daysAgo", { n: diffDays });
  return fmtDate(iso);
}

/* ── Scoring ── */
function priorityGrade(item) {
  const score = parseFloat(item.nuclear_relevance || item.nuclear_kw_score || item.score || 0);
  if (score >= 0.75) return { label: t("priorityHigh"), class: "nir-chip--official" };
  if (score >= 0.5) return { label: t("priorityMedium"), class: "nir-chip--media" };
  return { label: t("priorityLow"), class: "nir-chip--general" };
}

function scorePercent(item) {
  const score = parseFloat(item.nuclear_relevance || item.nuclear_kw_score || item.score || 0);
  return Math.round(score * 100);
}

/* ── Section helpers ── */
function sectionById(id) {
  return getSections().find((s) => s.id === id) || { id, label: id, description: "" };
}

function clientSectionFallback(item) {
  const title = (item.title || "").toLowerCase();
  const text = `${title} ${(item.summary || "").toLowerCase()}`;
  const site = (item.site_id || "").toLowerCase();

  const rules = [
    { id: "policy", kw: ["监管", "许可证", "审批", "法规", "政策", "核安全局", "regulation", "license", "permit", "safeguards"] },
    { id: "safety", kw: ["事件", "事故", "辐射", "应急", "停堆", "incident", "accident", "radiation", "leak", "shutdown"] },
    { id: "china", kw: ["中核", "中广核", "国家电投", "华能", "华龙一号", "国和一号", "玲龙一号", "cnnp", "cgn"] },
    { id: "newbuild", kw: ["建设", "并网", "调试", "投运", "商运", "construction", "grid connection", "commissioning"] },
    { id: "fuel", kw: ["铀", "浓缩", "燃料", "乏燃料", "uranium", "enrichment", "fuel cycle", "haleu"] },
    { id: "tech", kw: ["小堆", "聚变", "快堆", "高温气冷堆", "smr", "fusion", "tokamak", "fast reactor", "htgr"] },
    { id: "research", kw: ["论文", "实验", "研究", "预印本", "paper", "study", "experiment", "preprint"] },
    { id: "community", kw: [] },
  ];

  if (site === "hn_nuclear" || site === "reddit_nuclear" || site === "nucleartownhall") {
    return ["community", "community"];
  }

  const sections = [];
  for (const rule of rules) {
    if (rule.kw.some((k) => text.includes(k))) {
      sections.push(rule.id);
    }
  }

  if (sections.length) return [sections, sections[0]];
  return [["hot"], "hot"];
}

function normalizeSections(item) {
  if (item.sections && item.primary_section) {
    return { sections: item.sections, primary_section: item.primary_section };
  }
  const [sections, primary] = clientSectionFallback(item);
  return { sections, primary_section: primary };
}

/* ── Source helpers ── */
function sourceLabel(siteId) {
  return (NIR_SOURCE_KINDS[siteId] || {}).label || siteId;
}

function sourceTier(siteId, item) {
  if (item?.source_tier) return item.source_tier;
  return (NIR_SOURCE_KINDS[siteId] || {}).tier || "unknown";
}

function tierLabel(tier) {
  return getSourceTierLabels()[tier] || tier;
}

function chipClassForSite(siteId, item) {
  const tier = sourceTier(siteId, item);
  return NIR_TIER_CHIP_CLASS[tier] || "nir-chip--general";
}

/* ── Text ── */
function compact(text, limit = 140) {
  if (!text) return "";
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= limit) return t;
  return t.slice(0, limit - 1).replace(/\s+\S*$/, "") + "…";
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ── URL / params ── */
function getUrlParam(key) {
  return new URLSearchParams(window.location.search).get(key);
}

function setUrlParam(key, value) {
  const url = new URL(window.location.href);
  if (value === null || value === "" || value === undefined) {
    url.searchParams.delete(key);
  } else {
    url.searchParams.set(key, value);
  }
  window.history.replaceState({}, "", url);
}

/* ── Debounce ── */
function debounce(fn, wait = 200) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}
