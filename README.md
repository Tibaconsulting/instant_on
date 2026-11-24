# HPE Instant On for Home Assistant

An unofficial, strictly **read-only** Home Assistant integration for **HPE Networking Instant On** (formerly Aruba Instant On) access points and switches.

> [!WARNING]
> **Unofficial & Unsupported:** HPE Networking does not publish an official public API for Instant On. This integration uses the private cloud portal API (`portal.instant-on.hpe.com`). Use a dedicated, **view-only** account with **MFA disabled** so your primary admin account remains protected.

## Features

- **Site Telemetry:** Health status, health score, total/wireless/wired client counts, online/total device counts, active alerts, live throughput, and 24h data transferred.
- **Hardware Devices (APs & Switches):** Connectivity, firmware version & update availability, uptime, IP address, connected client count, PoE consumed/budget (switches), and per-band radio utilization with channel/width/Tx-power attributes (APs).
- **Wireless Networks (SSIDs):** Enabled state, connected clients (with 2.4/5/6 GHz breakdown, VLAN ID, security), and downstream/upstream throughput.
- **Rich Client Tracking (`device_tracker`):** Wired and wireless clients (including recently seen offline clients reported by `clientSummary`) with IP, MAC, hostname, vendor/device classification, connected AP/switch port, SNR, signal quality, throughput, 24h traffic, and top application category.
- **UI Configuration & Options:** Full UI Config Flow (multi-site support, re-authentication, configurable polling interval, and client filtering).
- **Diagnostics:** Redacted diagnostic dump for troubleshooting.
- **Languages:** English (`en`) and Hungarian (`hu`).

## Installation (HACS)

1. Open **HACS** in Home Assistant → **Integrations** → three-dot menu → **Custom repositories**.
2. Add `https://github.com/tibaconsulting/instant_on` with category **Integration**.
3. Search for **HPE Instant On**, download it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → HPE Instant On**.

## License

MIT License — see [LICENSE](LICENSE).
