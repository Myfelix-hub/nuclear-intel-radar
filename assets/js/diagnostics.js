/* ── Operator diagnostics (gated) ── */

const NIRDiagnostics = (() => {
  function render() {
    const content = document.getElementById("diagnosticsContent");
    if (!content) return;

    const status = NIRState.get("sourceStatus");
    if (!status || !status.sites) {
      content.innerHTML = `<p class='nir-text-muted'>${escapeHtml(t("noDiagnosticsData"))}</p>`;
      return;
    }

    const rows = status.sites.map((s) => {
      let health = "";
      let statusClass = "";
      if (s.ok) {
        if (s.warning) {
          health = `⚠️ ${t("statusWarning")}`;
          statusClass = "nir-text-muted";
        } else {
          health = `✅ ${t("statusOk")}`;
          statusClass = "nir-text-soft";
        }
      } else {
        health = `❌ ${t("statusError")}`;
        statusClass = "nir-text-muted";
      }
      return `<tr>
        <td>${escapeHtml(s.site_name || s.site_id)}</td>
        <td class="${statusClass}">${health}</td>
        <td>${s.item_count}</td>
        <td>${s.duration_ms || 0} ms</td>
        <td>${escapeHtml(s.warning || s.error || "—")}</td>
      </tr>`;
    }).join("");

    content.innerHTML = `
      <table class="nir-status-table">
        <thead>
          <tr>
            <th>${t("diagnosticsSite")}</th>
            <th>${t("diagnosticsStatus")}</th>
            <th>${t("diagnosticsCount")}</th>
            <th>${t("diagnosticsDuration")}</th>
            <th>${t("diagnosticsMessage")}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="nir-text-muted" style="margin-top: var(--nir-space-4);">
        ${t("diagnosticsSummary", { ok: status.successful_sites || 0, total: status.sites.length, raw: status.fetched_raw_items || 0 })}
      </p>
    `;
  }

  window.addEventListener("nir:localeChanged", () => {
    if (!document.getElementById("diagnosticsPanel")?.classList.contains("nir-hidden")) {
      render();
    }
  });

  return { render };
})();
