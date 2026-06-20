import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class FakeShadowRoot {
  innerHTML = "";

  getElementById() {
    return null;
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
    containers: [],
    items: [],
    locations: [],
    logbook: [],
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
assert.match(panel.shadowRoot.innerHTML, /Containers/);
inventoryUpdated();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(overviewRequests, 2, "inventory events refresh the panel immediately");
panel.disconnectedCallback();
assert.equal(eventsUnsubscribed, true, "the inventory event subscription is released");
