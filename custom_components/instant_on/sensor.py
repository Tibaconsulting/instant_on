"""Sensor platform for HPE Networking Instant On."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import InstantOnConfigEntry, InstantOnCoordinator, InstantOnData
from .entity import (
    InstantOnEntity,
    hardware_device_info,
    network_device_info,
    site_device_info,
)


@dataclass(frozen=True, kw_only=True)
class InstantOnSiteSensorDescription(SensorEntityDescription):
    """Describe a site-level Instant On sensor."""

    value_fn: Callable[[InstantOnData], Any]
    attrs_fn: Callable[[InstantOnData], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class InstantOnDeviceSensorDescription(SensorEntityDescription):
    """Describe a hardware-device-level Instant On sensor."""

    value_fn: Callable[[InstantOnData, dict[str, Any]], Any]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _dev: True


@dataclass(frozen=True, kw_only=True)
class InstantOnNetworkSensorDescription(SensorEntityDescription):
    """Describe a wireless-network-level Instant On sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SITE_SENSORS: tuple[InstantOnSiteSensorDescription, ...] = (
    InstantOnSiteSensorDescription(
        key="health",
        translation_key="site_health",
        value_fn=lambda d: d.site.get("health") or d.landing_page.get("health"),
        attrs_fn=lambda d: {
            "health_reason": d.site.get("healthReason")
            or d.landing_page.get("healthReason"),
            "score_trend": d.site.get("healthScoreTrend"),
        },
    ),
    InstantOnSiteSensorDescription(
        key="health_score",
        translation_key="health_score",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.site.get("currentHealthScore") or {}).get("score"),
    ),
    InstantOnSiteSensorDescription(
        key="total_clients",
        translation_key="total_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            (d.landing_page.get("wirelessClientsCount") or 0)
            + (d.landing_page.get("wiredClientsCount") or 0)
        ),
        attrs_fn=lambda d: {
            "known_clients_in_summary": len(d.clients),
        },
    ),
    InstantOnSiteSensorDescription(
        key="wireless_clients",
        translation_key="wireless_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get("wirelessClientsCount"),
    ),
    InstantOnSiteSensorDescription(
        key="wired_clients",
        translation_key="wired_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get("wiredClientsCount"),
    ),
    InstantOnSiteSensorDescription(
        key="devices_up",
        translation_key="devices_up",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get("deviceUpCount"),
    ),
    InstantOnSiteSensorDescription(
        key="devices_total",
        translation_key="devices_total",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get("deviceCount"),
    ),
    InstantOnSiteSensorDescription(
        key="active_alerts",
        translation_key="active_alerts",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get("activeAlertsCount"),
        attrs_fn=lambda d: {
            "alerts": [
                {
                    "type": a.get("type"),
                    "severity": a.get("severity"),
                    "raised_time": a.get("raisedTime"),
                    "cleared_time": a.get("clearedTime"),
                }
                for a in d.alerts[:10]
            ]
        },
    ),
    InstantOnSiteSensorDescription(
        key="throughput",
        translation_key="site_throughput",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.landing_page.get(
            "currentNetworkThroughputInBitsPerSecond"
        ),
    ),
    InstantOnSiteSensorDescription(
        key="traffic_24h",
        translation_key="site_traffic_24h",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.landing_page.get(
            "totalDataTransferredDuringLast24HoursInBytes"
        ),
    ),
)


DEVICE_SENSORS: tuple[InstantOnDeviceSensorDescription, ...] = (
    InstantOnDeviceSensorDescription(
        key="health",
        translation_key="device_health",
        value_fn=lambda _d, dev: dev.get("health"),
    ),
    InstantOnDeviceSensorDescription(
        key="uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _d, dev: dev.get("uptimeInSeconds"),
    ),
    InstantOnDeviceSensorDescription(
        key="clients",
        translation_key="device_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d, dev: sum(
            1
            for cli in d.clients.values()
            if cli.get("deviceId") == dev["id"] and cli.get("status") == "up"
        ),
    ),
    InstantOnDeviceSensorDescription(
        key="ip_address",
        translation_key="device_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _d, dev: dev.get("ipAddress") or dev.get("managementIpAddress"),
    ),
    InstantOnDeviceSensorDescription(
        key="software_version",
        translation_key="device_software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda _d, dev: dev.get("deviceSoftwareVersion"),
    ),
    InstantOnDeviceSensorDescription(
        key="poe_consumed",
        translation_key="poe_consumed",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda dev: dev.get("poePseNominalPowerInWatts") is not None,
        value_fn=lambda _d, dev: dev.get("poePseConsumedPowerInWatts"),
    ),
    InstantOnDeviceSensorDescription(
        key="poe_budget",
        translation_key="poe_budget",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda dev: dev.get("poePseNominalPowerInWatts") is not None,
        value_fn=lambda _d, dev: dev.get("poePseNominalPowerInWatts"),
    ),
)


NETWORK_SENSORS: tuple[InstantOnNetworkSensorDescription, ...] = (
    InstantOnNetworkSensorDescription(
        key="clients",
        translation_key="network_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda net: net.get("wirelessClientsCount"),
        attrs_fn=lambda net: {
            "clients_2_4ghz": net.get("wireless24GHzClientsCount"),
            "clients_5ghz": net.get("wireless5GHzClientsCount"),
            "clients_6ghz": net.get("wireless6GHzClientsCount"),
            "vlan_id": net.get("vlanId"),
            "security": net.get("security"),
            "type": net.get("type"),
            "is_ssid_hidden": net.get("isSsidHidden"),
            "is_guest_portal_enabled": net.get("isGuestPortalEnabled"),
        },
    ),
    InstantOnNetworkSensorDescription(
        key="downstream_throughput",
        translation_key="network_downstream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda net: net.get("downstreamThroughputInBitsPerSecond"),
    ),
    InstantOnNetworkSensorDescription(
        key="upstream_throughput",
        translation_key="network_upstream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda net: net.get("upstreamThroughputInBitsPerSecond"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InstantOnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Instant On sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        InstantOnSiteSensor(coordinator, desc) for desc in SITE_SENSORS
    ]

    for dev_id, dev in coordinator.data.devices.items():
        for desc in DEVICE_SENSORS:
            if desc.exists_fn(dev):
                entities.append(InstantOnDeviceSensor(coordinator, dev_id, desc))
        for radio in dev.get("radios") or []:
            band = radio.get("band")
            if band:
                entities.append(InstantOnRadioSensor(coordinator, dev_id, band))

    for net_id in coordinator.data.networks:
        for desc in NETWORK_SENSORS:
            entities.append(InstantOnNetworkSensor(coordinator, net_id, desc))

    async_add_entities(entities)


class InstantOnSiteSensor(InstantOnEntity, SensorEntity):
    """Site-level sensor for HPE Instant On."""

    entity_description: InstantOnSiteSensorDescription

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        description: InstantOnSiteSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site_id}_site_{description.key}"
        self._attr_device_info = site_device_info(coordinator)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class InstantOnDeviceSensor(InstantOnEntity, SensorEntity):
    """Hardware-device-level sensor for HPE Instant On."""

    entity_description: InstantOnDeviceSensorDescription

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        device_id: str,
        description: InstantOnDeviceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site_id}_dev_{device_id}_{description.key}"
        device = coordinator.data.devices[device_id]
        self._attr_device_info = hardware_device_info(coordinator, device)

    @property
    def _device(self) -> dict[str, Any] | None:
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def available(self) -> bool:
        return super().available and self._device is not None

    @property
    def native_value(self) -> Any:
        dev = self._device
        if dev is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data, dev)


class InstantOnRadioSensor(InstantOnEntity, SensorEntity):
    """Radio utilization sensor per AP band."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "radio_utilization"

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        device_id: str,
        band: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._band = band
        self._attr_unique_id = f"{coordinator.site_id}_dev_{device_id}_radio_{band}"
        self._attr_translation_placeholders = {"band": band.upper()}
        device = coordinator.data.devices[device_id]
        self._attr_device_info = hardware_device_info(coordinator, device)

    def _radio(self) -> dict[str, Any] | None:
        dev = self.coordinator.data.devices.get(self._device_id)
        if not dev:
            return None
        for radio in dev.get("radios") or []:
            if radio.get("band") == self._band:
                return radio
        return None

    @property
    def available(self) -> bool:
        return super().available and self._radio() is not None

    @property
    def native_value(self) -> Any:
        radio = self._radio()
        return radio.get("utilizationPercent") if radio else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        radio = self._radio()
        if not radio:
            return None
        return {
            "channel": radio.get("channel"),
            "channel_width": radio.get("channelWidth"),
            "wireless_clients_count": radio.get("wirelessClientsCount"),
            "tx_power_eirp_dbm": radio.get("txPowerEirpInDbm"),
            "regulatory_max_tx_power_dbm": radio.get("regulatoryMaxTxPowerEirpInDbm"),
        }


class InstantOnNetworkSensor(InstantOnEntity, SensorEntity):
    """Wireless network (SSID) sensor."""

    entity_description: InstantOnNetworkSensorDescription

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        network_id: str,
        description: InstantOnNetworkSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._network_id = network_id
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.site_id}_net_{network_id}_{description.key}"
        )
        net = coordinator.data.networks[network_id]
        self._attr_device_info = network_device_info(coordinator, net)

    @property
    def _network(self) -> dict[str, Any] | None:
        return self.coordinator.data.networks.get(self._network_id)

    @property
    def available(self) -> bool:
        return super().available and self._network is not None

    @property
    def native_value(self) -> Any:
        net = self._network
        if net is None:
            return None
        return self.entity_description.value_fn(net)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        net = self._network
        if net is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(net)
