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
    this._tab ??= "overview";
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
      this._notice = "";
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

  _render() {
    const data = this._data;
    if (!this.shadowRoot) {
      return;
    }
    const summary = data?.summary || {};
    const containers = data?.containers || [];
    const items = data?.items || [];
    const foods = data?.foods || [];
    const recipes = data?.recipes || [];
    const mealInventory = data?.meal_inventory?.components || [];
    const areas = data?.areas || [];
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
        input, textarea {
          width: 100%; border: 1px solid var(--divider-color); border-radius: 10px;
          padding: 10px 11px; background: var(--primary-background-color);
          color: var(--primary-text-color); font: inherit;
        }
        input[type="checkbox"] { width: auto; padding: 0; }
        label span { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; }
        textarea { min-height: 42px; resize: vertical; }
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
        .review-row { grid-template-columns: 1fr; align-items: stretch; }
        .review-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin-top: 10px;
        }
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
        .tabs { display:flex; gap:8px; margin: 0 0 18px; }
        .tabs button.active { background: var(--primary-color); color: var(--text-primary-color); }
        .health { margin-top: 10px; font-weight: 650; }
        .health.ok { color: var(--success-color, #43a047); }
        .health.warning { color: var(--warning-color, #ff9800); }
        .health.critical { color: var(--error-color, #f44336); }
        .reading-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top:12px; }
        .reading { background: var(--secondary-background-color, rgba(128,128,128,.08)); border-radius: 10px; padding: 8px; font-size: 13px; }
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
        .debug-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
        }
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
          header { align-items: flex-start; flex-direction: column; }
          .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .sections { grid-template-columns: 1fr; }
          .form-grid { grid-template-columns: 1fr; }
          .debug-grid { grid-template-columns: 1fr; }
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
        ${this._notice ? `<div class="card form">${this._safe(this._notice)}</div>` : ""}
        <nav class="tabs"><button class="${this._tab === "overview" ? "active" : "secondary"}" id="tab-overview">Overview</button><button class="${this._tab === "manage" ? "active" : "secondary"}" id="tab-manage">Manage locations & containers</button><button class="${this._tab === "dev" ? "active" : "secondary"}" id="tab-dev">Dev</button></nav>
        ${this._tab === "dev" ? this._devView(data) : this._tab === "manage" ? this._manageView(locations, containers, foods, recipes, areas) : this._overviewView(summary, mealInventory, items, containers, locations, logbook, data)}
      </main>
    `;
    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.getElementById("tab-overview")?.addEventListener("click", () => { this._tab = "overview"; this._render(); });
    this.shadowRoot.getElementById("tab-manage")?.addEventListener("click", () => { this._tab = "manage"; this._render(); });
    this.shadowRoot.getElementById("tab-dev")?.addEventListener("click", () => { this._tab = "dev"; this._render(); });
    this.shadowRoot.getElementById("add-container")?.addEventListener("click", () => { this._tab = "manage"; this._showCreate = !this._showCreate; this._render(); });
    this.shadowRoot.getElementById("add-location")?.addEventListener("click", () => { this._editingLocation = ""; this._showLocation = !this._showLocation; this._render(); });
    this.shadowRoot.getElementById("create-form")?.addEventListener("submit", (event) => this._createContainer(event));
    this.shadowRoot.getElementById("location-form")?.addEventListener("submit", (event) => this._createLocation(event));
    this.shadowRoot.getElementById("cancel-location")?.addEventListener("click", () => { this._showLocation = false; this._editingLocation = ""; this._render(); });
    this.shadowRoot.querySelectorAll("[data-edit-location]").forEach((button) => button.addEventListener("click", () => { this._editingLocation = button.dataset.editLocation; this._showLocation = true; this._render(); }));
    this.shadowRoot.querySelectorAll("[data-delete-location]").forEach((button) => button.addEventListener("click", () => this._deleteLocation(button.dataset.deleteLocation, button.dataset.locationName)));
    this.shadowRoot.querySelectorAll("[data-move-tag]").forEach((select) => select.addEventListener("change", () => this._moveContainer(select.dataset.moveTag, select.value)));
    this.shadowRoot.querySelectorAll("[data-product-metadata]").forEach((form) => form.addEventListener("submit", (event) => this._saveProductMetadata(event)));
    this.shadowRoot.getElementById("sync-missing-products")?.addEventListener("click", () => this._syncMissingProducts());
    this.shadowRoot.getElementById("dev-refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.getElementById("dev-copy-overview")?.addEventListener("click", () => this._copyOverview());
    this.shadowRoot.getElementById("dev-sync-missing-products")?.addEventListener("click", () => this._syncMissingProducts());
    this.shadowRoot.getElementById("cancel-create")?.addEventListener("click", () => { this._showCreate = false; this._render(); });
  }

  _overviewView(summary, mealInventory, items, containers, locations, logbook, data) {
    return `
        <section class="grid">
          ${this._metric("Containers", summary.containers ?? 0)}
          ${this._metric("Locations", summary.locations ?? 0)}
          ${this._metric("Food items", summary.items ?? 0)}
          ${this._metric("Low", summary.low ?? 0, summary.low ? "warn" : "")}
        </section>
        <section class="sections">
          <div class="stack">
            <section class="card">
              <h2>Ready meal inventory</h2>
              ${mealInventory.length ? mealInventory.map((entry) => this._mealInventoryRow(entry)).join("") : `<p class="muted">Tag Mealie recipes with mpa:component:protein, mpa:component:starch, or mpa:component:vegetable, then store them as meals.</p>`}
            </section>
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
              <h2>Shopping workflow</h2>
              ${this._shoppingStatus(data?.shopping)}
            </section>
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
    `;
  }

  _manageView(locations, containers, foods, recipes, areas) {
    const editableLocations = locations.filter((location) => location.editable !== false);
    const editingLocation = editableLocations.find((location) => location.id === this._editingLocation);
    return `${this._showLocation && editingLocation ? this._locationForm(areas, editingLocation) : ""}${this._showCreate ? this._createForm(editableLocations, foods, recipes) : ""}
      <section class="card form"><div class="actions"><h2>Storage locations</h2></div></section>
      <section class="sections"><div class="stack">${locations.map((location) => this._locationCard(location)).join("") || `<p class="muted">Create storage locations in Grocy, or enable DEV mode for mocked locations.</p>`}</div><div class="stack"><section class="card"><h2>Containers</h2>${containers.map((container) => this._managedContainerRow(container, locations)).join("") || `<p class="muted">No containers yet.</p>`}</section></div></section>`;
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
            ${(data?.product_attention || []).map((item) => `<div class="row"><div><p class="name">${this._safe(item.label)}</p><p class="muted">${this._safe((item.reasons || []).join(", "))}</p></div><div class="qty">${this._safe(item.quantity)}<br><span class="muted">${this._safe(item.unit)}</span></div></div>`).join("") || `<p class="muted">No product review items.</p>`}
          </section>
        </div>
        <div class="stack">
          <section class="card">
            <h2>Recent log</h2>
            ${(data?.logbook || []).slice(0, 8).map((entry) => this._logRow(entry)).join("") || `<p class="muted">No actions recorded yet.</p>`}
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

  _createForm(locations, foods, recipes) {
    const locationOptions = locations.map((location) => `<option value="${this._safe(location.id)}">${this._safe(location.name)}</option>`).join("");
    const foodOptions = foods.map((food) => `<option value="${this._safe(food.id)}">${this._safe(food.label)}</option>`).join("");
    const recipeOptions = recipes.map((recipe) => `<option value="${this._safe(recipe.id)}">${this._safe(recipe.label)}</option>`).join("");
    return `
      <form class="card form" id="create-form">
        <h2>Add a reusable container</h2>
        <p class="muted">Give the NFC-tagged container a stable name, then record what is in it now.</p>
        <div class="form-grid">
          <label>NFC tag<input name="tag_id" required placeholder="04:A1:C2" /></label>
          <label>Container name<input name="name" placeholder="Freezer bin 1" /></label>
          <label>Contents<select name="content_kind"><option value="ingredient">Ingredient</option><option value="recipe">Recipe batch</option><option value="meal">Ready meal</option></select></label>
          <label>Catalog food<select name="item_id"><option value="">Choose a catalog food</option>${foodOptions}</select></label>
          <label>Mealie recipe<select name="recipe_id"><option value="">Choose a Mealie recipe</option>${recipeOptions}</select></label>
          <label>Quantity<input name="quantity" required type="number" min="0" step="any" value="1" /></label>
          <label>Location<select name="location_id"><option value="">Choose a location</option>${locationOptions}</select></label>
          <label>Best before<input name="best_before_date" type="date" /></label>
          <label>Purchased<input name="purchased_date" type="date" /></label>
          <label>Opened<input name="opened_date" type="date" /></label>
        </div>
        <p class="muted">Ingredients use the product catalog. Recipe batches and meals use the recipe yield unit.</p>
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
      quantity: Number(value("quantity")),
    };
    const contentKind = value("content_kind");
    if (contentKind === "ingredient") data.item_id = value("item_id");
    else {
      data.recipe_id = value("recipe_id");
      data.content_kind = contentKind;
    }
    if (value("name")) data.name = value("name");
    if (value("location_id")) data.location_id = value("location_id");
    if (contentKind === "ingredient" && value("best_before_date")) data.best_before_date = value("best_before_date");
    if (contentKind === "ingredient" && value("purchased_date")) data.purchased_date = value("purchased_date");
    if (contentKind === "ingredient" && value("opened_date")) data.opened_date = value("opened_date");
    try {
      await this._hass.callService("mise_en_place_assistant", contentKind === "ingredient" ? "create_container" : "create_recipe_container", data);
      this._showCreate = false;
      await this._loadIfNoEventSocket();
    } catch (err) {
      this._error = err?.message || "Could not save the container.";
      this._render();
    }
  }

  _locationForm(areas, location = null) {
    const sensors = location?.sensors || {};
    const monitoring = location?.monitoring || {};
    const selected = (current, value) => current === value ? " selected" : "";
    const areaOptions = areas.map((area) => `<option value="${this._safe(area.id)}"${selected(location?.area_id, area.id)}>${this._safe(area.name)}</option>`).join("");
    const typeOptions = ["fridge", "freezer", "pantry", "dry_storage", "cellar", "counter", "other"]
      .map((type) => `<option value="${type}"${selected(location?.location_type || "other", type)}>${this._safe(type.replaceAll("_", " "))}</option>`)
      .join("");
    return `<form class="card form" id="location-form"><h2>Edit location monitoring</h2><div class="form-grid">
      <input type="hidden" name="location_id" value="${this._safe(location?.id || "")}" />
      <label>Grocy location<input name="name" required readonly value="${this._safe(location?.name || "")}" /></label>
      <label>Home Assistant area<select name="area_id"><option value="">No area</option>${areaOptions}</select></label>
      <label>Type<select name="location_type">${typeOptions}</select></label>
      <label>Temperature sensor<input name="temperature" placeholder="sensor.freezer_temperature" value="${this._safe(sensors.temperature || "")}" /></label>
      <label>Humidity sensor<input name="humidity" placeholder="sensor.freezer_humidity" value="${this._safe(sensors.humidity || "")}" /></label>
      <label>Door sensor<input name="door" placeholder="binary_sensor.freezer_door" value="${this._safe(sensors.door || "")}" /></label>
      <label>Power sensor<input name="power" placeholder="sensor.freezer_power" value="${this._safe(sensors.power || "")}" /></label>
      <label>Appliance plug<input name="power_switch" placeholder="switch.freezer_plug" value="${this._safe(sensors.power_switch || "")}" /></label>
      <label>Minimum temperature<input name="temperature_min" type="number" step="any" value="${this._safe(monitoring.temperature_min ?? "")}" /></label>
      <label>Maximum temperature<input name="temperature_max" type="number" step="any" value="${this._safe(monitoring.temperature_max ?? "")}" /></label>
    </div><div class="actions"><button type="button" class="secondary" id="cancel-location">Cancel</button><button type="submit">Save location</button></div></form>`;
  }

  async _createLocation(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    const sensors = Object.fromEntries(["temperature", "humidity", "door", "power", "power_switch"].filter((name) => value(name)).map((name) => [name, value(name)]));
    const monitoring = Object.fromEntries(["temperature_min", "temperature_max"].filter((name) => value(name) !== "").map((name) => [name, Number(value(name))]));
    if (value("power_switch")) monitoring.power_required = true;
    try {
      const locationId = value("location_id");
      if (!locationId) throw new Error("Choose a Grocy location to annotate.");
      await this._hass.callService(
        "mise_en_place_assistant",
        "update_location",
        { location_id: locationId, name: value("name"), location_type: value("location_type"), ...(value("area_id") ? { area_id: value("area_id") } : {}), sensors, monitoring },
      );
      this._showLocation = false;
      this._editingLocation = "";
      await this._loadIfNoEventSocket();
    } catch (err) { this._error = err?.message || "Could not save location."; this._render(); }
  }

  async _deleteLocation(locationId, name) {
    if (!window.confirm(`Remove local monitoring metadata for ${name}? The Grocy location will remain.`)) return;
    try { await this._hass.callService("mise_en_place_assistant", "delete_location", { location_id: locationId }); await this._loadIfNoEventSocket(); }
    catch (err) { this._error = err?.message || "Could not delete location."; this._render(); }
  }

  async _moveContainer(tagId, locationId) {
    if (!locationId) return;
    try { await this._hass.callService("mise_en_place_assistant", "move_container", { tag_id: tagId, location_id: locationId }); await this._loadIfNoEventSocket(); }
    catch (err) { this._error = err?.message || "Could not move container."; this._render(); }
  }

  async _syncMissingProducts() {
    try {
      await this._hass.callService("mise_en_place_assistant", "add_missing_products_to_shopping_list", {});
      await this._loadIfNoEventSocket();
    } catch (err) {
      this._error = err?.message || "Could not sync Grocy minimum-stock shopping.";
      this._render();
    }
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
    const form = event.currentTarget;
    const value = (name) => form.elements[name].value.trim();
    try {
      await this._hass.callService("mise_en_place_assistant", "update_product_metadata", {
        item_id: value("item_id"),
        container_policy: value("container_policy"),
        storage_behavior: value("storage_behavior"),
        meal_role: value("meal_role"),
        available_in_mealie: form.elements.available_in_mealie.checked,
        notes: value("notes"),
      });
      await this._loadIfNoEventSocket();
    } catch (err) {
      this._error = err?.message || "Could not save product metadata.";
      this._render();
    }
  }

  _containerRow(item, klass = "") {
    return `
      <div class="row">
          <div>
          <p class="name">${this._safe(item.name)}</p>
          <p class="muted">${this._safe(item.content_kind)} &middot; ${this._safe(item.item_label)} &middot; ${this._safe(item.location)}</p>
          <p class="muted">${this._safe(item.format)}</p>
          <span class="pill">${this._safe(item.tag_id || "no tag")}</span>
        </div>
        <div class="qty ${klass}">${this._safe(item.quantity)}<br><span class="muted">${this._safe(item.unit)}</span></div>
      </div>
    `;
  }

  _attentionRows(data) {
    const empty = data?.empty_containers || [];
    const low = data?.low_containers || [];
    const products = data?.product_attention || [];
    const rows = [
      ...products.map((item) => this._productAttentionRow(item)),
      ...empty.map((item) => this._containerRow(item, "empty")),
      ...low.map((item) => this._containerRow(item, "warn")),
    ];
    return rows.length ? rows.join("") : `<p class="muted">Nothing needs attention.</p>`;
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
      ["staple", "Staple"],
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
        <p class="muted">${quantity} · ${this._safe((item.reasons || []).join(", "))}</p>
      </div>
      <div class="review-grid">
        <label>Container policy<select name="container_policy">${this._options(containerPolicies, metadata.container_policy || "unknown")}</select></label>
        <label>Storage behavior<select name="storage_behavior">${this._options(storageBehaviors, metadata.storage_behavior || "unknown")}</select></label>
        <label>Meal role<select name="meal_role">${this._options(mealRoles, metadata.meal_role || "unknown")}</select></label>
        <label>Mealie recipes<span><input type="checkbox" name="available_in_mealie"${mealieChecked} /> Available in Mealie</span></label>
      </div>
      <label>Notes<textarea name="notes">${this._safe(metadata.notes || "")}</textarea></label>
      <div class="actions"><button type="submit" class="secondary">Save review</button></div>
    </form>`;
  }

  _options(options, current) {
    return options.map(([value, label]) => `<option value="${this._safe(value)}"${value === current ? " selected" : ""}>${this._safe(label)}</option>`).join("");
  }

  _shoppingStatus(shopping = {}) {
    const label = shopping.provider === "kitchenowl" ? "KitchenOwl" : shopping.provider === "grocy" ? "Grocy" : "Automatic";
    const productTarget = shopping.product_backed_target === "kitchenowl" ? "KitchenOwl" : "Grocy";
    const textTarget = shopping.free_text_target === "kitchenowl" ? "KitchenOwl" : "Grocy";
    return `<p class="name">${this._safe(label)}</p>
      <p class="muted">Products: ${this._safe(productTarget)} · Text: ${this._safe(textTarget)}</p>
      <p class="muted">Grocy ${shopping.grocy_configured ? "connected" : "not configured"} · KitchenOwl ${shopping.kitchenowl_configured ? "connected" : "not configured"}</p>
      <div class="actions">
        ${shopping.grocy_minimum_stock ? `<button type="button" class="secondary" id="sync-missing-products">Sync Grocy minimum stock</button>` : ""}
      </div>
      ${shopping.grocy_minimum_stock ? "" : `<p class="muted">Grocy minimum-stock sync is disabled while KitchenOwl owns shopping lists.</p>`}`;
  }

  _mealInventoryRow(entry) {
    const formatTotals = (totals) => Object.entries(totals || {}).map(([unit, amount]) => `${amount} ${unit}`).join(" + ");
    const proteins = Object.entries(entry.proteins || {}).map(([name, totals]) => `${name}: ${formatTotals(totals)}`).join(" · ");
    const recipes = Object.entries(entry.recipes || {}).map(([name, totals]) => `${name}: ${formatTotals(totals)}`).join(" · ");
    const quantities = Object.entries(entry.quantities || {}).map(([unit, amount]) => `${amount} ${unit}`).join(" + ");
    return `<div class="row"><div><p class="name">${this._safe(entry.component)}</p><p class="muted">${this._safe(proteins || recipes)}</p></div><div class="qty">${this._safe(quantities)}</div></div>`;
  }

  _locationCard(location) {
    const health = location.health || {};
    const readings = Object.entries(health.readings || {}).map(([role, reading]) => `<div class="reading"><strong>${this._safe(role.replaceAll("_", " "))}</strong><br>${this._safe(reading.state)}${reading.unit ? ` ${this._safe(reading.unit)}` : ""}</div>`).join("");
    const problems = health.problems?.length ? health.problems.join(" · ") : health.status === "ok" ? "Everything looks normal" : "Monitoring is not configured";
    return `<article class="card"><div class="actions"><div><h2>${this._safe(location.name)}</h2><p class="muted">${this._safe(location.location_type?.replaceAll("_", " ") || "location")}${location.area_name ? ` · ${this._safe(location.area_name)}` : ""}</p></div>${location.editable !== false ? `<button class="secondary" data-edit-location="${this._safe(location.id)}">Edit</button><button class="secondary" data-delete-location="${this._safe(location.id)}" data-location-name="${this._safe(location.name)}">Clear metadata</button>` : ""}</div><p class="metric">${this._safe(location.containers)} <span class="muted">containers</span></p><p class="health ${this._safe(health.status || "")}">${this._safe(problems)}</p>${readings ? `<div class="reading-grid">${readings}</div>` : ""}</article>`;
  }

  _managedContainerRow(container, locations) {
    const choices = locations.filter((location) => location.editable !== false).map((location) => `<option value="${this._safe(location.id)}">${this._safe(location.name)}</option>`).join("");
    return `<div class="row"><div><p class="name">${this._safe(container.name)}</p><p class="muted">${this._safe(container.item_label)} · ${this._safe(container.location)}</p></div><div><strong>${this._safe(container.quantity)} ${this._safe(container.unit)}</strong><select data-move-tag="${this._safe(container.tag_id)}"><option value="">Move to…</option>${choices}</select></div></div>`;
  }

  _locationRow(location) {
    return `<div class="location"><span>${this._safe(location.name)}<br><small class="muted">${this._safe(location.location_type || "location")}${location.area_name ? ` · ${this._safe(location.area_name)}` : ""}</small></span><strong>${this._safe(location.containers)}</strong></div>`;
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
