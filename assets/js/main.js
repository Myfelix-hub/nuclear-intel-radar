/* ── Application bootstrap ── */

(function () {
  const DATA_URLS = {
    latest: "data/latest-24h.json",
    latestAll: "data/latest-24h-all.json",
    sourceStatus: "data/source-status.json",
    stories: "data/stories-merged.json",
    brief: "data/daily-brief.json",
    community: "data/waytoagi-7d.json",
  };

  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${url}: ${res.status}`);
    return res.json();
  }

  async function init() {
    NIRState.initTheme();
    NIRI18n.init();

    const diagnosticsRequested = getUrlParam("diagnostics") === "1";
    if (diagnosticsRequested) {
      toggleVisibility("diagnosticsPanel", true);
    }

    // Seed UI before data arrives
    showLoading("topStoriesGrid", "loadingTopStories");
    showLoading("newsListItems", "loadingNews");

    try {
      const [latest, latestAll, sourceStatus, stories, brief, community] = await Promise.allSettled([
        fetchJson(DATA_URLS.latest),
        fetchJson(DATA_URLS.latestAll),
        fetchJson(DATA_URLS.sourceStatus),
        fetchJson(DATA_URLS.stories),
        fetchJson(DATA_URLS.brief),
        fetchJson(DATA_URLS.community),
      ]);

      NIRState.setPayloads({
        latest: latest.status === "fulfilled" ? latest.value : null,
        latestAll: latestAll.status === "fulfilled" ? latestAll.value : null,
        sourceStatus: sourceStatus.status === "fulfilled" ? sourceStatus.value : null,
        stories: stories.status === "fulfilled" ? stories.value : null,
        brief: brief.status === "fulfilled" ? brief.value : null,
        community: community.status === "fulfilled" ? community.value : null,
      });

      renderStats();
      renderSourceHealth();
      NIRSections.renderTabs();
      NIRFilters.bind();
      NIRStories.render();
      NIRCommunity.render();
      if (diagnosticsRequested) {
        NIRDiagnostics.render();
      }
      applyFilters();

      window.dispatchEvent(new CustomEvent("nir:ready", { detail: NIRState.get() }));
    } catch (err) {
      console.error("NIR init failed:", err);
      showEmpty("topStoriesGrid", "loadFailedTitle", "loadFailedMessage");
      showEmpty("newsListItems", "loadFailedTitle", "loadFailedMessage");
    }
  }

  function renderStats() {
    const latest = NIRState.get("latest");
    if (!latest) return;

    const items = NIRState.get("items") || [];
    const highPriority = items.filter((it) => parseFloat(it.nuclear_relevance || 0) >= 0.5).length;

    setText("statTotal", items.length);
    setText("statHighPriority", highPriority);
    setText("statSources", `${latest.ok_sources || 0}/${latest.total_sources || 0}`);
    setText("statUpdated", fmtRelative(latest.generated_at));
  }

  function renderSourceHealth() {
    const status = NIRState.get("sourceStatus");
    if (!status) return;

    const sites = status.sites || [];
    const ok = sites.filter((s) => s.ok).length;
    const total = sites.length;
    const failed = total - ok;

    const pill = document.getElementById("sourceHealthPill");
    if (!pill) return;

    pill.classList.remove("is-degraded", "is-down");
    if (failed === 0) {
      pill.textContent = t("sourceHealthHealthy", { ok, total });
    } else if (failed <= 2) {
      pill.textContent = t("sourceHealthDegraded", { ok, total });
      pill.classList.add("is-degraded");
    } else {
      pill.textContent = t("sourceHealthDown", { failed });
      pill.classList.add("is-down");
    }
  }

  function applyFilters() {
    const filters = NIRState.get("filters");
    const items = filters.section === "community"
      ? []
      : (NIRState.get("items") || []);

    let visible = items.filter((it) => {
      if (filters.section !== "hot" && !it.sections.includes(filters.section)) {
        return false;
      }
      if (filters.sourceType && it.source_tier !== filters.sourceType) {
        return false;
      }
      if (filters.query) {
        const q = filters.query.toLowerCase();
        const hay = `${it.title || ""} ${it.site_name || ""} ${it.source || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    if (filters.dedupe) {
      const seen = new Set();
      visible = visible.filter((it) => {
        const key = `${it.site_id}|${(it.title || "").slice(0, 60).toLowerCase()}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }

    visible = sortItems(visible, filters.sort);

    // Update section-specific view
    toggleVisibility("newsList", filters.section !== "community");
    toggleVisibility("communitySection", filters.section === "community");

    if (filters.section === "community") {
      NIRCommunity.render();
      NIRStories.render([]);
    } else {
      renderNewsList(visible);
      NIRStories.render(visible);
    }

    updateSummary(filters, visible.length);
  }

  function sortItems(items, sort) {
    const copy = [...items];
    switch (sort) {
      case "newest":
        copy.sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
        break;
      case "score":
        copy.sort((a, b) => parseFloat(b.nuclear_relevance || 0) - parseFloat(a.nuclear_relevance || 0));
        break;
      case "source":
        copy.sort((a, b) => (a.source_tier_rank || 9) - (b.source_tier_rank || 9));
        break;
      case "priority":
      default:
        copy.sort((a, b) => {
          const scoreDiff = parseFloat(b.nuclear_relevance || 0) - parseFloat(a.nuclear_relevance || 0);
          if (Math.abs(scoreDiff) > 0.05) return scoreDiff;
          return new Date(b.published_at || 0) - new Date(a.published_at || 0);
        });
        break;
    }
    return copy;
  }

  function renderNewsList(items) {
    const container = document.getElementById("newsListItems");
    const empty = document.getElementById("newsListEmpty");
    if (!container) return;

    if (!items.length) {
      container.innerHTML = "";
      empty.classList.remove("nir-hidden");
      return;
    }
    empty.classList.add("nir-hidden");

    const cards = items.map((it) => buildItemCard(it, { showSection: true }));
    renderInto(container, cards);
    window.dispatchEvent(new CustomEvent("nir:listRendered", { detail: items }));
  }

  function updateSummary(filters, count) {
    const section = sectionById(filters.section);
    let text = t("summarySection", { section: section.label });
    if (filters.query) text += t("summarySearch", { query: filters.query });
    if (filters.sourceType) text += t("summarySourceType", { sourceType: tierLabel(filters.sourceType) });
    setText("summaryText", text);
    setText("resultCount", t("resultCount", { count }));
  }

  // Subscribe to filter changes
  NIRState.subscribe((key) => {
    if (key?.startsWith("filters.")) {
      applyFilters();
    }
  });

  // Re-apply translations and re-render on language change
  window.addEventListener("nir:localeChanged", () => {
    NIRI18n.applyTranslations();
    renderStats();
    renderSourceHealth();
    NIRSections.renderTabs();
    applyFilters();
    if (!document.getElementById("diagnosticsPanel")?.classList.contains("nir-hidden")) {
      NIRDiagnostics.render();
    }
  });

  // Expose globally for modules
  window.NIRMain = {
    applyFilters,
    renderStats,
    renderSourceHealth,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
