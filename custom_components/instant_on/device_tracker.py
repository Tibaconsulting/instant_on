"""Device tracker platform for HPE Networking Instant On clients."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    CLIENT_FILTER_NAMED,
    CLIENT_FILTER_WIRED,
    CLIENT_FILTER_WIRELESS,
    CONF_CLIENT_FILTER,
    CONF_ENABLE_NEW_CLIENTS,
    CONF_TRACK_CLIENTS,
)
from .coordinator import InstantOnConfigEntry, InstantOnCoordinator
from .entity import InstantOnEntity

_LOGGER = logging.getLogger(__name__)

# Lightweight OUI prefix table for common network/virtualization/IoT vendors
# when Instant On does not report a hostname or classification.
_OUI_VENDORS: dict[str, str] = {
    "00:0c:29": "VMware",
    "00:50:56": "VMware",
    "00:15:5d": "Hyper-V",
    "08:00:27": "VirtualBox",
    "1c:98:ec": "HPE",
    "a4:5d:36": "HPE",
    "34:c5:15": "HPE Aruba",
    "94:ff:06": "HPE Aruba",
    "54:f0:b1": "HPE Aruba",
    "b8:27:eb": "Raspberry Pi",
    "dc:a6:32": "Raspberry Pi",
    "e4:5f:01": "Raspberry Pi",
    "2c:cf:67": "Raspberry Pi",
    "7c:87:ce": "Espressif",
    "9c:9c:1f": "Espressif",
    "24:6f:28": "Espressif",
    "30:ae:a4": "Espressif",
    "00:11:32": "Synology",
    "90:09:d0": "Synology",
    "24:5e:be": "QNAP",
    "00:e0:c5": "Bcom",
}

_AUTO_LABEL_PREFIXES = (
    "Instant On: ",
    "SSID: ",
    "VLAN: ",
)


def _should_track_client(client: dict[str, Any], client_filter: str) -> bool:
    if client_filter == CLIENT_FILTER_WIRELESS:
        return client.get("clientType") == "wireless"
    if client_filter == CLIENT_FILTER_WIRED:
        return client.get("clientType") == "wired"
    if client_filter == CLIENT_FILTER_NAMED:
        mac = (client.get("macAddress") or "").lower()
        name = (client.get("name") or "").lower()
        host = (client.get("hostName") or "").lower()
        return bool((name and name != mac) or host)
    return True


def _resolve_client_name(client: dict[str, Any], mac: str) -> str:
    """Resolve the best human-readable friendly name for a client."""
    name = (client.get("name") or "").strip()
    if name and name.lower() != mac:
        return name

    host = (client.get("hostName") or "").strip()
    if host:
        return host

    suffix = mac.replace(":", "")[-4:].upper()

    for port in client.get("connectedToPorts") or []:
        port_name = (port.get("portName") or "").strip()
        if port_name:
            return f"{port_name} ({suffix})"

    classifications = [
        c.get("str")
        for c in (client.get("classification") or [])
        if isinstance(c, dict) and c.get("str")
    ]
    if classifications:
        return f"{classifications[0]} ({suffix})"

    vendor = _OUI_VENDORS.get(mac[:8])
    if vendor:
        return f"{vendor} ({suffix})"

    return mac.upper()


def _compute_client_labels(client: dict[str, Any]) -> list[str]:
    """Compute grouping labels based on type, SSID/VLAN, function, and AP/switch."""
    labels: list[str] = []

    client_type = client.get("clientType")
    if client_type == "wireless":
        labels.append("Instant On: Wireless")
    elif client_type == "wired":
        labels.append("Instant On: Wired")

    if ssid := client.get("wirelessNetworkName"):
        labels.append(f"SSID: {ssid}")

    if wired_net := client.get("wiredNetworkName"):
        labels.append(f"VLAN: {wired_net}")

    if dev_name := client.get("deviceName"):
        labels.append(f"Instant On: {dev_name}")

    for item in client.get("classification") or []:
        if isinstance(item, dict) and (tag := item.get("str")):
            labels.append(f"Instant On: {tag}")

    return labels


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InstantOnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Instant On device trackers from a config entry."""
    if not entry.options.get(CONF_TRACK_CLIENTS, True):
        return

    coordinator = entry.runtime_data
    client_filter = entry.options.get(CONF_CLIENT_FILTER, "all")
    enable_default = entry.options.get(CONF_ENABLE_NEW_CLIENTS, True)
    tracked_macs: set[str] = set()

    @callback
    def _async_discover_clients() -> None:
        new_entities: list[InstantOnClientTracker] = []
        for mac, client in coordinator.data.clients.items():
            if mac in tracked_macs:
                continue
            if not _should_track_client(client, client_filter):
                continue
            tracked_macs.add(mac)
            new_entities.append(
                InstantOnClientTracker(coordinator, mac, enable_default)
            )
        if new_entities:
            async_add_entities(new_entities)

    _async_discover_clients()
    entry.async_on_unload(coordinator.async_add_listener(_async_discover_clients))


class InstantOnClientTracker(InstantOnEntity, ScannerEntity):
    """Representation of an Instant On network client."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        mac: str,
        entity_registry_enabled_default: bool,
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.site_id}_client_{mac}"
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        self._last_label_names: tuple[str, ...] = ()

    @property
    def _client(self) -> dict[str, Any] | None:
        return self.coordinator.data.clients.get(self._mac)

    async def async_added_to_hass(self) -> None:
        """Sync grouping labels when added to Home Assistant."""
        await super().async_added_to_hass()
        self._sync_labels()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update entity state and sync grouping labels on data refresh."""
        self._sync_labels()
        super()._handle_coordinator_update()

    @callback
    def _sync_labels(self) -> None:
        """Keep HA entity labels in sync with client SSID/type/category/AP."""
        client = self._client
        if client is None or not self.entity_id:
            return

        desired_names = tuple(_compute_client_labels(client))
        if desired_names == self._last_label_names:
            return

        try:
            label_reg = lr.async_get(self.hass)
            ent_reg = er.async_get(self.hass)
        except Exception:
            return

        entry = ent_reg.async_get(self.entity_id)
        if entry is None:
            return

        auto_label_ids: set[str] = set()
        for name in desired_names:
            label = label_reg.async_get_label_by_name(name)
            if label is None:
                label = label_reg.async_create(name=name)
            auto_label_ids.add(label.label_id)

        # Preserve any user-defined labels that don't use our auto prefixes
        preserved_ids: set[str] = set()
        for existing_id in entry.labels:
            existing_label = label_reg.async_get_label(existing_id)
            if existing_label and not existing_label.name.startswith(
                _AUTO_LABEL_PREFIXES
            ):
                preserved_ids.add(existing_id)

        new_labels = preserved_ids | auto_label_ids
        if new_labels != entry.labels:
            ent_reg.async_update_entity(self.entity_id, labels=new_labels)

        self._last_label_names = desired_names

    @property
    def name(self) -> str:
        client = self._client
        if client is None:
            return self._mac.upper()
        return _resolve_client_name(client, self._mac)

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        client = self._client
        if client is None:
            return False
        return client.get("status") == "up"

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def ip_address(self) -> str | None:
        client = self._client
        return client.get("ipAddress") if client else None

    @property
    def hostname(self) -> str | None:
        client = self._client
        return client.get("hostName") if client else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        client = self._client
        if client is None:
            return None

        traffic = client.get("dataTraffic") or {}
        ports = [
            {
                "device_name": p.get("deviceName"),
                "port_number": p.get("portNumber"),
                "port_name": p.get("portName"),
                "speed": p.get("portSpeed"),
                "duplex": p.get("duplex"),
                "is_powered_by_port": p.get("isPoweredByPort"),
            }
            for p in (client.get("connectedToPorts") or [])
        ]
        classifications = [
            c.get("str")
            for c in (client.get("classification") or [])
            if isinstance(c, dict) and c.get("str")
        ]

        return {
            "client_type": client.get("clientType"),
            "health": client.get("health"),
            "connected_device_name": client.get("deviceName"),
            "connected_device_id": client.get("deviceId"),
            "wireless_network": client.get("wirelessNetworkName"),
            "wireless_band": client.get("wirelessBand"),
            "wireless_radio_id": client.get("wirelessRadioId"),
            "signal_quality": client.get("signalQuality"),
            "snr_db": client.get("snrInDb"),
            "wired_network": client.get("wiredNetworkName"),
            "connected_ports": ports or None,
            "downstream_bps": client.get("downstreamThroughputInBitsPerSecond"),
            "upstream_bps": client.get("upstreamThroughputInBitsPerSecond"),
            "downstream_24h_bytes": traffic.get(
                "downstreamDataTransferredInBytesInLast24Hours"
            ),
            "upstream_24h_bytes": traffic.get(
                "upstreamDataTransferredInBytesInLast24Hours"
            ),
            "top_application_category": client.get("topApplicationCategory"),
            "classification": classifications or None,
            "state_duration_seconds": client.get("stateDurationInSeconds"),
            "last_state_change": client.get("lastStateChange"),
            "is_blocked": client.get("isBlocked"),
            "is_blacklisted": client.get("isBlacklisted"),
            "is_watchlisted": client.get("isWatchlisted"),
            "reserved_ip_address": client.get("reservedIpAddress"),
        }
