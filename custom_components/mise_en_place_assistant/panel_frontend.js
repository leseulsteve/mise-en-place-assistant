class MiseEnPlaceAssistantPanel extends HTMLElement {
  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._connected = true;
    this._data ??= null;
    this._error ??= "";
    this._showCreate ??= false;
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

  _render() {
    const data = this._data;
    if (!this.shadowRoot) {
      return;
    }
    const summary = data?.summary || {};
    const containers = data?.containers || [];
    const items = data?.items || [];
    const foods = data?.foods || [];
    const locations = data?.locations || [];
    const logbook = data?.logbook || [];
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100%;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
        }
        * { box-sizing: border-box; }
        main {
          width: min(1180px, 100%);
          margin: 0 auto;
          padding: 24px;
        }
        header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 22px;
        }
        h1, h2, h3, p { margin: 0; }
        h1 { font-size: 32px; font-weight: 720; letter-spacing: 0; }
        h2 { font-size: 18px; font-weight: 650; }
        button {
          border: 0;
          border-radius: 999px;
          padding: 10px 16px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          font-weight: 650;
          cursor: pointer;
        }
        .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        button.secondary {
          color: var(--primary-text-color);
          background: var(--secondary-background-color, var(--card-background-color));
          border: 1px solid var(--divider-color);
        }
        .muted { color: var(--secondary-text-color); }
        .error {
          margin-bottom: 16px;
          padding: 12px 14px;
          border-radius: 12px;
          background: rgba(244, 67, 54, 0.14);
          color: var(--error-color, #f44336);
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(5, minmax(120px, 1fr));
          gap: 12px;
          margin-bottom: 18px;
        }
        .card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 14px;
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .form { margin-bottom: 18px; }
        .form > p { margin-top: 6px; }
        .form-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin: 16px 0;
        }
        label { display: grid; gap: 6px; font-size: 13px; font-weight: 650; }
        input {
          width: 100%; border: 1px solid var(--divider-color); border-radius: 10px;
          padding: 10px 11px; background: var(--primary-background-color);
          color: var(--primary-text-color); font: inherit;
        }
        select {
          width: 100%; border: 1px solid var(--divider-color); border-radius: 10px;
          padding: 10px 11px; background: var(--primary-background-color);
          color: var(--primary-text-color); font: inherit;
        }
        .metric {
          font-size: 30px;
          font-weight: 750;
          margin-top: 8px;
        }
        .sections {
          display: grid;
          grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
          gap: 18px;
          align-items: start;
        }
        .stack { display: grid; gap: 12px; }
        .row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: center;
          padding: 12px 0;
          border-top: 1px solid var(--divider-color);
        }
        .row:first-of-type { border-top: 0; }
        .name { font-weight: 650; overflow-wrap: anywhere; }
        .pill {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          background: color-mix(in srgb, var(--primary-color) 14%, transparent);
          color: var(--primary-color);
          padding: 4px 9px;
          font-size: 12px;
          font-weight: 650;
          margin-top: 6px;
        }
        .warn { color: var(--warning-color, #ff9800); }
        .empty { color: var(--error-color, #f44336); }
        .qty { font-weight: 750; text-align: right; white-space: nowrap; }
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
          padding: 11px 0;
          border-top: 1px solid var(--divider-color);
        }
        .log:first-of-type { border-top: 0; }
        .log-action { font-weight: 650; }
        .log-time { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; }
        @media (max-width: 850px) {
          main { padding: 16px; }
          header { align-items: flex-start; flex-direction: column; }
          .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .sections { grid-template-columns: 1fr; }
          .form-grid { grid-template-columns: 1fr; }
        }
      </style>
      <main>
        <header>
          <div>
            <h1>Mise en Place Assistant</h1>
            <p class="muted">Inventory, meal planning, grocery lists, food prep, and pantry management for Home Assistant.</p>
            <p class="muted">${data ? `Updated ${new Date().toLocaleTimeString()}` : "Loading overview..."}</p>
          </div>
          <div class="actions">
            <button type="button" class="secondary" id="add-container">Add container</button>
            <button type="button" id="refresh">Refresh</button>
          </div>
        </header>
        ${this._error ? `<div class="error">${this._safe(this._error)}</div>` : ""}
        ${this._showCreate ? this._createForm(locations, foods) : ""}
        <section class="grid">
          ${this._metric("Containers", summary.containers ?? 0)}
          ${this._metric("Locations", summary.locations ?? 0)}
          ${this._metric("Food items", summary.items ?? 0)}
          ${this._metric("Low", summary.low ?? 0, summary.low ? "warn" : "")}
          ${this._metric("To wash", summary.dirty ?? 0, summary.dirty ? "warn" : "")}
        </section>
        <section class="sections">
          <div class="stack">
            <section class="card">
              <h2>Inventory by product</h2>
              ${items.length ? items.map((item) => this._itemRow(item)).join("") : `<p class="muted">No filled containers yet.</p>`}
            </section>
            <section class="card">
              <h2>Containers</h2>
              ${containers.length ? containers.map((item) => this._containerRow(item)).join("") : `<p class="muted">Scan a container to start building inventory.</p>`}
            </section>
            <section class="card">
              <h2>Logbook</h2>
              ${logbook.length ? logbook.map((entry) => this._logRow(entry)).join("") : `<p class="muted">No actions recorded yet.</p>`}
            </section>
          </div>
          <div class="stack">
            <section class="card">
              <h2>Needs Attention</h2>
              ${this._attentionRows(data)}
            </section>
            <section class="card">
              <h2>Locations</h2>
              ${locations.length ? locations.map((location) => this._locationRow(location)).join("") : `<p class="muted">No locations yet.</p>`}
            </section>
          </div>
        </section>
      </main>
    `;
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.getElementById("add-container")?.addEventListener("click", () => {
      this._showCreate = !this._showCreate;
      this._render();
    });
    this.shadowRoot.getElementById("create-form")?.addEventListener("submit", (event) => this._createContainer(event));
    this.shadowRoot.getElementById("cancel-create")?.addEventListener("click", () => {
      this._showCreate = false;
      this._render();
    });
  }

  _metric(label, value, klass = "") {
    return `<article class="card"><p class="muted">${this._safe(label)}</p><p class="metric ${klass}">${this._safe(value)}</p></article>`;
  }

  _createForm(locations, foods) {
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.name)}">${this._safe(location.name)}</option>`).join("");
    const foodOptions = foods.map((food) => `<option value="${this._safe(food.id)}">${this._safe(food.label)}</option>`).join("");
    return `
      <form class="card form" id="create-form">
        <h2>Add a reusable container</h2>
        <p class="muted">Give the NFC-tagged container a stable name, then record what is in it now.</p>
        <div class="form-grid">
          <label>NFC tag<input name="tag_id" required placeholder="04:A1:C2" /></label>
          <label>Container name<input name="name" placeholder="Freezer bin 1" /></label>
          <label>Catalog food<select name="item_id" required><option value="">Choose a catalog food</option>${foodOptions}</select></label>
          <label>Quantity<input name="quantity" required type="number" min="0" step="any" value="1" /></label>
          <label>Location<input name="location" list="locations" placeholder="Freezer" /></label>
          <datalist id="locations">${locationOptions}</datalist>
        </div>
        <p class="muted">Food names and units come from the configured catalog. Container amounts remain local to each NFC tag.</p>
        <div class="actions"><button type="button" class="secondary" id="cancel-create">Cancel</button><button type="submit">Save container</button></div>
      </form>
    `;
  }

  async _createContainer(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    const data = {
      tag_id: value("tag_id"),
      item_id: value("item_id"),
      quantity: Number(value("quantity")),
    };
    if (value("name")) data.name = value("name");
    if (value("location")) data.location = value("location");
    try {
      await this._hass.callService("mise_en_place_assistant", "create_container", data);
      this._showCreate = false;
      await this._load();
    } catch (err) {
      this._error = err?.message || "Could not save the container.";
      this._render();
    }
  }

  _containerRow(item, klass = "") {
    return `
      <div class="row">
          <div>
          <p class="name">${this._safe(item.name)}</p>
          <p class="muted">${this._safe(item.item_label)} &middot; ${this._safe(item.location)}</p>
          <p class="muted">${this._safe(item.format || item.state)}</p>
          <span class="pill">${this._safe(item.tag_id || "no tag")}</span>
        </div>
        <div class="qty ${klass}">${this._safe(item.quantity)}<br><span class="muted">${this._safe(item.unit)}</span></div>
      </div>
    `;
  }

  _attentionRows(data) {
    const empty = data?.empty_containers || [];
    const low = data?.low_containers || [];
    const dirty = data?.dirty_containers || [];
    const rows = [
      ...dirty.map((item) => this._containerRow(item, "warn")),
      ...empty.map((item) => this._containerRow(item, "empty")),
      ...low.map((item) => this._containerRow(item, "warn")),
    ];
    return rows.length ? rows.join("") : `<p class="muted">Nothing needs attention.</p>`;
  }

  _locationRow(location) {
    return `<div class="location"><span>${this._safe(location.name)}</span><strong>${this._safe(location.containers)}</strong></div>`;
  }

  _itemRow(item) {
    const places = Object.keys(item.locations || {}).join(" · ");
    const amount = item.quantity ?? Object.entries(item.quantities || {}).map(([unit, quantity]) => `${quantity} ${unit}`).join(" + ");
    return `<div class="row"><div><p class="name">${this._safe(item.label)}</p><p class="muted">${this._safe(places || "Unassigned")}</p></div><div class="qty">${this._safe(amount)}${item.unit ? `<br><span class="muted">${this._safe(item.unit)}</span>` : ""}</div></div>`;
  }

  _logRow(entry) {
    return `
      <div class="log">
        <div>
          <p class="log-action">${this._safe(entry.action)}</p>
          <p class="muted">${this._safe(entry.message)}</p>
        </div>
        <time class="log-time">${this._formatTime(entry.created_at)}</time>
      </div>
    `;
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
