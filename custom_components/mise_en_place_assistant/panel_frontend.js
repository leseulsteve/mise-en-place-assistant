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
    return ["dashboard", "inventory", "storage", "planning", "dev"].includes(tab) ? tab : "dashboard";
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
      ["dev", "Dev"],
    ];
    const body = this._tab === "dev"
      ? this._devView(data)
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
        .name { font-weight: 650; overflow-wrap: anywhere; }
        .subline { margin-top: 3px; }
        .readiness-card { margin-bottom: 18px; }
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
        .qty { font-weight: 750; text-align: right; white-space: nowrap; }
        .container-actions {
          display: grid;
          grid-template-columns: minmax(110px, 1fr) auto auto;
          gap: 8px;
          align-items: end;
          margin-top: 10px;
        }
        .health { margin-top: 9px; font-weight: 650; }
        .reading-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top:12px; }
        .reading { background: var(--secondary-background-color, rgba(128,128,128,.08)); border-radius: 8px; padding: 8px; font-size: 13px; }
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
          .readiness-grid { grid-template-columns: 1fr; }
          .compare-grid { grid-template-columns: 1fr; }
          .form-grid, .review-grid, .inline-grid, .debug-grid, .container-actions { grid-template-columns: 1fr; }
          .row { grid-template-columns: 1fr; }
          .qty { text-align: left; }
        }
      </style>
      <main>
        <header>
          <div>
            <h1>Mise en Place Assistant</h1>
            <p class="muted">${data ? `Updated ${new Date().toLocaleTimeString()}` : "Loading overview..."}</p>
          </div>
          <div class="actions">
            <button type="button" id="refresh">Refresh</button>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._safe(this._error)}</div>` : ""}
        ${this._notice ? `<div class="notice">${this._safe(this._notice)}</div>` : ""}
        <nav class="tabs">${tabs.map(([id, label]) => `<button type="button" class="${this._tab === id ? "active" : "secondary"}" data-tab="${id}">${label}</button>`).join("")}</nav>
        ${this._busyAction ? `<p class="busy">Working: ${this._safe(this._busyAction)}</p>` : ""}
        ${this._opsStrip(summary, operations, data?.shopping, data?.storage_attention)}
        ${body}
      </main>
    `;
    this._wireEvents();
  }

  _wireEvents() {
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => this._load());
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
      <section class="card readiness-card">
        <div class="toolbar"><h2>Readiness</h2><button type="button" class="secondary" data-open-tab="planning">Planning</button></div>
        ${this._readinessPanel(readiness)}
      </section>
      <section class="card readiness-card">
        <div class="toolbar"><h2>Suggested next actions</h2><button type="button" class="secondary" data-open-tab="planning">Planning</button></div>
        ${this._suggestedActionsPanel(suggestedActions)}
      </section>
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
    return `
      ${this._showLocation ? this._locationForm(areas, editingLocation || null) : ""}
      ${this._showCreate ? this._createForm(editableLocations, foods, recipes) : ""}
      <section class="sections">
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Storage locations</h2><button type="button" id="add-location">Add location</button></div>
          </section>
          ${locations.map((location) => this._locationCard(location)).join("") || this._emptyCard("Create storage locations in Grocy, or enable DEV mode for mocked locations.")}
        </div>
        <div class="stack">
          <section class="card">
            <div class="toolbar"><h2>Containers</h2><button type="button" id="add-container">Add container</button></div>
            ${containers.map((container) => this._managedContainerRow(container, locations)).join("") || this._empty("No containers.")}
          </section>
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

  _opsStrip(summary, operations, shopping = {}, storageAttention = {}) {
    const providers = (operations.catalog_providers || []).join(" + ") || "none";
    const health = operations.health || {};
    const badHealth = storageAttention.attention_count ?? ((health.warning || 0) + (health.critical || 0));
    const mode = operations.dev_mode ? "DEV" : "Live";
    const shoppingProvider = shopping.provider || operations.shopping_provider || "auto";
    const productTarget = shopping.product_backed_target || "grocy";
    const textTarget = shopping.free_text_target || "grocy";
    const minimumStock = shopping.grocy_minimum_stock ? "minimum stock available" : "minimum stock unavailable";
    return `<section class="ops-strip">
      <div class="ops-card"><strong>Catalog: ${this._safe(mode)}</strong><span>${this._safe(providers)}</span></div>
      <div class="ops-card"><strong>Catalog size</strong><span>${this._safe(summary.foods ?? 0)} foods / ${this._safe(summary.recipes ?? 0)} recipes</span></div>
      <div class="ops-card"><strong class="${badHealth ? "warn" : "ok"}">Storage alerts: ${this._safe(badHealth)}</strong><span>${this._safe(storageAttention.unhealthy_locations_count ?? 0)} unhealthy locations</span></div>
      <div class="ops-card"><strong>Shopping: ${this._safe(shoppingProvider)}</strong><span>Products: ${this._safe(productTarget)} · Text: ${this._safe(textTarget)} · ${this._safe(minimumStock)}</span></div>
    </section>`;
  }

  _createForm(locations, foods, recipes) {
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}">${this._safe(location.name)}</option>`).join("");
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
      </div></div>
      <div class="form-section"><h3>Monitoring sensors</h3><div class="form-grid">
        <label>Temperature sensor<input name="temperature" placeholder="sensor.freezer_temperature" value="${this._safe(sensors.temperature || "")}" /></label>
        <label>Humidity sensor<input name="humidity" placeholder="sensor.freezer_humidity" value="${this._safe(sensors.humidity || "")}" /></label>
        <label>Door sensor<input name="door" placeholder="binary_sensor.freezer_door" value="${this._safe(sensors.door || "")}" /></label>
        <label>Power sensor<input name="power" placeholder="sensor.freezer_power" value="${this._safe(sensors.power || "")}" /></label>
        <label>Appliance plug<input name="power_switch" placeholder="switch.freezer_plug" value="${this._safe(sensors.power_switch || "")}" /></label>
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
    if (value("power_switch")) monitoring.power_required = true;
    const locationId = value("location_id");
    await this._withBusy("saving location", async () => {
      await this._hass.callService(
        "mise_en_place_assistant",
        locationId ? "update_location" : "create_location",
        { ...(locationId ? { location_id: locationId } : {}), name: value("name"), location_type: value("location_type"), ...(value("area_id") ? { area_id: value("area_id") } : {}), sensors, monitoring },
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

  async _moveContainer(tagId, locationId) {
    if (!locationId || this._isBusy()) return;
    await this._withBusy("moving container", async () => {
      await this._hass.callService("mise_en_place_assistant", "move_container", { tag_id: tagId, location_id: locationId });
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
    const button = action.service
      ? `<button type="button" class="secondary" data-suggested-service="${this._safe(action.service)}" data-suggested-payload="${payload}" data-suggested-title="${this._safe(action.title)}">Run</button>`
      : action.open_tab
        ? `<button type="button" class="secondary" data-suggested-tab="${this._safe(action.open_tab)}">Review</button>`
        : "";
    return `<div class="row">
      <div>
        <p class="name ${klass}">${this._safe(action.title)}</p>
        <p class="muted subline">Because ${this._safe(action.because || "existing Mise data points here.")}</p>
      </div>
      <div class="actions">${button}</div>
    </div>`;
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
    const parts = [
      `${storageAttention.containers_needing_location_count || 0} unassigned`,
      `${storageAttention.unhealthy_locations_count || 0} unhealthy locations`,
      `${storageAttention.prepared_inventory_at_risk_count || 0} prepared at risk`,
    ].join(" · ");
    return `<div class="row compact-row">
      <div>
        <p class="name ${this._safe(status === "critical" ? "critical" : count ? "warn" : "ok")}">${count ? "Storage attention needed" : "Storage automation clear"}</p>
        <p class="muted subline">${this._safe(parts)}</p>
      </div>
    </div>`;
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
    return `<div class="row">
      <div>
        <p class="name">${this._safe(container.item_label)}</p>
        <p class="muted subline">${this._safe(container.content_kind)} &middot; ${this._safe(container.location)}</p>
        ${meta ? `<p class="muted subline">${this._safe(meta)}</p>` : ""}
        ${taxonomy ? `<p class="muted subline">${this._safe(taxonomy)}</p>` : ""}
        ${identity ? `<span class="pill">${this._safe(identity)}</span>` : ""}
      </div>
      <div class="qty">${this._safe(container.quantity)}<br><span class="muted">${this._safe(container.unit)}</span></div>
    </div>`;
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
    return `<div class="row"><div><p class="name">${this._safe(item.label)}</p><p class="muted subline">${quantity} &middot; ${this._safe((item.reasons || []).join(", "))}</p></div><div class="qty warn">Review</div></div>`;
  }

  _containerRow(item, klass = "") {
    const details = [item.content_kind, item.item_label, item.location].filter(Boolean).join(" · ");
    return `
      <div class="row">
        <div>
          <p class="name">${this._safe(item.name)}</p>
          <p class="muted subline">${this._safe(details)}</p>
          ${item.format ? `<p class="muted subline">${this._safe(item.format)}</p>` : ""}
          <span class="pill">${this._safe(item.tag_id || "no tag")}</span>
        </div>
        <div class="qty ${klass}">${this._safe(item.quantity)}<br><span class="muted">${this._safe(item.unit)}</span></div>
      </div>
    `;
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
          <button type="submit" class="secondary" name="action" value="fill">Add</button>
          <button type="submit" class="secondary" name="action" value="remove">Remove</button>
        </form>
        <div class="actions">
          <button type="button" class="secondary" data-clear-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}">Clear</button>
          ${empty ? `<button type="button" class="secondary" data-archive-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}">Archive</button>` : ""}
          ${this._moveSelect(container, locations)}
        </div>
      </div>
    </div>`;
  }

  _archivedContainerRow(container) {
    return `<div class="row"><div><p class="name">${this._safe(container.name)}</p><p class="muted">${this._safe(container.item_label)} &middot; archived ${this._formatTime(container.archived_at)}</p><span class="pill">${this._safe(container.tag_id || "no tag")}</span></div><button type="button" class="secondary" data-restore-container="${this._safe(container.tag_id)}">Restore</button></div>`;
  }

  _managedContainerRow(container, locations) {
    return `<div class="row"><div><p class="name">${this._safe(container.name)}</p><p class="muted">${this._safe(container.item_label)} &middot; ${this._safe(container.location)}</p><p class="muted">${this._safe(container.quantity)} ${this._safe(container.unit)}</p></div><div>${this._moveSelect(container, locations)}</div></div>`;
  }

  _moveSelect(container, locations) {
    const choices = locations.filter((location) => location.editable !== false).map((location) => `<option value="${this._safe(location.id)}">${this._safe(location.name)}</option>`).join("");
    return `<select data-move-tag="${this._safe(container.tag_id)}"><option value="">Move to...</option>${choices}</select>`;
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
    return `<div class="row"><div><p class="name">${this._safe(entry.component)}</p><p class="muted subline">${this._safe(proteins || recipes)}</p></div><div class="qty">${this._safe(quantities)}</div></div>`;
  }

  _locationCard(location) {
    const health = location.health || {};
    const readings = Object.entries(health.readings || {}).map(([role, reading]) => `<div class="reading"><strong>${this._safe(role.replaceAll("_", " "))}</strong><br>${this._safe(reading.state)}${reading.unit ? ` ${this._safe(reading.unit)}` : ""}</div>`).join("");
    const problems = health.problems?.length ? health.problems.join(" · ") : health.status === "ok" ? "Everything looks normal" : "Monitoring is not configured";
    const deleteLabel = location.provider === "mocked" && location.local ? "Remove" : "Clear metadata";
    return `<article class="card"><div class="toolbar"><div><h2>${this._safe(location.name)}</h2><p class="muted subline">${this._safe(location.location_type?.replaceAll("_", " ") || "location")}${location.area_name ? ` &middot; ${this._safe(location.area_name)}` : ""}</p></div>${location.editable !== false ? `<div class="actions"><button class="secondary" data-edit-location="${this._safe(location.id)}">Edit</button><button class="secondary" data-delete-location="${this._safe(location.id)}" data-location-name="${this._safe(location.name)}" data-location-provider="${this._safe(location.provider || "")}" data-location-local="${location.local ? "true" : "false"}">${deleteLabel}</button></div>` : ""}</div><p class="metric">${this._safe(location.containers)} <span class="muted">containers</span></p><p class="health ${this._safe(health.status || "")}">${this._safe(problems)}</p>${readings ? `<div class="reading-grid">${readings}</div>` : ""}</article>`;
  }

  _locationRow(location) {
    const health = location.health || {};
    const problems = health.problems?.length ? ` &middot; ${health.problems.join(" · ")}` : "";
    return `<div class="location"><span>${this._safe(location.name)}<br><small class="muted">${this._safe(location.location_type || "location")}${location.area_name ? ` &middot; ${this._safe(location.area_name)}` : ""}${this._safe(problems)}</small></span><strong class="${this._safe(health.status || "")}">${this._safe(location.containers)}</strong></div>`;
  }

  _itemRow(item) {
    const places = Object.keys(item.locations || {}).join(" · ");
    const amount = item.quantity ?? Object.entries(item.quantities || {}).map(([unit, quantity]) => `${quantity} ${unit}`).join(" + ");
    const containers = (item.physical_containers || []).map((container) => `${container.name}: ${container.quantity} ${container.unit} @ ${container.location}`).join(" · ");
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

  _empty(message) {
    return `<p class="muted">${this._safe(message)}</p>`;
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
}

if (!customElements.get("mise_en_place_assistant-panel")) {
  customElements.define("mise_en_place_assistant-panel", MiseEnPlaceAssistantPanel);
}
