# Mise en Place Assistant

Mise en Place Assistant is a private Home Assistant custom integration for the
physical side of kitchen prep: what is prepped, where it is, whether it is safe,
and what the next useful kitchen action should be.

Mealie knows what the household wants to cook. Grocy knows what stock exists.
KitchenOwl knows what to buy. Home Assistant knows what the home is sensing.
Mise ties those signals to tagged containers, storage health, local prep state,
logbook history, and fast NFC workflows on the M5Dial.

> This is an experiment. Do not install or clone it for production or critical
> household tracking.

## What it contains

- `custom_components/mise_en_place_assistant/` — the Home Assistant
  integration, including config flow, local storage, entities, services, and
  frontend panel.
- `m5dial/m5dial-mise-en-place-assistant.yaml` — ESPHome firmware for an M5Dial
  NFC inventory controller and Bluetooth proxy.

## What Mise owns

Mise owns the household-facing prep layer:

- reusable NFC-tagged containers and their local lifecycle;
- where prepared food physically lives;
- whether storage locations need attention from Home Assistant sensors;
- M5Dial scan, create, update, cancel, timeout, and result workflows;
- local prep state, storage attention, recommendations, and logbook history.

Provider ownership stays outside Mise:

- Mealie owns recipes, foods, and meal-planning context.
- Grocy owns durable stock, products, units, storage locations, expiry, and
  minimum-stock policy.
- KitchenOwl owns household shopping-list execution.
- Home Assistant owns automations, entities, devices, and environmental
  signals.

The integration treats an NFC tag as the identity of a reusable physical
container. A container may be filled, emptied, washed, stored, and refilled
without changing its tag identity. Mocked data is available only through the
integration's DEV mode when no live data provider is configured.

## Setup outline

1. Copy `custom_components/mise_en_place_assistant` into Home Assistant's
   `custom_components` directory and restart Home Assistant.
2. Add **Mise en Place Assistant** from Settings → Devices & services. Configure
   initial locations and, optionally, the ESPHome M5Dial device.
3. Compile the M5Dial YAML in ESPHome and adopt the device in Home Assistant.
4. Use the integration panel or its services to create locations and containers;
   scanning a tag on the Dial then opens the appropriate create or update flow.

## Services and inventory

The integration exposes services to create locations and containers, update a
container, fill or remove items, scan a container, and mark a cleaned container
as ready for storage. Container quantities are stored with their unit and
location; a zero quantity represents an empty container rather than deleting
the physical container. Shopping services route explicit requests to the
configured shopping target while preserving Grocy-backed product identity where
possible.

## Unmanaged ESPHome secrets

The M5Dial configuration intentionally references local ESPHome secrets but
does not manage or provide them. Create a local `secrets.yaml` beside the device
configuration (or use your existing ESPHome secret source) with values for:

```yaml
wifi_ssid: "your-wifi-name"
wifi_password: "your-wifi-password"
api_encryption_key: "your-esphome-api-key"
ota_password: "your-ota-password"
fallback_ap_password: "your-fallback-ap-password"
```

Keep that file out of version control. Never add Wi-Fi credentials, API keys,
device identifiers, or private endpoints to this repository.

## Development notes

Inventory data is durable local state. Changes to the Home Assistant integration
and the M5Dial firmware should be checked together: event names, action names,
payload fields, NFC tag identity, and cancel/timeout paths must stay aligned.
