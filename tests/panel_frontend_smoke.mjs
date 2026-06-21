import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class FakeShadowRoot {
  innerHTML = "";

  getElementById(id) {
    if (id === "edit-container-form" && this.innerHTML.includes('id="edit-container-form"')) {
      return {
        addEventListener() {},
        elements: {
          tag_id: { value: "demo:peas" },
          name: { value: "Freezer bin" },
          quantity: { value: "0" },
          unit: { value: "bags" },
          location_id: { value: "freezer" },
          sublocation: { value: "Door bin" },
        },
      };
    }
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
const serviceCalls = [];
panel.hass = {
  callService: async (domain, service, data) => {
    serviceCalls.push({ domain, service, data });
  },
  callWS: async () => {
    overviewRequests += 1;
    return {
    summary: { containers: 2, locations: 2, items: 1, foods: 2, recipes: 1, low: 1, dirty: 0 },
    containers: [{
      tag_id: "demo:sauce",
      name: "Sauce tub",
      item_label: "Tomato sauce",
      quantity: 2,
      unit: "cups",
      canonical_quantity: 2,
      canonical_unit: "cups",
      location_id: "fridge",
      location: "Fridge",
      sublocation: "Top shelf",
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
    }, {
      tag_id: "demo:peas",
      name: "Freezer bin",
      item_label: "Frozen peas",
      quantity: 0,
      unit: "bags",
      canonical_quantity: 0,
      canonical_unit: "bags",
      location_id: "freezer",
      location: "Freezer",
      sublocation: "Door bin",
      content_kind: "ingredient",
    }],
    items: [{
      product_id: "product_tomatoes",
      item_id: "grocy:12",
      label: "Tomatoes",
      source: "grocy",
      quantity: 4,
      unit: "cans",
      best_before_date: "2026-07-01",
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
    locations: [{
      id: "fridge",
      name: "Fridge",
      location_type: "fridge",
      area_id: "kitchen",
      area_name: "Kitchen",
      area_icon: "mdi:silverware-fork-knife",
      sensors: {
        temperature: "sensor.fridge_temperature",
        door: "binary_sensor.fridge_door",
        power_switch: "switch.fridge_plug",
      },
      monitoring: {},
      sublocations: ["Top shelf"],
      containers: 1,
      health: {
        status: "ok",
        problems: [],
        readings: {
          temperature: { entity_id: "sensor.fridge_temperature", state: "37", unit: "°F" },
          door: { entity_id: "binary_sensor.fridge_door", state: "off" },
          power_switch: { entity_id: "switch.fridge_plug", state: "on" },
        },
      },
    }, {
      id: "freezer",
      name: "Freezer",
      location_type: "freezer",
      area_id: "kitchen",
      area_name: "Kitchen",
      area_icon: "mdi:silverware-fork-knife",
      sensors: {},
      monitoring: {},
      sublocations: ["Door bin"],
      containers: 1,
      health: {
        status: "not_configured",
        problems: [],
        readings: {},
      },
    }],
    areas: [{ id: "kitchen", name: "Kitchen", icon: "mdi:silverware-fork-knife" }],
    entities: [
      { entity_id: "binary_sensor.fridge_door", domain: "binary_sensor", name: "Fridge Door" },
      { entity_id: "sensor.fridge_humidity", domain: "sensor", name: "Fridge Humidity" },
      { entity_id: "sensor.fridge_temperature", domain: "sensor", name: "Fridge Temperature" },
      { entity_id: "switch.fridge_plug", domain: "switch", name: "Fridge Plug" },
    ],
    foods: [
      { id: "grocy:12", label: "Tomatoes", metadata: { available_in_mealie: true } },
      { id: "mocked:peas", label: "Frozen peas", metadata: { available_in_mealie: false } },
    ],
    recipes: [{
      id: "mocked:recipe:sauce",
      provider: "mocked_recipe",
      label: "Tomato sauce",
    }],
    logbook: [],
    readiness: {
      ready: [{ label: "Tomato sauce", detail: "2 cups", reason: "Prepared component exists", status: "ok" }],
      missing: [],
      empty: [],
      unassigned: [],
      stale: [],
      location_at_risk: [{ label: "Fridge", detail: "warning", reason: "temperature above range", status: "warning" }],
    },
    planning_comparison: [{
      component: "sauce",
      prepared: "2 cups",
      recipes: [{ label: "Tomato sauce", quantity: "2 cups" }],
      proteins: [],
      grocy_stock: [{ label: "Tomatoes", quantity: "4 cans", containers: 1 }],
    }],
    recipe_suggestions: [{
      id: "mocked:recipe:sauce",
      label: "Tomato sauce",
      score: 31,
      matched_count: 1,
      ingredient_count: 2,
      missing_count: 1,
      reason: "Uses Tomatoes before 2026-07-01 and matches 1 stocked ingredients.",
      matched: [{ label: "Tomatoes", stock_quantity: "4 cans", best_before_date: "2026-07-01" }],
      missing: [{ label: "Garlic", amount: "2 cloves" }],
      best_before: [{ label: "Tomatoes", best_before_date: "2026-07-01", status: "soon", days: 10 }],
    }],
    complete_meal_plan: {
      meal_count: 2,
      status: "ready",
      complete: true,
      uses: {
        veggie: [
          { label: "Roasted broccoli", quantity: 2, unit: "portions", family: "cruciferous", detail: "broccoli", location: "Fridge", sublocation: "Top shelf" },
        ],
        starch: [
          { label: "Cooked basmati rice", quantity: 1, unit: "portions", family: "rice", detail: "basmati_rice", location: "Fridge", sublocation: "Top shelf" },
          { label: "Sweet potatoes", quantity: 1, unit: "portions", family: "potato", detail: "sweet_potato", location: "Fridge", sublocation: "Top shelf" },
        ],
        protein: [
          { label: "Chicken curry", quantity: 1, unit: "portions", family: "poultry", detail: "chicken", location: "Fridge", sublocation: "Top shelf" },
          { label: "Salmon portions", quantity: 1, unit: "portions", family: "fish", detail: "salmon", location: "Freezer", sublocation: "Top shelf" },
        ],
      },
      shortages: {},
      skipped: [
        { label: "Gram-counted pulled pork", role: "protein", unit: "g", reason: 'unit "g" is not portion-compatible' },
      ],
    },
    meal_prep: {
      status: "missing items",
      meal_count: 2,
      calendar_entities: [{
        entity_id: "calendar.meal_prep",
        name: "Meal Prep",
        state: "off",
      }],
      prep_calendar_entity_id: "calendar.meal_prep",
      calendar_events: [{
        entity_id: "calendar.meal_prep",
        name: "Meal Prep",
        state: "on",
        message: "Sunday prep",
        start_time: "2026-06-21 10:00:00",
        end_time: "2026-06-21 12:00:00",
      }],
      sessions: [{
        id: "prep_old",
        calendar_entity_id: "calendar.meal_prep",
        summary: "Last prep",
        start_date_time: "2026-06-14T10:00",
        end_date_time: "2026-06-14T12:00",
        status: "past",
        recipes: [{ id: "mocked:recipe:sauce", label: "Tomato sauce" }],
      }, {
        id: "prep_next",
        calendar_entity_id: "calendar.meal_prep",
        summary: "Next prep",
        start_date_time: "2026-06-21T10:00",
        end_date_time: "2026-06-21T12:00",
        status: "upcoming",
        recipes: [{ id: "mocked:recipe:sauce", label: "Tomato sauce" }],
      }],
      provider_roles: {
        schedule: "Home Assistant calendar",
        recipes: "Mealie",
        stock: "Grocy",
        shopping: "Grocy shopping list",
        storage: "Grocy storage locations + Mise container tags",
      },
      storage_plan: [{
        label: "Complete meal portions",
        count: 2,
        container_type: "medium square",
        destination: "fridge",
        eat_by: "next 3-4 days",
        note: "One assembled meal per container",
      }, {
        label: "Protein staging",
        count: 1,
        container_type: "medium square",
        destination: "fridge/freezer",
        eat_by: "session dependent",
        note: "Chicken curry",
      }],
      container_plan: [{
        type: "medium square",
        needed: 3,
        available: 1,
        missing: 2,
        status: "missing",
      }, {
        type: "small bag",
        needed: 0,
        available: 2,
        missing: 0,
        status: "ready",
      }],
      clone_templates: [{
        id: "current_complete_meals",
        name: "2 complete meals",
        source: "Mealie complete-meal preview",
        keeps: ["recipes", "servings", "storage plan", "container plan", "checklist", "notes"],
      }],
      checklist: [
        "Pick a Home Assistant calendar and schedule the prep block",
        "Queue missing ingredients through Grocy or the configured shopping provider",
      ],
    },
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
    }, {
      id: "configure_mealie",
      title: "Configure Mealie",
      because: "Mealie provider is not configured.",
      status: "warning",
      service: "",
      payload: {},
      open_tab: "info",
      sources: ["Configuration"],
      target: "",
      last_queued: null,
    }],
    shopping: {
      provider: "auto",
      product_backed_target: "grocy",
      free_text_target: "kitchenowl",
      grocy_configured: true,
      kitchenowl_configured: true,
      grocy_minimum_stock: true,
    },
    operations: { catalog_providers: ["mocked"], dev_mode: true, health: { ok: 1 }, attention_total: 0 },
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
    low_containers: [{
      tag_id: "demo:sauce",
      name: "Sauce tub",
      item_label: "Tomato sauce",
      quantity: 2,
      unit: "cups",
    }],
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
assert.match(panel.shadowRoot.innerHTML, /Critical: 1/);
assert.match(panel.shadowRoot.innerHTML, /0 missing/);
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
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Shopping activity/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Add shopping item/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Shopping workflow/);
panel._tab = "inventory";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Current inventory/);
assert.match(panel.shadowRoot.innerHTML, /Stocked products/);
assert.match(panel.shadowRoot.innerHTML, /Inventory sources/);
assert.match(panel.shadowRoot.innerHTML, /Grocy stock/);
assert.match(panel.shadowRoot.innerHTML, /Last stock write/);
assert.match(panel.shadowRoot.innerHTML, /Fridge: 2 cans/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Active containers/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Empty containers/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /best before 2026-07-01/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Sauce tub: 2 cups/);
panel._tab = "planning";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Prepared components vs Grocy stock/);
assert.match(panel.shadowRoot.innerHTML, /Tomatoes/);
assert.match(panel.shadowRoot.innerHTML, /Recipe suggestions/);
assert.match(panel.shadowRoot.innerHTML, /best before 2026-07-01/);
assert.match(panel.shadowRoot.innerHTML, /Missing or unknown/);
assert.match(panel.shadowRoot.innerHTML, /Prepared components/);
assert.match(panel.shadowRoot.innerHTML, /mpa:component:sauce/);
assert.match(panel.shadowRoot.innerHTML, /Complete meals/);
assert.match(panel.shadowRoot.innerHTML, /2 complete meals ready/);
assert.match(panel.shadowRoot.innerHTML, /Roasted broccoli/);
assert.match(panel.shadowRoot.innerHTML, /cruciferous/);
assert.match(panel.shadowRoot.innerHTML, /Chicken curry/);
assert.match(panel.shadowRoot.innerHTML, /Gram-counted pulled pork/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Add shopping item/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Shopping activity/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Shopping workflow/);
panel._tab = "meal-prep";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Meal Prep/);
assert.match(panel.shadowRoot.innerHTML, /Session Calendar/);
assert.match(panel.shadowRoot.innerHTML, /Last prep/);
assert.match(panel.shadowRoot.innerHTML, /Next prep/);
assert.match(panel.shadowRoot.innerHTML, /Past/);
assert.match(panel.shadowRoot.innerHTML, /Upcoming/);
assert.match(panel.shadowRoot.innerHTML, /Home Assistant calendar/);
assert.match(panel.shadowRoot.innerHTML, /calendar\.meal_prep/);
assert.match(panel.shadowRoot.innerHTML, /New prep session/);
assert.match(panel.shadowRoot.innerHTML, /Recipe chooser/);
assert.match(panel.shadowRoot.innerHTML, /Recipe rank/);
assert.match(panel.shadowRoot.innerHTML, /Session details/);
assert.match(panel.shadowRoot.innerHTML, /Session name/);
assert.match(panel.shadowRoot.innerHTML, /Scheduled date\/time/);
assert.match(panel.shadowRoot.innerHTML, /Recipes or meals included/);
assert.match(panel.shadowRoot.innerHTML, /Number of servings/);
assert.match(panel.shadowRoot.innerHTML, /Expected finished portions/);
assert.match(panel.shadowRoot.innerHTML, /Session notes/);
assert.match(panel.shadowRoot.innerHTML, /Readiness summary/);
assert.match(panel.shadowRoot.innerHTML, /2 finished portions/);
assert.match(panel.shadowRoot.innerHTML, /Ingredient readiness/);
assert.match(panel.shadowRoot.innerHTML, /best before 2026-07-01/);
panel._selectPrepSession({ dataset: { selectPrepSession: "prep_next" } });
assert.match(panel.shadowRoot.innerHTML, /Next prep/);
assert.match(panel.shadowRoot.innerHTML, /Tomato sauce/);
panel._tab = "attention";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Needs user attention/);
assert.match(panel.shadowRoot.innerHTML, /Kitchen and inventory issues only/);
assert.match(panel.shadowRoot.innerHTML, /Queue empty containers/);
assert.match(panel.shadowRoot.innerHTML, /Queue shopping/);
assert.match(panel.shadowRoot.innerHTML, /Fridge/);
assert.match(panel.shadowRoot.innerHTML, /Storage safety/);
assert.match(panel.shadowRoot.innerHTML, /Sauce tub/);
assert.match(panel.shadowRoot.innerHTML, /Container inventory/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Configure Mealie/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /not configured/);
panel._tab = "meal-prep";
panel._render();
const prepForm = {
  elements: {
    entity_id: { value: "calendar.meal_prep" },
    summary: { value: "Sunday prep" },
    start_date_time: { value: "2026-06-21T10:00" },
    end_date_time: { value: "2026-06-21T12:00" },
    description: { value: "Created from test" },
  },
  querySelectorAll(selector) {
    return selector === 'input[name="recipe_ids"]:checked'
      ? [{ value: "mocked:recipe:sauce" }]
      : [];
  },
};
await panel._createMealPrepCalendarEvent({ preventDefault() {}, currentTarget: prepForm });
assert.deepEqual(serviceCalls.at(-2), {
  domain: "calendar",
  service: "create_event",
  data: {
    entity_id: "calendar.meal_prep",
    summary: "Sunday prep",
    start_date_time: "2026-06-21T10:00",
    end_date_time: "2026-06-21T12:00",
    description: "Created from test",
  },
});
assert.deepEqual(serviceCalls.at(-1), {
  domain: "mise_en_place_assistant",
  service: "create_prep_session",
  data: {
    calendar_entity_id: "calendar.meal_prep",
    name: "Sunday prep",
    start_date_time: "2026-06-21T10:00",
    end_date_time: "2026-06-21T12:00",
    recipe_ids: ["mocked:recipe:sauce"],
    description: "Created from test",
  },
});
panel._tab = "info";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Catalog: DEV/);
assert.match(panel.shadowRoot.innerHTML, /Catalog size/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Catalog mode/);
assert.match(panel.shadowRoot.innerHTML, /mocked/);
assert.match(panel.shadowRoot.innerHTML, /2 foods \/ 1 recipes/);
assert.match(panel.shadowRoot.innerHTML, /Mealie/);
assert.match(panel.shadowRoot.innerHTML, /1 foods marked available in Mealie/);
assert.match(panel.shadowRoot.innerHTML, /Grocy shopping/);
assert.match(panel.shadowRoot.innerHTML, /KitchenOwl shopping/);
panel._tab = "storage";
panel._showLocation = true;
panel._editingLocation = "fridge";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /name="temperature"><option value="">None<\/option><option value="sensor.fridge_humidity"/);
assert.match(panel.shadowRoot.innerHTML, /value="sensor.fridge_temperature" selected/);
assert.match(panel.shadowRoot.innerHTML, /value="binary_sensor.fridge_door" selected/);
assert.match(panel.shadowRoot.innerHTML, /value="switch.fridge_plug" selected/);
assert.match(panel.shadowRoot.innerHTML, /class="card location-card type-fridge selected"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /location-count/);
assert.match(panel.shadowRoot.innerHTML, /class="card location-card type-freezer" data-select-location="freezer" tabindex="0"/);
assert.match(panel.shadowRoot.innerHTML, /data-select-location="fridge" tabindex="0"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /aria-expanded=/);
assert.match(panel.shadowRoot.innerHTML, /class="row container-card kind-meal"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /class="row container-card kind-ingredient"/);
assert.match(panel.shadowRoot.innerHTML, /ha-icon icon="mdi:fridge-outline"/);
assert.match(panel.shadowRoot.innerHTML, /ha-icon icon="mdi:snowflake"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /location-card-title">\s*<ha-icon/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /View containers/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /mdi:format-list-bulleted/);
assert.match(panel.shadowRoot.innerHTML, /title="Add container here" aria-label="Add container here"/);
assert.match(panel.shadowRoot.innerHTML, /data-add-container-location="fridge"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /location-card-actions"><button class="icon-button" data-add-container-location/);
assert.match(panel.shadowRoot.innerHTML, /title="Edit location" aria-label="Edit location"/);
assert.match(panel.shadowRoot.innerHTML, /ha-icon icon="mdi:map-marker-right-outline"/);
assert.match(panel.shadowRoot.innerHTML, /data-open-move-container="demo:sauce" data-current-location="fridge" title="Move container" aria-label="Move container"/);
assert.match(panel.shadowRoot.innerHTML, /title="Edit container" aria-label="Edit container"/);
assert.match(panel.shadowRoot.innerHTML, /data-edit-container="demo:sauce"/);
assert.match(panel.shadowRoot.innerHTML, /<span class="location-chip"><ha-icon icon="mdi:fridge-outline"><\/ha-icon><span class="location-type">fridge<\/span><\/span>/);
assert.match(panel.shadowRoot.innerHTML, /<span class="location-chip"><ha-icon icon="mdi:silverware-fork-knife"><\/ha-icon><span>Kitchen<\/span><\/span>/);
assert.match(panel.shadowRoot.innerHTML, /<span>Status<\/span><strong>Storage automation clear<\/strong>/);
assert.match(panel.shadowRoot.innerHTML, /<span>Sublocations<\/span><strong>1 active \/ 1 configured<\/strong>/);
assert.match(panel.shadowRoot.innerHTML, /<span>Contents<\/span><strong>1 meal<\/strong>/);
assert.match(panel.shadowRoot.innerHTML, /class="card storage-detail"/);
assert.match(panel.shadowRoot.innerHTML, /class="sublocation-button active" data-location-id="fridge" data-select-sublocation="Top shelf"/);
assert.match(panel.shadowRoot.innerHTML, /<strong>Top shelf<\/strong>/);
assert.match(panel.shadowRoot.innerHTML, /Top shelf · 1 container/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Door bin · 1 container/);
assert.match(panel.shadowRoot.innerHTML, /Tomato sauce/);
assert.match(panel.shadowRoot.innerHTML, /Sauce tub/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Frozen peas/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Freezer bin/);
assert.match(panel.shadowRoot.innerHTML, /Ready meal/);
assert.match(panel.shadowRoot.innerHTML, /Fridge \/ Top shelf/);
assert.match(panel.shadowRoot.innerHTML, /demo:sauce/);
assert.match(panel.shadowRoot.innerHTML, /Low stock/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Empty/);
assert.match(panel.shadowRoot.innerHTML, /1 item needs attention/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /selected-chip/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, />Selected</);
assert.match(panel.shadowRoot.innerHTML, /Storage automation clear/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Storage monitoring not configured/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Catalog: DEV/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /Catalog size/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /<h2>Containers<\/h2>/);
panel._openContainerMove("demo:sauce", "fridge");
assert.match(panel.shadowRoot.innerHTML, /id="move-container-form"/);
assert.match(panel.shadowRoot.innerHTML, /id="move-container-location" required><option value="">Choose a location<\/option><option value="fridge" selected>Fridge<\/option>/);
assert.match(panel.shadowRoot.innerHTML, /<label>Sublocation<select name="sublocation"><option value="Top shelf" selected>Top shelf<\/option><\/select><\/label>/);
const moveForm = {
  elements: {
    tag_id: { value: "demo:sauce" },
    location_id: { value: "freezer" },
    sublocation: { value: "Door bin" },
  },
};
await panel._saveContainerMove({ preventDefault() {}, currentTarget: moveForm });
assert.deepEqual(serviceCalls.at(-1), {
  domain: "mise_en_place_assistant",
  service: "move_container",
  data: {
    tag_id: "demo:sauce",
    location_id: "freezer",
    sublocation: "Door bin",
  },
});
panel._openCreateContainer("freezer");
assert.match(panel.shadowRoot.innerHTML, /<option value="freezer" selected>Freezer<\/option>/);
assert.match(panel.shadowRoot.innerHTML, /class="card location-card type-freezer selected"/);
assert.doesNotMatch(panel.shadowRoot.innerHTML, /id="add-container"/);
panel._selectedLocation = "freezer";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /class="card location-card type-freezer selected"/);
assert.match(panel.shadowRoot.innerHTML, /class="row container-card kind-ingredient"/);
assert.match(panel.shadowRoot.innerHTML, /<span>Status<\/span><strong>No live sensors<\/strong>/);
assert.match(panel.shadowRoot.innerHTML, /class="sublocation-button active" data-location-id="freezer" data-select-sublocation="Door bin"/);
assert.match(panel.shadowRoot.innerHTML, /Door bin · 1 container/);
assert.match(panel.shadowRoot.innerHTML, /Frozen peas/);
assert.match(panel.shadowRoot.innerHTML, /Freezer bin/);
assert.match(panel.shadowRoot.innerHTML, /Freezer \/ Door bin/);
assert.match(panel.shadowRoot.innerHTML, /Tracked/);
assert.match(panel.shadowRoot.innerHTML, /title="Mark physical container deleted" aria-label="Mark physical container deleted"/);
assert.match(panel.shadowRoot.innerHTML, /Empty/);
panel._openContainerEdit("demo:peas");
assert.match(panel.shadowRoot.innerHTML, /id="edit-container-form"/);
assert.match(panel.shadowRoot.innerHTML, /value="demo:peas" readonly/);
assert.match(panel.shadowRoot.innerHTML, /name="name" value="Freezer bin"/);
assert.match(panel.shadowRoot.innerHTML, /name="quantity" required type="number" min="0" step="any" value="0"/);
const editForm = {
  elements: {
    tag_id: { value: "demo:peas" },
    name: { value: "Freezer door bin" },
    quantity: { value: "3" },
    unit: { value: "bags" },
    location_id: { value: "freezer" },
    sublocation: { value: "Door bin" },
    best_before_date: { value: "" },
    purchased_date: { value: "" },
    opened_date: { value: "" },
  },
};
await panel._saveContainerEdit({ preventDefault() {}, currentTarget: editForm });
assert.deepEqual(serviceCalls.at(-1), {
  domain: "mise_en_place_assistant",
  service: "update_container",
  data: {
    tag_id: "demo:peas",
    quantity: 3,
    name: "Freezer door bin",
    unit: "bags",
    location_id: "freezer",
    sublocation: "Door bin",
  },
});
panel._tab = "dev";
panel._render();
assert.match(panel.shadowRoot.innerHTML, /Simulate CRUD/);
assert.match(panel.shadowRoot.innerHTML, /Shopping workflow/);
assert.match(panel.shadowRoot.innerHTML, /Add shopping item/);
assert.match(panel.shadowRoot.innerHTML, /Shopping activity/);
assert.match(panel.shadowRoot.innerHTML, /data-sync-missing-products/);
await panel._simulateCrud();
assert.deepEqual(serviceCalls.at(-1), {
  domain: "mise_en_place_assistant",
  service: "simulate_crud",
  data: {},
});
inventoryUpdated();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(overviewRequests, 2, "inventory events refresh the panel immediately");
panel.disconnectedCallback();
assert.equal(eventsUnsubscribed, true, "the inventory event subscription is released");
