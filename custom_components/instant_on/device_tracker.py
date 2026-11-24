"""Device tracker platform for HPE Networking Instant On clients."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
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


def _should_track_client(
    client: dict[str, Any], client_filter: str
) -> bool:
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
    name = (client.get("name") or "").strip()
    if name and name.lower() != mac:
        return name
    host = (client.get("hostName") or "").strip()
    if host:
        return host
    classifications = [
        c.get("str")
        for c in (client.get("classification") or [])
        if isinstance(c, dict) and c.get("str")
    ]
    if classifications:
        suffix = mac.replace(":", "")[-4:].upper()
        return f"{classifications[0]} ({suffix})"
    return mac.upper()


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

    @property
    def _client(self) -> dict[str, Any] | None:
        return self.coordinator.data.clients.get(self._mac)

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
