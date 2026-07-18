/* ── Reactive state store ── */

const NIRState = (() => {
  const getSectionDefs = () => getSections();

  const data = {
    // Raw payloads
    latest: null,
    latestAll: null,
    sourceStatus: null,
    stories: null,
    brief: null,
    community: null,

    // Derived
    items: [],           // normalized nuclear items
    allItems: [],        // normalized all-mode items
    sectionCounts: {},

    // UI state
    filters: {
      section: "hot",
      query: "",
      sourceType: "",
      sort: "priority",
      dedupe: true,
    },

    theme: "light",
    reducedMotion: false,
    ready: false,
  };

  const listeners = new Set();

  function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  function notify(key) {
    listeners.forEach((fn) => fn(key, data));
  }

  function set(path, value) {
    const keys = path.split(".");
    let target = data;
    for (let i = 0; i < keys.length - 1; i += 1) {
      target = target[keys[i]];
    }
    target[keys[keys.length - 1]] = value;
    notify(path);
  }

  function setFilter(key, value) {
    data.filters[key] = value;
    notify(`filters.${key}`);
  }

  function get(path) {
    if (!path) return data;
    return path.split(".").reduce((obj, key) => obj?.[key], data);
  }

  function setPayloads(payloads) {
    data.latest = payloads.latest || null;
    data.latestAll = payloads.latestAll || null;
    data.sourceStatus = payloads.sourceStatus || null;
    data.stories = payloads.stories || null;
    data.brief = payloads.brief || null;
    data.community = payloads.community || null;

    const normalizedItems = (data.latest?.items || []).map((it) => ({
      ...it,
      ...normalizeSections(it),
    }));
    data.items = normalizedItems;

    const normalizedAll = (data.latestAll?.items_all || []).map((it) => ({
      ...it,
      ...normalizeSections(it),
    }));
    data.allItems = normalizedAll;

    data.sectionCounts = data.latest?.section_counts || {};
    data.ready = true;
    notify("payloads");
  }

  function initTheme() {
    const stored = localStorage.getItem("nir-theme");
    if (stored === "dark" || stored === "light") {
      data.theme = stored;
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      data.theme = "dark";
    }
    data.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    applyTheme();
  }

  function applyTheme() {
    document.documentElement.setAttribute("data-theme", data.theme);
  }

  function toggleTheme() {
    data.theme = data.theme === "dark" ? "light" : "dark";
    localStorage.setItem("nir-theme", data.theme);
    applyTheme();
    notify("theme");
  }

  return {
    get SECTION_DEFS() { return getSectionDefs(); },
    subscribe,
    set,
    get,
    setFilter,
    setPayloads,
    initTheme,
    toggleTheme,
    applyTheme,
  };
})();
