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
    this._selectedSublocation ??= "";
    this._createContainerLocation ??= "";
    this._containerContentKind ??= "ingredient";
    this._editingContainerTag ??= "";
    this._movingContainerTag ??= "";
    this._moveContainerLocation ??= "";
    this._busyAction ??= "";
    this._planningFilter ??= "all";
    this._inventoryFilters ??= { category: "all", source: "all", location: "all" };
    this._inventoryPage ??= 1;
    this._inventoryPageSize ??= 10;
    this._readyMealPage ??= 1;
    this._mealPlanCount ??= 1;
    this._tvDinnerCount ??= 1;
    this._tvDinnerPlan ??= null;
    this._mealPrepSummaryDraft ??= "";
    this._selectedPrepSessionId ??= "";
    this._prepRecipeSelection ??= {};
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
      this._data = await this._hass.callWS({ type: "mise_en_place_assistant/overview", meal_count: this._mealPlanCount || 1 });
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
    return ["dashboard", "inventory", "storage", "planning", "tv-dinner", "meal-prep", "attention", "info", "dev"].includes(tab) ? tab : "dashboard";
  }

  _render() {
    const data = this._data;
    if (!this.shadowRoot) {
      return;
    }
    this._tab = this._normalizeTab(this._tab);
    const summary = data?.summary || {};
    const containers = data?.containers || [];
    const items = data?.items || [];
    const foods = data?.foods || [];
    const recipes = data?.recipes || [];
    const mealInventory = data?.meal_inventory?.components || [];
    const areas = data?.areas || [];
    const locations = data?.locations || [];
    const logbook = data?.logbook || [];
    const operations = data?.operations || {};
    const mealPrep = data?.meal_prep || {};
    const tabs = [
      ["dashboard", "Dashboard"],
      ["inventory", "Inventory"],
      ["storage", "Storage"],
      ["planning", "Planning"],
      ["tv-dinner", "Tv dinner"],
      ["meal-prep", "Meal Prep"],
      ["attention", "Attention"],
      ["info", "Info"],
      ["dev", "Dev"],
    ];
    const body = this._tab === "dev"
      ? this._devView(data)
      : this._tab === "info"
        ? this._infoView(data)
        : this._tab === "attention"
          ? this._attentionView(data)
          : this._tab === "meal-prep"
            ? this._mealPrepView(mealPrep, data)
            : this._tab === "tv-dinner"
              ? this._tvDinnerView(data)
              : this._tab === "planning"
                ? this._planningView(mealInventory, data, foods, logbook)
                : this._tab === "storage"
                  ? this._storageView(locations, containers, foods, recipes, areas)
                  : this._tab === "inventory"
                    ? this._inventoryView(items, containers, locations)
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
        .ops-strip.triple { grid-template-columns: repeat(3, minmax(0, 1fr)); }
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
        .ops-card.critical {
          border-color: rgba(244, 67, 54, 0.44);
          background: rgba(244, 67, 54, 0.10);
        }
        .ops-card.warning {
          border-color: rgba(255, 152, 0, 0.44);
          background: rgba(255, 152, 0, 0.10);
        }
        .ops-card.ok {
          border-color: rgba(67, 160, 71, 0.35);
          background: rgba(67, 160, 71, 0.08);
        }
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
        .prep-quantity { width: 72px; }
        .meal-selector {
          min-width: 0;
        }
        .meal-stepper {
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .meal-stepper output {
          min-width: 38px;
          height: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-weight: 750;
        }
        .meal-transfer {
          display: flex;
          gap: 8px;
          align-items: end;
          flex-wrap: wrap;
          margin-top: 10px;
        }
        .meal-transfer label {
          min-width: 170px;
        }
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
        .inventory-controls {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          margin-bottom: 12px;
        }
        .pager {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
        }
        .pager .actions { margin-left: auto; }
        .table-wrap {
          width: 100%;
          overflow-x: auto;
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
          overflow: hidden;
          padding: 0;
          background: var(--card-background-color);
        }
        .location-card:not(.selected) {
          cursor: pointer;
        }
        .location-card.selected {
          border-color: var(--primary-color);
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .location-card-header {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: start;
          padding: 14px 15px 12px;
          border-bottom: 1px solid var(--divider-color);
        }
        .location-card-title {
          display: flex;
          align-items: center;
          gap: 9px;
          min-width: 0;
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
          border: 1px solid var(--divider-color);
          border-radius: 999px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          padding: 4px 8px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
        }
        .location-chip ha-icon { --mdc-icon-size: 15px; color: var(--primary-color); }
        .location-card .location-type {
          color: var(--primary-text-color);
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
          border: 1px solid var(--divider-color);
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          color: var(--primary-color);
          padding: 0;
        }
        .icon-button.danger {
          --card-accent: var(--error-color, #f44336);
        }
        .icon-button ha-icon { --mdc-icon-size: 18px; }
        .location-card-body { padding: 12px 15px 15px; }
        .storage-layout {
          display: grid;
          grid-template-columns: minmax(320px, 0.42fr) minmax(0, 0.58fr);
          gap: 14px;
          align-items: start;
        }
        .storage-left {
          display: grid;
          gap: 12px;
        }
        .storage-detail {
          position: sticky;
          top: 16px;
          max-height: calc(100vh - 120px);
          overflow: auto;
        }
        .storage-detail-header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
          margin-bottom: 12px;
        }
        .storage-detail-title {
          display: flex;
          gap: 10px;
          align-items: center;
          min-width: 0;
        }
        .storage-detail-title ha-icon {
          color: var(--primary-color);
          --mdc-icon-size: 24px;
          flex: 0 0 auto;
        }
        .sublocation-list {
          display: grid;
          gap: 7px;
        }
        .sublocation-button {
          width: 100%;
          display: flex;
          justify-content: space-between;
          gap: 8px;
          align-items: center;
          border: 1px solid var(--divider-color);
          background: var(--secondary-background-color, rgba(128,128,128,.04));
          color: var(--primary-text-color);
          text-align: left;
        }
        .sublocation-button.active {
          border-color: var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 10%, var(--card-background-color));
        }
        .sublocation-button span {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 750;
        }
        .location-overview {
          display: grid;
          gap: 10px;
          margin-bottom: 12px;
        }
        .location-facts {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }
        .location-fact {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--secondary-background-color, rgba(128,128,128,.04));
          padding: 9px 10px;
          min-width: 0;
        }
        .location-fact span {
          display: block;
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 750;
          text-transform: uppercase;
        }
        .location-fact strong {
          display: block;
          margin-top: 3px;
          color: var(--primary-text-color);
          font-size: 13px;
          overflow-wrap: anywhere;
        }
        .location-problems {
          display: flex;
          align-items: flex-start;
          gap: 7px;
          border: 1px solid rgba(255, 152, 0, 0.38);
          border-radius: 8px;
          background: rgba(255, 152, 0, 0.10);
          color: var(--primary-text-color);
          padding: 9px 10px;
          font-size: 13px;
          font-weight: 650;
        }
        .location-problems ha-icon { --mdc-icon-size: 18px; color: var(--warning-color, #ff9800); }
        .container-card {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          padding: 10px 11px;
        }
        .container-card.row { border-top: 1px solid var(--divider-color); }
        .container-card + .container-card { margin-top: 8px; }
        .container-card .row-side { align-self: stretch; align-content: space-between; }
        .container-titleline {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }
        .container-titleline > ha-icon {
          color: var(--primary-color);
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
          border: 1px solid var(--divider-color);
          border-radius: 999px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          padding: 3px 8px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
        }
        .container-chip ha-icon { --mdc-icon-size: 15px; }
        .container-chip.place ha-icon { color: var(--primary-color); }
        .container-chip.state-active ha-icon { color: var(--success-color, #43a047); }
        .container-chip.state-deleted {
          border-color: rgba(244, 67, 54, 0.38);
          background: rgba(244, 67, 54, 0.10);
          color: var(--error-color, #f44336);
        }
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
        .icon-select {
          position: relative;
          width: 34px;
          min-width: 34px;
          height: 34px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--divider-color);
          border-radius: 999px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          color: var(--primary-color);
          overflow: hidden;
        }
        .icon-select ha-icon {
          --mdc-icon-size: 18px;
          pointer-events: none;
        }
        .icon-select select {
          position: absolute;
          inset: 0;
          width: 100%;
          min-width: 0;
          max-width: none;
          height: 100%;
          opacity: 0;
          cursor: pointer;
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
        .prep-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
          gap: 16px;
          align-items: start;
        }
        .prep-table {
          width: 100%;
          border-collapse: collapse;
          margin-top: 8px;
        }
        .prep-table th, .prep-table td {
          border-top: 1px solid var(--divider-color);
          padding: 9px 8px;
          text-align: left;
          vertical-align: top;
        }
        .prep-table th {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 750;
          text-transform: uppercase;
        }
        .prep-table td:last-child, .prep-table th:last-child {
          text-align: right;
        }
        .ready-meal-table {
          min-width: 620px;
        }
        .ready-meal-table .name {
          display: block;
          margin-bottom: 3px;
        }
        .ready-age {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          min-width: 58px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 5px 7px;
          background: var(--secondary-background-color, rgba(128,128,128,.06));
          color: var(--primary-text-color);
          font-weight: 750;
        }
        .ready-age ha-icon {
          --mdc-icon-size: 17px;
          color: var(--primary-color);
        }
        .ready-age strong {
          font-size: 18px;
          line-height: 1;
        }
        .ready-age span {
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 700;
        }
        .ready-age.warn ha-icon, .ready-age.warn strong { color: var(--warning-color, #ff9800); }
        .ready-age.critical ha-icon, .ready-age.critical strong { color: var(--error-color, #f44336); }
        .prep-source-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin-top: 10px;
        }
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
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--secondary-background-color, rgba(128,128,128,.04));
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
          color: var(--secondary-text-color);
          font-size: 13px;
          font-weight: 750;
          margin-bottom: 0;
          display: flex;
          justify-content: space-between;
          gap: 8px;
          align-items: center;
        }
        .content-count { color: var(--secondary-text-color); font-size: 11px; font-weight: 700; }
        .content-group .row:first-of-type { border-top: 0; }
        .inventory-group + .inventory-group { margin-top: 10px; }
        .tv-dinner-component {
          display: grid;
          grid-template-columns: minmax(72px, .45fr) minmax(0, 1fr);
          gap: 9px;
          align-items: start;
          padding: 8px 10px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--secondary-background-color, rgba(128,128,128,.04));
        }
        .tv-dinner-component strong { font-size: 12px; }
        .tv-dinner-component .muted { display: block; margin-top: 2px; }
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
          .prep-grid { grid-template-columns: 1fr; }
          .prep-source-grid { grid-template-columns: 1fr; }
          .action-context-grid { grid-template-columns: 1fr; }
          .readiness-grid { grid-template-columns: 1fr; }
          .compare-grid { grid-template-columns: 1fr; }
          .inventory-controls { grid-template-columns: 1fr; }
          .tv-dinner-component { grid-template-columns: 1fr; }
          .form-grid, .review-grid, .inline-grid, .debug-grid, .container-actions { grid-template-columns: 1fr; }
          .location-card-header { grid-template-columns: 1fr; }
          .location-card-actions { justify-content: flex-start; }
          .location-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .storage-layout { grid-template-columns: 1fr; }
          .storage-detail { position: static; max-height: none; }
          .row { grid-template-columns: 1fr; }
          .row-side { justify-items: start; }
          .qty { text-align: left; }
        }
      </style>
      <main>
        <header>
          <div>
            <h1>Mise en Place Assistant</h1>
            <p class="muted">${data ? "Updated just now" : "Loading overview..."}</p>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._safe(this._error)}</div>` : ""}
        ${this._notice ? `<div class="notice">${this._safe(this._notice)}</div>` : ""}
        <nav class="tabs">${tabs.map(([id, label]) => `<button type="button" class="${this._tab === id ? "active" : "secondary"}" data-tab="${id}">${label}</button>`).join("")}</nav>
        ${this._busyAction ? `<p class="busy">Working: ${this._safe(this._busyAction)}</p>` : ""}
        ${this._opsStrip(summary, operations, data?.shopping, data?.storage_attention, this._tab, mealPrep)}
        ${body}
      </main>
    `;
    this._wireEvents();
  }

  _wireEvents() {
    this.shadowRoot.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => { this._tab = button.dataset.tab; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-open-tab]").forEach((button) => button.addEventListener("click", () => { this._tab = button.dataset.openTab; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-planning-filter]").forEach((button) => button.addEventListener("click", () => { this._planningFilter = button.dataset.planningFilter; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-inventory-filter]").forEach((select) => select.addEventListener("change", () => {
      this._inventoryFilters = { ...(this._inventoryFilters || {}), [select.dataset.inventoryFilter]: select.value };
      this._inventoryPage = 1;
      this._render();
    }));
    this.shadowRoot.querySelectorAll("[data-inventory-page]").forEach((button) => button.addEventListener("click", () => {
      this._inventoryPage = Math.max(1, Number(button.dataset.inventoryPage || 1));
      this._render();
    }));
    this.shadowRoot.querySelectorAll("[data-inventory-page-size]").forEach((select) => select.addEventListener("change", () => {
      this._inventoryPageSize = Math.max(5, Number(select.value) || 10);
      this._inventoryPage = 1;
      this._render();
    }));
    this.shadowRoot.querySelectorAll("[data-ready-meal-page]").forEach((button) => button.addEventListener("click", () => {
      this._readyMealPage = Math.max(1, Number(button.dataset.readyMealPage || 1));
      this._render();
    }));
    this.shadowRoot.getElementById("complete-meal-count")?.addEventListener("change", (event) => {
      const count = Math.max(1, Math.floor(Number(event.currentTarget.value) || 1));
      this._mealPlanCount = count;
      event.currentTarget.value = String(count);
      this._load();
    });
    this.shadowRoot.querySelectorAll("[data-tv-dinner-count-step]").forEach((button) => button.addEventListener("click", () => {
      const current = Math.max(1, Math.floor(Number(this._tvDinnerCount) || 1));
      this._tvDinnerCount = Math.max(1, current + Number(button.dataset.tvDinnerCountStep || 0));
      this._render();
    }));
    this.shadowRoot.getElementById("tv-dinner-dice")?.addEventListener("click", () => this._rollTvDinner());
    this.shadowRoot.querySelectorAll("[data-tv-dinner-ready]").forEach((button) => button.addEventListener("click", () => this._transferTvDinnerMeal(button.dataset.tvDinnerReady)));
    this.shadowRoot.getElementById("add-location")?.addEventListener("click", () => { if (this._isBusy()) return; this._editingLocation = ""; this._showLocation = !this._showLocation; this._render(); });
    this.shadowRoot.getElementById("create-form")?.addEventListener("submit", (event) => this._createContainer(event));
    this.shadowRoot.getElementById("edit-container-form")?.addEventListener("submit", (event) => this._saveContainerEdit(event));
    this.shadowRoot.getElementById("move-container-form")?.addEventListener("submit", (event) => this._saveContainerMove(event));
    this.shadowRoot.getElementById("move-container-location")?.addEventListener("change", (event) => { this._moveContainerLocation = event.currentTarget.value; this._render(); });
    this.shadowRoot.getElementById("container-content-kind")?.addEventListener("change", (event) => { this._containerContentKind = event.currentTarget.value; this._render(); });
    this.shadowRoot.getElementById("location-form")?.addEventListener("submit", (event) => this._createLocation(event));
    this.shadowRoot.getElementById("shopping-item-form")?.addEventListener("submit", (event) => this._addShoppingItem(event));
    this.shadowRoot.getElementById("meal-prep-calendar-form")?.addEventListener("submit", (event) => this._createMealPrepCalendarEvent(event));
    this.shadowRoot.getElementById("cancel-location")?.addEventListener("click", () => { if (this._isBusy()) return; this._showLocation = false; this._editingLocation = ""; this._render(); });
    this.shadowRoot.getElementById("cancel-create")?.addEventListener("click", () => { if (this._isBusy()) return; this._showCreate = false; this._createContainerLocation = ""; this._render(); });
    this.shadowRoot.getElementById("cancel-container-edit")?.addEventListener("click", () => { if (this._isBusy()) return; this._editingContainerTag = ""; this._render(); });
    this.shadowRoot.getElementById("cancel-container-move")?.addEventListener("click", () => { if (this._isBusy()) return; this._movingContainerTag = ""; this._moveContainerLocation = ""; this._render(); });
    this.shadowRoot.querySelectorAll("[data-queue-empty-containers]").forEach((button) => button.addEventListener("click", () => this._queueEmptyContainers()));
    this.shadowRoot.querySelectorAll("[data-select-location]").forEach((card) => {
      const selectLocation = (event) => {
        if (
          this._isBusy()
          || this._selectedLocation === card.dataset.selectLocation
          || (card.tagName !== "BUTTON" && event.target.closest("button, input, select, textarea, a, form"))
        ) {
          return;
        }
        this._selectedLocation = card.dataset.selectLocation;
        this._selectedSublocation = "";
        this._render();
      };
      card.addEventListener("click", selectLocation);
      card.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        event.preventDefault();
        selectLocation(event);
      });
    });
    this.shadowRoot.querySelectorAll("[data-select-sublocation]").forEach((button) => button.addEventListener("click", () => {
      if (this._isBusy()) return;
      this._selectedLocation = button.dataset.locationId || this._selectedLocation;
      this._selectedSublocation = button.dataset.selectSublocation || "";
      this._render();
    }));
    this.shadowRoot.querySelectorAll("[data-edit-location]").forEach((button) => button.addEventListener("click", () => { if (this._isBusy()) return; this._editingLocation = button.dataset.editLocation; this._showLocation = true; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-add-container-location]").forEach((button) => button.addEventListener("click", () => this._openCreateContainer(button.dataset.addContainerLocation)));
    this.shadowRoot.querySelectorAll("[data-delete-location]").forEach((button) => button.addEventListener("click", () => this._deleteLocation(button.dataset.deleteLocation, button.dataset.locationName, button.dataset.locationProvider, button.dataset.locationLocal)));
    this.shadowRoot.querySelectorAll("[data-edit-container]").forEach((button) => button.addEventListener("click", () => this._openContainerEdit(button.dataset.editContainer)));
    this.shadowRoot.querySelectorAll("[data-open-move-container]").forEach((button) => button.addEventListener("click", () => this._openContainerMove(button.dataset.openMoveContainer, button.dataset.currentLocation)));
    this.shadowRoot.querySelectorAll("[data-move-tag]").forEach((select) => select.addEventListener("change", () => this._moveContainer(select.dataset.moveTag, select.value)));
    this.shadowRoot.querySelectorAll("[data-clear-container]").forEach((button) => button.addEventListener("click", () => this._runContainerService("clear_container", button.dataset.clearContainer, `Clear ${button.dataset.containerName}?`, "Could not clear container.")));
    this.shadowRoot.querySelectorAll("[data-mark-container-eaten]").forEach((button) => button.addEventListener("click", () => this._runContainerService("mark_container_eaten", button.dataset.markContainerEaten, `Mark ${button.dataset.containerName} as eaten?`, "Could not mark meal eaten.")));
    this.shadowRoot.querySelectorAll("[data-delete-container]").forEach((button) => button.addEventListener("click", () => this._runContainerService("delete_container", button.dataset.deleteContainer, `Delete ${button.dataset.containerName}?`, "Could not delete container.")));
    this.shadowRoot.querySelectorAll("[data-product-metadata]").forEach((form) => form.addEventListener("submit", (event) => this._saveProductMetadata(event)));
    this.shadowRoot.querySelectorAll("[data-queue-product]").forEach((button) => button.addEventListener("click", () => this._queueProduct(button.dataset.queueProduct, button.dataset.productLabel)));
    this.shadowRoot.querySelectorAll("[data-sync-missing-products]").forEach((button) => button.addEventListener("click", () => this._syncMissingProducts()));
    this.shadowRoot.querySelectorAll("[data-clone-prep-session]").forEach((button) => button.addEventListener("click", () => this._clonePrepSession(button)));
    this.shadowRoot.querySelectorAll("[data-select-prep-session]").forEach((button) => button.addEventListener("click", () => this._selectPrepSession(button)));
    this.shadowRoot.querySelectorAll("[data-prep-recipe-input]").forEach((input) => input.addEventListener("input", () => this._updatePrepShoppingPreview()));
    this.shadowRoot.querySelectorAll("[data-prep-recipe-input]").forEach((input) => input.addEventListener("change", () => this._updatePrepShoppingPreview()));
    this.shadowRoot.querySelectorAll("[data-suggested-service]").forEach((button) => button.addEventListener("click", () => this._runSuggestedService(button)));
    this.shadowRoot.querySelectorAll("[data-suggested-tab]").forEach((button) => button.addEventListener("click", () => { if (this._isBusy()) return; this._tab = this._normalizeTab(button.dataset.suggestedTab); this._render(); }));
    this.shadowRoot.getElementById("dev-refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.getElementById("dev-copy-overview")?.addEventListener("click", () => this._copyOverview());
    this.shadowRoot.getElementById("dev-simulate-crud")?.addEventListener("click", () => this._simulateCrud());
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

  _inventoryView(items, containers, locations) {
    const groups = this._inventoryProductGroups(items);
    const filteredStocked = this._inventoryFilteredProducts(groups.stocked);
    const pagedStocked = this._inventoryPagedProducts(filteredStocked);
    const attention = this._inventoryReviewRows(this._data?.product_attention || []);
    const readyToEatSoon = this._inventoryReadyToEatSoon(containers, locations);
    const pagedReadyToEatSoon = this._inventoryPagedReadyMeals(readyToEatSoon);
    return `
      <section class="stack">
        <section class="grid">
          ${this._metric("Stocked products", items.length)}
          ${this._metric("Grocy products", items.filter((item) => item.source === "grocy").length)}
          ${this._metric("Prepared foods", groups.prepared.length)}
          ${this._metric("Needs review", attention.length, attention.length ? "warn" : "ok")}
          ${this._metric("Locations", this._inventoryLocationCount(items))}
        </section>
        <section class="sections">
          <div class="stack">
            <section class="card">
              <div class="toolbar"><h2>Current inventory</h2><button type="button" class="secondary" data-open-tab="attention">Attention</button></div>
              ${this._inventoryFilterControls(groups.stocked)}
              ${filteredStocked.length ? this._inventoryGroupedProducts(pagedStocked.items) : this._empty(groups.stocked.length ? "No stocked products match these filters." : "No stocked products.")}
              ${this._inventoryPager(pagedStocked)}
            </section>
            <section class="card">
              <h2>Prepared inventory</h2>
              ${groups.prepared.length ? groups.prepared.map((item) => this._inventoryProductRow(item)).join("") : this._empty("No prepared foods currently stocked.")}
            </section>
          </div>
          <div class="stack">
            <section class="card">
              <h2>Ready to eat soon</h2>
              ${readyToEatSoon.length ? this._inventoryReadyToEatTable(pagedReadyToEatSoon.items, locations) : this._empty("No ready-to-eat meals need attention.")}
              ${this._inventoryReadyMealPager(pagedReadyToEatSoon)}
            </section>
            <section class="card">
              <h2>Needs review</h2>
              ${attention.length ? attention.map((item) => this._inventoryReviewRow(item)).join("") : this._empty("No inventory review items.")}
            </section>
            <section class="card">
              <h2>Inventory sources</h2>
              ${this._inventorySourceSummary(items)}
            </section>
          </div>
        </section>
      </section>
    `;
  }

  _storageView(locations, containers, foods, recipes, areas) {
    const editableLocations = locations.filter((location) => location.editable !== false);
    const editingLocation = editableLocations.find((location) => location.id === this._editingLocation);
    const editingContainer = containers.find((container) => container.tag_id === this._editingContainerTag) || null;
    const movingContainer = containers.find((container) => container.tag_id === this._movingContainerTag) || null;
    const selectedLocation = locations.some((location) => location.id === this._selectedLocation)
      ? this._selectedLocation
      : locations[0]?.id || "";
    this._selectedLocation = selectedLocation;
    const selectedLocationRecord = locations.find((location) => location.id === selectedLocation) || null;
    const sublocations = selectedLocationRecord ? this._locationSublocations(selectedLocationRecord, containers) : [];
    const selectedSublocation = sublocations.some((sublocation) => sublocation.name === this._selectedSublocation)
      ? this._selectedSublocation
      : sublocations[0]?.name || "Main";
    this._selectedSublocation = selectedSublocation;
    return `
      ${this._showLocation ? this._locationForm(areas, editingLocation || null) : ""}
      ${this._showCreate ? this._createForm(editableLocations, foods, recipes) : ""}
      ${editingContainer ? this._containerEditForm(editingContainer, editableLocations) : ""}
      ${movingContainer ? this._containerMoveForm(movingContainer, editableLocations) : ""}
      <section class="storage-layout">
        <div class="storage-left">
          <section class="card">
            <div class="toolbar"><h2>Storage locations</h2><div class="actions"><button type="button" id="add-location">Add location</button></div></div>
          </section>
          ${locations.map((location) => this._locationCard(location, containers, locations, location.id === selectedLocation, selectedSublocation)).join("") || this._emptyCard("Create storage locations in Grocy, or enable DEV mode for mocked locations.")}
        </div>
        ${selectedLocationRecord ? this._storageDetail(selectedLocationRecord, selectedSublocation, containers, locations) : ""}
      </section>
    `;
  }

  _planningView(mealInventory, data, foods, logbook) {
    const productAttention = data?.product_attention || [];
    const readiness = data?.readiness || {};
    const planningComparison = data?.planning_comparison || [];
    const recipeSuggestions = data?.recipe_suggestions || [];
    const completeMealPlan = data?.complete_meal_plan || {};
    const recipeContainers = this._filteredRecipeContainers(data?.containers || []);
    return `
      <section class="sections">
        <div class="stack">
          <section class="card">
            <div class="toolbar">
              <h2>Complete meals</h2>
              <label>Meals<input id="complete-meal-count" type="number" min="1" step="1" value="${this._safe(this._mealPlanCount || completeMealPlan.meal_count || 1)}" /></label>
            </div>
            ${this._completeMealPlan(completeMealPlan)}
          </section>
          <section class="card">
            <h2>Prepared components</h2>
            ${this._planningFilterBar(data?.containers || [])}
            ${recipeContainers.length ? recipeContainers.map((container) => this._recipeContainerRow(container)).join("") : this._empty("No recipe containers match this filter.")}
          </section>
          <section class="card">
            <h2>Recipe suggestions</h2>
            ${recipeSuggestions.length ? recipeSuggestions.map((recipe) => this._recipeSuggestionRow(recipe)).join("") : this._empty("No recipe suggestions until recipes have ingredient details.")}
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
      </section>
    `;
  }

  _tvDinnerView(data) {
    const plan = this._tvDinnerPlan || data?.tv_dinner_plan || null;
    const mealCount = Math.max(1, Math.floor(Number(this._tvDinnerCount) || 1));
    this._tvDinnerCount = mealCount;
    return `
      <section class="sections single">
        <div class="stack">
          <section class="card">
            <div class="toolbar">
              <h2>Tv dinner</h2>
              <div class="actions">
                <label class="meal-selector" aria-label="Number of meals to generate">
                  <span class="meal-stepper">
                    <button type="button" class="icon-button" data-tv-dinner-count-step="-1" title="Fewer meals" aria-label="Fewer meals"><ha-icon icon="mdi:minus"></ha-icon></button>
                    <output id="tv-dinner-count" aria-live="polite">${this._safe(mealCount)}</output>
                    <button type="button" class="icon-button" data-tv-dinner-count-step="1" title="More meals" aria-label="More meals"><ha-icon icon="mdi:plus"></ha-icon></button>
                  </span>
                </label>
                <button type="button" id="tv-dinner-dice" title="Roll TV dinner" aria-label="Roll TV dinner"><ha-icon icon="mdi:dice-multiple"></ha-icon></button>
              </div>
            </div>
            ${plan ? this._tvDinnerPlanView(plan, data) : this._empty("Roll for complete meals.")}
          </section>
        </div>
      </section>
    `;
  }

  _tvDinnerPlanView(plan = {}, data = {}) {
    const shortages = Object.values(plan.shortages || {});
    const meals = plan.meals || [];
    const availableContainers = this._availableTvDinnerContainers(data);
    const transferable = this._tvDinnerTransferMeals(plan, availableContainers, data);
    const skipped = (plan.skipped || []).slice(0, 6).map((item) => `<p class="muted subline">${this._safe(item.label)}: ${this._safe(item.reason)}</p>`).join("");
    return `
      <div class="summary-row ${plan.complete ? "ok" : "warn"}">
        <p class="name">${plan.complete ? `${this._safe(plan.meal_count || meals.length || 1)} TV dinner${Number(plan.meal_count || meals.length || 1) === 1 ? "" : "s"}` : "Missing components"}</p>
        <p class="muted subline">Best-before and variety weighted random assignment</p>
      </div>
      ${shortages.length ? `<div class="row compact-row"><div><p class="name">Shortages</p>${shortages.map((item) => `<p class="muted subline">${this._safe(item.label || "")}: missing ${this._safe(item.missing)}</p>`).join("")}</div></div>` : ""}
      <div class="recipe-grid">${meals.map((meal) => this._tvDinnerMeal(meal, transferable)).join("")}</div>
      ${skipped ? `<div class="row compact-row"><div><p class="name">Skipped</p>${skipped}</div></div>` : ""}
    `;
  }

  _tvDinnerMeal(meal = {}, transferable = []) {
    const components = meal.components || {};
    const rows = [
      ["protein", "Protein"],
      ["starch", "Starch"],
      ["veggie", "Veggie"],
    ].map(([role, label]) => this._tvDinnerComponentRow(label, components[role])).join("");
    const mealId = String(meal.meal || "");
    const transferableMeal = transferable.find((candidate) => String(candidate.meal || "") === mealId);
    const ready = Boolean(transferableMeal?.container_tag_id);
    return `<article class="row compact-row">
      <div>
        <p class="name">Meal ${this._safe(meal.meal || "")}</p>
        ${rows}
        <div class="meal-transfer">
          <button type="button" data-tv-dinner-ready="${this._safe(mealId)}"${ready ? "" : " disabled"}>Ready</button>
        </div>
      </div>
    </article>`;
  }

  _tvDinnerComponentRow(label, component = null) {
    if (!component) {
      return `<div class="tv-dinner-component"><strong>${this._safe(label)}</strong><span class="muted subline">Missing source component</span></div>`;
    }
    const place = [component.location, component.sublocation].filter(Boolean).join(" / ") || "No location";
    const productInfo = this._tvDinnerComponentProductInfo(component);
    return `<div class="tv-dinner-component">
      <strong>${this._safe(label)}</strong>
      <span>
        1 portion ${this._safe(component.label)}
        <span class="muted subline">Source: ${this._safe(place)}</span>
        ${productInfo ? `<span class="muted subline">Product: ${this._safe(productInfo)}</span>` : ""}
      </span>
    </div>`;
  }

  _tvDinnerComponentProductInfo(component = {}) {
    return [
      component.family && component.family !== "unknown" ? component.family : "",
      component.detail || "",
      component.tag_id || "",
    ].filter(Boolean).join(" · ");
  }

  _mealPrepView(mealPrep = {}, data = {}) {
    const readiness = data?.readiness || {};
    const completeMealPlan = data?.complete_meal_plan || {};
    const calendars = mealPrep.calendar_entities || [];
    const prepCalendar = this._prepCalendar(mealPrep);
    const recipeSuggestions = data?.recipe_suggestions || [];
    const defaultSummary = this._mealPrepSummaryDraft || "Meal prep";
    return `
      <section class="sections">
        <div class="stack">
          <section class="card">
            <div class="toolbar">
              <div>
                <h2>Session Calendar</h2>
                <p class="muted subline">Home Assistant calendar scheduling with Mise prep details.</p>
              </div>
            </div>
            ${this._prepMiniCalendar(mealPrep)}
          </section>
          <section class="card">
            <h2>New prep session</h2>
            ${prepCalendar ? this._prepCalendarForm(prepCalendar, defaultSummary, recipeSuggestions) : this._empty(calendars.length ? "Choose a prep calendar in the integration configuration before scheduling prep sessions." : "No Home Assistant calendar entities found. Add a calendar integration, then choose it in the integration configuration.")}
          </section>
          <section class="card">
            <div class="toolbar"><h2>Ingredient readiness</h2><button type="button" class="secondary" data-open-tab="planning">Open product review</button></div>
            ${this._readinessPanel(readiness, true)}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <h2>Shopping list preview</h2>
            <div id="prep-shopping-preview">${this._prepShoppingPreview(recipeSuggestions, this._prepRecipeSelectionFromState(recipeSuggestions))}</div>
          </section>
          <section class="card">
            <h2>Recipe rank</h2>
            ${recipeSuggestions.length ? recipeSuggestions.map((recipe) => this._prepRecipeRankRow(recipe)).join("") : this._empty("No ranked recipes until Mealie recipes expose ingredient details.")}
          </section>
          <section class="card">
            <h2>Session details</h2>
            ${this._prepSelectedSessionDetails(mealPrep, data)}
          </section>
        </div>
      </section>
    `;
  }

  _attentionView(data = {}) {
    const rows = this._attentionRows(data);
    const critical = rows.filter((row) => row.status === "critical").length;
    const warning = rows.filter((row) => row.status === "warning" || row.status === "empty").length;
    const grouped = [
      ["critical", "Fix first"],
      ["warning", "Act next"],
      ["empty", "Empty or low stock"],
      ["review", "Review when convenient"],
    ];
    return `
      <section class="stack">
        <section class="grid">
          ${this._metric("Open tasks", rows.length, rows.length ? "warn" : "ok")}
          ${this._metric("Critical", critical, critical ? "critical" : "")}
          ${this._metric("Action needed", warning, warning ? "warn" : "")}
          ${this._metric("Suggested actions", this._actionableSuggestedActions(data?.suggested_actions || []).length)}
        </section>
        <section class="card">
          <div class="toolbar">
            <div>
              <h2>Kitchen punch list</h2>
              <p class="muted subline">Clear the list by fixing stale food, storage risks, and empty containers.</p>
            </div>
            <button type="button" class="secondary" data-open-tab="planning">Planning</button>
          </div>
          ${rows.length ? grouped.map(([status, label]) => this._attentionGroup(label, rows.filter((row) => row.group === status))).join("") : this._empty("List clear.")}
        </section>
      </section>
    `;
  }

  _attentionRows(data = {}) {
    const rows = [];
    const add = (row) => {
      if (!row || this._isConfigurationAttention(row)) {
        return;
      }
      rows.push(row);
    };
    for (const action of this._actionableSuggestedActions(data.suggested_actions || [])) {
      add({
        id: `action:${action.id}`,
        title: action.title,
        detail: action.because,
        source: (action.sources || []).join(" + ") || "Suggested action",
        status: action.status === "critical" ? "critical" : action.status === "empty" ? "empty" : "warning",
        group: action.status === "critical" ? "critical" : action.status === "empty" ? "empty" : "warning",
        action,
      });
    }
    const readiness = data.readiness || {};
    for (const item of readiness.missing || []) {
      add({ id: `missing:${item.label}`, title: item.label, detail: item.reason || item.detail, source: "Ingredient readiness", status: "warning", group: "warning", openTab: "planning" });
    }
    for (const item of readiness.stale || []) {
      add({ id: `stale:${item.label}`, title: item.label, detail: item.reason || item.detail, source: "Freshness", status: "critical", group: "critical", openTab: "inventory" });
    }
    for (const item of readiness.unassigned || []) {
      add({ id: `unassigned:${item.label}`, title: item.label, detail: item.reason || item.detail, source: "Storage location", status: "warning", group: "warning", openTab: "storage" });
    }
    for (const item of readiness.location_at_risk || []) {
      add({ id: `location:${item.label}`, title: item.label, detail: item.reason || item.detail, source: "Storage safety", status: item.status === "critical" ? "critical" : "warning", group: item.status === "critical" ? "critical" : "warning", openTab: "storage" });
    }
    for (const item of data.product_attention || []) {
      const detail = (item.reasons || []).join(", ") || "Product needs review";
      add({ id: `product:${item.item_id || item.label}`, title: item.label, detail, source: item.source === "grocy" ? "Grocy product" : "Product review", status: item.has_stock ? "review" : "warning", group: item.has_stock ? "review" : "warning", openTab: "planning" });
    }
    for (const container of data.empty_containers || []) {
      add({ id: `empty:${container.tag_id}`, title: container.name || container.item_label, detail: container.item_label || "Empty reusable container", source: "Container inventory", status: "empty", group: "empty", openTab: "inventory" });
    }
    for (const container of data.low_containers || []) {
      add({ id: `low:${container.tag_id}`, title: container.name || container.item_label, detail: `${container.quantity ?? 0} ${container.unit || ""}`.trim(), source: "Container inventory", status: "empty", group: "empty", openTab: "inventory" });
    }
    const seen = new Set();
    return rows.filter((row) => {
      const key = row.id || `${row.title}:${row.detail}:${row.source}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  _actionableSuggestedActions(actions = []) {
    return actions.filter((action) => !this._isConfigurationAttention({
      title: action.title,
      detail: action.because,
      source: (action.sources || []).join(" "),
      status: action.status,
    }));
  }

  _isConfigurationAttention(row = {}) {
    const text = `${row.title || ""} ${row.detail || row.reason || ""} ${row.source || ""}`.toLowerCase();
    return [
      "not configured",
      "setup",
      "configure",
      "configuration",
      "credentials",
      "token",
      "api key",
      "provider unavailable",
      "integration unavailable",
      "no live sensors",
      "storage monitoring unavailable",
      "storage monitoring not configured",
    ].some((needle) => text.includes(needle));
  }

  _attentionGroup(label, rows) {
    if (!rows.length) {
      return "";
    }
    return `<section class="readiness-section" style="margin-top: 12px;">
      <h3>${this._safe(label)} <span class="muted">${this._safe(rows.length)}</span></h3>
      ${rows.map((row) => this._attentionRow(row)).join("")}
    </section>`;
  }

  _attentionRow(row) {
    const klass = row.status === "critical" ? "critical" : row.status === "review" ? "" : row.status === "empty" ? "empty" : "warn";
    const action = row.action
      ? this._suggestedActionButtons(row.action)
      : row.openTab
        ? `<button type="button" class="secondary" data-open-tab="${this._safe(row.openTab)}">Open</button>`
        : "";
    return this._summaryRow(row.title || "Attention item", [
      row.detail || "",
      row.source || "",
    ], {
      quantity: row.status === "review" ? "Review" : row.status === "empty" ? "Empty" : row.status === "critical" ? "Critical" : "Action",
      klass,
      action,
    });
  }

  _prepCalendar(mealPrep = {}) {
    const entityId = mealPrep.prep_calendar_entity_id || "";
    if (!entityId) {
      return null;
    }
    return (mealPrep.calendar_entities || []).find((calendar) => calendar.entity_id === entityId) || {
      entity_id: entityId,
      name: entityId,
    };
  }

  _prepMiniCalendar(mealPrep = {}) {
    const sessions = mealPrep.sessions || [];
    const active = mealPrep.calendar_events || [];
    if (!sessions.length && !active.length) {
      return this._empty("No prep sessions yet.");
    }
    const activeRows = active.map((event) => ({
      id: this._prepCalendarEventId(event),
      summary: event.name || event.message || "Active calendar session",
      start_date_time: event.start_date || event.start_time || "",
      end_date_time: event.end_date || event.end_time || "",
      calendar_entity_id: event.entity_id || "",
      status: event.state === "on" ? "now" : "calendar",
      recipes: [],
      calendar_event: true,
    }));
    const rows = [...sessions, ...activeRows].sort((left, right) => String(left.start_date_time || "").localeCompare(String(right.start_date_time || "")));
    return `<div class="stack">${rows.map((session) => this._prepCalendarRow(session)).join("")}</div>`;
  }

  _prepCalendarRow(session) {
    const recipes = (session.recipes || []).map((recipe) => recipe.label).filter(Boolean).join(" · ");
    const status = session.status === "past" ? "Past" : session.status === "now" ? "Now" : "Upcoming";
    const klass = session.status === "past" ? "" : session.status === "now" ? "ok" : "warn";
    const sessionId = session.id || this._prepCalendarEventId({
      entity_id: session.calendar_entity_id,
      name: session.summary,
      start_time: session.start_date_time,
    });
    const selected = this._selectedPrepSessionId && this._selectedPrepSessionId === sessionId;
    return this._summaryRow(session.summary || "Meal prep session", [
      this._prepScheduleLabel(session),
      session.calendar_entity_id || "",
      recipes,
    ], {
      quantity: status,
      klass,
      action: `<button type="button" class="secondary" data-select-prep-session="${this._safe(sessionId)}">${selected ? "Selected" : "Details"}</button>`,
    });
  }

  _prepCalendarForm(calendar, defaultSummary, recipeSuggestions = []) {
    return `<form id="meal-prep-calendar-form">
      <input type="hidden" name="entity_id" value="${this._safe(calendar.entity_id)}" />
      <p class="muted subline">Prep sessions will be scheduled in ${this._safe(calendar.name)} (${this._safe(calendar.entity_id)}).</p>
      <div class="form-grid">
        <input type="hidden" name="summary" value="${this._safe(defaultSummary)}" />
        <label>Prep date<input name="start_date" required type="date" /></label>
        <label>Description<textarea name="description" rows="3">Created from Mise en Place Assistant meal prep readiness.</textarea></label>
      </div>
      <div class="readiness-section" style="margin-top: 12px;">
        <h3>Recipe chooser</h3>
        ${this._prepRecipeChooser(recipeSuggestions)}
      </div>
      <div class="actions"><button type="submit">Create calendar session</button></div>
    </form>`;
  }

  _prepRecipeChooser(recipeSuggestions = []) {
    if (!recipeSuggestions.length) {
      return this._empty("No ranked recipes available.");
    }
    const selection = this._prepRecipeSelectionFromState(recipeSuggestions);
    return recipeSuggestions.slice(0, 8).map((recipe, index) => {
      const bestBefore = (recipe.best_before || [])[0];
      const urgency = bestBefore ? ` · best before ${this._safe(this._relativeDateLabel(bestBefore.best_before_date))}` : "";
      const missing = recipe.missing_count ? ` · ${this._safe(recipe.missing_count)} missing` : "";
      const checked = selection[recipe.id]?.selected ?? index === 0;
      const quantity = selection[recipe.id]?.quantity || 1;
      return `<label class="row compact-row">
        <span><input type="checkbox" name="recipe_ids" value="${this._safe(recipe.id)}" data-prep-recipe-input data-recipe-id="${this._safe(recipe.id)}"${checked ? " checked" : ""} /> ${this._safe(recipe.label)}</span>
        <span class="actions"><input class="prep-quantity" type="number" min="1" step="1" name="recipe_quantity" data-prep-recipe-input data-recipe-id="${this._safe(recipe.id)}" value="${this._safe(quantity)}" aria-label="${this._safe(recipe.label)} quantity" /></span>
        <span class="muted">${this._safe(recipe.matched_count || 0)}/${this._safe(recipe.ingredient_count || 0)}${urgency}${missing}</span>
      </label>`;
    }).join("");
  }

  _prepRecipeSelectionFromState(recipeSuggestions = []) {
    const selection = {};
    recipeSuggestions.slice(0, 8).forEach((recipe, index) => {
      const existing = this._prepRecipeSelection[recipe.id] || {};
      selection[recipe.id] = {
        selected: existing.selected ?? index === 0,
        quantity: this._prepPositiveNumber(existing.quantity, 1),
      };
    });
    return selection;
  }

  _prepRecipeSelectionFromForm(form) {
    const selection = {};
    form.querySelectorAll('input[name="recipe_ids"]').forEach((input) => {
      const recipeId = input.value;
      const quantityInput = [...form.querySelectorAll('input[name="recipe_quantity"]')].find((candidate) => candidate.dataset.recipeId === recipeId);
      selection[recipeId] = {
        selected: Boolean(input.checked),
        quantity: this._prepPositiveNumber(quantityInput?.value, 1),
      };
    });
    return selection;
  }

  _prepSelectedRecipePayload(form) {
    const selection = this._prepRecipeSelectionFromForm(form);
    const recipeIds = Object.entries(selection).filter(([, row]) => row.selected).map(([recipeId]) => recipeId);
    const recipeQuantities = Object.fromEntries(
      Object.entries(selection)
        .filter(([, row]) => row.selected)
        .map(([recipeId, row]) => [recipeId, row.quantity]),
    );
    return { selection, recipeIds, recipeQuantities };
  }

  _prepShoppingPreview(recipeSuggestions = [], selection = {}) {
    const selected = recipeSuggestions
      .filter((recipe) => selection[recipe.id]?.selected)
      .map((recipe) => ({ recipe, quantity: this._prepPositiveNumber(selection[recipe.id]?.quantity, 1) }));
    if (!selected.length) {
      return this._empty("Select recipes to preview missing shopping items.");
    }
    const rows = this._prepShoppingPreviewRows(selected);
    if (!rows.length) {
      return this._empty("Selected recipes have no missing ingredients in the current preview.");
    }
    return `<div class="stack">${rows.map((row) => this._summaryRow(row.label, [
      row.amount || "Quantity not specified",
      row.recipes.join(" + "),
    ], { quantity: row.count > 1 ? `${row.count} recipes` : "Missing", klass: "warn" })).join("")}</div>`;
  }

  _prepShoppingPreviewRows(selectedRecipes = []) {
    const rows = new Map();
    for (const { recipe, quantity } of selectedRecipes) {
      for (const item of recipe.missing || []) {
        const key = String(item.label || item.original || "Ingredient").toLocaleLowerCase();
        const current = rows.get(key) || { label: item.label || "Ingredient", quantity: 0, unit: "", rawAmounts: [], recipes: [], count: 0 };
        const parsed = this._parsePrepAmount(item.amount);
        if (parsed) {
          current.quantity += parsed.quantity * quantity;
          current.unit = current.unit || parsed.unit;
        } else if (item.amount) {
          current.rawAmounts.push(quantity > 1 ? `${quantity} x ${item.amount}` : item.amount);
        }
        current.recipes.push(`${recipe.label}${quantity > 1 ? ` x${quantity}` : ""}`);
        current.count += 1;
        rows.set(key, current);
      }
    }
    return [...rows.values()].map((row) => ({
      ...row,
      amount: row.quantity ? `${this._formatPrepQuantity(row.quantity)} ${row.unit}`.trim() : row.rawAmounts.join(" + "),
    })).sort((left, right) => left.label.localeCompare(right.label));
  }

  _parsePrepAmount(amount) {
    const match = /^(\d+(?:\.\d+)?)\s*(.*)$/.exec(String(amount || "").trim());
    return match ? { quantity: Number(match[1]), unit: match[2].trim() } : null;
  }

  _formatPrepQuantity(value) {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
  }

  _updatePrepShoppingPreview() {
    const form = this.shadowRoot?.getElementById("meal-prep-calendar-form");
    const preview = this.shadowRoot?.getElementById("prep-shopping-preview");
    if (!form || !preview) {
      return;
    }
    const { selection } = this._prepSelectedRecipePayload(form);
    this._prepRecipeSelection = selection;
    preview.innerHTML = this._prepShoppingPreview(this._data?.recipe_suggestions || [], selection);
  }

  _prepRecipeRankRow(recipe) {
    const bestBefore = (recipe.best_before || [])[0];
    const urgency = bestBefore ? `${bestBefore.label}: ${this._relativeDateLabel(bestBefore.best_before_date)}` : "No urgent best-before";
    return this._summaryRow(recipe.label || "Recipe", [
      recipe.reason || "",
      `Best-before: ${urgency}`,
      `${recipe.matched_count || 0}/${recipe.ingredient_count || 0} ingredients matched${recipe.missing_count ? `, ${recipe.missing_count} missing` : ""}`,
    ], { quantity: recipe.score || 0, klass: recipe.missing_count ? "warn" : "ok" });
  }

  _prepSelectedSessionDetails(mealPrep = {}, data = {}) {
    const session = this._selectedPrepSession(mealPrep);
    if (!session) {
      return this._empty("No prep session selected yet.");
    }
    const completeMealPlan = data?.complete_meal_plan || {};
    const readiness = data?.readiness || {};
    const recipes = this._prepSessionRecipeLabels(session, completeMealPlan);
    const servings = this._prepPositiveNumber(session.servings || mealPrep.meal_count || completeMealPlan.meal_count, 1);
    const expectedPortions = this._prepPositiveNumber(session.expected_portions || this._prepExpectedFinishedPortions(mealPrep, completeMealPlan, servings), servings);
    const notes = session.description || session.notes || "No session notes.";
    const scheduled = this._prepScheduleLabel(session);
    return `<div class="stack">
      ${this._summaryRow("Scheduled date", [scheduled || "No Home Assistant calendar date available", session.calendar_entity_id || session.entity_id || "Home Assistant calendar"], { quantity: session.status === "past" ? "Past" : session.status === "now" ? "Today" : "All day", klass: session.status === "past" ? "" : "ok" })}
      ${this._summaryRow("Recipes or meals included", [recipes.length ? recipes.join(" · ") : "No recipes selected"], { quantity: recipes.length || 0 })}
      ${this._summaryRow("Number of servings", [`${this._safe(servings)} serving${servings === 1 ? "" : "s"}`], { quantity: servings })}
      ${this._summaryRow("Expected finished portions", [`${this._safe(expectedPortions)} finished portion${expectedPortions === 1 ? "" : "s"}`], { quantity: expectedPortions })}
      ${this._summaryRow("Session notes", [notes])}
      ${this._prepReadinessSummary(readiness)}
    </div>`;
  }

  _selectedPrepSession(mealPrep = {}) {
    const rows = this._prepSessionRows(mealPrep);
    if (!rows.length) {
      return null;
    }
    const selected = rows.find((session) => session.id === this._selectedPrepSessionId);
    if (selected) {
      return selected;
    }
    return rows.find((session) => session.status === "now")
      || rows.find((session) => session.status !== "past")
      || rows.at(-1);
  }

  _prepSessionRows(mealPrep = {}) {
    const activeRows = (mealPrep.calendar_events || []).map((event) => ({
      id: this._prepCalendarEventId(event),
      summary: event.name || event.message || "Active calendar session",
      start_date_time: event.start_date || event.start_time || "",
      end_date_time: event.end_date || event.end_time || "",
      calendar_entity_id: event.entity_id || "",
      status: event.state === "on" ? "now" : "calendar",
      description: event.message || "",
      recipes: [],
    }));
    return [...(mealPrep.sessions || []), ...activeRows].sort((left, right) => String(left.start_date_time || "").localeCompare(String(right.start_date_time || "")));
  }

  _prepCalendarEventId(event = {}) {
    return `calendar:${event.entity_id || ""}:${event.start_date || event.start_time || event.start_date_time || ""}:${event.name || event.message || ""}`;
  }

  _prepScheduleLabel(session = {}) {
    const start = session.start_date_time || session.start_time || session.start_date || "";
    const end = session.end_date_time || session.end_time || session.end_date || "";
    if (!start) {
      return "";
    }
    const startDay = String(start).slice(0, 10);
    const endDay = String(end).slice(0, 10);
    return !endDay || endDay === startDay || endDay === this._nextDate(startDay)
      ? `${this._relativeDateLabel(startDay)} · all day`
      : `${this._relativeDateLabel(startDay)} to ${this._relativeDateLabel(endDay)}`;
  }

  _nextDate(dateText) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateText || ""));
    if (!match) {
      return "";
    }
    const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + 1));
    return date.toISOString().slice(0, 10);
  }

  _prepSessionRecipeLabels(session = {}, completeMealPlan = {}) {
    const recipes = (session.recipes || []).map((recipe) => {
      const label = recipe.label || recipe.name;
      const quantity = this._prepPositiveNumber(recipe.quantity, 1);
      return label ? `${label}${quantity > 1 ? ` x${quantity}` : ""}` : "";
    }).filter(Boolean);
    if (recipes.length) {
      return recipes;
    }
    const uses = completeMealPlan.uses || {};
    return Object.values(uses).flat().map((item) => item.label || item.name).filter(Boolean);
  }

  _prepExpectedFinishedPortions(mealPrep = {}, completeMealPlan = {}, fallback = 1) {
    const completePortions = (mealPrep.storage_plan || []).find((row) => String(row.label || "").toLowerCase().includes("complete meal"));
    return Number(completePortions?.count || completeMealPlan.meal_count || fallback || 1);
  }

  _prepPositiveNumber(value, fallback = 1) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : fallback;
  }

  _prepReadinessSummary(readiness = {}) {
    const parts = [
      `${readiness.ready?.length || 0} ready`,
      `${readiness.missing?.length || 0} missing`,
      `${readiness.empty?.length || 0} empty`,
      `${readiness.unassigned?.length || 0} unassigned`,
      `${readiness.stale?.length || 0} stale`,
      `${readiness.location_at_risk?.length || 0} location at risk`,
    ];
    const blocking = (readiness.missing?.length || 0) + (readiness.empty?.length || 0) + (readiness.stale?.length || 0) + (readiness.location_at_risk?.length || 0);
    return this._summaryRow("Readiness summary", [parts.join(" · ")], { quantity: blocking ? "Review" : "Ready", klass: blocking ? "warn" : "ok" });
  }

  _selectPrepSession(button) {
    this._selectedPrepSessionId = button.dataset.selectPrepSession || "";
    this._render();
  }

  _prepCalendarEvents(events) {
    if (!events.length) {
      return `<p class="muted subline">No active calendar session is currently exposed by Home Assistant.</p>`;
    }
    return `<div class="stack" style="margin-top: 12px;">${events.map((event) => this._summaryRow(event.name, [
      event.message || "Calendar session",
      [event.start_time, event.end_time].filter(Boolean).join(" to "),
      event.entity_id,
    ], { quantity: event.state === "on" ? "Now" : event.state, klass: event.state === "on" ? "ok" : "" })).join("")}</div>`;
  }

  _prepProviderRoles(roles) {
    const entries = Object.entries(roles);
    if (!entries.length) {
      return this._empty("Provider roles will appear after the overview loads.");
    }
    return `<div class="prep-source-grid">${entries.map(([label, value]) => `
      <div class="state"><p class="muted">${this._safe(label.replaceAll("_", " "))}</p><p class="name">${this._safe(value)}</p></div>
    `).join("")}</div>`;
  }

  _prepStoragePlan(rows) {
    if (!rows.length) {
      return this._empty("No storage plan generated yet.");
    }
    return `<table class="prep-table">
      <thead><tr><th>Output</th><th>Container</th><th>Destination</th><th>Count</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <td><strong>${this._safe(row.label)}</strong><p class="muted subline">${this._safe(row.note || "")}</p><p class="muted subline">${this._safe(row.eat_by || "")}</p></td>
        <td>${this._safe(row.container_type)}</td>
        <td>${this._safe(row.destination)}</td>
        <td>${this._safe(row.count)}</td>
      </tr>`).join("")}</tbody>
    </table>`;
  }

  _prepContainerPlan(rows) {
    const neededRows = rows.filter((row) => row.needed || row.available || row.missing);
    if (!neededRows.length) {
      return this._empty("No container requirements generated yet.");
    }
    return `<table class="prep-table">
      <thead><tr><th>Type</th><th>Needed</th><th>Available</th><th>Status</th></tr></thead>
      <tbody>${neededRows.map((row) => `<tr>
        <td><strong>${this._safe(row.type)}</strong></td>
        <td>${this._safe(row.needed)}</td>
        <td>${this._safe(row.available)}</td>
        <td class="${row.missing ? "warn" : "ok"}">${row.missing ? `Missing ${this._safe(row.missing)}` : "Ready"}</td>
      </tr>`).join("")}</tbody>
    </table>`;
  }

  _prepCloneTemplates(templates) {
    if (!templates.length) {
      return this._empty("No prep session templates yet.");
    }
    return templates.map((template) => this._summaryRow(template.name, [
      template.source,
      `Keeps ${this._safe((template.keeps || []).join(", "))}`,
    ], {
      action: `<button type="button" class="secondary" data-clone-prep-session="${this._safe(template.id)}" data-template-name="${this._safe(template.name)}">Use as base</button>`,
    })).join("");
  }

  _prepChecklist(items) {
    return items.length
      ? items.map((item) => `<label class="row compact-row"><span><input type="checkbox" /> ${this._safe(item)}</span></label>`).join("")
      : this._empty("No checklist items.");
  }

  _infoView(data) {
    const summary = data?.summary || {};
    const operations = data?.operations || {};
    const shopping = data?.shopping || {};
    const foods = data?.foods || [];
    const recipes = data?.recipes || [];
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
    const foods = data?.foods || [];
    const logbook = data?.logbook || [];
    const socket = this._eventUnsubscribe ? "subscribed" : this._eventSubscription ? "subscribing" : "fallback";
    const payload = JSON.stringify(data || {}, null, 2);
    return `<section class="stack">
      <section class="card">
        <div class="actions">
          <h2>Dev controls</h2>
          <button type="button" class="secondary" id="dev-refresh">Refresh overview</button>
          <button type="button" class="secondary" id="dev-copy-overview">Copy overview JSON</button>
          ${data?.operations?.dev_mode ? `<button type="button" class="secondary" id="dev-simulate-crud">Simulate CRUD</button>` : ""}
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
            <h2>Shopping workflow</h2>
            ${this._shoppingStatus(shopping)}
          </section>
          <section class="card">
            <h2>Add shopping item</h2>
            ${this._shoppingItemForm(foods)}
          </section>
          <section class="card">
            <h2>Shopping activity</h2>
            ${logbook.filter((entry) => String(entry.action || "").toLowerCase().includes("shopping")).slice(0, 8).map((entry) => this._logRow(entry)).join("") || this._empty("No shopping actions recorded.")}
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

  _opsStrip(summary, operations, shopping = {}, storageAttention = {}, activeTab = "", mealPrep = {}) {
    const providers = (operations.catalog_providers || []).join(" + ") || "none";
    const health = operations.health || {};
    const badHealth = storageAttention.attention_count ?? ((health.warning || 0) + (health.critical || 0));
    const mode = operations.dev_mode ? "DEV" : "Live";
    const shoppingProvider = shopping.provider || operations.shopping_provider || "auto";
    const productTarget = shopping.product_backed_target || "grocy";
    const textTarget = shopping.free_text_target || "grocy";
    const minimumStock = shopping.grocy_minimum_stock ? "minimum stock available" : "minimum stock unavailable";
    const missing = summary.missing ?? 0;
    const empty = summary.empty ?? 0;
    const dirty = summary.dirty ?? 0;
    const dashboardSeverity = badHealth || missing || empty ? "critical" : dirty ? "warning" : "ok";
    if (activeTab === "dashboard") {
      return `<section class="ops-strip">
        <div class="ops-card ${dashboardSeverity}"><strong>Critical: ${this._safe((badHealth || 0) + (missing || 0) + (empty || 0))}</strong><span>${this._safe(badHealth)} storage · ${this._safe(missing)} missing · ${this._safe(empty)} empty</span></div>
        <div class="ops-card ${badHealth ? "warning" : "ok"}"><strong>Storage alerts: ${this._safe(badHealth)}</strong><span>${this._safe(storageAttention.unhealthy_locations_count ?? 0)} unhealthy locations</span></div>
        <div class="ops-card ${missing ? "warning" : "ok"}"><strong>Missing prep: ${this._safe(missing)}</strong><span>${this._safe(summary.ready ?? 0)} ready components</span></div>
        <div class="ops-card ${empty ? "warning" : "ok"}"><strong>Empty containers: ${this._safe(empty)}</strong><span>${this._safe(dirty)} dirty containers</span></div>
      </section>`;
    }
    if (activeTab === "inventory") {
      return `<section class="ops-strip triple">
        <div class="ops-card"><strong>Stocked products: ${this._safe(summary.items ?? 0)}</strong><span>${this._safe(summary.foods ?? 0)} foods · ${this._safe(summary.recipes ?? 0)} recipes known</span></div>
        <div class="ops-card ${summary.product_attention ? "warning" : "ok"}"><strong>Needs review: ${this._safe(summary.product_attention ?? 0)}</strong><span>${this._safe(missing)} missing prep signals</span></div>
        <div class="ops-card"><strong>Inventory source</strong><span>Products: ${this._safe(productTarget)} · text: ${this._safe(textTarget)}</span></div>
      </section>`;
    }
    if (activeTab === "storage") {
      return `<section class="ops-strip compact">
        <div class="ops-card ${badHealth ? "warning" : "ok"}"><strong>Storage alerts: ${this._safe(badHealth)}</strong><span>${this._safe(storageAttention.unhealthy_locations_count ?? 0)} unhealthy locations</span></div>
        <div class="ops-card"><strong>Location contents</strong><span>${this._safe(summary.containers ?? 0)} containers · ${this._safe(storageAttention.prepared_inventory_at_risk_count ?? 0)} prepared at risk</span></div>
      </section>`;
    }
    if (activeTab === "planning") {
      return `<section class="ops-strip triple">
        <div class="ops-card ${missing ? "warning" : "ok"}"><strong>Missing: ${this._safe(missing)}</strong><span>${this._safe(summary.ready ?? 0)} ready</span></div>
        <div class="ops-card ${storageAttention.prepared_inventory_at_risk_count ? "warning" : "ok"}"><strong>Prep at risk: ${this._safe(storageAttention.prepared_inventory_at_risk_count ?? 0)}</strong><span>${this._safe(badHealth)} storage alerts</span></div>
        <div class="ops-card"><strong>Shopping: ${this._safe(shoppingProvider)}</strong><span>${this._safe(minimumStock)}</span></div>
      </section>`;
    }
    if (activeTab === "meal-prep") {
      const missingContainers = (mealPrep.container_plan || []).reduce((total, row) => total + (Number(row.missing) || 0), 0);
      const calendarCount = (mealPrep.calendar_entities || []).length;
      return `<section class="ops-strip triple">
        <div class="ops-card ${mealPrep.status === "ready" ? "ok" : "warning"}"><strong>Session: ${this._safe(mealPrep.status || "not planned")}</strong><span>${this._safe(mealPrep.meal_count || 1)} meals from Mealie/Grocy preview</span></div>
        <div class="ops-card ${missingContainers ? "warning" : "ok"}"><strong>Containers missing: ${this._safe(missingContainers)}</strong><span>${this._safe((mealPrep.storage_plan || []).length)} storage plan rows</span></div>
        <div class="ops-card ${calendarCount ? "ok" : "warning"}"><strong>Calendars: ${this._safe(calendarCount)}</strong><span>Home Assistant owns session scheduling</span></div>
      </section>`;
    }
    if (activeTab === "attention") {
      const attentionTotal = operations.attention_total ?? ((summary.product_attention || 0) + (summary.empty || 0) + (summary.low || 0) + (storageAttention.attention_count || 0));
      return `<section class="ops-strip triple">
        <div class="ops-card ${attentionTotal ? "warning" : "ok"}"><strong>Open tasks: ${this._safe(attentionTotal)}</strong><span>${this._safe(summary.product_attention || 0)} product · ${this._safe(summary.empty || 0)} empty · ${this._safe(summary.low || 0)} low</span></div>
        <div class="ops-card ${badHealth ? "warning" : "ok"}"><strong>Storage safety: ${this._safe(badHealth)}</strong><span>${this._safe(storageAttention.unhealthy_locations_count ?? 0)} unhealthy locations</span></div>
        <div class="ops-card ${missing ? "warning" : "ok"}"><strong>Missing prep: ${this._safe(missing)}</strong><span>${this._safe(summary.stale ?? 0)} stale · ${this._safe(summary.unassigned ?? 0)} unassigned</span></div>
      </section>`;
    }
    if (activeTab === "info") {
      return `<section class="ops-strip">
        <div class="ops-card"><strong>Catalog: ${this._safe(mode)}</strong><span>${this._safe(providers)}</span></div>
        <div class="ops-card"><strong>Catalog size</strong><span>${this._safe(summary.foods ?? 0)} foods / ${this._safe(summary.recipes ?? 0)} recipes</span></div>
        <div class="ops-card ${shopping.grocy_configured ? "ok" : "warning"}"><strong>Grocy</strong><span>${shopping.grocy_configured ? "connected" : "not configured"} · ${this._safe(minimumStock)}</span></div>
        <div class="ops-card ${shopping.kitchenowl_configured ? "ok" : "warning"}"><strong>KitchenOwl</strong><span>${shopping.kitchenowl_configured ? "connected" : "not configured"} · ${this._safe(shoppingProvider)}</span></div>
      </section>`;
    }
    return `<section class="ops-strip triple">
      <div class="ops-card"><strong>Catalog: ${this._safe(mode)}</strong><span>${this._safe(providers)}</span></div>
      <div class="ops-card"><strong>Socket/dev</strong><span>${operations.dev_mode ? "DEV simulator available" : "Live providers"}</span></div>
      <div class="ops-card"><strong>Shopping: ${this._safe(shoppingProvider)}</strong><span>Products: ${this._safe(productTarget)} · Text: ${this._safe(textTarget)}</span></div>
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
    const draftLocation = locations.some((location) => location.id === this._createContainerLocation) ? this._createContainerLocation : this._selectedLocation;
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}"${location.id === draftLocation ? " selected" : ""}>${this._safe(location.name)}</option>`).join("");
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
          <label>Container name<input name="name" placeholder="Freezer bag 1" /></label>
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

  _openCreateContainer(locationId = "") {
    if (this._isBusy()) return;
    this._tab = "storage";
    this._selectedLocation = locationId || this._selectedLocation;
    this._createContainerLocation = locationId || this._selectedLocation;
    this._showCreate = true;
    this._render();
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
      this._createContainerLocation = "";
      this._notice = "Container saved.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not save the container.";
      this._render();
    });
  }

  _openContainerEdit(tagId = "") {
    if (this._isBusy()) return;
    this._tab = "storage";
    this._showCreate = false;
    this._movingContainerTag = "";
    this._moveContainerLocation = "";
    this._editingContainerTag = tagId;
    this._render();
  }

  _openContainerMove(tagId = "", currentLocation = "") {
    if (this._isBusy()) return;
    this._tab = "storage";
    this._showCreate = false;
    this._editingContainerTag = "";
    this._movingContainerTag = tagId;
    this._moveContainerLocation = currentLocation;
    this._render();
  }

  _containerEditForm(container, locations) {
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}"${location.id === container.location_id ? " selected" : ""}>${this._safe(location.name)}</option>`).join("");
    const sublocationOptions = locations.flatMap((location) => (location.sublocations || []).map((sublocation) => `<option value="${this._safe(sublocation)}">${this._safe(location.name)} / ${this._safe(sublocation)}</option>`)).join("");
    return `
      <form class="card form" id="edit-container-form">
        <h2>Edit container</h2>
        <input type="hidden" name="tag_id" value="${this._safe(container.tag_id)}" />
        <div class="form-grid">
          <label>NFC tag<input value="${this._safe(container.tag_id)}" readonly /></label>
          <label>Container name<input name="name" value="${this._safe(container.name || "")}" /></label>
          <label>Quantity<input name="quantity" required type="number" min="0" step="any" value="${this._safe(container.quantity ?? 0)}" /></label>
          <label>Unit<input name="unit" value="${this._safe(container.unit || "")}" /></label>
          <label>Location<select name="location_id"><option value="">Choose a location</option>${locationOptions}</select></label>
          <label>Sublocation<input name="sublocation" list="edit-sublocation-options" value="${this._safe(container.sublocation || "")}" /></label>
          <datalist id="edit-sublocation-options">${sublocationOptions}</datalist>
          <label>Best before<input name="best_before_date" type="date" value="${this._safe(container.best_before_date || "")}" /></label>
          <label>Purchased<input name="purchased_date" type="date" value="${this._safe(container.purchased_date || "")}" /></label>
          <label>Opened<input name="opened_date" type="date" value="${this._safe(container.opened_date || "")}" /></label>
        </div>
        <div class="actions"><button type="button" class="secondary" id="cancel-container-edit">Cancel</button><button type="submit">Save container</button></div>
      </form>
    `;
  }

  async _saveContainerEdit(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name]?.value?.trim() || "";
    const data = {
      tag_id: value("tag_id"),
      quantity: Number(value("quantity")),
    };
    if (value("name")) data.name = value("name");
    if (value("unit")) data.unit = value("unit");
    if (value("location_id")) data.location_id = value("location_id");
    if (value("sublocation")) data.sublocation = value("sublocation");
    if (value("best_before_date")) data.best_before_date = value("best_before_date");
    if (value("purchased_date")) data.purchased_date = value("purchased_date");
    if (value("opened_date")) data.opened_date = value("opened_date");
    await this._withBusy("saving container", async () => {
      await this._hass.callService("mise_en_place_assistant", "update_container", data);
      this._editingContainerTag = "";
      this._notice = "Container saved.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not save the container.";
      this._render();
    });
  }

  _containerMoveForm(container, locations) {
    const selectedLocation = locations.some((location) => location.id === this._moveContainerLocation)
      ? this._moveContainerLocation
      : container.location_id || locations[0]?.id || "";
    this._moveContainerLocation = selectedLocation;
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}"${location.id === selectedLocation ? " selected" : ""}>${this._safe(location.name)}</option>`).join("");
    const location = locations.find((item) => item.id === selectedLocation) || {};
    const sublocations = location.sublocations?.length ? location.sublocations : [""];
    const currentSublocation = container.location_id === selectedLocation ? container.sublocation || "" : "";
    const sublocationOptions = sublocations.map((sublocation) => `<option value="${this._safe(sublocation)}"${sublocation === currentSublocation ? " selected" : ""}>${this._safe(sublocation || "Main")}</option>`).join("");
    return `
      <form class="card form" id="move-container-form">
        <h2>Move container</h2>
        <input type="hidden" name="tag_id" value="${this._safe(container.tag_id)}" />
        <div class="form-grid">
          <label>Container<input value="${this._safe(container.name || container.tag_id || "Container")}" readonly /></label>
          <label>Location<select name="location_id" id="move-container-location" required><option value="">Choose a location</option>${locationOptions}</select></label>
          <label>Sublocation<select name="sublocation">${sublocationOptions}</select></label>
        </div>
        <div class="actions"><button type="button" class="secondary" id="cancel-container-move">Cancel</button><button type="submit">Move container</button></div>
      </form>
    `;
  }

  async _saveContainerMove(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name]?.value?.trim() || "";
    const data = { tag_id: value("tag_id"), location_id: value("location_id") };
    if (value("sublocation")) data.sublocation = value("sublocation");
    await this._withBusy("moving container", async () => {
      await this._hass.callService("mise_en_place_assistant", "move_container", data);
      this._movingContainerTag = "";
      this._moveContainerLocation = "";
      this._notice = "Container moved.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not move container.";
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

  async _runContainerService(service, tagId, confirmMessage, errorMessage) {
    if (this._isBusy()) return;
    if (confirmMessage && !window.confirm(confirmMessage)) {
      return;
    }
    await this._withBusy(service.replace("_", " "), async () => {
      await this._hass.callService("mise_en_place_assistant", service, { tag_id: tagId });
      this._notice = service === "delete_container"
        ? "Container deleted."
        : service === "mark_container_eaten"
          ? "Ready meal marked eaten."
          : "Container cleared.";
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

  async _createMealPrepCalendarEvent(event) {
    event.preventDefault();
    if (this._isBusy()) return;
    const form = event.currentTarget;
    const value = (name) => form.elements[name]?.value?.trim() || "";
    const startDate = value("start_date");
    const data = {
      entity_id: value("entity_id"),
      summary: value("summary") || "Meal prep",
      start_date: startDate,
      end_date: this._nextDate(startDate),
    };
    const { selection, recipeIds, recipeQuantities } = this._prepSelectedRecipePayload(form);
    this._prepRecipeSelection = selection;
    if (value("description")) {
      data.description = value("description");
    }
    await this._withBusy("creating meal prep calendar session", async () => {
      await this._hass.callService("calendar", "create_event", data);
      await this._hass.callService("mise_en_place_assistant", "create_prep_session", {
        calendar_entity_id: data.entity_id,
        start_date_time: data.start_date,
        end_date_time: data.start_date,
        recipe_ids: recipeIds,
        recipe_quantities: recipeQuantities,
        description: data.description || "",
      });
      this._mealPrepSummaryDraft = "";
      this._notice = "Meal prep session added to Home Assistant calendar.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not create the meal prep calendar session.";
      this._render();
    });
  }

  _clonePrepSession(button) {
    if (this._isBusy()) return;
    const templateName = button.dataset.templateName || "Meal prep session";
    this._mealPrepSummaryDraft = `Clone: ${templateName}`;
    this._notice = "Prep session template loaded. Choose a new calendar time to save it.";
    this._render();
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

  async _rollTvDinner() {
    if (this._isBusy() || !this._hass) return;
    await this._withBusy("rolling tv dinner", async () => {
      this._tvDinnerPlan = await this._hass.callWS({
        type: "mise_en_place_assistant/tv_dinner_plan",
        meal_count: this._tvDinnerCount || 1,
      });
      this._notice = "TV dinner rolled.";
      this._render();
    }, (err) => {
      this._error = err?.message || "Could not roll TV dinner.";
      this._render();
    });
  }

  async _transferTvDinnerMeal(mealId) {
    if (this._isBusy() || !this._hass) return;
    await this._load();
    const meals = this._tvDinnerTransferMeals(this._tvDinnerPlan, this._availableTvDinnerContainers(this._data), this._data)
      .filter((meal) => String(meal.meal || "") === String(mealId || ""));
    if (!meals.length) {
      this._error = "This TV dinner meal is no longer available. Roll again to refresh the source components.";
      this._render();
      return;
    }
    await this._withBusy("transferring tv dinner", async () => {
      await this._hass.callService("mise_en_place_assistant", "transfer_tv_dinners", { meals });
      const remaining = (this._tvDinnerPlan?.meals || []).filter((meal) => String(meal.meal || "") !== String(mealId || ""));
      this._tvDinnerPlan = remaining.length ? { ...this._tvDinnerPlan, meals: remaining, meal_count: remaining.length } : null;
      this._notice = "TV dinner transferred to a fridge container.";
      await this._loadIfNoEventSocket();
    }, (err) => {
      this._error = err?.message || "Could not transfer TV dinner.";
      this._render();
    });
  }

  _tvDinnerTransferMeals(plan = {}, availableContainers = [], data = {}) {
    const currentContainers = new Map((data?.containers || []).map((container) => [container.tag_id, container]));
    const usedContainers = new Set();
    return (plan?.meals || []).map((meal, index) => ({ meal, index })).filter(({ meal }) => {
      const components = meal.components || {};
      return meal.complete !== false && ["veggie", "starch", "protein"].every((role) => this._tvDinnerSourceAvailable(components[role], role, currentContainers));
    }).slice(0, availableContainers.length).map(({ meal, index }) => {
      const components = meal.components || {};
      const preferredContainer = availableContainers[index]?.tag_id || "";
      const fallbackContainer = availableContainers.find((container) => !usedContainers.has(container.tag_id))?.tag_id || "";
      const containerTagId = preferredContainer && !usedContainers.has(preferredContainer) ? preferredContainer : fallbackContainer;
      if (containerTagId) {
        usedContainers.add(containerTagId);
      }
      return {
        meal: meal.meal,
        complete: true,
        container_type: "tv_dinner",
        container_tag_id: containerTagId,
        components: {
          veggie: this._tvDinnerTransferComponent(components.veggie),
          starch: this._tvDinnerTransferComponent(components.starch),
          protein: this._tvDinnerTransferComponent(components.protein),
        },
      };
    });
  }

  _tvDinnerTransferComponent(component = {}) {
    return {
      tag_id: component.tag_id,
      label: component.label,
      quantity: 1,
    };
  }

  _tvDinnerSourceAvailable(component = {}, role = "", currentContainers = new Map()) {
    if (!component?.tag_id) {
      return false;
    }
    if (!currentContainers.size) {
      return true;
    }
    const container = currentContainers.get(component.tag_id);
    const quantity = Number(container?.canonical_quantity ?? container?.quantity ?? 0);
    const currentRole = container?.recipe?.meal_component_role || container?.recipe?.component || component.role || "";
    return Boolean(container && Number.isFinite(quantity) && quantity > 0 && currentRole === role);
  }

  _availableTvDinnerContainers(data = {}) {
    return (data?.containers || []).filter((container) => {
      const quantity = Number(container.canonical_quantity ?? container.quantity ?? 0);
      return Number.isFinite(quantity) && quantity === 0 && this._normalizedContainerType(container) === "tv dinner";
    });
  }

  _normalizedContainerType(container = {}) {
    const explicit = String(container.container_type || container.storage_container_type || container.item_format || container.format || "").trim().toLowerCase().replaceAll("_", " ").replaceAll("-", " ");
    const haystack = [explicit, container.name, container.item_label].map((value) => String(value || "")).join(" ").toLowerCase().replaceAll("_", " ").replaceAll("-", " ");
    return haystack.includes("tv dinner") ? "tv dinner" : explicit;
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
        meal_component_role: value("meal_component_role"),
        meal_component_family: value("meal_component_family"),
        meal_component_detail: value("meal_component_detail"),
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
    const button = this._suggestedActionButtons(action, payload);
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

  _suggestedActionButtons(action, encodedPayload = "") {
    const payload = encodedPayload || encodeURIComponent(JSON.stringify(action.payload || {}));
    return action.service
      ? `<button type="button" class="secondary" data-suggested-service="${this._safe(action.service)}" data-suggested-payload="${payload}" data-suggested-title="${this._safe(action.title)}">${this._safe(this._suggestedActionLabel(action))}</button>`
      : action.open_tab
        ? `<button type="button" class="secondary" data-suggested-tab="${this._safe(action.open_tab)}">Open review</button>`
        : "";
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
    if (service.includes("clear")) {
      return "Clear container";
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

  _completeMealPlan(plan = {}) {
    const uses = plan.uses || {};
    const roles = [
      ["veggie", "Veggie"],
      ["starch", "Starch"],
      ["protein", "Protein"],
    ];
    const status = plan.complete ? "ok" : "warn";
    const summary = plan.complete
      ? `${plan.meal_count || 1} complete meal${Number(plan.meal_count || 1) === 1 ? "" : "s"} ready`
      : "Missing meal components";
    const roleRows = roles.map(([role, label]) => {
      const rows = uses[role] || [];
      const shortage = plan.shortages?.[role];
      return `<div class="row compact-row">
        <div>
          <p class="name">${label}${shortage ? ` · missing ${this._safe(shortage.missing)}` : ""}</p>
          ${rows.length ? rows.map((item) => this._completeMealSource(item)).join("") : this._empty("No eligible portions.")}
        </div>
      </div>`;
    }).join("");
    const skipped = (plan.skipped || []).slice(0, 6).map((item) => `<p class="muted subline">${this._safe(item.label)}: ${this._safe(item.reason)}</p>`).join("");
    return `<div class="summary-row ${status}">
        <p class="name">${this._safe(summary)}</p>
        <p class="muted subline">Preview only &middot; ${this._safe(plan.meal_count || 1)} portions per role</p>
      </div>
      ${roleRows}
      ${skipped ? `<div class="row compact-row"><div><p class="name">Skipped</p>${skipped}</div></div>` : ""}`;
  }

  _completeMealSource(item) {
    const diversity = [item.family && item.family !== "unknown" ? item.family : "", item.detail || ""].filter(Boolean).join(" · ");
    const place = [item.location, item.sublocation].filter(Boolean).join(" / ");
    return `<p class="muted subline">${this._safe(item.quantity)} ${this._safe(item.unit)} ${this._safe(item.label)}${diversity ? ` · ${this._safe(diversity)}` : ""}${place ? ` · ${this._safe(place)}` : ""}</p>`;
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

  _recipeSuggestionRow(recipe) {
    const coverage = recipe.ingredient_count ? `${recipe.matched_count || 0}/${recipe.ingredient_count}` : "";
    const matched = (recipe.matched || []).map((item) => {
      const bestBefore = item.best_before_date ? ` · best before ${this._safe(this._relativeDateLabel(item.best_before_date))}` : "";
      return `<p class="muted subline">${this._safe(item.label)}${item.stock_quantity ? ` · ${this._safe(item.stock_quantity)}` : ""}${bestBefore}</p>`;
    }).join("");
    const missing = (recipe.missing || []).map((item) => `<p class="muted subline">${this._safe(item.label)}${item.amount ? ` · ${this._safe(item.amount)}` : ""}</p>`).join("");
    const bestBefore = (recipe.best_before || []).map((item) => `<p class="muted subline">${this._safe(item.label)}: ${this._safe(this._relativeDateLabel(item.best_before_date))}${item.days !== null && item.days !== undefined ? ` (${this._safe(this._relativeDayCount(item.days))})` : ""}</p>`).join("");
    return `<div class="row compact-row">
      <div>
        <p class="name">${this._safe(recipe.label)}</p>
        <p class="muted subline">${this._safe(this._relativeDatesInText(recipe.reason || "Matches current stock."))}</p>
        <div class="compare-grid">
          <div>
            <p class="muted">Stock match</p>
            ${matched || this._empty("No matched ingredients.")}
          </div>
          <div>
            <p class="muted">Best-before</p>
            ${bestBefore || this._empty("No urgent best-before ingredient.")}
          </div>
        </div>
        ${missing ? `<div style="margin-top: 8px;"><p class="muted">Missing or unknown</p>${missing}</div>` : ""}
      </div>
      <div class="qty ${recipe.missing_count ? "warn" : "ok"}">${this._safe(coverage)}<br><span class="muted">${this._safe(recipe.score || 0)}</span></div>
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
    const details = [item.format, ...extraDetails].filter(Boolean).map((line) => `<p class="muted subline">${this._safe(this._relativeDatesInText(line))}</p>`).join("");
    const pills = [item.tag_id || "no tag", ...extraPills].filter(Boolean).map((pill) => `<span class="pill">${this._safe(pill)}</span>`).join("");
    const attention = this._containerAttention(item).join("");
    const lifecycle = this._containerLifecycleChip(item);
    return `<div class="row container-card kind-${this._safe(this._cssToken(kind))}">
      <div>
        <div class="container-titleline">
          <ha-icon icon="${this._contentKindIcon(kind)}"></ha-icon>
          <p class="name container-name"><span>${this._safe(title)}</span>${itemLabel}</p>
        </div>
        <div class="container-meta">
          ${lifecycle}
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

  _containerLifecycleChip(item) {
    const state = item.state === "deleted" ? "deleted" : "active";
    const labels = {
      active: "Tracked",
      deleted: "Deleted",
    };
    const icons = {
      active: "mdi:check-circle-outline",
      deleted: "mdi:trash-can-outline",
    };
    return `<span class="container-chip state-${this._safe(state)}" title="${this._safe(this._containerLifecycleTitle(state))}"><ha-icon icon="${icons[state]}"></ha-icon>${this._safe(labels[state])}</span>`;
  }

  _containerLifecycleTitle(state) {
    return {
      active: "This physical container is managed and has contents.",
      empty: "This physical container is managed and ready to refill.",
      low: "This physical container is managed but running low.",
      deleted: "This physical container was marked gone, damaged, or discarded.",
    }[state] || "Container lifecycle state";
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

  _managedContainerRow(container, locations) {
    const empty = this._quantityNumber(container) === 0;
    const details = [
      this._containerDateLine(container),
      container.updated_at ? `Updated ${this._relativeDateTimeLabel(container.updated_at)}` : "",
    ];
    return this._containerRow(container, empty ? "empty" : "", details, [], this._storageContainerActions(container, locations));
  }

  _storageContainerActions(container, locations) {
    const edit = `<button type="button" class="icon-button" data-edit-container="${this._safe(container.tag_id)}" title="Edit container" aria-label="Edit container"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>`;
    const move = `<button type="button" class="icon-button" data-open-move-container="${this._safe(container.tag_id)}" data-current-location="${this._safe(container.location_id || "")}" title="Move container" aria-label="Move container"><ha-icon icon="mdi:map-marker-right-outline"></ha-icon></button>`;
    const clear = `<button type="button" class="icon-button danger" data-clear-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}" title="Clear container" aria-label="Clear container"><ha-icon icon="mdi:delete-sweep-outline"></ha-icon></button>`;
    const remove = `<button type="button" class="icon-button danger" data-delete-container="${this._safe(container.tag_id)}" data-container-name="${this._safe(container.name)}" title="Mark physical container deleted" aria-label="Mark physical container deleted"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>`;
    return `${edit}${move}${clear}${remove}`;
  }

  _moveSelect(container, locations) {
    const choices = locations.filter((location) => location.editable !== false).flatMap((location) => {
      const base = [`<option value="${this._safe(location.id)}||">${this._safe(location.name)}</option>`];
      return base.concat((location.sublocations || []).map((sublocation) => `<option value="${this._safe(location.id)}||${this._safe(sublocation)}">${this._safe(location.name)} / ${this._safe(sublocation)}</option>`));
    }).join("");
    return `<span class="icon-select" title="Move container"><ha-icon icon="mdi:map-marker-right-outline"></ha-icon><select data-move-tag="${this._safe(container.tag_id)}" aria-label="Move container"><option value="">Move container</option>${choices}</select></span>`;
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
    const componentRoles = [
      ["unknown", "Choose component"],
      ["veggie", "Veggie"],
      ["starch", "Starch"],
      ["protein", "Protein"],
      ["ignore", "Ignore"],
    ];
    const componentFamilies = [
      ["unknown", "Choose family"],
      ["leafy_green", "Leafy green"],
      ["cruciferous", "Cruciferous"],
      ["root", "Root"],
      ["squash", "Squash"],
      ["legume", "Legume"],
      ["mixed_vegetable", "Mixed vegetable"],
      ["rice", "Rice"],
      ["pasta", "Pasta"],
      ["potato", "Potato"],
      ["bread", "Bread"],
      ["grain", "Grain"],
      ["noodle", "Noodle"],
      ["corn", "Corn"],
      ["poultry", "Poultry"],
      ["red_meat", "Red meat"],
      ["fish", "Fish"],
      ["seafood", "Seafood"],
      ["vegetarian", "Vegetarian"],
      ["pork", "Pork"],
      ["egg", "Egg"],
      ["dairy", "Dairy"],
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
        <label>Complete meal<select name="meal_component_role">${this._options(componentRoles, metadata.meal_component_role || "unknown")}</select></label>
        <label>Diversity family<select name="meal_component_family">${this._options(componentFamilies, metadata.meal_component_family || "unknown")}</select></label>
        <label>Specific detail<input name="meal_component_detail" value="${this._safe(metadata.meal_component_detail || "")}" /></label>
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
    const details = detailLines.filter(Boolean).map((line) => `<p class="muted subline">${this._safe(this._relativeDatesInText(line))}</p>`).join("");
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

  _locationCard(location, containers = [], locations = [], selected = false, selectedSublocation = "") {
    const health = location.health || {};
    const sublocations = (location.sublocations || []).map((sublocation) => `<span class="pill">${this._safe(sublocation)}</span>`).join("");
    const sublocationNav = selected ? this._sublocationNav(location, containers, selectedSublocation) : "";
    const removeButton = location.provider === "mocked" && location.local
      ? `<button class="icon-button danger" data-delete-location="${this._safe(location.id)}" data-location-name="${this._safe(location.name)}" data-location-provider="${this._safe(location.provider || "")}" data-location-local="true" title="Remove location" aria-label="Remove location"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>`
      : "";
    const locationType = location.location_type || "other";
    const contentAttention = this._locationContentAttention(location, containers);
    const actions = location.editable !== false ? `<div class="location-card-actions"><button class="icon-button" data-edit-location="${this._safe(location.id)}" title="Edit location" aria-label="Edit location"><ha-icon icon="mdi:pencil-outline"></ha-icon></button>${removeButton}</div>` : "";
    return `<article class="card location-card type-${this._safe(this._cssToken(locationType))}${selected ? " selected" : ""}" data-select-location="${this._safe(location.id)}" tabindex="0">
      <div class="location-card-header">
        <div>
          <div class="location-card-title">
            <h2>${this._safe(location.name)}</h2>
          </div>
          <div class="location-card-meta">
            <span class="location-chip"><ha-icon icon="${this._locationTypeIcon(locationType)}"></ha-icon><span class="location-type">${this._safe(locationType.replaceAll("_", " "))}</span></span>
            ${this._locationArea(location)}
            ${contentAttention}
            ${sublocations}
          </div>
        </div>
        ${actions}
      </div>
      <div class="location-card-body">
        ${sublocationNav}
      </div>
    </article>`;
  }

  _storageDetail(location, selectedSublocation, containers = [], locations = []) {
    const health = location.health || {};
    const readings = Object.entries(health.readings || {}).map(([role, reading]) => `<div class="reading"><strong>${this._safe(role.replaceAll("_", " "))}</strong><br>${this._safe(reading.state)}${reading.unit ? ` ${this._safe(reading.unit)}` : ""}</div>`).join("");
    const matching = containers
      .filter((container) => container.location_id === location.id && (container.sublocation || "Main") === selectedSublocation)
      .sort((a, b) => [
        (a.item_label || a.name || "").localeCompare(b.item_label || b.name || ""),
        (a.name || "").localeCompare(b.name || ""),
      ].find((result) => result !== 0) || 0);
    const problems = health.problems?.length ? `<div class="location-problems"><ha-icon icon="mdi:alert"></ha-icon><span>${this._safe(health.problems.join(" · "))}</span></div>` : "";
    const locationType = location.location_type || "other";
    return `<section class="card storage-detail">
      <div class="storage-detail-header">
        <div class="storage-detail-title">
          <ha-icon icon="${this._locationTypeIcon(locationType)}"></ha-icon>
          <div>
            <h2>${this._safe(location.name)}</h2>
            <p class="muted subline">${this._safe(selectedSublocation)} · ${this._safe(matching.length)} ${matching.length === 1 ? "container" : "containers"}</p>
          </div>
        </div>
        <div class="actions">${location.editable === false ? "" : `<button class="icon-button" data-add-container-location="${this._safe(location.id)}" title="Add container here" aria-label="Add container here"><ha-icon icon="mdi:plus-box-outline"></ha-icon></button>`}</div>
      </div>
      <section class="location-overview">
        ${this._locationFacts(location, containers, health)}
        ${this._locationMonitoring(health, readings)}
        ${problems}
      </section>
      <div class="location-contents">
        ${matching.length ? matching.map((item) => this._locationContentRow(item, locations)).join("") : this._empty(`No containers in ${selectedSublocation}.`)}
      </div>
    </section>`;
  }

  _locationSublocations(location, containers = []) {
    const counts = new Map();
    for (const container of containers.filter((item) => item.location_id === location.id)) {
      const name = container.sublocation || "Main";
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    for (const name of location.sublocations || []) {
      if (!counts.has(name)) {
        counts.set(name, 0);
      }
    }
    if (!counts.size) {
      counts.set("Main", 0);
    }
    return Array.from(counts.entries()).map(([name, count]) => ({ name, count }));
  }

  _sublocationNav(location, containers = [], selectedSublocation = "") {
    return `<div class="sublocation-list">${this._locationSublocations(location, containers).map((sublocation) => `
      <button type="button" class="sublocation-button${sublocation.name === selectedSublocation ? " active" : ""}" data-location-id="${this._safe(location.id)}" data-select-sublocation="${this._safe(sublocation.name)}">
        <strong>${this._safe(sublocation.name)}</strong>
        <span>${this._safe(sublocation.count)} ${sublocation.count === 1 ? "container" : "containers"}</span>
      </button>
    `).join("")}</div>`;
  }

  _locationFacts(location, containers = [], health = {}) {
    const matching = containers.filter((container) => container.location_id === location.id);
    const sublocationCount = new Set(matching.map((container) => container.sublocation || "Main")).size;
    const kinds = matching.reduce((acc, container) => {
      const kind = container.content_kind || "empty";
      acc[kind] = (acc[kind] || 0) + 1;
      return acc;
    }, {});
    const contentMix = Object.entries(kinds)
      .map(([kind, count]) => `${count} ${kind.replaceAll("_", " ")}`)
      .join(" · ") || "No contents";
    const configured = health.status && health.status !== "not_configured";
    const status = configured ? this._storageStatusLabel(health.status, ["warning", "critical"].includes(health.status) ? 1 : 0) : "No live sensors";
    const provider = [location.provider || "local", location.local ? "local" : ""].filter(Boolean).join(" · ");
    const facts = [
      ["Status", status],
      ["Sublocations", sublocationCount ? `${sublocationCount} active / ${(location.sublocations || []).length || 0} configured` : `${(location.sublocations || []).length || 0} configured`],
      ["Contents", contentMix],
      ["Source", provider],
    ];
    return `<div class="location-facts">${facts.map(([label, value]) => `<div class="location-fact"><span>${this._safe(label)}</span><strong>${this._safe(value)}</strong></div>`).join("")}</div>`;
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
      dry_storage: "mdi:package-variant-closed",
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
        <h3><span>${this._safe(sublocation)}</span><span class="content-count">${this._safe(items.length)} ${items.length === 1 ? "container" : "containers"}</span></h3>
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

  _inventoryProductGroups(items = []) {
    const stocked = items
      .filter((item) => this._inventoryAmountValue(item) > 0)
      .sort((a, b) => (a.label || "").localeCompare(b.label || ""));
    const prepared = stocked.filter((item) => {
      const text = `${item.label || ""} ${item.content_kind || ""} ${item.source || ""}`.toLowerCase();
      return text.includes("meal") || text.includes("recipe") || text.includes("prepared");
    });
    return {
      stocked,
      prepared,
    };
  }

  _inventoryFilterControls(items = []) {
    const filters = this._normalizedInventoryFilters(items);
    const categoryOptions = [
      ["all", "All stock"],
      ["prepared", "Prepared"],
      ["catalog", "Catalog stock"],
      ["local", "Local stock"],
    ];
    const sources = [...new Set(items.map((item) => item.source || "mise").filter(Boolean))]
      .sort((a, b) => this._inventorySourceLabel(a).localeCompare(this._inventorySourceLabel(b)));
    const sourceOptions = [["all", "All sources"], ...sources.map((source) => [source, this._inventorySourceLabel(source)])];
    const locations = [...new Set(items.flatMap((item) => Object.keys(item.locations || {})))]
      .sort((a, b) => a.localeCompare(b));
    const locationOptions = [["all", "All locations"], ...locations.map((location) => [location, location])];
    const pageSizeOptions = [[5, "5 rows"], [10, "10 rows"], [25, "25 rows"], [50, "50 rows"]];
    return `
      <div class="inventory-controls">
        <label>Type<select data-inventory-filter="category">${this._options(categoryOptions, filters.category)}</select></label>
        <label>Source<select data-inventory-filter="source">${this._options(sourceOptions, filters.source)}</select></label>
        <label>Location<select data-inventory-filter="location">${this._options(locationOptions, filters.location)}</select></label>
        <label>Rows<select data-inventory-page-size>${this._options(pageSizeOptions, String(this._inventoryPageSize || 10))}</select></label>
      </div>
    `;
  }

  _inventoryFilteredProducts(items = []) {
    const filters = this._normalizedInventoryFilters(items);
    return items.filter((item) => {
      if (filters.category !== "all" && this._inventoryCategory(item) !== filters.category) {
        return false;
      }
      if (filters.source !== "all" && (item.source || "mise") !== filters.source) {
        return false;
      }
      if (filters.location !== "all" && !Object.keys(item.locations || {}).includes(filters.location)) {
        return false;
      }
      return true;
    });
  }

  _inventoryGroupedProducts(items = []) {
    return this._inventoryLogicalGroups(items).map((group) => `
      <section class="content-group inventory-group">
        <h3>${this._safe(group.label)} <span class="content-count">${this._safe(group.items.length)} ${group.items.length === 1 ? "item" : "items"}</span></h3>
        ${group.items.map((item) => this._inventoryProductRow(item)).join("")}
      </section>
    `).join("");
  }

  _inventoryLogicalGroups(items = []) {
    const groups = new Map();
    for (const item of items) {
      const label = this._inventoryLogicalGroupLabel(item);
      if (!groups.has(label)) {
        groups.set(label, []);
      }
      groups.get(label).push(item);
    }
    const order = ["Prepared foods", "Grocy stock", "Mealie recipe stock", "DEV stock", "Mise inventory", "Other stock"];
    return [...groups.entries()]
      .sort(([left], [right]) => {
        const leftIndex = order.includes(left) ? order.indexOf(left) : order.length;
        const rightIndex = order.includes(right) ? order.indexOf(right) : order.length;
        return leftIndex - rightIndex || left.localeCompare(right);
      })
      .map(([label, groupItems]) => ({
        label,
        items: groupItems.sort((a, b) => (a.label || "").localeCompare(b.label || "")),
      }));
  }

  _inventoryPagedProducts(items = []) {
    const pageSize = Math.max(5, Number(this._inventoryPageSize) || 10);
    const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
    const page = Math.min(Math.max(1, Number(this._inventoryPage) || 1), pageCount);
    this._inventoryPage = page;
    this._inventoryPageSize = pageSize;
    const start = (page - 1) * pageSize;
    return {
      items: items.slice(start, start + pageSize),
      page,
      pageCount,
      pageSize,
      total: items.length,
      start: items.length ? start + 1 : 0,
      end: Math.min(items.length, start + pageSize),
    };
  }

  _inventoryPager(page = {}) {
    if (!page.total) {
      return "";
    }
    return `
      <div class="pager">
        <span class="muted">${this._safe(page.start)}-${this._safe(page.end)} of ${this._safe(page.total)} stocked products</span>
        <div class="actions">
          <button type="button" class="secondary" data-inventory-page="${this._safe(page.page - 1)}" ${page.page <= 1 ? "disabled" : ""}>Previous</button>
          <span class="muted">Page ${this._safe(page.page)} of ${this._safe(page.pageCount)}</span>
          <button type="button" class="secondary" data-inventory-page="${this._safe(page.page + 1)}" ${page.page >= page.pageCount ? "disabled" : ""}>Next</button>
        </div>
      </div>
    `;
  }

  _normalizedInventoryFilters(items = []) {
    const filters = this._inventoryFilters || {};
    const sources = new Set(items.map((item) => item.source || "mise"));
    const locations = new Set(items.flatMap((item) => Object.keys(item.locations || {})));
    const category = ["all", "prepared", "catalog", "local"].includes(filters.category) ? filters.category : "all";
    return {
      category,
      source: filters.source === "all" || sources.has(filters.source) ? filters.source || "all" : "all",
      location: filters.location === "all" || locations.has(filters.location) ? filters.location || "all" : "all",
    };
  }

  _inventoryCategory(item = {}) {
    return this._inventoryIsPrepared(item) ? "prepared" : item.source && item.source !== "mise" ? "catalog" : "local";
  }

  _inventoryLogicalGroupLabel(item = {}) {
    if (this._inventoryIsPrepared(item)) {
      return "Prepared foods";
    }
    if (item.source) {
      return this._inventorySourceLabel(item.source);
    }
    return Object.keys(item.locations || {}).length ? "Mise inventory" : "Other stock";
  }

  _inventoryIsPrepared(item = {}) {
    const text = `${item.label || ""} ${item.content_kind || ""} ${item.source || ""}`.toLowerCase();
    return text.includes("meal") || text.includes("recipe") || text.includes("prepared");
  }

  _inventoryReviewRows(items = []) {
    return items
      .filter((item) => item && (item.reasons?.length || !item.has_stock))
      .sort((a, b) => (a.label || "").localeCompare(b.label || ""));
  }

  _inventoryProductRow(item) {
    const amount = this._inventoryAmount(item);
    const freshness = this._inventoryProductFreshness(item);
    const pills = [...this._inventorySummaryPills(item), freshness.pill].filter(Boolean);
    const lastStock = item.last_stock_log?.action ? `${item.last_stock_log.action}: ${item.last_stock_log.message || ""}` : "";
    const action = this._inventoryProductActions(item);
    return this._summaryRow(item.label || "Inventory item", [
      this._inventoryProductIdentity(item),
      this._inventoryLocationSummary(item),
      this._inventoryPhysicalStockSummary(item),
      freshness.detail,
      lastStock ? `Last stock write: ${lastStock}` : "",
    ], {
      quantity: amount.value,
      unit: amount.unit,
      klass: freshness.klass,
      pills,
      action,
    });
  }

  _inventoryReviewRow(item) {
    const quantity = item.has_stock ? `${item.quantity ?? 0} ${item.unit || ""}`.trim() : "Missing";
    return this._summaryRow(item.label || "Review item", [
      (item.reasons || []).join(", ") || "Inventory policy needs review",
      this._inventorySourceLabel(item.source),
    ], {
      quantity,
      klass: item.has_stock ? "warn" : "critical",
      action: item.item_id ? `<button type="button" class="secondary" data-queue-product="${this._safe(item.item_id)}" data-product-label="${this._safe(item.label)}">Queue missing prep</button>` : "",
    });
  }

  _inventoryReadyToEatSoon(containers = [], locations = []) {
    const locationTypes = new Map(locations.map((location) => [location.id, location.location_type || "other"]));
    return containers
      .filter((container) => {
        const locationType = locationTypes.get(container?.location_id) || "";
        return this._isReadyToEatContainer(container, locationType) && this._inventoryDueSoonStatus(container, locationType).rank > 0;
      })
      .sort((left, right) => {
        const leftStatus = this._inventoryDueSoonStatus(left, locationTypes.get(left.location_id) || "");
        const rightStatus = this._inventoryDueSoonStatus(right, locationTypes.get(right.location_id) || "");
        return rightStatus.rank - leftStatus.rank || leftStatus.sortDate.localeCompare(rightStatus.sortDate);
      });
  }

  _inventoryPagedReadyMeals(items = []) {
    const pageSize = 5;
    const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
    const page = Math.min(Math.max(1, Number(this._readyMealPage) || 1), pageCount);
    this._readyMealPage = page;
    const start = (page - 1) * pageSize;
    return {
      items: items.slice(start, start + pageSize),
      page,
      pageCount,
      pageSize,
      total: items.length,
      start: items.length ? start + 1 : 0,
      end: Math.min(items.length, start + pageSize),
    };
  }

  _inventoryReadyMealPager(page = {}) {
    if (!page.total) {
      return "";
    }
    return `
      <div class="pager">
        <span class="muted">${this._safe(page.start)}-${this._safe(page.end)} of ${this._safe(page.total)} ready meals</span>
        <div class="actions">
          <button type="button" class="secondary" data-ready-meal-page="${this._safe(page.page - 1)}" ${page.page <= 1 ? "disabled" : ""}>Previous</button>
          <span class="muted">Page ${this._safe(page.page)} of ${this._safe(page.pageCount)}</span>
          <button type="button" class="secondary" data-ready-meal-page="${this._safe(page.page + 1)}" ${page.page >= page.pageCount ? "disabled" : ""}>Next</button>
        </div>
      </div>
    `;
  }

  _inventoryReadyToEatTable(containers = [], locations = []) {
    return `
      <div class="table-wrap">
        <table class="prep-table ready-meal-table">
          <thead>
            <tr>
              <th>Meal</th>
              <th>Container and place</th>
              <th>Qty</th>
              <th>Out</th>
              <th>Urgency</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>${containers.map((container) => this._inventoryReadyToEatRow(container, locations)).join("")}</tbody>
        </table>
      </div>
    `;
  }

  _inventoryReadyToEatRow(container, locations = []) {
    const locationType = (locations.find((location) => location.id === container.location_id) || {}).location_type || "";
    const status = this._inventoryDueSoonStatus(container, locationType);
    const location = this._containerPlace(container) || "No location";
    const quantity = `${container.quantity ?? 0} ${container.unit || ""}`.trim();
    const label = container.item_label || container.name || "Ready meal";
    const containerLabel = container.name && container.name !== label ? container.name : "Ready meal container";
    const urgency = this._inventoryReadyMealUrgency(container, status);
    return `
      <tr>
        <td><span class="name">${this._safe(label)}</span><span class="muted subline">Ready to eat</span></td>
        <td><span class="name">${this._safe(containerLabel)}</span><span class="muted subline">${this._safe(location)}</span></td>
        <td>${this._safe(quantity || "1")}</td>
        <td>${this._inventoryReadyAgeBadge(container, locationType)}</td>
        <td class="${this._safe(status.klass)}">${this._safe(urgency)}</td>
        <td><button type="button" class="secondary" data-mark-container-eaten="${this._safe(container.tag_id)}" data-container-name="${this._safe(label)}">Mark eaten</button></td>
      </tr>
    `;
  }

  _inventoryReadyMealUrgency(container = {}, status = {}) {
    if (status.label) {
      return status.label;
    }
    if (container.best_before_date) {
      return `Best before ${this._relativeDateLabel(container.best_before_date)}`;
    }
    return "Ready to eat";
  }

  _inventoryReadyAgeBadge(container = {}, locationType = "") {
    const status = this._inventoryReadyStorageStatus(container, locationType);
    const age = this._inventoryReadyOutOfFreezerAge(container, locationType);
    return `<span class="ready-age ${this._safe(status.klass)}" title="${this._safe(age.label)}"><ha-icon icon="mdi:snowflake-off"></ha-icon><strong>${this._safe(age.days)}</strong><span>${age.days === 1 ? "day" : "days"}</span></span>`;
  }

  _inventoryReadyOutOfFreezerAge(container = {}, locationType = "") {
    if (locationType === "freezer") {
      return { days: 0, label: "Still in freezer" };
    }
    const age = this._inventoryReadyStorageAge(container, locationType);
    if (age) {
      return { days: age.days, label: `Out of freezer for ${this._relativeDayCount(age.days)}` };
    }
    return { days: 0, label: "Out-of-freezer date unavailable" };
  }

  _isReadyToEatContainer(container = {}, locationType = "") {
    const quantity = Number(container.canonical_quantity ?? container.quantity ?? 0);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      return false;
    }
    if (container.content_kind === "meal" && locationType !== "freezer") {
      return true;
    }
    return this._normalizedContainerType(container) === "tv dinner";
  }

  _inventoryDueSoonStatus(container = {}, locationType = "") {
    const bestBefore = this._parseInventoryDate(container.best_before_date);
    const storageStatus = this._inventoryReadyStorageStatus(container, locationType);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (!bestBefore) {
      return storageStatus;
    }
    const days = Math.round((bestBefore.getTime() - today.getTime()) / 86400000);
    let freshnessStatus = { rank: 0, label: "", klass: "", sortDate: String(container.best_before_date || "") };
    if (days < 0) {
      freshnessStatus = { rank: 4, label: `Best before ${this._relativeDateLabel(container.best_before_date)} · overdue`, klass: "critical", sortDate: String(container.best_before_date || "") };
    } else if (days <= 1) {
      freshnessStatus = { rank: 3, label: `Best before ${this._relativeDateLabel(container.best_before_date)} · due now`, klass: "critical", sortDate: String(container.best_before_date || "") };
    } else if (days <= 3) {
      freshnessStatus = { rank: 2, label: `Best before ${this._relativeDateLabel(container.best_before_date)} · ${this._relativeDayCount(days)} left`, klass: "warn", sortDate: String(container.best_before_date || "") };
    } else if (days <= 7) {
      freshnessStatus = { rank: 1, label: `Best before ${this._relativeDateLabel(container.best_before_date)} · this week`, klass: "warn", sortDate: String(container.best_before_date || "") };
    }
    return storageStatus.rank > freshnessStatus.rank ? storageStatus : freshnessStatus;
  }

  _inventoryReadyStorageStatus(container = {}, locationType = "") {
    const readyAge = this._inventoryReadyStorageAge(container, locationType);
    if (!readyAge) {
      return { rank: 0, label: "", klass: "", sortDate: "" };
    }
    const limit = locationType === "fridge" ? 4 : 1;
    if (readyAge.days >= limit) {
      return { rank: 3, label: readyAge.label, klass: "critical", sortDate: readyAge.date };
    }
    if (readyAge.days >= Math.max(1, limit - 1)) {
      return { rank: 1, label: readyAge.label, klass: "warn", sortDate: readyAge.date };
    }
    return { rank: 0, label: "", klass: "", sortDate: readyAge.date };
  }

  _inventoryReadyStorageLabel(container = {}, locationType = "") {
    return this._inventoryReadyStorageAge(container, locationType)?.label || "";
  }

  _inventoryReadyStorageAge(container = {}, locationType = "") {
    const storedSince = this._parseInventoryDateTime(container.updated_at || container.created_at);
    if (!storedSince || locationType === "freezer") {
      return null;
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    storedSince.setHours(0, 0, 0, 0);
    const days = Math.max(0, Math.round((today.getTime() - storedSince.getTime()) / 86400000));
    const date = this._formatDate(storedSince);
    return {
      date,
      days,
      label: `Not in freezer for ${this._relativeDayCount(days)}`,
    };
  }

  _parseInventoryDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) {
      return null;
    }
    const [year, month, day] = String(value).split("-").map((part) => Number(part));
    const parsed = new Date(year, month - 1, day);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  _parseInventoryDateTime(value) {
    if (!value) {
      return null;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  _formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  _containerPlace(container = {}) {
    return [container.location, container.sublocation].filter(Boolean).join(" / ");
  }

  _inventorySourceSummary(items = []) {
    if (!items.length) {
      return this._empty("No inventory sources have stock.");
    }
    const counts = items.reduce((acc, item) => {
      const label = this._inventorySourceLabel(item.source);
      acc[label] = (acc[label] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([source, count]) => this._summaryRow(source, [`${count} stocked ${count === 1 ? "product" : "products"}`]))
      .join("");
  }

  _inventoryAmount(item) {
    if (item.quantity !== undefined && item.quantity !== null && item.quantity !== "") {
      return { value: item.quantity, unit: item.unit || "" };
    }
    const quantities = Object.entries(item.quantities || {});
    if (quantities.length === 1) {
      const [[unit, value]] = quantities;
      return { value, unit };
    }
    if (quantities.length > 1) {
      return { value: quantities.map(([unit, value]) => `${value} ${unit}`).join(" + "), unit: "" };
    }
    return { value: 0, unit: item.unit || "" };
  }

  _inventoryAmountValue(item) {
    const quantity = Number(item.quantity);
    if (Number.isFinite(quantity)) {
      return quantity;
    }
    return Object.values(item.quantities || {}).reduce((total, value) => {
      const number = Number(value);
      return total + (Number.isFinite(number) ? number : 0);
    }, 0);
  }

  _inventoryLocationSummary(item) {
    const locations = Object.entries(item.locations || {});
    if (!locations.length) {
      return "Locations: not tracked";
    }
    const summary = locations.map(([location, quantities]) => {
      const amount = Object.entries(quantities || {}).map(([unit, value]) => `${value} ${unit}`).join(" + ");
      return amount ? `${location}: ${amount}` : location;
    }).join(" · ");
    return `Locations: ${summary}`;
  }

  _inventoryProductIdentity(item = {}) {
    return [
      item.item_id ? `ID ${item.item_id}` : "",
      item.content_kind ? this._inventoryContentKindLabel(item.content_kind) : "",
    ].filter(Boolean).join(" · ");
  }

  _inventoryPhysicalStockSummary(item = {}) {
    const containers = (item.physical_containers || [])
      .filter(Boolean)
      .map((container) => {
        return container.name || container.item_label || "Container";
      });
    if (containers.length) {
      return `Containers: ${containers.join(", ")}`;
    }
    if (item.containers) {
      return `Containers: ${item.containers} tracked`;
    }
    return "";
  }

  _inventoryProductFreshness(item = {}) {
    const freshnessDates = item.freshness_dates || [];
    const bestBeforeDates = [item.best_before_date, ...freshnessDates.map((entry) => entry.best_before_date)]
      .filter(Boolean)
      .sort((left, right) => String(left).localeCompare(String(right)));
    const bestBefore = bestBeforeDates[0] || "";
    const metadata = this._inventoryFreshnessMetadata(freshnessDates);
    if (!bestBefore) {
      return {
        detail: metadata ? `Freshness: ${metadata}` : "",
        pill: metadata ? "Dated stock" : "",
        klass: "",
      };
    }
    const status = this._inventoryBestBeforeStatus(bestBefore);
    const parts = [`best before ${this._relativeDateLabel(bestBefore)}`, status.detail, metadata].filter(Boolean);
    return {
      detail: `Freshness: ${parts.join(" · ")}`,
      pill: status.pill,
      klass: status.klass,
    };
  }

  _inventoryFreshnessMetadata(entries = []) {
    const lines = [];
    for (const entry of entries) {
      const dated = [
        entry.opened_date ? `opened ${this._relativeDateLabel(entry.opened_date)}` : "",
        entry.purchased_date ? `purchased ${this._relativeDateLabel(entry.purchased_date)}` : "",
        entry.price ? `price ${entry.price}` : "",
      ].filter(Boolean).join(" · ");
      if (dated) {
        lines.push(`${entry.container || "Stock"}: ${dated}`);
      }
    }
    return lines.join("; ");
  }

  _inventoryBestBeforeStatus(value) {
    const bestBefore = this._parseInventoryDate(value);
    if (!bestBefore) {
      return { detail: "", pill: "Best before", klass: "" };
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    bestBefore.setHours(0, 0, 0, 0);
    const days = Math.round((bestBefore.getTime() - today.getTime()) / 86400000);
    if (days < 0) {
      return { detail: "overdue", pill: "Overdue", klass: "critical" };
    }
    if (days === 0) {
      return { detail: "due today", pill: "Due today", klass: "critical" };
    }
    if (days <= 3) {
      return { detail: `${this._relativeDayCount(days)} left`, pill: "Use soon", klass: "warn" };
    }
    if (days <= 7) {
      return { detail: "this week", pill: "This week", klass: "warn" };
    }
    return { detail: `${this._relativeDayCount(days)} left`, pill: "Dated stock", klass: "" };
  }

  _inventoryContentKindLabel(value) {
    return { ingredient: "Ingredient", recipe: "Recipe batch", meal: "Ready meal", empty: "Empty" }[value] || String(value).replaceAll("_", " ");
  }

  _inventoryProductActions(item = {}) {
    const actions = [];
    if (this._inventoryAttentionForProduct(item)) {
      actions.push(`<button type="button" class="secondary" data-open-tab="attention">Review</button>`);
    }
    if ((item.physical_containers || []).length) {
      actions.push(`<button type="button" class="secondary" data-open-tab="storage">Storage</button>`);
    }
    if (item.item_id) {
      actions.push(`<button type="button" class="secondary" data-queue-product="${this._safe(item.item_id)}" data-product-label="${this._safe(item.label)}">Queue</button>`);
    }
    return actions.join("");
  }

  _inventoryAttentionForProduct(item = {}) {
    return (this._data?.product_attention || []).some((attention) => {
      return [item.product_id, item.item_id, item.label].filter(Boolean).some((value) => {
        return value === attention.product_id || value === attention.item_id || value === attention.label;
      });
    });
  }

  _inventoryLocationCount(items = []) {
    const names = new Set();
    for (const item of items) {
      for (const name of Object.keys(item.locations || {})) {
        names.add(name);
      }
    }
    return names.size;
  }

  _inventorySummaryPills(item) {
    const pills = [];
    if (item.has_stock === false) {
      pills.push("Missing");
    }
    return pills;
  }

  _inventorySourceLabel(source) {
    return source === "grocy" ? "Grocy stock" : source === "mealie" ? "Mealie recipe" : source === "mocked" ? "DEV stock" : source === "mise" ? "Mise inventory" : source ? `${source} stock` : "Mise inventory";
  }

  _logRow(entry) {
    return `
      <div class="log">
        <div>
          <p class="log-action">${this._safe(entry.action)}</p>
          <p class="muted subline">${this._safe(entry.message)}</p>
        </div>
        <time class="log-time">${this._relativeDateTimeLabel(entry.created_at)}</time>
      </div>
    `;
  }

  _containerDateLine(container) {
    const dates = [
      ["Best before", container.best_before_date],
      ["Purchased", container.purchased_date],
      ["Opened", container.opened_date],
    ].filter(([, value]) => value);
    return dates.map(([label, value]) => `${label}: ${this._relativeDateLabel(value)}`).join(" · ");
  }

  _quantityNumber(container) {
    const quantity = Number(container.canonical_quantity ?? container.quantity ?? 0);
    return Number.isFinite(quantity) ? quantity : 0;
  }

  _options(options, current) {
    return options.map(([value, label]) => `<option value="${this._safe(value)}"${String(value) === String(current) ? " selected" : ""}>${this._safe(label)}</option>`).join("");
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
    return this._safe(this._relativeDateTimeLabel(value));
  }

  _relativeDatesInText(value) {
    return String(value ?? "").replace(/\b\d{4}-\d{2}-\d{2}\b/g, (match) => this._relativeDateLabel(match));
  }

  _relativeDateLabel(value) {
    const date = this._parseInventoryDate(value);
    if (!date) {
      return String(value || "");
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    const days = Math.round((date.getTime() - today.getTime()) / 86400000);
    if (days === 0) {
      return "today";
    }
    if (days === 1) {
      return "tomorrow";
    }
    if (days === -1) {
      return "yesterday";
    }
    if (days > 0) {
      return `in ${this._relativeDayCount(days)}`;
    }
    return `${this._relativeDayCount(Math.abs(days))} ago`;
  }

  _relativeDateTimeLabel(value) {
    const date = this._parseInventoryDateTime(value);
    if (!date) {
      return String(value || "");
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const day = new Date(date);
    day.setHours(0, 0, 0, 0);
    const days = Math.round((day.getTime() - today.getTime()) / 86400000);
    if (days === 0) {
      return "today";
    }
    if (days === 1) {
      return "tomorrow";
    }
    if (days === -1) {
      return "yesterday";
    }
    if (days > 0) {
      return `in ${this._relativeDayCount(days)}`;
    }
    return `${this._relativeDayCount(Math.abs(days))} ago`;
  }

  _relativeDayCount(days) {
    const count = Math.abs(Number(days) || 0);
    return `${count} ${count === 1 ? "day" : "days"}`;
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
