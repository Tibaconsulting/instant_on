# Changelog

## v0.4.0 (2026-11-24)
- **Tested Environment:**
  - Home Assistant Core: `2026.11`
  - Instant On API Version: `x-ion-api-version: 20`
  - Instant On Portal Build (`Last-Modified`): `Thu, 19 Nov 2026 20:25:34 GMT`
  - Tested Device Firmware: AP `3.4.2.0`, Switch `3.4.3.0`
- **Features & Fixes:**
  - Added full HPE Networking Instant On SKU & hardware model catalog (`models.py`) covering AP11–AP32, 1830/1930/1960 switches, and SG1004/SG2505P gateways, populating both `model` (marketing name) and `model_id` (HW model / SKU) in `DeviceInfo`.
  - Added `client_aliases` (`mac=Friendly Name`) in OptionsFlow so MAC-only `device_tracker` entities can be given persistent human-readable names inside Home Assistant.
  - Added `uplink_device_name`, `uplink_port_number`, `uplink_speed`, `sku`, and `hardware_model` attributes to hardware device health sensors, plus `portal_build` and `topology` in diagnostics.

## v0.3.0 (2026-11-24)
- **Tested Environment:** HA Core `2026.11`, API `v20`, AP `3.4.2.0`, Switch `3.4.3.0`
- Bumped `x-ion-api-version` from `7` to `20` so all AP models appear in `/inventory`.
- Added dynamic entity discovery on refresh for hardware devices, radios, and SSIDs.
- Added `Last sync` diagnostic timestamp sensor on the Site device.

## v0.2.0 (2026-11-24)
- Attached SSID entities directly to the Site device (`DeviceEntryType.SERVICE`) instead of creating per-SSID devices.
- Added port-name and OUI vendor fallbacks for client names and automatic Home Assistant Labels for client grouping.

## v0.1.0 (2026-11-24)
- Initial read-only HPE Networking Instant On integration with OAuth2 PKCE + `refresh_token` support, UI ConfigFlow/Reauth/Options, Site/Device/Radio/SSID sensors, binary sensors, client `device_tracker`, refresh button, diagnostics, and `en`/`hu` translations.
