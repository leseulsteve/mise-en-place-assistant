import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class FakeShadowRoot {
  innerHTML = "";

  getElementById() {
    return null;
  }

  querySelectorAll() {
    return [];
  }
}

globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = new FakeShadowRoot();
    return this.shadowRoot;
  }
};
globalThis.customElements = {
  registry: new Map(),
  define(name, element) {
    this.registry.set(name, element);
  },
  get(name) {
    return this.registry.get(name);
  },
};
globalThis.document = {
  createElement() {
    return { textContent: "", get innerHTML() { return this.textContent; } };
  },
};
globalThis.window = {
  clearInterval() {},
  setInterval() {
    return 1;
  },
};

const source = await readFile(
  new URL("../custom_components/mise_en_place_assistant/panel_frontend.js", import.meta.url),
  "utf8",
);
vm.runInThisContext(source, { filename: "panel_frontend.js" });

const Panel = customElements.get("mise_en_place_assistant-panel");
assert.ok(Panel, "the custom panel element must be registered");

const panel = new Panel();
let inventoryUpdated;
let eventsUnsubscribed = false;
let overviewRequests = 0;
panel.hass = {
  callWS: async () => {
    overviewRequests += 1;
    return {
    summary: { containers: 1, locations: 1, items: 1, low: 0, dirty: 0 },
    containers: [{
      tag_id: "demo:sauce",
      name: "Sauce tub",
      item_label: "Tomato sauce",
      quantity: 2,
      unit: "cups",
      canonical_quantity: 2,
      canonical_unit: "cups",
      location: "Fridge",
      content_kind: "meal",
      recipe: {
        id: "mocked:recipe:sauce",
        provider: "mocked_recipe",
        label: "Tomato sauce",
        yield_unit: "cups",
        tags: ["mpa:component:sauce"],
        categories: ["Prep"],
        component: "sauce",
        primary_protein: "",
      },
    }],
    items: [{
      product_id: "product_tomatoes",
      item_id: "grocy:12",
      label: "Tomatoes",
      source: "grocy",
      quantity: 4,
      unit: "cans",
      containers: 1,
      locations: { Fridge: { cans: 2 } },
      physical_containers: [{
        name: "Sauce tub",
        quantity: 2,
        unit: "cups",
        location: "Fridge",
      }],
      freshness_dates: [{
        container: "Sauce tub",
        best_before_date: "2026-07-01",
        purchased_date: "2026-06-18",
        opened_date: "2026-06-19",
        price: "3.49",
      }],
      last_stock_log: {
        action: "Grocy stock updated",
        message: "Grocy stock was updated for Sauce tub.",
      },
    }],
    locations: [],
    areas: [],
    logbook: [],
    readiness: {
      ready: [{ label: "Tomato sauce", detail: "2 cups", reason: "Prepared component exists", status: "ok" }],
      missing: [],
      empty: [],
      unassigned: [],
      stale: [],
      location_at_risk: [],
    },
    planning_comparison: [{
      component: "sauce",
      prepared: "2 cups",
      recipes: [{ label: "Tomato sauce", quantity: "2 cups" }],
      proteins: [],
      grocy_stock: [{ label: "Tomatoes", quantity: "4 cans", containers: 1 }],
    }],
    suggested_actions: [{
      id: "queue_empty_containers",
      title: "Queue empty containers",
      because: "1 empty container can become a shopping request.",
      status: "warning",
      service: "add_empty_containers_to_shopping_list",
      payload: {},
      open_tab: "",
      sources: ["Mise container"],
      target: "Grocy shopping list for Grocy products; KitchenOwl shopping list fallback",
      last_queued: {
        action: "Empty containers queued",
        message: "1 empty-container refill item was sent to shopping providers.",
        provider: "auto",
        targets: { grocy: 1 },
        item_count: 1,
        reason: "empty_container_refill",
      },
    }],
    shopping: {
      provider: "auto",
      product_backed_target: "grocy",
      free_text_target: "kitchenowl",
      grocy_configured: true,
      kitchenowl_configured: true,
      grocy_minimum_stock: true,
    },
    operations: { catalog_providers: ["mocked"], health: { ok: 1 }, attention_total: 0 },
    storage_attention: {
      status: "warning",
      status_label: "Storage attention needed",
      attention_count: 1,
      containers_needing_location_count: 0,
      unhealthy_locations_count: 1,
      critical_locations_count: 0,
      warning_locations_count: 1,
      prepared_inventory_at_risk_count: 0,
      containers_needing_location: [],
      unhealthy_locations: [{ location_id: "fridge", name: "Fridge", status: "warning", problems: ["temperature above range"] }],
      critical_locations: [],
      warning_locations: [{ location_id: "fridge", name: "Fridge", problems: ["temperature above range"] }],
      prepared_inventory_at_risk: [],
    },
    empty_containers: [],
    low_containers: [],
    dirty_containers: [],
    };
  },
  connection: {
    subscribeEvents(listener, eventType) {
      assert.equal(eventType, "mise_en_place_assistant.updated");
      inventoryUpdated = listener;
      return Promise.resolve(() => {
        eventsUnsubscribed = true;
      });
    },
  },
};
panel.connectedCallback();
await new Promise((resolve) => setImmediate(resolve));

assert.match(panel.shadowRoot.innerHTML, /Mise en Place Assistant/);
assert.match(panel.shadowRoot.innerHTML, /Active containers/);
assert.match(panel.shadowRoot.innerHTML, /Next actions/);
assert.match(panel.shadowRoot.innerHTML, /Readiness/);
assert.match(panel.shadowRoot.innerHTML, /Suggested next actions/);
assert.match(panel.shadowRoot.innerHTML, /Queue empty containers/);
assert.match(panel.shadowRoot.innerHTML, /Queue shopping/);
assert.match(panel.shadowRoot.innerHTML, /Mise container/);
assert.match(panel.shadowRoot.innerHTML, /Target: Grocy shopping list/);
assert.match(panel.shadowRoot.innerHTML, /Last queued: 1 item/);
assert.match(panel.shadowRoot.innerHTML, /Storage attention needed/);
panel._tab = "inventory";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Grocy stock/);
assert.match(panel.shadowRoot.innerHTML, /Last stock write/);
assert.match(panel.shadowRoot.innerHTML, /best before 2026-07-01/);
panel._tab = "planning";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Prepared components vs Grocy stock/);
assert.match(panel.shadowRoot.innerHTML, /Tomatoes/);
assert.match(panel.shadowRoot.innerHTML, /Prepared components/);
assert.match(panel.shadowRoot.innerHTML, /mpa:component:sauce/);
inventoryUpdated();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(overviewRequests, 2, "inventory events refresh the panel immediately");
panel.disconnectedCallback();
assert.equal(eventsUnsubscribed, true, "the inventory event subscription is released");
