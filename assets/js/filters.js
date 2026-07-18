/* ── Search and filters ── */

const NIRFilters = (() => {
  function bind() {
    const searchInput = document.getElementById("searchInput");
    const sourceTypeSelect = document.getElementById("sourceTypeSelect");
    const sortSelect = document.getElementById("sortSelect");
    const dedupeToggle = document.getElementById("dedupeToggle");
    const disclosure = document.getElementById("advancedFilters");
    const filterSummary = document.getElementById("filterSummary");
    const themeToggle = document.getElementById("themeToggle");
    const langToggle = document.getElementById("langToggle");

    if (searchInput) {
      const filters = NIRState.get("filters");
      searchInput.value = filters.query || "";
      searchInput.addEventListener("input", debounce((e) => {
        NIRState.setFilter("query", e.target.value.trim());
      }, 200));
    }

    if (sourceTypeSelect) {
      sourceTypeSelect.value = NIRState.get("filters.sourceType") || "";
      sourceTypeSelect.addEventListener("change", (e) => {
        NIRState.setFilter("sourceType", e.target.value);
      });
    }

    if (sortSelect) {
      sortSelect.value = NIRState.get("filters.sort") || "priority";
      sortSelect.addEventListener("change", (e) => {
        NIRState.setFilter("sort", e.target.value);
      });
    }

    if (dedupeToggle) {
      dedupeToggle.checked = NIRState.get("filters.dedupe");
      dedupeToggle.addEventListener("change", (e) => {
        NIRState.setFilter("dedupe", e.target.checked);
      });
    }

    NIRState.subscribe((key) => {
      if (key?.startsWith("filters.")) {
        updateFilterSummary();
      }
    });

    if (themeToggle) {
      themeToggle.addEventListener("click", () => NIRState.toggleTheme());
    }

    if (langToggle) {
      langToggle.addEventListener("click", () => {
        NIRI18n.toggle();
        updateLangToggleUI();
      });
      updateLangToggleUI();
    }

    updateFilterSummary();
  }

  function updateFilterSummary() {
    const filters = NIRState.get("filters");
    const parts = [];
    if (filters.sourceType) parts.push(tierLabel(filters.sourceType));
    if (filters.sort === "newest") parts.push(t("sortNewest"));
    else if (filters.sort === "score") parts.push(t("sortScore"));
    else if (filters.sort === "source") parts.push(t("sortSource"));
    if (!filters.dedupe) parts.push(t("dedupe"));

    const elmt = document.getElementById("filterSummary");
    if (elmt) elmt.textContent = parts.length ? parts.join(" · ") : t("filterSummaryAll");
  }

  function updateLangToggleUI() {
    const btn = document.getElementById("langToggle");
    if (!btn) return;
    const locale = NIRI18n.getLocale();
    btn.textContent = locale === "zh" ? "EN" : "中";
    btn.setAttribute("title", t("toggleLanguage"));
    btn.setAttribute("aria-label", t("toggleLanguage"));
  }

  // Re-apply translations for dynamic summary on language change
  window.addEventListener("nir:localeChanged", () => {
    updateFilterSummary();
    updateLangToggleUI();
  });

  return { bind, updateFilterSummary };
})();
