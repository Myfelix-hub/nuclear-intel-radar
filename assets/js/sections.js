/* ── Section tabs rendering ── */

const NIRSections = (() => {
  function renderTabs() {
    const container = document.getElementById("sectionTabs");
    if (!container) return;

    const counts = NIRState.get("sectionCounts") || {};
    const active = NIRState.get("filters.section");

    const tabs = NIRState.SECTION_DEFS.map((section) => {
      const count = counts[section.id] || 0;
      const isActive = section.id === active;

      const btn = el("button", {
        class: `nir-tab ${isActive ? "is-active" : ""}`,
        role: "tab",
        "aria-selected": String(isActive),
        "aria-controls": "newsList",
        "data-section": section.id,
        title: section.description,
      }, [
        section.label,
        el("span", { class: "nir-tab__count" }, [String(count)]),
      ]);

      btn.addEventListener("click", () => {
        NIRState.setFilter("section", section.id);
        setUrlParam("section", section.id);
        renderTabs();
      });

      return btn;
    });

    renderInto(container, tabs);
  }

  function initFromUrl() {
    const section = getUrlParam("section");
    if (section && NIRState.SECTION_DEFS.some((s) => s.id === section)) {
      NIRState.setFilter("section", section);
    }
  }

  return { renderTabs, initFromUrl };
})();

// Init section from URL on load
NIRSections.initFromUrl();

// Re-render tabs when language changes so labels update
window.addEventListener("nir:localeChanged", () => NIRSections.renderTabs());
