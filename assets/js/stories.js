/* ── Top Stories rendering ── */

const NIRStories = (() => {
  let mode = "timeline"; // 'timeline' | 'hot'

  function render(items) {
    const grid = document.getElementById("topStoriesGrid");
    if (!grid) return;

    let stories = [];
    if (items !== undefined) {
      // items passed from main: derive stories from filtered items
      stories = deriveStories(items);
    } else {
      // use pre-merged stories payload, filtered by section
      stories = filterStories(NIRState.get("stories")?.stories || []);
    }

    if (!stories.length) {
      showEmpty("topStoriesGrid", "noTopStoriesTitle", "noTopStoriesMessage");
      window.dispatchEvent(new CustomEvent("nir:storiesRendered", { detail: [] }));
      return;
    }

    if (mode === "hot") {
      stories = [...stories].sort((a, b) => (b.duplicate_count || 1) - (a.duplicate_count || 1));
    }

    const cards = stories.slice(0, 3).map((s, i) => buildStoryCard(s, { showWhy: i === 0 }));
    renderInto(grid, cards);
    window.dispatchEvent(new CustomEvent("nir:storiesRendered", { detail: stories }));
  }

  function deriveStories(items) {
    const section = NIRState.get("filters.section");
    let filtered = items;
    if (section !== "hot") {
      filtered = items.filter((it) => it.sections.includes(section));
    }

    // Simple clustering by normalized URL + title similarity
    const groups = [];
    const used = new Set();

    for (let i = 0; i < filtered.length; i += 1) {
      if (used.has(i)) continue;
      const a = filtered[i];
      const group = [a];
      used.add(i);

      for (let j = i + 1; j < filtered.length; j += 1) {
        if (used.has(j)) continue;
        const b = filtered[j];
        if (sameStory(a, b)) {
          group.push(b);
          used.add(j);
        }
      }

      groups.push({
        story_id: `story-${i}`,
        title: a.title,
        representative_url: a.url,
        first_published_at: a.published_at,
        items: group,
        duplicate_count: group.length,
        primary_section: a.primary_section,
      });
    }

    return groups
      .filter((g) => g.duplicate_count >= 1)
      .sort((a, b) => new Date(b.first_published_at || 0) - new Date(a.first_published_at || 0))
      .slice(0, 10);
  }

  function sameStory(a, b) {
    if (!a.url || !b.url) return false;
    try {
      const ua = new URL(a.url);
      const ub = new URL(b.url);
      if (ua.origin + ua.pathname === ub.origin + ub.pathname) return true;
    } catch {
      // ignore
    }
    const ta = (a.title || "").toLowerCase().replace(/[^\w一-龥]+/g, " ");
    const tb = (b.title || "").toLowerCase().replace(/[^\w一-龥]+/g, " ");
    const setA = new Set(ta.split(/\s+/).filter(Boolean));
    const setB = new Set(tb.split(/\s+/).filter(Boolean));
    const inter = [...setA].filter((x) => setB.has(x));
    const union = new Set([...setA, ...setB]);
    return inter.length / union.size >= 0.7;
  }

  function filterStories(stories) {
    const section = NIRState.get("filters.section");
    if (section === "hot") return stories;
    return stories.filter((s) => (s.primary_section || "hot") === section || s.items?.some((it) => (it.sections || []).includes(section)));
  }

  function bind() {
    const timelineBtn = document.getElementById("storiesTimelineBtn");
    const hotBtn = document.getElementById("storiesHotBtn");

    const setMode = (m) => {
      mode = m;
      timelineBtn.classList.toggle("is-active", m === "timeline");
      hotBtn.classList.toggle("is-active", m === "hot");
      timelineBtn.textContent = t("timeline");
      hotBtn.textContent = t("hot");
      render();
    };

    if (timelineBtn) timelineBtn.addEventListener("click", () => setMode("timeline"));
    if (hotBtn) hotBtn.addEventListener("click", () => setMode("hot"));
  }

  window.addEventListener("nir:localeChanged", () => {
    const timelineBtn = document.getElementById("storiesTimelineBtn");
    const hotBtn = document.getElementById("storiesHotBtn");
    if (timelineBtn) timelineBtn.textContent = t("timeline");
    if (hotBtn) hotBtn.textContent = t("hot");
    render();
  });

  return { render, bind };
})();

NIRStories.bind();
