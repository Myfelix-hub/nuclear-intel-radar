/* ── Internationalization ── */

const NIRI18n = (() => {
  const DEFAULT_LOCALE = "zh";
  const STORAGE_KEY = "nir-locale";

  const messages = {
    zh: {
      // Masthead
      brandTitle: "核能信息雷达",
      brandSubtitle: "Nuclear Intel Radar",
      sourceStatusLoading: "源状态加载中",
      sourceHealthHealthy: "{ok}/{total} 信源正常",
      sourceHealthDegraded: "{ok}/{total} 信源正常",
      sourceHealthDown: "{failed} 信源异常",
      toggleTheme: "切换深色模式",
      toggleLanguage: "Switch to English",
      github: "GitHub",

      // Stats
      statSignals: "24h 核能信号",
      statHighPriority: "重点信号",
      statSources: "活跃信源",
      statUpdated: "更新时间",

      // Controls
      searchPlaceholder: "搜索核能信号 / 来源 / 标题",
      advancedFilters: "高级筛选",
      filterSummaryAll: "全部",
      sourceType: "来源类型",
      sourceTypeAll: "全部来源",
      sourceTypeOfficial: "官方 / 一手",
      sourceTypeRegulator: "监管机构",
      sourceTypeMedia: "核能媒体",
      sourceTypeIndustry: "产业 / 运营商",
      sourceTypeResearch: "学术 / 研究",
      sourceTypeAggregator: "聚合 / 社区",
      sortBy: "排序",
      sortPriority: "综合优先级",
      sortNewest: "最新发布",
      sortScore: "相关性分数",
      sortSource: "来源等级",
      dedupe: "去重",

      // Summary
      summaryLoading: "正在整理 24 小时信号…",
      summarySection: "当前栏目：{section}",
      summarySearch: " · 搜索 \"{query}\"",
      summarySourceType: " · {sourceType}",
      resultCount: "{count} 条",

      // Top stories
      topStoriesTitle: "重点信号",
      timeline: "时间线",
      hot: "多源热点",
      noTopStoriesTitle: "暂无重点信号",
      noTopStoriesMessage: "当前栏目下没有足够强的交叉验证信号。",
      whyItMatters: "为什么重要",
      sourceConfirmed: "{count} 源确认",
      officialSource: "来自官方或监管机构的一手信息。",
      researchSource: "学术或研究前沿动态。",
      communitySource: "社区讨论热度较高。",
      genericStoryWhy: "核能行业相关新动态。",

      // News list
      latestSignalsTitle: "最新信号",
      noResultsTitle: "该筛选条件下暂无信号",
      noResultsMessage: "试试切换栏目、清除搜索词或调整筛选条件。",

      // Community
      communityTitle: "社区动态 · HN / Reddit r/nuclear",
      today: "今日",
      sevenDays: "7 天",
      communityLabel: "HN / Reddit",
      communityLoadFailedTitle: "社区动态加载失败",
      communityLoadFailedMessage: "无法读取 community 数据。",
      noCommunityTodayTitle: "暂无社区动态",
      noCommunityTodayMessage: "今日 HN / Reddit r/nuclear 暂无更新。",
      noCommunity7dTitle: "暂无社区动态",
      noCommunity7dMessage: "近 7 天 HN / Reddit r/nuclear 暂无更新。",

      // Diagnostics
      diagnosticsTitle: "运维诊断",
      noDiagnosticsData: "暂无诊断数据。",
      diagnosticsSite: "信源",
      diagnosticsStatus: "状态",
      diagnosticsCount: "条目数",
      diagnosticsDuration: "耗时",
      diagnosticsMessage: "诊断信息",
      diagnosticsSummary: "健康：{ok} / {total} · 原始抓取：{raw} 条",
      statusOk: "正常",
      statusWarning: "警告",
      statusError: "异常",

      // Footer
      footer: "Nuclear Intel Radar · 数据每 30 分钟自动更新 ·",
      diagnosticsLink: "运维诊断",

      // Loading / errors
      loadingTopStories: "正在整理重点信号…",
      loadingNews: "正在加载核能信号…",
      loadFailedTitle: "加载失败",
      loadFailedMessage: "无法读取数据文件，请检查网络或稍后重试。",

      // Priority
      priorityHigh: "高",
      priorityMedium: "中",
      priorityLow: "低",

      // Time
      justNow: "刚刚",
      minutesAgo: "{n} 分钟前",
      hoursAgo: "{n} 小时前",
      daysAgo: "{n} 天前",

      // Sections
      "section.hot": "热点",
      "section.policy": "政策法规",
      "section.newbuild": "新项目",
      "section.tech": "技术进展",
      "section.fuel": "铀矿燃料",
      "section.safety": "核安全",
      "section.research": "学术前沿",
      "section.china": "国内核电",
      "section.community": "社区讨论",
      "sectionDesc.hot": "多源交叉验证的核能热点事件",
      "sectionDesc.policy": "核安全监管、许可证、法规、政府决策",
      "sectionDesc.newbuild": "新建核电站、SMR部署、项目里程碑",
      "sectionDesc.tech": "反应堆技术、核聚变、燃料循环、材料",
      "sectionDesc.fuel": "铀矿开采、浓缩、HALEU、燃料供应链",
      "sectionDesc.safety": "运行事件、INES分级、经验反馈、辐射防护",
      "sectionDesc.research": "arXiv预印本、期刊论文、会议报告",
      "sectionDesc.china": "中核、中广核、国家电投、华能等国内动态",
      "sectionDesc.community": "HN / Reddit r/nuclear 社区讨论",

      // Source tiers
      tierOfficial: "官方",
      tierRegulator: "监管",
      tierMedia: "核能媒体",
      tierIndustry: "产业",
      tierResearch: "学术",
      tierAggregator: "聚合",
      tierGeneral: "综合媒体",
      tierCommunity: "社区",
      tierUnknown: "其他",
    },

    en: {
      // Masthead
      brandTitle: "Nuclear Intel Radar",
      brandSubtitle: "Global Nuclear Intelligence",
      sourceStatusLoading: "Source status loading",
      sourceHealthHealthy: "{ok}/{total} sources healthy",
      sourceHealthDegraded: "{ok}/{total} sources healthy",
      sourceHealthDown: "{failed} sources down",
      toggleTheme: "Toggle dark mode",
      toggleLanguage: "切换到中文",
      github: "GitHub",

      // Stats
      statSignals: "24h Nuclear Signals",
      statHighPriority: "High Priority",
      statSources: "Active Sources",
      statUpdated: "Updated",

      // Controls
      searchPlaceholder: "Search signals / source / title",
      advancedFilters: "Advanced filters",
      filterSummaryAll: "All",
      sourceType: "Source type",
      sourceTypeAll: "All sources",
      sourceTypeOfficial: "Official / Primary",
      sourceTypeRegulator: "Regulator",
      sourceTypeMedia: "Nuclear Media",
      sourceTypeIndustry: "Industry / Operator",
      sourceTypeResearch: "Research / Academic",
      sourceTypeAggregator: "Aggregator / Community",
      sortBy: "Sort",
      sortPriority: "Priority",
      sortNewest: "Newest",
      sortScore: "Relevance score",
      sortSource: "Source tier",
      dedupe: "Deduplicate",

      // Summary
      summaryLoading: "Organizing 24h signals…",
      summarySection: "Section: {section}",
      summarySearch: " · search \"{query}\"",
      summarySourceType: " · {sourceType}",
      resultCount: "{count} results",

      // Top stories
      topStoriesTitle: "Top Stories",
      timeline: "Timeline",
      hot: "Multi-source",
      noTopStoriesTitle: "No top stories",
      noTopStoriesMessage: "No strong cross-verified signals in this section.",
      whyItMatters: "Why it matters",
      sourceConfirmed: "{count} sources",
      officialSource: "First-hand information from an official or regulator source.",
      researchSource: "Academic or research-frontier update.",
      communitySource: "High community discussion activity.",
      genericStoryWhy: "Nuclear industry update.",

      // News list
      latestSignalsTitle: "Latest Signals",
      noResultsTitle: "No signals for this filter",
      noResultsMessage: "Try switching sections, clearing the search, or adjusting filters.",

      // Community
      communityTitle: "Community · HN / Reddit r/nuclear",
      today: "Today",
      sevenDays: "7 days",
      communityLabel: "HN / Reddit",
      communityLoadFailedTitle: "Community feed failed",
      communityLoadFailedMessage: "Could not load community data.",
      noCommunityTodayTitle: "No community updates",
      noCommunityTodayMessage: "No HN / Reddit r/nuclear updates today.",
      noCommunity7dTitle: "No community updates",
      noCommunity7dMessage: "No HN / Reddit r/nuclear updates in the last 7 days.",

      // Diagnostics
      diagnosticsTitle: "Operator diagnostics",
      noDiagnosticsData: "No diagnostics data available.",
      diagnosticsSite: "Source",
      diagnosticsStatus: "Status",
      diagnosticsCount: "Items",
      diagnosticsDuration: "Duration",
      diagnosticsMessage: "Message",
      diagnosticsSummary: "Healthy: {ok} / {total} · Raw fetched: {raw} items",
      statusOk: "OK",
      statusWarning: "Warning",
      statusError: "Error",

      // Footer
      footer: "Nuclear Intel Radar · Auto-updated every 30 minutes ·",
      diagnosticsLink: "Diagnostics",

      // Loading / errors
      loadingTopStories: "Organizing top stories…",
      loadingNews: "Loading nuclear signals…",
      loadFailedTitle: "Load failed",
      loadFailedMessage: "Unable to read data files. Please check your network and try again.",

      // Priority
      priorityHigh: "High",
      priorityMedium: "Medium",
      priorityLow: "Low",

      // Time
      justNow: "just now",
      minutesAgo: "{n} minutes ago",
      hoursAgo: "{n} hours ago",
      daysAgo: "{n} days ago",

      // Sections
      "section.hot": "Hot",
      "section.policy": "Policy",
      "section.newbuild": "New Build",
      "section.tech": "Technology",
      "section.fuel": "Fuel Cycle",
      "section.safety": "Safety",
      "section.research": "Research",
      "section.china": "China Nuclear",
      "section.community": "Community",
      "sectionDesc.hot": "Cross-verified nuclear hot events",
      "sectionDesc.policy": "Regulation, licensing, policy and government decisions",
      "sectionDesc.newbuild": "New reactors, SMR deployments and project milestones",
      "sectionDesc.tech": "Reactor tech, fusion, fuel cycle and materials",
      "sectionDesc.fuel": "Uranium mining, enrichment, HALEU and fuel supply",
      "sectionDesc.safety": "Incidents, INES ratings, lessons learned and radiation protection",
      "sectionDesc.research": "arXiv preprints, journal papers and conference reports",
      "sectionDesc.china": "CNNC, CGN, SPIC, CHN Energy and domestic projects",
      "sectionDesc.community": "HN / Reddit r/nuclear community discussions",

      // Source tiers
      tierOfficial: "Official",
      tierRegulator: "Regulator",
      tierMedia: "Nuclear Media",
      tierIndustry: "Industry",
      tierResearch: "Research",
      tierAggregator: "Aggregator",
      tierGeneral: "General Media",
      tierCommunity: "Community",
      tierUnknown: "Other",
    },
  };

  let current = localStorage.getItem(STORAGE_KEY) || DEFAULT_LOCALE;
  if (!messages[current]) current = DEFAULT_LOCALE;

  function t(key, vars = {}) {
    const dict = messages[current] || messages[DEFAULT_LOCALE];
    let text = dict[key];
    if (text === undefined) {
      // Fallback to default locale
      text = messages[DEFAULT_LOCALE][key] || key;
    }
    return text.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? String(vars[k]) : `{${k}}`));
  }

  function setLocale(locale) {
    if (!messages[locale]) return;
    current = locale;
    localStorage.setItem(STORAGE_KEY, current);
    document.documentElement.setAttribute("lang", current === "zh" ? "zh-CN" : "en");
    applyTranslations();
    window.dispatchEvent(new CustomEvent("nir:localeChanged", { detail: current }));
  }

  function getLocale() {
    return current;
  }

  function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const attr = el.getAttribute("data-i18n-attr");
      const text = t(key);
      if (attr) {
        el.setAttribute(attr, text);
      } else {
        el.textContent = text;
      }
    });
  }

  function toggle() {
    setLocale(current === "zh" ? "en" : "zh");
  }

  function init() {
    document.documentElement.setAttribute("lang", current === "zh" ? "zh-CN" : "en");
    applyTranslations();
  }

  return { t, setLocale, getLocale, toggle, init, applyTranslations };
})();

// Expose short alias globally
window.t = NIRI18n.t;

// Apply on DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", NIRI18n.init);
} else {
  NIRI18n.init();
}
