/* ── Shared UI builders ── */

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (key === "class") {
      node.className = value;
    } else if (key === "dataset") {
      Object.entries(value).forEach(([k, v]) => (node.dataset[k] = v));
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value !== undefined && value !== null) {
      node.setAttribute(key, value);
    }
  });
  children.forEach((child) => {
    if (child === null || child === undefined) return;
    if (typeof child === "string" || typeof child === "number") {
      node.appendChild(document.createTextNode(String(child)));
    } else if (child instanceof Node) {
      node.appendChild(child);
    }
  });
  return node;
}

function buildSourceChip(siteId, item) {
  const label = sourceLabel(siteId);
  const tier = item?.source_tier || sourceTier(siteId);
  return el("span", { class: `nir-chip ${chipClassForSite(siteId, item)}` }, [
    `${label} · ${tierLabel(tier)}`,
  ]);
}

function buildPriorityChip(item) {
  const grade = priorityGrade(item);
  return el("span", { class: `nir-chip ${grade.class}` }, [grade.label]);
}

function buildSectionChip(sectionId) {
  const section = sectionById(sectionId);
  return el("span", { class: "nir-chip nir-chip--official" }, [section.label]);
}

function buildItemCard(item, opts = {}) {
  const showSummary = opts.summary !== false && item.summary;
  const metaChildren = [
    buildSourceChip(item.site_id, item),
    buildPriorityChip(item),
  ];

  if (opts.showSection) {
    metaChildren.push(buildSectionChip(item.primary_section));
  }

  metaChildren.push(el("time", { class: "nir-text-muted" }, [fmtRelative(item.published_at)]));

  const card = el("article", { class: "nir-news-card" }, [
    el("a", {
      class: "nir-news-card__link",
      href: item.url,
      target: "_blank",
      rel: "noopener noreferrer",
    }, [
      el("h3", { class: "nir-news-card__title" }, [item.title]),
      el("div", { class: "nir-news-card__meta" }, metaChildren),
      showSummary ? el("p", { class: "nir-news-card__summary" }, [compact(item.summary, 160)]) : null,
    ]),
  ]);

  return card;
}

function buildStoryCard(story, opts = {}) {
  const rep = story.items?.[0] || {};
  const chips = [
    buildSourceChip(rep.site_id, rep),
  ];
  if (story.duplicate_count > 1) {
    chips.push(el("span", { class: "nir-chip nir-chip--media" }, [t("sourceConfirmed", { count: story.duplicate_count })]));
  }

  const whyText = storyWhy(story, rep);

  return el("article", { class: "nir-story-card" }, [
    el("a", {
      class: "nir-story-card__link",
      href: story.representative_url,
      target: "_blank",
      rel: "noopener noreferrer",
    }, [
      el("div", { class: "nir-story-card__meta" }, chips),
      el("h3", { class: "nir-story-card__title" }, [story.title]),
      el("div", { class: "nir-story-card__meta" }, [
        el("time", { class: "nir-text-muted" }, [fmtRelative(story.first_published_at)]),
      ]),
      opts.showWhy && whyText
        ? el("div", { class: "nir-story-card__why" }, [el("strong", {}, [t("whyItMatters")]), `：${whyText}`])
        : null,
    ]),
  ]);
}

function storyWhy(story, rep) {
  if (story.duplicate_count > 1) {
    return t("sourceConfirmed", { count: story.duplicate_count });
  }
  if (rep.source_tier === "official" || rep.source_tier === "regulator") {
    return t("officialSource");
  }
  if (rep.source_tier === "research") {
    return t("researchSource");
  }
  if (rep.source_tier === "community") {
    return t("communitySource");
  }
  return t("genericStoryWhy");
}

function renderInto(container, nodes) {
  const elmt = typeof container === "string" ? document.getElementById(container) : container;
  if (!elmt) return;
  elmt.innerHTML = "";
  const fragment = document.createDocumentFragment();
  nodes.forEach((n) => n && fragment.appendChild(n));
  elmt.appendChild(fragment);
}

function toggleVisibility(id, show) {
  const node = document.getElementById(id);
  if (!node) return;
  if (show) node.classList.remove("nir-hidden");
  else node.classList.add("nir-hidden");
}

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html;
}

function showLoading(id, textKey = "loadingNews") {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = "";
  node.appendChild(el("div", { class: "nir-loading" }, [
    t(textKey),
  ]));
}

function showEmpty(id, titleKey, messageKey) {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = "";
  node.appendChild(el("div", { class: "nir-empty" }, [
    el("div", { class: "nir-empty__title" }, [t(titleKey)]),
    el("p", {}, [t(messageKey)]),
  ]));
}
