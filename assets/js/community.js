/* ── Community feed (HN / Reddit) ── */

const NIRCommunity = (() => {
  let mode = "today"; // 'today' | '7d'

  function render() {
    const container = document.getElementById("communityItems");
    if (!container) return;

    const data = NIRState.get("community");
    if (!data) {
      showEmpty("communityItems", "communityLoadFailedTitle", "communityLoadFailedMessage");
      return;
    }

    const updates = mode === "today" ? (data.updates_today || []) : (data.updates_7d || []);

    if (!updates.length) {
      const titleKey = mode === "today" ? "noCommunityTodayTitle" : "noCommunity7dTitle";
      const msgKey = mode === "today" ? "noCommunityTodayMessage" : "noCommunity7dMessage";
      showEmpty("communityItems", titleKey, msgKey);
      return;
    }

    const cards = updates.map((u) => buildCommunityCard(u));
    renderInto(container, cards);
  }

  function buildCommunityCard(update) {
    return el("article", { class: "nir-news-card" }, [
      el("a", {
        class: "nir-news-card__link",
        href: update.url,
        target: "_blank",
        rel: "noopener noreferrer",
      }, [
        el("h3", { class: "nir-news-card__title" }, [update.title]),
        el("div", { class: "nir-news-card__meta" }, [
          el("span", { class: "nir-chip nir-chip--community" }, [t("communityLabel")]),
          el("time", { class: "nir-text-muted" }, [update.date]),
        ]),
      ]),
    ]);
  }

  function bind() {
    const todayBtn = document.getElementById("communityTodayBtn");
    const sevenBtn = document.getElementById("community7dBtn");

    const setMode = (m) => {
      mode = m;
      todayBtn.classList.toggle("is-active", m === "today");
      sevenBtn.classList.toggle("is-active", m === "7d");
      todayBtn.textContent = t("today");
      sevenBtn.textContent = t("sevenDays");
      render();
    };

    if (todayBtn) todayBtn.addEventListener("click", () => setMode("today"));
    if (sevenBtn) sevenBtn.addEventListener("click", () => setMode("7d"));
  }

  window.addEventListener("nir:localeChanged", () => {
    const todayBtn = document.getElementById("communityTodayBtn");
    const sevenBtn = document.getElementById("community7dBtn");
    if (todayBtn) todayBtn.textContent = t("today");
    if (sevenBtn) sevenBtn.textContent = t("sevenDays");
    render();
  });

  return { render, bind };
})();

NIRCommunity.bind();
