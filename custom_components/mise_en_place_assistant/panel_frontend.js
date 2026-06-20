class MiseEnPlaceAssistantPanel extends HTMLElement {
  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._connected = true;
    this._data ??= null;
    this._error ??= "";
    this._notice ??= "";
    this._showCreate ??= false;
    this._showLocation ??= false;
    this._editingLocation ??= "";
    this._selectedLocation ??= "";
    this._containerContentKind ??= "ingredient";
    this._busyAction ??= "";
    this._planningFilter ??= "all";
    this._tab = this._normalizeTab(this._tab ?? "dashboard");
    this._render();
    this._load();
    this._subscribeToUpdates();
    this._timer ??= window.setInterval(() => this._load(), 15000);
  }

  disconnectedCallback() {
    this._connected = false;
    this._eventUnsubscribe?.();
    this._eventUnsubscribe = undefined;
    window.clearInterval(this._timer);
    this._timer = undefined;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot) {
      return;
    }
    if (!this._loadedOnce) {
      this._load();
    }
    this._subscribeToUpdates();
  }

  set panel(panel) {
    this._panel = panel;
  }

  set route(route) {
    this._route = route;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this.shadowRoot) {
      this._render();
    }
  }

  async _load() {
    if (!this._hass || this._loading) {
      return;
    }
    this._loading = true;
    try {
      this._data = await this._hass.callWS({ type: "mise_en_place_assistant/overview" });
      this._error = "";
      if (!this._busyAction) {
        this._notice = "";
      }
      this._loadedOnce = true;
    } catch (err) {
      this._error = err?.message || "Could not load Mise en Place Assistant overview.";
    } finally {
      this._loading = false;
    }
    if (this._connected) {
      this._render();
    }
  }

  _subscribeToUpdates() {
    const connection = this._hass?.connection;
    if (!connection || this._eventUnsubscribe || this._eventSubscription) {
      return;
    }
    this._eventSubscription = connection.subscribeEvents(
      () => this._load(),
      "mise_en_place_assistant.updated",
    ).then((unsubscribe) => {
      this._eventSubscription = undefined;
      if (!this._connected || this._hass?.connection !== connection) {
        unsubscribe();
        return;
      }
      this._eventUnsubscribe = unsubscribe;
    }).catch(() => {
      this._eventSubscription = undefined;
    });
  }

  async _loadIfNoEventSocket() {
    if (this._eventUnsubscribe) {
      return;
    }
    await this._load();
  }

  _normalizeTab(tab) {
    if (tab === "overview") {
      return "dashboard";
    }
    if (tab === "manage") {
      return "storage";
    }
    return ["dashboard", "inventory", "storage", "planning", "info", "dev"].includes(tab) ? tab : "dashboard";
  }

  _render() {
    const data = this._data;
    if (!this.shadowRoot) {
      return;
    }
    this._tab = this._normalizeTab(this._tab);
    const summary = data?.summary || {};
    const containers = data?.containers || [];
    const archivedContainers = data?.archived_containers || [];
    const items = data?.items || [];
    const foods = data?.foods || [];
    const recipes = data?.recipes || [];
    const mealInventory = data?.meal_inventory?.components || [];
    const areas = data?.areas || [];
    const locations = data?.locations || [];
    const logbook = data?.logbook || [];
    const operations = data?.operations || {};
    const tabs = [
      ["dashboard", "Dashboard"],
      ["inventory", "Inventory"],
      ["storage", "Storage"],
      ["planning", "Planning"],
      ["info", "Info"],
      ["dev", "Dev"],
    ];
    const body = this._tab === "dev"
      ? this._devView(data)
      : this._tab === "info"
        ? this._infoView(data)
        : this._tab === "planning"
          ? this._planningView(mealInventory, data, foods, logbook)
          : this._tab === "storage"
            ? this._storageView(locations, containers, foods, recipes, areas)
            : this._tab === "inventory"
              ? this._inventoryView(items, containers, archivedContainers, locations)
              : this._dashboardView(summary, mealInventory, items, containers, locations, logbook, data);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100%;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
        }
        .ops-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          margin-bottom: 18px;
        }
        .ops-strip.compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ops-card {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 11px 12px;
          background: var(--card-background-color);
          min-width: 0;
        }
        .ops-card strong {
          display: block;
          font-size: 14px;
          overflow-wrap: anywhere;
        }
        .ops-card span { display: block; margin-top: 3px; font-size: 12px; color: var(--secondary-text-color); }
        * { box-sizing: border-box; }
        main {
          width: min(1240px, 100%);
          margin: 0 auto;
          padding: 24px;
        }
        header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }
        h1, h2, h3, p { margin: 0; }
        h1 { font-size: 28px; font-weight: 720; letter-spacing: 0; }
        h2 { font-size: 17px; font-weight: 680; }
        h3 { font-size: 14px; font-weight: 680; }
        button {
          border: 0;
          border-radius: 8px;
          padding: 9px 13px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          font-weight: 650;
          cursor: pointer;
        }
        button:disabled, input:disabled, select:disabled, textarea:disabled {
          cursor: not-allowed;
          opacity: 0.55;
        }
        button.secondary {
          color: var(--primary-text-color);
          background: var(--secondary-background-color, var(--card-background-color));
          border: 1px solid var(--divider-color);
        }
        button.danger {
          background: rgba(244, 67, 54, 0.14);
          color: var(--error-color, #f44336);
          border: 1px solid rgba(244, 67, 54, 0.35);
        }
        .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }
        .muted { color: var(--secondary-text-color); }
        .error, .notice {
          margin-bottom: 14px;
          padding: 11px 13px;
          border-radius: 8px;
        }
        .error {
          background: rgba(244, 67, 54, 0.14);
          color: var(--error-color, #f44336);
        }
        .notice {
          background: color-mix(in srgb, var(--primary-color) 12%, transparent);
          color: var(--primary-text-color);
          border: 1px solid color-mix(in srgb, var(--primary-color) 24%, transparent);
        }
        .tabs {
          display: flex;
          gap: 6px;
          margin: 0 0 18px;
          overflow-x: auto;
        }
        .tabs button.active { background: var(--primary-color); color: var(--text-primary-color); }
        .filter-bar {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
          margin-bottom: 12px;
        }
        .grid, .debug-grid {
          display: grid;
          grid-template-columns: repeat(5, minmax(130px, 1fr));
          gap: 12px;
          margin-bottom: 18px;
        }
        .debug-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .sections {
          display: grid;
          grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
          gap: 16px;
          align-items: start;
        }
        .stack { display: grid; gap: 12px; }
        .card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 15px;
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .location-card {
          --card-accent: var(--location-accent, var(--primary-color));
          overflow: hidden;
          padding: 0;
          background:
            linear-gradient(135deg, color-mix(in srgb, var(--card-accent) 18%, transparent), transparent 36%),
            var(--card-background-color);
        }
        .location-card.selected {
          border-color: color-mix(in srgb, var(--card-accent) 58%, var(--divider-color));
          box-shadow: 0 0 0 1px color-mix(in srgb, var(--card-accent) 34%, transparent);
        }
        .location-card-header {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: start;
          padding: 14px 15px 12px;
          border-top: 5px solid var(--card-accent);
          border-bottom: 1px solid color-mix(in srgb, var(--card-accent) 38%, var(--divider-color));
        }
        .location-card-title {
          display: flex;
          align-items: center;
          gap: 9px;
          min-width: 0;
        }
        .location-card-title ha-icon {
          color: var(--card-accent);
          --mdc-icon-size: 22px;
          flex: 0 0 auto;
        }
        .location-card-title h2 { overflow-wrap: anywhere; }
        .location-card-meta {
          display: flex;
          gap: 7px;
          flex-wrap: wrap;
          margin-top: 8px;
        }
        .location-card-meta .pill { margin-top: 0; }
        .location-chip {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border: 1px solid color-mix(in srgb, var(--card-accent) 42%, var(--divider-color));
          border-radius: 999px;
          background: color-mix(in srgb, var(--card-accent) 13%, transparent);
          padding: 4px 8px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
        }
        .location-chip ha-icon { --mdc-icon-size: 15px; color: var(--card-accent); }
        .location-card .location-type {
          color: var(--card-accent);
          font-weight: 800;
        }
        .selected-chip {
          color: var(--card-accent);
          font-weight: 800;
        }
        .location-card-actions {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-wrap: wrap;
          justify-content: flex-end;
          margin-top: 2px;
        }
        .icon-button {
          width: 34px;
          min-width: 34px;
          height: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          border: 1px solid color-mix(in srgb, var(--card-accent, var(--primary-color)) 46%, var(--divider-color));
          background: color-mix(in srgb, var(--card-accent, var(--primary-color)) 16%, transparent);
          color: var(--card-accent, var(--primary-color));
          padding: 0;
        }
        .icon-button.danger {
          --card-accent: var(--error-color, #f44336);
        }
        .icon-button ha-icon { --mdc-icon-size: 18px; }
        .location-count {
          display: grid;
          justify-items: end;
          gap: 6px;
          min-width: 82px;
        }
        .location-count strong {
          color: var(--card-accent);
          font-size: 24px;
          line-height: 1;
        }
        .location-count span {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
        }
        .location-card-body { padding: 12px 15px 15px; }
        .location-card.type-fridge { --location-accent: #039be5; }
        .location-card.type-freezer { --location-accent: #5e97f6; }
        .location-card.type-pantry { --location-accent: #7cb342; }
        .location-card.type-dry_storage { --location-accent: #8d6e63; }
        .location-card.type-cellar { --location-accent: #6d4c41; }
        .location-card.type-counter { --location-accent: #f9a825; }
        .location-card.type-other { --location-accent: var(--secondary-text-color); }
        .container-card {
          --card-accent: var(--container-accent, var(--primary-color));
          border: 1px solid color-mix(in srgb, var(--card-accent) 34%, var(--divider-color));
          border-radius: 8px;
          background:
            linear-gradient(90deg, color-mix(in srgb, var(--card-accent) 16%, transparent), transparent 42%),
            var(--card-background-color);
          padding: 10px 11px;
        }
        .container-card.row { border-top: 1px solid color-mix(in srgb, var(--card-accent) 34%, var(--divider-color)); }
        .container-card + .container-card { margin-top: 8px; }
        .container-card .row-side { align-self: stretch; align-content: space-between; }
        .container-card.kind-ingredient { --container-accent: #2e7d32; }
        .container-card.kind-recipe { --container-accent: #8e24aa; }
        .container-card.kind-meal { --container-accent: #ef6c00; }
        .container-card.kind-empty { --container-accent: var(--secondary-text-color); }
        .container-titleline {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }
        .container-titleline > ha-icon {
          color: var(--card-accent);
          --mdc-icon-size: 22px;
          flex: 0 0 auto;
        }
        .container-name {
          display: flex;
          gap: 8px;
          align-items: baseline;
          flex-wrap: wrap;
        }
        .container-item {
          color: var(--secondary-text-color);
          font-size: 13px;
          font-weight: 600;
        }
        .container-meta {
          display: flex;
          gap: 7px;
          flex-wrap: wrap;
          margin-top: 7px;
        }
        .container-chip {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border: 1px solid color-mix(in srgb, var(--card-accent, var(--primary-color)) 38%, var(--divider-color));
          border-radius: 999px;
          background: color-mix(in srgb, var(--card-accent, var(--primary-color)) 12%, transparent);
          padding: 3px 8px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
        }
        .container-chip ha-icon { --mdc-icon-size: 15px; }
        .container-chip.kind-ingredient,
        .container-chip.kind-recipe,
        .container-chip.kind-meal,
        .container-chip.kind-empty { color: var(--card-accent); }
        .container-chip.place ha-icon { color: var(--primary-color); }
        .container-actions-line {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-wrap: wrap;
          justify-content: flex-end;
        }
        .container-actions-line select {
          width: auto;
          min-width: 158px;
          max-width: 230px;
          padding: 7px 28px 7px 9px;
        }
        .attention-chip {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border: 1px solid rgba(255, 152, 0, 0.38);
          border-radius: 999px;
          background: rgba(255, 152, 0, 0.12);
          color: var(--warning-color, #ff9800);
          padding: 3px 8px;
          font-size: 12px;
          font-weight: 750;
        }
        .attention-chip.critical {
          border-color: rgba(244, 67, 54, 0.38);
          background: rgba(244, 67, 54, 0.12);
          color: var(--error-color, #f44336);
        }
        .attention-chip ha-icon { --mdc-icon-size: 15px; }
        .form { margin-bottom: 16px; }
        .form-section {
          border-top: 1px solid var(--divider-color);
          padding-top: 12px;
          margin-top: 12px;
        }
        .form-section:first-of-type {
          border-top: 0;
          padding-top: 0;
          margin-top: 0;
        }
        .form-section h3 { margin-bottom: 10px; }
        .form-grid, .review-grid, .inline-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 10px;
          margin: 14px 0;
        }
        .review-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .inline-grid { grid-template-columns: minmax(0, 1fr) 120px auto; align-items: end; }
        label { display: grid; gap: 5px; font-size: 13px; font-weight: 650; }
        input, select, textarea {
          width: 100%;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 9px 10px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font: inherit;
        }
        input[type="checkbox"] { width: auto; padding: 0; }
        label span { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; }
        .metric {
          font-size: 29px;
          font-weight: 760;
          margin-top: 7px;
        }
        .row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: center;
          padding: 12px 0;
          border-top: 1px solid var(--divider-color);
        }
        .row:first-of-type { border-top: 0; }
        .review-row { grid-template-columns: 1fr; align-items: stretch; }
        .compact-row { grid-template-columns: minmax(0, 1fr); }
        .row-side {
          display: grid;
          gap: 8px;
          justify-items: end;
        }
        .name { font-weight: 650; overflow-wrap: anywhere; }
        .subline { margin-top: 3px; }
        .readiness-card { margin-bottom: 18px; }
        .action-context-grid {
          display: grid;
          grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.35fr);
          gap: 14px;
          align-items: start;
        }
        .action-context-panel {
          min-width: 0;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 12px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
        }
        .action-context-panel h3 { margin-bottom: 8px; }
        .readiness-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
        }
        .readiness-section {
          min-width: 0;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 10px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
        }
        .readiness-section h3 { margin-bottom: 8px; }
        .compare-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
          gap: 10px;
          margin-top: 8px;
        }
        .pill {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          background: color-mix(in srgb, var(--primary-color) 14%, transparent);
          color: var(--primary-color);
          padding: 3px 8px;
          font-size: 12px;
          font-weight: 650;
          margin-top: 6px;
        }
        .warn, .warning { color: var(--warning-color, #ff9800); }
        .empty, .critical { color: var(--error-color, #f44336); }
        .ok { color: var(--success-color, #43a047); }
        .state {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          color: var(--secondary-text-color);
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          padding: 10px 11px;
        }
        .qty { font-weight: 750; text-align: right; white-space: nowrap; }
        .container-actions {
          display: grid;
          grid-template-columns: minmax(110px, 1fr) 34px 34px;
          gap: 8px;
          align-items: end;
          margin-top: 10px;
        }
        .health { margin-top: 9px; font-weight: 650; }
        .monitoring-panel {
          border: 1px solid color-mix(in srgb, var(--location-accent, var(--divider-color)) 28%, var(--divider-color));
          border-radius: 8px;
          background: color-mix(in srgb, var(--location-accent, var(--primary-color)) 7%, transparent);
          padding: 10px;
          margin-bottom: 12px;
        }
        .monitoring-status {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          font-weight: 700;
        }
        .monitoring-status ha-icon { --mdc-icon-size: 18px; }
        .reading-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top:10px; }
        .reading { background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; padding: 8px; font-size: 13px; }
        .location-contents { display: grid; gap: 10px; }
        .content-group {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--secondary-background-color, rgba(128,128,128,.04));
          padding: 9px 10px 2px;
        }
        .content-group h3 {
          color: var(--location-accent, var(--secondary-text-color));
          font-size: 13px;
          font-weight: 750;
          margin-bottom: 0;
        }
        .content-group .row:first-of-type { border-top: 0; }
        .location {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          padding: 10px 0;
          border-top: 1px solid var(--divider-color);
        }
        .location:first-of-type { border-top: 0; }
        .log {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 8px;
          padding: 10px 0;
          border-top: 1px solid var(--divider-color);
        }
        .log:first-of-type { border-top: 0; }
        .log-action { font-weight: 650; }
        .log-time { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; }
        .busy { color: var(--secondary-text-color); font-size: 13px; font-weight: 650; }
        pre {
          max-height: 520px;
          overflow: auto;
          margin: 0;
          white-space: pre-wrap;
          word-break: break-word;
          font-size: 12px;
          line-height: 1.45;
        }
        @media (max-width: 850px) {
          main { padding: 16px; }
          header, .toolbar { align-items: flex-start; flex-direction: column; }
          .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .ops-strip { grid-template-columns: 1fr; }
          .sections { grid-template-columns: 1fr; }
          .action-context-grid { grid-template-columns: 1fr; }
          .readiness-grid { grid-template-columns: 1fr; }
          .compare-grid { grid-template-columns: 1fr; }
          .form-grid, .review-grid, .inline-grid, .debug-grid, .container-actions { grid-template-columns: 1fr; }
          .location-card-header { grid-template-columns: 1fr; }
          .location-count { justify-items: start; }
          .location-card-actions { justify-content: flex-start; }
          .row { grid-template-columns: 1fr; }
          .row-side { justify-items: start; }
          .qty { text-align: left; }
        }
      </style>
      <main>
        <header>
          <div>
            <h1>Mise en Place Assistant</h1>
            <p class="muted">${data ? `Updated ${new Date().toLocaleTimeString()}` : "Loading overview..."}</p>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._safe(this._error)}</div>` : ""}
        ${this._notice ? `<div class="notice">${this._safe(this._notice)}</div>` : ""}
        <nav class="tabs">${tabs.map(([id, label]) => `<button type="button" class="${this._tab === id ? "active" : "secondary"}" data-tab="${id}">${label}</button>`).join("")}</nav>
        ${this._busyAction ? `<p class="busy">Working: ${this._safe(this._busyAction)}</p>` : ""}
        ${this._opsStrip(summary, operations, data?.shopping, data?.storage_attention, this._tab)}
        ${body}
      </main>
    `;
    this._wireEvents();
  }

  _wireEvents() {
    this.shadowRoot.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => { this._tab = button.dataset.tab; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-open-tab]").forEach((button) => button.addEventListener("click", () => { this._tab = button.dataset.openTab; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-planning-filter]").forEach((button) => button.addEventListener("click", () => { this._planningFilter = button.dataset.planningFilter; this._render(); }));
    this.shadowRoot.getElementById("add-container")?.addEventListener("click", () => { if (this._isBusy()) return; this._tab = "storage"; this._showCreate = !this._showCreate; this._render(); });
    this.shadowRoot.getElementById("add-location")?.addEventListener("click", () => { if (this._isBusy()) return; this._editingLocation = ""; this._showLocation = !this._showLocation; this._render(); });
    this.shadowRoot.getElementById("create-form")?.addEventListener("submit", (event) => this._createContainer(event));
    this.shadowRoot.getElementById("container-content-kind")?.addEventListener("change", (event) => { this._containerContentKind = event.currentTarget.value; this._render(); });
    this.shadowRoot.getElementById("location-form")?.addEventListener("submit", (event) => this._createLocation(event));
    this.shadowRoot.getElementById("shopping-item-form")?.addEventListener("submit", (event) => this._addShoppingItem(event));
    this.shadowRoot.getElementById("cancel-location")?.addEventListener("click", () => { if (this._isBusy()) return; this._showLocation = false; this._editingLocation = ""; this._render(); });
    this.shadowRoot.getElementById("cancel-create")?.addEventListener("click", () => { if (this._isBusy()) return; this._showCreate = false; this._render(); });
    this.shadowRoot.querySelectorAll("[data-queue-empty-containers]").forEach((button) => button.addEventListener("click", () => this._queueEmptyContainers()));
    this.shadowRoot.querySelectorAll("[data-select-location]").forEach((button) => button.addEventListener("click", () => { if (this._isBusy()) return; this._selectedLocation = button.dataset.selectLocation; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-edit-location]").forEach((button) => button.addEventListener("click", () => { if (this._isBusy()) return; this._editingLocation = button.dataset.editLocation; this._showLocation = true; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-delete-location]").forEach((button) => button.addEventListener("click", () => this._deleteLocation(button.dataset.deleteLocation, button.dataset.locationName, button.dataset.locationProvider, button.dataset.locationLocal)));
    this.shadowRoot.querySelectorAll("[data-move-tag]").forEach((select) => select.addEventListener("change", () => this._moveContainer(select.dataset.moveTag, select.value)));
    this.shadowRoot.querySelectorAll("[data-adjust-container]").forEach((form) => form.addEventListener("submit", (event) => this._adjustContainer(event)));
    this.shadowRoot.querySelectorAll("[data-clear-container]").forEach((button) => button.addEventListener("click", () => this._runContainerService("clear_container", button.dataset.clearContainer, `Clear ${button.dataset.containerName}?`, "Could not clear container.")));
    this.shadowRoot.querySelectorAll("[data-archive-container]").forEach((button) => button.addEventListener("click", () => this._runContainerService("archive_container", button.dataset.archiveContainer, `Archive ${button.dataset.containerName}?`, "Could not archive container.")));
    this.shadowRoot.querySelectorAll("[data-restore-container]").forEach((button) => button.addEventListener("click", () => this._runContainerService("restore_container", button.dataset.restoreContainer, "", "Could not restore container.")));
    this.shadowRoot.querySelectorAll("[data-product-metadata]").forEach((form) => form.addEventListener("submit", (event) => this._saveProductMetadata(event)));
    this.shadowRoot.querySelectorAll("[data-queue-product]").forEach((button) => button.addEventListener("click", () => this._queueProduct(button.dataset.queueProduct, button.dataset.productLabel)));
    this.shadowRoot.querySelectorAll("[data-sync-missing-products]").forEach((button) => button.addEventListener("click", () => this._syncMissingProducts()));
    this.shadowRoot.querySelectorAll("[data-suggested-service]").forEach((button) => button.addEventListener("click", () => this._runSuggestedService(button)));
    this.shadowRoot.querySelectorAll("[data-suggested-tab]").forEach((button) => button.addEventListener("click", () => { if (this._isBusy()) return; this._tab = this._normalizeTab(button.dataset.suggestedTab); this._render(); }));
    this.shadowRoot.getElementById("dev-refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.getElementById("dev-copy-overview")?.addEventListener("click", () => this._copyOverview());
    this.shadowRoot.getElementById("dev-simulate-crud")?.addEventListener("click", () => this._simulateCrud());
    this.shadowRoot.getElementById("dev-sync-missing-products")?.addEventListener("click", () => this._syncMissingProducts());
    this._applyBusyState();
  }

  _dashboardView(summary, mealInventory, items, containers, locations, logbook, data) {
    const productAttention = data?.product_attention || [];
    const empty = data?.empty_containers || [];
    const low = data?.low_containers || [];
    const readiness = data?.readiness || {};
    const suggestedActions = data?.suggested_actions || [];
    const storageAttention = data?.storage_attention || {};
    const locationProblems = locations.filter((location) => ["warning", "critical"].includes(location.health?.status));
    return `
      <section class="grid">
        ${this._metric("Active containers", summary.containers ?? 0)}
        ${this._metric("Ready", summary.ready ?? readiness.ready?.length ?? 0, readiness.ready?.length ? "ok" : "")}
        ${this._metric("Missing", summary.missing ?? readiness.missing?.length ?? 0, readiness.missing?.length ? "warn" : "")}
        ${this._metric("Empty", summary.empty ?? empty.length, empty.length ? "empty" : "")}
        ${this._metric("Storage attention", storageAttention.attention_count ?? summary.location_at_risk ?? 0, storageAttention.status === "critical" ? "critical" : storageAttention.attention_count ? "warn" : "")}
      </section>
      ${this._dashboardActionContext(readiness, suggestedActions)}
      <section class="sections">
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Attention</h2><button type="button" class="secondary" data-open-tab="planning">Review products</button></div>
            ${this._attentionSummary(productAttention, empty, low)}
          </section>
          <section class="card">
            <div class="toolbar"><h2>Ready meals</h2><button type="button" class="secondary" data-open-tab="planning">Planning</button></div>
            ${mealInventory.length ? mealInventory.slice(0, 6).map((entry) => this._mealInventoryRow(entry)).join("") : this._empty("No ready meal components tracked.")}
          </section>
          <section class="card">
            <div class="toolbar"><h2>Recent containers</h2><button type="button" class="secondary" data-open-tab="inventory">Inventory</button></div>
            ${containers.length ? containers.slice(0, 6).map((item) => this._containerRow(item)).join("") : this._empty("No active containers.")}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Shopping</h2><button type="button" class="secondary" data-open-tab="planning">Open</button></div>
            ${this._shoppingStatus(data?.shopping)}
          </section>
          <section class="card">
            <div class="toolbar"><h2>Storage health</h2><button type="button" class="secondary" data-open-tab="storage">Storage</button></div>
            ${this._storageAttentionSummary(storageAttention)}
            ${locationProblems.length ? locationProblems.map((location) => this._locationRow(location)).join("") : this._empty("Storage locations look normal.")}
          </section>
          <section class="card">
            <h2>Activity</h2>
            ${logbook.length ? logbook.slice(0, 8).map((entry) => this._logRow(entry)).join("") : this._empty("No actions recorded.")}
          </section>
        </div>
      </section>
    `;
  }

  _inventoryView(items, containers, archivedContainers, locations) {
    return `
      <section class="sections">
        <div class="stack">
          <section class="card">
            <h2>Inventory by product</h2>
            ${items.length ? items.map((item) => this._itemRow(item)).join("") : this._empty("No filled products.")}
          </section>
          <section class="card">
            <h2>Active containers</h2>
            ${containers.length ? containers.map((container) => this._inventoryContainerRow(container, locations)).join("") : this._empty("No active containers.")}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Empty containers</h2><button type="button" class="secondary" data-queue-empty-containers>Queue shopping</button></div>
            ${containers.filter((container) => this._quantityNumber(container) === 0).map((container) => this._containerRow(container, "empty")).join("") || this._empty("No empty containers.")}
          </section>
          <section class="card">
            <h2>Archived containers</h2>
            ${archivedContainers.length ? archivedContainers.map((container) => this._archivedContainerRow(container)).join("") : this._empty("No archived containers.")}
          </section>
        </div>
      </section>
    `;
  }

  _storageView(locations, containers, foods, recipes, areas) {
    const editableLocations = locations.filter((location) => location.editable !== false);
    const editingLocation = editableLocations.find((location) => location.id === this._editingLocation);
    const selectedLocation = locations.some((location) => location.id === this._selectedLocation)
      ? this._selectedLocation
      : locations[0]?.id || "";
    this._selectedLocation = selectedLocation;
    return `
      ${this._showLocation ? this._locationForm(areas, editingLocation || null) : ""}
      ${this._showCreate ? this._createForm(editableLocations, foods, recipes) : ""}
      <section class="stack">
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Storage locations</h2><div class="actions"><button type="button" id="add-location">Add location</button><button type="button" id="add-container" class="secondary">Add container</button></div></div>
          </section>
          ${locations.map((location) => this._locationCard(location, containers, locations, location.id === selectedLocation)).join("") || this._emptyCard("Create storage locations in Grocy, or enable DEV mode for mocked locations.")}
        </div>
      </section>
    `;
  }

  _planningView(mealInventory, data, foods, logbook) {
    const productAttention = data?.product_attention || [];
    const readiness = data?.readiness || {};
    const planningComparison = data?.planning_comparison || [];
    const recipeContainers = this._filteredRecipeContainers(data?.containers || []);
    return `
      <section class="sections">
        <div class="stack">
          <section class="card">
            <h2>Prepared components</h2>
            ${this._planningFilterBar(data?.containers || [])}
            ${recipeContainers.length ? recipeContainers.map((container) => this._recipeContainerRow(container)).join("") : this._empty("No recipe containers match this filter.")}
          </section>
          <section class="card">
            <h2>Prepared components vs Grocy stock</h2>
            ${planningComparison.length ? planningComparison.map((entry) => this._planningComparisonRow(entry)).join("") : this._empty("No prepared components to compare yet.")}
          </section>
          <section class="card">
            <h2>Readiness</h2>
            ${this._readinessPanel(readiness, true)}
          </section>
          <section class="card">
            <h2>Product review</h2>
            ${productAttention.length ? productAttention.map((item) => this._productAttentionRow(item)).join("") : this._empty("No product review items.")}
          </section>
          <section class="card">
            <h2>Ready meal inventory</h2>
            ${mealInventory.length ? mealInventory.map((entry) => this._mealInventoryRow(entry)).join("") : this._empty("No ready meal components tracked.")}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <h2>Shopping workflow</h2>
            ${this._shoppingStatus(data?.shopping)}
          </section>
          <section class="card">
            <h2>Add shopping item</h2>
            ${this._shoppingItemForm(foods)}
          </section>
          <section class="card">
            <h2>Shopping activity</h2>
            ${logbook.filter((entry) => String(entry.action || "").toLowerCase().includes("shopping")).slice(0, 8).map((entry) => this._logRow(entry)).join("") || this._empty("No shopping actions recorded.")}
          </section>
        </div>
      </section>
    `;
  }

  _infoView(data) {
    const summary = data?.summary || {};
    const operations = data?.operations || {};
    const shopping = data?.shopping || {};
    const foods = data?.foods || [];
    const recipes = data?.recipes || [];
    const containers = data?.containers || [];
    const locations = data?.locations || [];
    const productAttention = data?.product_attention || [];
    const mealInventory = data?.meal_inventory?.components || [];
    const providers = (operations.catalog_providers || []).join(" + ") || "none";
    const mode = operations.dev_mode ? "DEV" : "Live";
    const mealieFoodCount = foods.filter((food) => food?.metadata?.available_in_mealie || food?.available_in_mealie).length;
    const recipeProviderCount = recipes.reduce((counts, recipe) => {
      const provider = recipe.provider || "unknown";
      counts[provider] = (counts[provider] || 0) + 1;
      return counts;
    }, {});
    const recipeProviderLines = Object.entries(recipeProviderCount)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([provider, count]) => `<p class="muted subline">${this._safe(provider)}: ${this._safe(count)} recipes</p>`)
      .join("");
    return `<section class="stack">
      <section class="grid">
        ${this._metric("Catalog mode", mode)}
        ${this._metric("Foods", summary.foods ?? foods.length)}
        ${this._metric("Recipes", summary.recipes ?? recipes.length)}
        ${this._metric("Containers", summary.containers ?? containers.length)}
        ${this._metric("Locations", locations.length)}
      </section>
      <section class="sections">
        <div class="stack">
          <section class="card">
            <h2>Catalog</h2>
            ${this._summaryRow("Providers", [providers])}
            ${this._summaryRow("Catalog size", [`${summary.foods ?? foods.length} foods / ${summary.recipes ?? recipes.length} recipes`])}
            ${this._summaryRow("Product review", [`${productAttention.length} products need review`])}
          </section>
          <section class="card">
            <h2>Mealie</h2>
            ${this._summaryRow("Recipe catalog", [`${recipes.length} recipes loaded`])}
            ${this._summaryRow("Food metadata", [`${mealieFoodCount} foods marked available in Mealie`])}
            ${recipeProviderLines || this._empty("No recipe provider stats.")}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <h2>Grocy</h2>
            ${this._integrationStatusRow("Grocy shopping", shopping.grocy_configured, shopping.product_backed_target === "grocy" || shopping.free_text_target === "grocy")}
            ${this._summaryRow("Minimum stock", [shopping.grocy_minimum_stock ? "Available for shopping sync" : "Not available"])}
            ${this._summaryRow("Grocy stock items", [`${(data?.items || []).filter((item) => item.source === "grocy").length} products`])}
          </section>
          <section class="card">
            <h2>KitchenOwl</h2>
            ${this._integrationStatusRow("KitchenOwl shopping", shopping.kitchenowl_configured, shopping.product_backed_target === "kitchenowl" || shopping.free_text_target === "kitchenowl")}
            ${this._summaryRow("Shopping target", [`Products: ${this._shoppingTargetLabel(shopping.product_backed_target)} / Text: ${this._shoppingTargetLabel(shopping.free_text_target)}`])}
            ${this._summaryRow("Prepared inventory", [`${mealInventory.length} meal components tracked`])}
          </section>
        </div>
      </section>
    </section>`;
  }

  _integrationStatusRow(label, configured, activeTarget) {
    const status = configured ? "connected" : "not configured";
    const target = activeTarget ? "active target" : "not targeted";
    const icon = configured ? "mdi:check-circle" : "mdi:alert-circle-outline";
    const klass = configured ? "ok" : "warn";
    return `<div class="row"><div><p class="name"><ha-icon icon="${icon}"></ha-icon> ${this._safe(label)}</p><p class="muted subline">${this._safe(status)} &middot; ${this._safe(target)}</p></div><div class="qty ${klass}">${configured ? "OK" : "Setup"}</div></div>`;
  }

  _shoppingTargetLabel(provider) {
    return provider === "kitchenowl" ? "KitchenOwl" : provider === "grocy" ? "Grocy" : "Automatic";
  }

  _devView(data) {
    const summary = data?.summary || {};
    const shopping = data?.shopping || {};
    const socket = this._eventUnsubscribe ? "subscribed" : this._eventSubscription ? "subscribing" : "fallback";
    const payload = JSON.stringify(data || {}, null, 2);
    return `<section class="stack">
      <section class="card">
        <div class="actions">
          <h2>Dev controls</h2>
          <button type="button" class="secondary" id="dev-refresh">Refresh overview</button>
          <button type="button" class="secondary" id="dev-copy-overview">Copy overview JSON</button>
          ${data?.operations?.dev_mode ? `<button type="button" class="secondary" id="dev-simulate-crud">Simulate CRUD</button>` : ""}
          ${shopping.grocy_minimum_stock ? `<button type="button" class="secondary" id="dev-sync-missing-products">Queue Grocy minimum stock</button>` : ""}
        </div>
      </section>
      <section class="debug-grid">
        ${this._metric("Socket", socket)}
        ${this._metric("Foods", data?.foods?.length ?? 0)}
        ${this._metric("Recipes", data?.recipes?.length ?? 0)}
        ${this._metric("Attention", data?.product_attention?.length ?? 0)}
        ${this._metric("Containers", summary.containers ?? 0)}
        ${this._metric("Log entries", data?.logbook?.length ?? 0)}
      </section>
      <section class="sections">
        <div class="stack">
          <section class="card">
            <h2>Workflow status</h2>
            ${this._shoppingStatus(shopping)}
          </section>
          <section class="card">
            <h2>Attention products</h2>
            ${(data?.product_attention || []).map((item) => `<div class="row"><div><p class="name">${this._safe(item.label)}</p><p class="muted">${this._safe((item.reasons || []).join(", "))}</p></div><div class="qty">${this._safe(item.quantity)}<br><span class="muted">${this._safe(item.unit)}</span></div></div>`).join("") || this._empty("No product review items.")}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <h2>Recent log</h2>
            ${(data?.logbook || []).slice(0, 8).map((entry) => this._logRow(entry)).join("") || this._empty("No actions recorded.")}
          </section>
        </div>
      </section>
      <section class="card">
        <h2>Overview payload</h2>
        <pre>${this._safe(payload)}</pre>
      </section>
    </section>`;
  }

  _metric(label, value, klass = "") {
    return `<article class="card"><p class="muted">${this._safe(label)}</p><p class="metric ${klass}">${this._safe(value)}</p></article>`;
  }

  _opsStrip(summary, operations, shopping = {}, storageAttention = {}, activeTab = "") {
    const providers = (operations.catalog_providers || []).join(" + ") || "none";
    const health = operations.health || {};
    const badHealth = storageAttention.attention_count ?? ((health.warning || 0) + (health.critical || 0));
    const mode = operations.dev_mode ? "DEV" : "Live";
    const shoppingProvider = shopping.provider || operations.shopping_provider || "auto";
    const productTarget = shopping.product_backed_target || "grocy";
    const textTarget = shopping.free_text_target || "grocy";
    const minimumStock = shopping.grocy_minimum_stock ? "minimum stock available" : "minimum stock unavailable";
    const catalogCards = activeTab === "storage" ? "" : `
      <div class="ops-card"><strong>Catalog: ${this._safe(mode)}</strong><span>${this._safe(providers)}</span></div>
      <div class="ops-card"><strong>Catalog size</strong><span>${this._safe(summary.foods ?? 0)} foods / ${this._safe(summary.recipes ?? 0)} recipes</span></div>`;
    return `<section class="ops-strip${activeTab === "storage" ? " compact" : ""}">
      ${catalogCards}
      <div class="ops-card"><strong class="${badHealth ? "warn" : "ok"}">Storage alerts: ${this._safe(badHealth)}</strong><span>${this._safe(storageAttention.unhealthy_locations_count ?? 0)} unhealthy locations</span></div>
      <div class="ops-card"><strong>Shopping: ${this._safe(shoppingProvider)}</strong><span>Products: ${this._safe(productTarget)} · Text: ${this._safe(textTarget)} · ${this._safe(minimumStock)}</span></div>
    </section>`;
  }

  _dashboardActionContext(readiness = {}, suggestedActions = []) {
    const context = [
      `${suggestedActions.length} actions`,
      `${readiness.ready?.length || 0} ready`,
      `${readiness.missing?.length || 0} missing`,
      `${readiness.location_at_risk?.length || 0} at risk`,
    ].join(" · ");
    return `<section class="card readiness-card">
      <div class="toolbar">
        <div>
          <h2>Next actions</h2>
          <p class="muted subline">${this._safe(context)}</p>
        </div>
        <button type="button" class="secondary" data-open-tab="planning">Open review</button>
      </div>
      <div class="action-context-grid">
        <section class="action-context-panel">
          <h3>Suggested next actions</h3>
          ${this._suggestedActionsPanel(suggestedActions)}
        </section>
        <section class="action-context-panel">
          <h3>Readiness</h3>
          ${this._readinessPanel(readiness, true)}
        </section>
      </div>
    </section>`;
  }

  _createForm(locations, foods, recipes) {
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}">${this._safe(location.name)}</option>`).join("");
    const sublocationOptions = locations.flatMap((location) => (location.sublocations || []).map((sublocation) => `<option value="${this._safe(sublocation)}">${this._safe(location.name)} / ${this._safe(sublocation)}</option>`)).join("");
    const foodOptions = foods.map((food) => `<option value="${this._safe(food.id)}">${this._safe(food.label)}</option>`).join("");
    const recipeOptions = recipes.map((recipe) => `<option value="${this._safe(recipe.id)}">${this._safe(recipe.label)}</option>`).join("");
    const selected = (value) => this._containerContentKind === value ? " selected" : "";
    const contentSelector = `<label>Contents<select name="content_kind" id="container-content-kind"><option value="ingredient"${selected("ingredient")}>Ingredient</option><option value="recipe"${selected("recipe")}>Recipe batch</option><option value="meal"${selected("meal")}>Ready meal</option></select></label>`;
    const contentField = this._containerContentKind === "ingredient"
      ? `<label>Catalog food<select name="item_id" required><option value="">Choose a catalog food</option>${foodOptions}</select></label>`
      : `<label>Mealie recipe<select name="recipe_id" required><option value="">Choose a Mealie recipe</option>${recipeOptions}</select></label>`;
    return `
      <form class="card form" id="create-form">
        <h2>Add container</h2>
        <div class="form-grid">
          <label>NFC tag<input name="tag_id" required placeholder="04:A1:C2" /></label>
          <label>Container name<input name="name" placeholder="Freezer bin 1" /></label>
          ${contentSelector}
          ${contentField}
          <label>Quantity<input name="quantity" required type="number" min="0" step="any" value="1" /></label>
          <label>Location<select name="location_id"><option value="">Choose a location</option>${locationOptions}</select></label>
          <label>Sublocation<input name="sublocation" list="sublocation-options" placeholder="Top shelf, drawer..." /></label>
          <datalist id="sublocation-options">${sublocationOptions}</datalist>
          ${this._containerContentKind === "ingredient" ? `<label>Best before<input name="best_before_date" type="date" /></label><label>Purchased<input name="purchased_date" type="date" /></label><label>Opened<input name="opened_date" type="date" /></label>` : ""}
        </div>
        <div class="actions"><button type="button" class="secondary" id="cancel-create">Cancel</button><button type="submit">Save container</button></div>
      </form>
    `;
  }

  async _createContainer(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name]?.value?.trim() || "";
    const data = {
      tag_id: value("tag_id"),
      quantity: Number(value("quantity")),
    };
    const contentKind = value("content_kind");
    if (contentKind === "ingredient") {
      if (!value("item_id")) {
        this._error = "Choose a catalog food before saving the container.";
        this._render();
        return;
      }
      data.item_id = value("item_id");
    } else {
      if (!value("recipe_id")) {
        this._error = "Choose a Mealie recipe before saving the container.";
        this._render();
        return;
      }
      data.recipe_id = value("recipe_id");
      data.content_kind = contentKind;
    }
    if (value("name")) data.name = value("name");
    if (value("location_id")) data.location_id = value("location_id");
    if (value("sublocation")) data.sublocation = value("sublocation");
    if (contentKind === "ingredient" && value("best_before_date")) data.best_before_date = value("best_before_date");
    if (contentKind === "ingredient" && value("purchased_date")) data.purchased_date = value("purchased_date");
    if (contentKind === "ingredient" && value("opened_date")) data.opened_date = value("opened_date");
    await this._withBusy("saving container", async () => {
      await this._hass.callService("mise_en_place_assistant", contentKind === "ingredient" ? "create_container" : "create_recipe_container", data);
      this._showCreate = false;
      this._notice = "Container saved.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not save the container.";
      this._render();
    });
  }

  _locationForm(areas, location = null) {
    const sensors = location?.sensors || {};
    const monitoring = location?.monitoring || {};
    const sublocations = (location?.sublocations || []).join(", ");
    const selected = (current, value) => current === value ? " selected" : "";
    const areaOptions = areas.map((area) => `<option value="${this._safe(area.id)}"${selected(location?.area_id, area.id)}>${this._safe(area.name)}</option>`).join("");
    const typeOptions = ["fridge", "freezer", "pantry", "dry_storage", "cellar", "counter", "other"]
      .map((type) => `<option value="${type}"${selected(location?.location_type || "other", type)}>${this._safe(type.replaceAll("_", " "))}</option>`)
      .join("");
    const isEditing = Boolean(location?.id);
    return `<form class="card form" id="location-form"><h2>${isEditing ? "Edit location" : "Add location"}</h2>
      <input type="hidden" name="location_id" value="${this._safe(location?.id || "")}" />
      <div class="form-section"><h3>Identity</h3><div class="form-grid">
        <label>Storage location<input name="name" required ${isEditing ? "readonly " : ""}value="${this._safe(location?.name || "")}" /></label>
        <label>Home Assistant area<select name="area_id"><option value="">No area</option>${areaOptions}</select></label>
        <label>Type<select name="location_type">${typeOptions}</select></label>
        <label>Sublocations<input name="sublocations" placeholder="Top shelf, bottom drawer" value="${this._safe(sublocations)}" /></label>
      </div></div>
      <div class="form-section"><h3>Monitoring sensors</h3><div class="form-grid">
        <label>Temperature sensor${this._entitySelect("temperature", sensors.temperature, ["sensor"])}</label>
        <label>Humidity sensor${this._entitySelect("humidity", sensors.humidity, ["sensor"])}</label>
        <label>Door sensor${this._entitySelect("door", sensors.door, ["binary_sensor"])}</label>
        <label>Power sensor${this._entitySelect("power", sensors.power, ["sensor"])}</label>
        <label>Appliance plug${this._entitySelect("power_switch", sensors.power_switch, ["switch"])}</label>
      </div></div>
      <div class="form-section"><h3>Thresholds</h3><div class="form-grid">
        <label>Minimum temperature<input name="temperature_min" type="number" step="any" value="${this._safe(monitoring.temperature_min ?? "")}" /></label>
        <label>Maximum temperature<input name="temperature_max" type="number" step="any" value="${this._safe(monitoring.temperature_max ?? "")}" /></label>
      </div></div>
      <div class="actions"><button type="button" class="secondary" id="cancel-location">Cancel</button><button type="submit">Save location</button></div></form>`;
  }

  async _createLocation(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    const sensors = Object.fromEntries(["temperature", "humidity", "door", "power", "power_switch"].filter((name) => value(name)).map((name) => [name, value(name)]));
    const monitoring = Object.fromEntries(["temperature_min", "temperature_max"].filter((name) => value(name) !== "").map((name) => [name, Number(value(name))]));
    const sublocations = value("sublocations").split(",").map((name) => name.trim()).filter(Boolean);
    if (value("power_switch")) monitoring.power_required = true;
    const locationId = value("location_id");
    await this._withBusy("saving location", async () => {
      await this._hass.callService(
        "mise_en_place_assistant",
        locationId ? "update_location" : "create_location",
        { ...(locationId ? { location_id: locationId } : {}), name: value("name"), location_type: value("location_type"), sublocations, ...(value("area_id") ? { area_id: value("area_id") } : {}), sensors, monitoring },
      );
      this._showLocation = false;
      this._editingLocation = "";
      this._notice = "Location saved.";
      await this._loadIfNoEventSocket();
    }, (err) => { this._error = err?.message || "Could not save location."; this._render(); });
  }

  async _deleteLocation(locationId, name, provider, local) {
    if (this._isBusy()) return;
    const message = provider === "mocked" && local === "true" ? `Remove ${name} as a storage location? Containers there will move to The Void.` : `Remove local monitoring metadata for ${name}? The provider location will remain.`;
    if (!window.confirm(message)) return;
    await this._withBusy("removing location", async () => {
      await this._hass.callService("mise_en_place_assistant", "delete_location", { location_id: locationId });
      this._notice = "Location removed.";
      await this._loadIfNoEventSocket();
    }, (err) => { this._error = err?.message || "Could not delete location."; this._render(); });
  }

  async _moveContainer(tagId, selection) {
    if (!selection || this._isBusy()) return;
    const [locationId, sublocation = ""] = selection.split("||");
    await this._withBusy("moving container", async () => {
      await this._hass.callService("mise_en_place_assistant", "move_container", { tag_id: tagId, location_id: locationId, ...(sublocation ? { sublocation } : {}) });
      this._notice = "Container moved.";
      await this._loadIfNoEventSocket();
    }, (err) => { this._error = err?.message || "Could not move container."; this._render(); });
  }

  async _adjustContainer(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const quantity = Number(form.elements.quantity.value);
    const service = event.submitter?.value === "remove" ? "remove_items" : "fill_container";
    await this._withBusy(service === "remove_items" ? "removing items" : "filling container", async () => {
      await this._hass.callService("mise_en_place_assistant", service, {
        tag_id: form.dataset.adjustContainer,
        quantity,
      });
      this._notice = service === "remove_items" ? "Items removed." : "Container filled.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not update container quantity.";
      this._render();
    });
  }

  async _runContainerService(service, tagId, confirmMessage, errorMessage) {
    if (this._isBusy()) return;
    if (confirmMessage && !window.confirm(confirmMessage)) {
      return;
    }
    await this._withBusy(service.replace("_", " "), async () => {
      await this._hass.callService("mise_en_place_assistant", service, { tag_id: tagId });
      this._notice = service === "restore_container" ? "Container restored." : service === "archive_container" ? "Container archived." : "Container cleared.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || errorMessage;
      this._render();
    });
  }

  async _syncMissingProducts() {
    if (this._isBusy()) return;
    await this._withBusy("queuing Grocy minimum stock", async () => {
      await this._hass.callService("mise_en_place_assistant", "add_missing_products_to_shopping_list", {});
      this._notice = "Grocy minimum stock queued.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not sync Grocy minimum-stock shopping.";
      this._render();
    });
  }

  async _simulateCrud() {
    if (this._isBusy()) return;
    await this._withBusy("simulating CRUD", async () => {
      await this._hass.callService("mise_en_place_assistant", "simulate_crud", {});
      this._notice = "DEV CRUD simulation completed.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not simulate DEV CRUD.";
      this._render();
    });
  }

  async _queueEmptyContainers() {
    if (this._isBusy()) return;
    await this._withBusy("queuing empty containers", async () => {
      await this._hass.callService("mise_en_place_assistant", "add_empty_containers_to_shopping_list", {});
      this._notice = "Empty containers queued.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not queue empty containers.";
      this._render();
    });
  }

  async _queueProduct(itemId, label) {
    if (!itemId || this._isBusy()) return;
    await this._withBusy("queuing product", async () => {
      await this._hass.callService("mise_en_place_assistant", "add_to_shopping_list", {
        item_id: itemId,
        quantity: 1,
        description: "Queued from Mise product review; reason=missing_prep_item",
      });
      this._notice = `${label || "Product"} queued.`;
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not queue product.";
      this._render();
    });
  }

  async _runSuggestedService(button) {
    if (this._isBusy()) return;
    const service = button.dataset.suggestedService;
    if (!service) return;
    let payload = {};
    try {
      payload = JSON.parse(decodeURIComponent(button.dataset.suggestedPayload || "%7B%7D"));
    } catch (err) {
      this._error = "Suggested action payload is invalid.";
      this._render();
      return;
    }
    await this._withBusy(`running ${service.replaceAll("_", " ")}`, async () => {
      await this._hass.callService("mise_en_place_assistant", service, payload);
      this._notice = `${button.dataset.suggestedTitle || "Suggested action"} done.`;
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not run suggested action.";
      this._render();
    });
  }

  async _addShoppingItem(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    const payload = {
      quantity: Number(value("quantity") || 1),
    };
    if (value("item_id")) payload.item_id = value("item_id");
    if (value("name")) payload.name = value("name");
    if (value("description")) payload.description = value("description");
    await this._withBusy("adding shopping item", async () => {
      await this._hass.callService("mise_en_place_assistant", "add_to_shopping_list", payload);
      form.reset();
      this._notice = "Shopping item added.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not add shopping item.";
      this._render();
    });
  }

  async _copyOverview() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(this._data || {}, null, 2));
      this._notice = "Overview JSON copied.";
      this._render();
    } catch (err) {
      this._error = err?.message || "Could not copy overview JSON.";
      this._render();
    }
  }

  async _saveProductMetadata(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    await this._withBusy("saving product review", async () => {
      await this._hass.callService("mise_en_place_assistant", "update_product_metadata", {
        item_id: value("item_id"),
        container_policy: value("container_policy"),
        storage_behavior: value("storage_behavior"),
        meal_role: value("meal_role"),
        available_in_mealie: form.elements.available_in_mealie.checked,
      });
      this._notice = "Product review saved.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not save product metadata.";
      this._render();
    });
  }

  _readinessPanel(readiness = {}, compact = false) {
    const groups = [
      ["ready", "Ready"],
      ["missing", "Missing"],
      ["empty", "Empty"],
      ["unassigned", "Unassigned"],
      ["stale", "Stale"],
      ["location_at_risk", "Location at risk"],
    ];
    const sections = groups.map(([key, label]) => this._readinessSection(label, readiness[key] || [], compact)).join("");
    const log = readiness.recent_provider_action;
    return `<div class="readiness-grid">${sections}</div>${log ? `<p class="muted subline">Latest provider note: ${this._safe(log.action || "")}${log.message ? ` · ${this._safe(log.message)}` : ""}</p>` : ""}`;
  }

  _suggestedActionsPanel(actions = []) {
    return actions.length ? actions.map((action) => this._suggestedActionRow(action)).join("") : this._empty("No suggested actions right now.");
  }

  _suggestedActionRow(action) {
    const klass = action.status === "critical" ? "critical" : action.status === "ok" ? "ok" : action.status === "empty" ? "empty" : "warn";
    const payload = encodeURIComponent(JSON.stringify(action.payload || {}));
    const sources = (action.sources || []).map((source) => `<span class="pill">${this._safe(source)}</span>`).join("");
    const target = action.target ? `<p class="muted subline">Target: ${this._safe(action.target)}</p>` : "";
    const lastQueued = action.last_queued ? `<p class="muted subline">Last queued: ${this._safe(this._shoppingLogSummary(action.last_queued))}</p>` : "";
    const button = action.service
      ? `<button type="button" class="secondary" data-suggested-service="${this._safe(action.service)}" data-suggested-payload="${payload}" data-suggested-title="${this._safe(action.title)}">${this._safe(this._suggestedActionLabel(action))}</button>`
      : action.open_tab
        ? `<button type="button" class="secondary" data-suggested-tab="${this._safe(action.open_tab)}">Open review</button>`
        : "";
    return `<div class="row">
      <div>
        <p class="name ${klass}">${this._safe(action.title)}</p>
        <p class="muted subline">Because ${this._safe(action.because || "existing Mise data points here.")}</p>
        ${target}
        ${lastQueued}
        ${sources ? `<div class="actions">${sources}</div>` : ""}
      </div>
      <div class="actions">${button}</div>
    </div>`;
  }

  _shoppingLogSummary(log) {
    const target = log.targets && Object.keys(log.targets).length
      ? Object.entries(log.targets).map(([provider, count]) => `${provider}: ${count}`).join(", ")
      : log.provider || "";
    const count = log.item_count ? `${log.item_count} item${Number(log.item_count) === 1 ? "" : "s"}` : "";
    return [count, target, log.message].filter(Boolean).join(" · ");
  }

  _suggestedActionLabel(action) {
    const service = action.service || "";
    if (service.includes("shopping")) {
      return "Queue shopping";
    }
    if (service.includes("move")) {
      return "Move container";
    }
    if (service.includes("metadata") || service.includes("update")) {
      return "Save metadata";
    }
    if (service.includes("clear") || service.includes("archive")) {
      return "Clear/archive";
    }
    return "Run action";
  }

  _readinessSection(label, items, compact) {
    const rows = items.slice(0, compact ? 3 : 4).map((item) => this._readinessRow(item)).join("");
    return `<section class="readiness-section"><h3>${this._safe(label)} <span class="muted">${this._safe(items.length)}</span></h3>${rows || this._empty("None")}</section>`;
  }

  _readinessRow(item) {
    const status = item.status || "";
    const log = item.log?.action ? `<p class="muted subline">${this._safe(item.log.action)}</p>` : "";
    return `<div class="row compact-row">
      <div>
        <p class="name ${this._safe(status)}">${this._safe(item.label)}</p>
        <p class="muted subline">${this._safe(item.detail || item.reason || "")}</p>
        <p class="muted subline">${this._safe(item.reason || "")}</p>
        ${log}
      </div>
    </div>`;
  }

  _storageAttentionSummary(storageAttention = {}) {
    const count = storageAttention.attention_count || 0;
    const status = storageAttention.status || "ok";
    const label = storageAttention.status_label || this._storageStatusLabel(status, count);
    const parts = [
      `${storageAttention.containers_needing_location_count || 0} unassigned`,
      `${storageAttention.critical_locations_count || 0} critical`,
      `${storageAttention.warning_locations_count || 0} warning`,
      `${storageAttention.unhealthy_locations_count || 0} unhealthy locations`,
      `${storageAttention.prepared_inventory_at_risk_count || 0} prepared at risk`,
    ].join(" · ");
    return `<div class="row compact-row">
      <div>
        <p class="name ${this._safe(status === "critical" ? "critical" : count ? "warn" : "ok")}">${this._safe(label)}</p>
        <p class="muted subline">${this._safe(parts)}</p>
      </div>
    </div>`;
  }

  _storageStatusLabel(status, attentionCount = 0) {
    if (status === "critical") return "Storage attention critical";
    if (attentionCount) return "Storage attention needed";
    if (status === "unavailable") return "Storage monitoring unavailable";
    if (status === "unknown") return "Storage monitoring unavailable";
    return "Storage automation clear";
  }

  _planningFilterBar(containers) {
    const recipeContainers = containers.filter((container) => ["recipe", "meal"].includes(container.content_kind));
    const componentClasses = [...new Set(recipeContainers.map((container) => container.recipe?.component).filter(Boolean))].sort();
    const filters = [
      ["all", "All"],
      ["recipe", "Prepared batches"],
      ["meal", "Ready meals"],
      ["empty_recipe", "Zero quantity"],
      ...componentClasses.map((component) => [`component:${component}`, component]),
    ];
    return `<div class="filter-bar">${filters.map(([value, label]) => `<button type="button" class="${this._planningFilter === value ? "active" : "secondary"}" data-planning-filter="${this._safe(value)}">${this._safe(label)}</button>`).join("")}</div>`;
  }

  _filteredRecipeContainers(containers) {
    const recipeContainers = containers.filter((container) => ["recipe", "meal"].includes(container.content_kind));
    if (this._planningFilter === "recipe") {
      return recipeContainers.filter((container) => container.content_kind === "recipe");
    }
    if (this._planningFilter === "meal") {
      return recipeContainers.filter((container) => container.content_kind === "meal");
    }
    if (this._planningFilter === "empty_recipe") {
      return recipeContainers.filter((container) => this._quantityNumber(container) === 0);
    }
    if (this._planningFilter.startsWith("component:")) {
      const component = this._planningFilter.slice("component:".length);
      return recipeContainers.filter((container) => container.recipe?.component === component);
    }
    return recipeContainers;
  }

  _recipeContainerRow(container) {
    const recipe = container.recipe || {};
    const meta = [
      recipe.component ? `component: ${recipe.component}` : "",
      recipe.primary_protein ? `protein: ${recipe.primary_protein}` : "",
      recipe.yield_unit ? `yield: ${recipe.yield_unit}` : "",
    ].filter(Boolean).join(" · ");
    const taxonomy = [
      ...(recipe.tags || []).map((tag) => `#${tag}`),
      ...(recipe.categories || []).map((category) => category),
    ].join(" · ");
    const identity = [recipe.provider, recipe.id].filter(Boolean).join(" · ");
    return this._containerRow(container, "", [meta, taxonomy], identity ? [identity] : []);
  }

  _planningComparisonRow(entry) {
    const recipes = (entry.recipes || []).map((recipe) => `<p class="muted subline">${this._safe(recipe.label)}: ${this._safe(recipe.quantity)}</p>`).join("");
    const proteins = (entry.proteins || []).map((protein) => `<p class="muted subline">${this._safe(protein.label)}: ${this._safe(protein.quantity)}</p>`).join("");
    const stock = (entry.grocy_stock || []).map((item) => `<p class="muted subline">${this._safe(item.label)}: ${this._safe(item.quantity)}${item.containers ? `, ${this._safe(item.containers)} containers` : ""}</p>`).join("");
    const log = entry.log?.action ? `<p class="muted subline">Why: ${this._safe(entry.log.action)}${entry.log.message ? ` &middot; ${this._safe(entry.log.message)}` : ""}</p>` : "";
    return `<div class="row compact-row">
      <div>
        <p class="name">${this._safe(entry.component)}</p>
        <div class="compare-grid">
          <div>
            <p class="muted">Prepared</p>
            <p class="name ok">${this._safe(entry.prepared || "Ready")}</p>
            ${recipes || proteins || this._empty("No recipe details.")}
          </div>
          <div>
            <p class="muted">Grocy stock</p>
            ${stock || this._empty("No related Grocy stock found.")}
          </div>
        </div>
        ${log}
      </div>
    </div>`;
  }

  _attentionSummary(products, empty, low) {
    const rows = [
      ...products.slice(0, 4).map((item) => this._productAttentionSummaryRow(item)),
      ...empty.slice(0, 3).map((item) => this._containerRow(item, "empty")),
      ...low.slice(0, 3).map((item) => this._containerRow(item, "warn")),
    ];
    return rows.length ? rows.join("") : this._empty("Nothing needs attention.");
  }

  _productAttentionSummaryRow(item) {
    const quantity = item.has_stock ? `${this._safe(item.quantity)} ${this._safe(item.unit)}` : "No stock";
    return this._summaryRow(item.label, [`${quantity} · ${(item.reasons || []).join(", ")}`], { quantity: "Review", klass: "warn" });
  }

  _containerRow(item, klass = "", extraDetails = [], extraPills = [], action = "") {
    const title = item.name || item.item_label || "Container";
    const kind = item.content_kind || "empty";
    const itemLabel = item.item_label && item.item_label !== title ? `<span class="container-item">${this._safe(item.item_label)}</span>` : "";
    const details = [item.format, ...extraDetails].filter(Boolean).map((line) => `<p class="muted subline">${this._safe(line)}</p>`).join("");
    const pills = [item.tag_id || "no tag", ...extraPills].filter(Boolean).map((pill) => `<span class="pill">${this._safe(pill)}</span>`).join("");
    const attention = this._containerAttention(item).join("");
    return `<div class="row container-card kind-${this._safe(this._cssToken(kind))}">
      <div>
        <div class="container-titleline">
          <ha-icon icon="${this._contentKindIcon(kind)}"></ha-icon>
          <p class="name container-name"><span>${this._safe(title)}</span>${itemLabel}</p>
        </div>
        <div class="container-meta">
          ${this._contentKindChip(kind)}
          ${this._placeChip(item)}
          ${attention}
        </div>
        ${details}
        ${pills}
      </div>
      <div class="row-side"><div class="qty ${this._safe(klass)}">${this._safe(item.quantity)}${item.unit ? `<br><span class="muted">${this._safe(item.unit)}</span>` : ""}</div>${action ? `<div class="container-actions-line">${action}</div>` : ""}</div>
    </div>`;
  }

  _placeLabel(item) {
    return [item.location, item.sublocation].filter(Boolean).join(" / ");
  }

  _contentKindChip(contentKind) {
    const kind = contentKind || "empty";
    const labels = { ingredient: "Ingredient", recipe: "Recipe batch", meal: "Ready meal", empty: "Empty" };
    return `<span class="container-chip kind-${this._safe(this._cssToken(kind))}"><ha-icon icon="${this._contentKindIcon(kind)}"></ha-icon>${this._safe(labels[kind] || kind.replaceAll("_", " "))}</span>`;
  }

  _contentKindIcon(contentKind) {
    return {
      ingredient: "mdi:food-apple-outline",
      recipe: "mdi:chef-hat",
      meal: "mdi:silverware-fork-knife",
      empty: "mdi:package-variant",
    }[contentKind] || "mdi:package-variant";
  }

  _placeChip(item) {
    const place = this._placeLabel(item);
    return place ? `<span class="container-chip place"><ha-icon icon="mdi:map-marker-outline"></ha-icon>${this._safe(place)}</span>` : "";
  }

  _containerAttention(item) {
    const warnings = [];
    const quantity = this._quantityNumber(item);
    if (quantity === 0) {
      warnings.push(`<span class="attention-chip critical"><ha-icon icon="mdi:package-variant-closed-remove"></ha-icon>Empty</span>`);
    } else if (quantity <= 2) {
      warnings.push(`<span class="attention-chip"><ha-icon icon="mdi:alert"></ha-icon>Low stock</span>`);
    }
    const today = new Date().toISOString().slice(0, 10);
    if (item.best_before_date && String(item.best_before_date) < today) {
      warnings.push(`<span class="attention-chip critical"><ha-icon icon="mdi:calendar-alert"></ha-icon>Past best before</span>`);
    }
    return warnings;
  }

  _inventoryContainerRow(container, locations) {
    const dateLine = this._containerDateLine(container);
    const empty = this._quantityNumber(container) === 0;
    return `<div class="row compact-row">
      <div>
        ${this._containerRow(container, empty ? "empty" : "")}
        ${dateLine ? `<p class="muted subline">${dateLine}</p>` : ""}
        <form class="container-actions" data-adjust-container="${this._safe(container.tag_id)}">
          <label>Quantity<input name="quantity" required type="number" min="0.000001" step="any" /></label>
          <button type="submit" class="icon-button" name="action" value="fill" title="Add quantity" aria-label="Add quantity"><ha-icon icon="mdi:plus"></ha-icon></button>
          <button type="submit" class="icon-button" name="action" value="remove" title="Remove quantity" aria-label="Remove quantity"><ha-icon icon="mdi:minus"></ha-icon></button>
        </form>
        <div class="container-actions-line">
          <button type="button" class="icon-button danger" data-clear-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}" title="Clear container" aria-label="Clear container"><ha-icon icon="mdi:delete-sweep-outline"></ha-icon></button>
          ${empty ? `<button type="button" class="icon-button danger" data-archive-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}" title="Archive container" aria-label="Archive container"><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon></button>` : ""}
          ${this._moveSelect(container, locations)}
        </div>
      </div>
    </div>`;
  }

  _archivedContainerRow(container) {
    return this._summaryRow(
      container.name,
      [`${container.item_label || "Container"} · archived ${this._formatTime(container.archived_at)}`],
      {
        pills: [container.tag_id || "no tag"],
        action: `<button type="button" class="icon-button" data-restore-container="${this._safe(container.tag_id)}" title="Restore container" aria-label="Restore container"><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon></button>`,
      },
    );
  }

  _managedContainerRow(container, locations) {
    return this._containerRow(container, "", [], [], this._moveSelect(container, locations));
  }

  _moveSelect(container, locations) {
    const choices = locations.filter((location) => location.editable !== false).flatMap((location) => {
      const base = [`<option value="${this._safe(location.id)}||">${this._safe(location.name)}</option>`];
      return base.concat((location.sublocations || []).map((sublocation) => `<option value="${this._safe(location.id)}||${this._safe(sublocation)}">${this._safe(location.name)} / ${this._safe(sublocation)}</option>`));
    }).join("");
    return `<select data-move-tag="${this._safe(container.tag_id)}" title="Move container" aria-label="Move container"><option value="">Move...</option>${choices}</select>`;
  }

  _productAttentionRow(item) {
    const metadata = item.metadata || {};
    const containerPolicies = [
      ["unknown", "Choose policy"],
      ["container", "Container"],
      ["original_packaging", "Original packaging"],
      ["either", "Either"],
      ["no_container", "No container"],
    ];
    const storageBehaviors = [
      ["unknown", "Choose storage"],
      ["fridge", "Fridge"],
      ["freezer", "Freezer"],
      ["pantry", "Pantry"],
      ["dry_storage", "Dry storage"],
      ["cellar", "Cellar"],
      ["counter", "Counter"],
    ];
    const mealRoles = [
      ["unknown", "Choose role"],
      ["ingredient", "Ingredient"],
      ["staple", "Staple / par-managed"],
      ["condiment", "Condiment"],
      ["prepared_component", "Prepared component"],
      ["ignore", "Ignore"],
    ];
    const mealieChecked = metadata.available_in_mealie ? " checked" : "";
    const quantity = item.has_stock ? `${this._safe(item.quantity)} ${this._safe(item.unit)}` : "No stock";
    return `<form class="row review-row" data-product-metadata>
      <input type="hidden" name="item_id" value="${this._safe(item.item_id)}" />
      <div>
        <p class="name">${this._safe(item.label)}</p>
        <p class="muted subline">${quantity} &middot; ${this._safe((item.reasons || []).join(", "))}</p>
      </div>
      <div class="review-grid">
        <label>Container policy<select name="container_policy">${this._options(containerPolicies, metadata.container_policy || "unknown")}</select></label>
        <label>Expected storage<select name="storage_behavior">${this._options(storageBehaviors, metadata.storage_behavior || "unknown")}</select></label>
        <label>Meal role<select name="meal_role">${this._options(mealRoles, metadata.meal_role || "unknown")}</select></label>
        <label>Mealie recipes<span><input type="checkbox" name="available_in_mealie"${mealieChecked} /> Available in Mealie</span></label>
      </div>
      <div class="actions"><button type="submit" class="secondary">Save review</button><button type="button" class="secondary" data-queue-product="${this._safe(item.item_id)}" data-product-label="${this._safe(item.label)}">Queue missing prep</button></div>
    </form>`;
  }

  _shoppingStatus(shopping = {}) {
    const label = shopping.provider === "kitchenowl" ? "KitchenOwl" : shopping.provider === "grocy" ? "Grocy" : "Automatic";
    const productTarget = shopping.product_backed_target === "kitchenowl" ? "KitchenOwl" : "Grocy";
    const textTarget = shopping.free_text_target === "kitchenowl" ? "KitchenOwl" : "Grocy";
    return `<p class="name">${this._safe(label)}</p>
      <p class="muted subline">Products: ${this._safe(productTarget)} &middot; Text: ${this._safe(textTarget)}</p>
      <p class="muted subline">Grocy ${shopping.grocy_configured ? "connected" : "not configured"} &middot; KitchenOwl ${shopping.kitchenowl_configured ? "connected" : "not configured"}</p>
      <div class="actions" style="margin-top: 10px;">
        ${shopping.grocy_minimum_stock ? `<button type="button" class="secondary" data-sync-missing-products>Queue Grocy minimum stock</button>` : ""}
        <button type="button" class="secondary" data-queue-empty-containers>Queue empty containers</button>
      </div>`;
  }

  _shoppingItemForm(foods) {
    const foodOptions = foods.map((food) => `<option value="${this._safe(food.id)}">${this._safe(food.label)}</option>`).join("");
    return `<form id="shopping-item-form">
      <div class="form-grid">
        <label>Catalog product<select name="item_id"><option value="">Free text item</option>${foodOptions}</select></label>
        <label>Name<input name="name" placeholder="Milk" /></label>
        <label>Quantity<input name="quantity" required type="number" min="0.000001" step="any" value="1" /></label>
        <label>Description<input name="description" placeholder="Optional note" /></label>
      </div>
      <div class="actions"><button type="submit">Add to shopping list</button></div>
    </form>`;
  }

  _mealInventoryRow(entry) {
    const formatTotals = (totals) => Object.entries(totals || {}).map(([unit, amount]) => `${amount} ${unit}`).join(" + ");
    const proteins = Object.entries(entry.proteins || {}).map(([name, totals]) => `${name}: ${formatTotals(totals)}`).join(" · ");
    const recipes = Object.entries(entry.recipes || {}).map(([name, totals]) => `${name}: ${formatTotals(totals)}`).join(" · ");
    const quantities = Object.entries(entry.quantities || {}).map(([unit, amount]) => `${amount} ${unit}`).join(" + ");
    return this._summaryRow(entry.component, [proteins || recipes], { quantity: quantities });
  }

  _summaryRow(title, detailLines = [], options = {}) {
    const details = detailLines.filter(Boolean).map((line) => `<p class="muted subline">${this._safe(line)}</p>`).join("");
    const pills = (options.pills || []).filter(Boolean).map((pill) => `<span class="pill">${this._safe(pill)}</span>`).join("");
    const quantity = options.quantity !== undefined && options.quantity !== null && options.quantity !== ""
      ? `<div class="qty ${this._safe(options.klass || "")}">${this._safe(options.quantity)}${options.unit ? `<br><span class="muted">${this._safe(options.unit)}</span>` : ""}</div>`
      : "";
    const action = options.action ? `<div class="actions">${options.action}</div>` : "";
    const side = [quantity, action].filter(Boolean).join("");
    return `<div class="row">
      <div>
        <p class="name">${this._safe(title)}</p>
        ${details}
        ${pills}
      </div>
      ${side ? `<div class="row-side">${side}</div>` : ""}
    </div>`;
  }

  _locationCard(location, containers = [], locations = [], selected = false) {
    const health = location.health || {};
    const readings = Object.entries(health.readings || {}).map(([role, reading]) => `<div class="reading"><strong>${this._safe(role.replaceAll("_", " "))}</strong><br>${this._safe(reading.state)}${reading.unit ? ` ${this._safe(reading.unit)}` : ""}</div>`).join("");
    const sublocations = (location.sublocations || []).map((sublocation) => `<span class="pill">${this._safe(sublocation)}</span>`).join("");
    const contents = selected ? this._locationContents(location, containers, locations) : "";
    const monitoring = selected ? this._locationMonitoring(health, readings) : "";
    const problems = selected && health.problems?.length ? `<p class="muted subline">${this._safe(health.problems.join(" · "))}</p>` : "";
    const removeButton = location.provider === "mocked" && location.local
      ? `<button class="icon-button danger" data-delete-location="${this._safe(location.id)}" data-location-name="${this._safe(location.name)}" data-location-provider="${this._safe(location.provider || "")}" data-location-local="true" title="Remove location" aria-label="Remove location"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>`
      : "";
    const locationType = location.location_type || "other";
    const contentAttention = this._locationContentAttention(location, containers);
    const selectButton = selected ? "" : `<button class="icon-button" data-select-location="${this._safe(location.id)}" title="View containers" aria-label="View containers"><ha-icon icon="mdi:format-list-bulleted"></ha-icon></button>`;
    const selectedChip = selected ? `<span class="location-chip selected-chip"><ha-icon icon="mdi:check-circle"></ha-icon><span>Selected</span></span>` : "";
    const actions = location.editable !== false ? `<div class="location-card-actions">${selectButton}<button class="icon-button" data-edit-location="${this._safe(location.id)}" title="Edit location" aria-label="Edit location"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>${removeButton}</div>` : `<div class="location-card-actions">${selectButton}</div>`;
    return `<article class="card location-card type-${this._safe(this._cssToken(locationType))}${selected ? " selected" : ""}">
      <div class="location-card-header">
        <div>
          <div class="location-card-title">
            <ha-icon icon="${this._locationTypeIcon(locationType)}"></ha-icon>
            <h2>${this._safe(location.name)}</h2>
          </div>
          <div class="location-card-meta">
            <span class="location-chip"><span class="location-type">${this._safe(locationType.replaceAll("_", " "))}</span></span>
            ${this._locationArea(location)}
            ${contentAttention}
            ${selectedChip}
            ${sublocations}
          </div>
        </div>
        <div class="location-count"><strong>${this._safe(location.containers)}</strong><span>containers</span>${actions}</div>
      </div>
      <div class="location-card-body">
        ${monitoring}
        ${problems}
        ${contents}
      </div>
    </article>`;
  }

  _locationArea(location) {
    if (!location.area_name) {
      return "";
    }
    const icon = location.area_icon || "mdi:floor-plan";
    return `<span class="location-chip"><ha-icon icon="${this._safe(icon)}"></ha-icon><span>${this._safe(location.area_name)}</span></span>`;
  }

  _locationTypeIcon(locationType) {
    return {
      fridge: "mdi:fridge-outline",
      freezer: "mdi:snowflake",
      pantry: "mdi:food-variant",
      dry_storage: "mdi:archive-outline",
      cellar: "mdi:home-floor-b",
      counter: "mdi:countertop-outline",
    }[locationType] || "mdi:map-marker-outline";
  }

  _locationContentAttention(location, containers) {
    const count = containers.filter((container) => (
      container.location_id === location.id && this._containerAttention(container).length
    )).length;
    if (!count) {
      return "";
    }
    const label = count === 1 ? "1 item needs attention" : `${count} items need attention`;
    return `<span class="attention-chip"><ha-icon icon="mdi:alert"></ha-icon>${this._safe(label)}</span>`;
  }

  _locationMonitoring(health, readings) {
    if (health.status === "not_configured" || !readings) {
      return "";
    }
    const status = health.status || "unknown";
    const icon = status === "critical" ? "mdi:alert-circle" : status === "warning" ? "mdi:alert" : status === "ok" ? "mdi:check-circle" : "mdi:help-circle";
    const attentionCount = ["warning", "critical"].includes(status) ? 1 : 0;
    const label = this._storageStatusLabel(status, attentionCount);
    return `<section class="monitoring-panel"><div class="monitoring-status ${this._safe(status)}"><ha-icon icon="${icon}"></ha-icon><span>${this._safe(label)}</span></div><div class="reading-grid">${readings}</div></section>`;
  }

  _locationContents(location, containers, locations = []) {
    const matching = containers
      .filter((container) => container.location_id === location.id)
      .sort((a, b) => [
        (a.sublocation || "").localeCompare(b.sublocation || ""),
        (a.item_label || a.name || "").localeCompare(b.item_label || b.name || ""),
        (a.name || "").localeCompare(b.name || ""),
      ].find((result) => result !== 0) || 0);
    if (!matching.length) {
      return `<div class="location-contents">${this._empty("No containers in this location.")}</div>`;
    }
    const groups = new Map();
    for (const container of matching) {
      const sublocation = container.sublocation || "Main";
      if (!groups.has(sublocation)) {
        groups.set(sublocation, []);
      }
      groups.get(sublocation).push(container);
    }
    const sections = Array.from(groups.entries()).map(([sublocation, items]) => `
      <section class="content-group">
        <h3>${this._safe(sublocation)}</h3>
        ${items.map((item) => this._locationContentRow(item, locations)).join("")}
      </section>
    `).join("");
    return `<div class="location-contents">${sections}</div>`;
  }

  _locationContentRow(container, locations = []) {
    return locations.length ? this._managedContainerRow(container, locations) : this._containerRow(container);
  }

  _locationRow(location) {
    const health = location.health || {};
    const problems = health.problems?.length ? ` &middot; ${health.problems.join(" · ")}` : "";
    return `<div class="location"><span>${this._safe(location.name)}<br><small class="muted">${this._safe(location.location_type || "location")}${location.area_name ? ` &middot; ${this._safe(location.area_name)}` : ""}${this._safe(problems)}</small></span><strong class="${this._safe(health.status || "")}">${this._safe(location.containers)}</strong></div>`;
  }

  _itemRow(item) {
    const places = Object.keys(item.locations || {}).join(" · ");
    const amount = item.quantity ?? Object.entries(item.quantities || {}).map(([unit, quantity]) => `${quantity} ${unit}`).join(" + ");
    const containers = (item.physical_containers || []).map((container) => `${container.name}: ${container.quantity} ${container.unit} @ ${this._placeLabel(container)}`).join(" · ");
    const freshness = (item.freshness_dates || []).map((entry) => {
      const dates = [
        entry.best_before_date ? `best before ${entry.best_before_date}` : "",
        entry.opened_date ? `opened ${entry.opened_date}` : "",
        entry.purchased_date ? `purchased ${entry.purchased_date}` : "",
        entry.price ? `price ${entry.price}` : "",
      ].filter(Boolean).join(", ");
      return dates ? `${entry.container}: ${dates}` : "";
    }).filter(Boolean).join(" · ");
    const stockLabel = item.source === "grocy" ? "Grocy stock" : "Mise containers";
    const lastStock = item.last_stock_log?.action ? `${item.last_stock_log.action}: ${item.last_stock_log.message || ""}` : "";
    return `<div class="row">
      <div>
        <p class="name">${this._safe(item.label)}</p>
        <p class="muted subline">${this._safe(stockLabel)} &middot; ${this._safe(places || "Unassigned")}</p>
        ${containers ? `<p class="muted subline">Mise: ${this._safe(containers)}</p>` : ""}
        ${freshness ? `<p class="muted subline">Dates: ${this._safe(freshness)}</p>` : ""}
        ${lastStock ? `<p class="muted subline">Last stock write: ${this._safe(lastStock)}</p>` : ""}
      </div>
      <div class="qty">${this._safe(amount)}${item.unit ? `<br><span class="muted">${this._safe(item.unit)}</span>` : ""}</div>
    </div>`;
  }

  _logRow(entry) {
    return `
      <div class="log">
        <div>
          <p class="log-action">${this._safe(entry.action)}</p>
          <p class="muted subline">${this._safe(entry.message)}</p>
        </div>
        <time class="log-time">${this._formatTime(entry.created_at)}</time>
      </div>
    `;
  }

  _containerDateLine(container) {
    const dates = [
      ["Best before", container.best_before_date],
      ["Purchased", container.purchased_date],
      ["Opened", container.opened_date],
    ].filter(([, value]) => value);
    return dates.map(([label, value]) => `${label}: ${this._safe(value)}`).join(" · ");
  }

  _quantityNumber(container) {
    const quantity = Number(container.canonical_quantity ?? container.quantity ?? 0);
    return Number.isFinite(quantity) ? quantity : 0;
  }

  _options(options, current) {
    return options.map(([value, label]) => `<option value="${this._safe(value)}"${value === current ? " selected" : ""}>${this._safe(label)}</option>`).join("");
  }

  _entitySelect(name, current, domains) {
    const currentValue = current || "";
    const entities = (this._data?.entities || []).filter((entity) => domains.includes(entity.domain));
    const seen = new Set();
    const options = entities.map((entity) => {
      seen.add(entity.entity_id);
      const label = entity.name && entity.name !== entity.entity_id ? `${entity.name} (${entity.entity_id})` : entity.entity_id;
      return `<option value="${this._safe(entity.entity_id)}"${entity.entity_id === currentValue ? " selected" : ""}>${this._safe(label)}</option>`;
    });
    if (currentValue && !seen.has(currentValue)) {
      options.unshift(`<option value="${this._safe(currentValue)}" selected>${this._safe(currentValue)} (currently saved)</option>`);
    }
    return `<select name="${this._safe(name)}"><option value="">None</option>${options.join("")}</select>`;
  }

  _empty(message) {
    return `<p class="state">${this._safe(message)}</p>`;
  }

  _emptyCard(message) {
    return `<section class="card">${this._empty(message)}</section>`;
  }

  _isBusy() {
    return Boolean(this._busyAction);
  }

  _applyBusyState() {
    if (!this._isBusy()) {
      return;
    }
    this.shadowRoot.querySelectorAll("button, input, select, textarea").forEach((control) => {
      control.disabled = true;
    });
  }

  async _withBusy(label, action, onError) {
    if (this._isBusy()) {
      return;
    }
    this._busyAction = label;
    this._render();
    try {
      await action();
    } catch (err) {
      onError?.(err);
    } finally {
      this._busyAction = "";
      if (this._connected) {
        this._render();
      }
    }
  }

  _formatTime(value) {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return this._safe(value);
    }
    return this._safe(date.toLocaleString());
  }

  _safe(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  _cssToken(value) {
    return String(value || "other").toLowerCase().replace(/[^a-z0-9_-]/g, "_") || "other";
  }
}

if (!customElements.get("mise_en_place_assistant-panel")) {
  customElements.define("mise_en_place_assistant-panel", MiseEnPlaceAssistantPanel);
}
