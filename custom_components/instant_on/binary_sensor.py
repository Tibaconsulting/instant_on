"""Binary sensor platform for HPE Networking Instant On."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import InstantOnConfigEntry, InstantOnCoordinator, InstantOnData
from .entity import (
    InstantOnEntity,
    hardware_device_info,
    site_device_info,
)


@dataclass(frozen=True, kw_only=True)
class InstantOnSiteBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a site-level binary sensor."""

    value_fn: Callable[[InstantOnData], bool | None]


@dataclass(frozen=True, kw_only=True)
class InstantOnDeviceBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a device-level binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda _dev: True


SITE_BINARY_SENSORS: tuple[InstantOnSiteBinarySensorDescription, ...] = (
    InstantOnSiteBinarySensorDescription(
        key="connectivity",
        translation_key="site_connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: (d.site.get("status") == "up")
        if d.site.get("status") is not None
        else None,
    ),
    InstantOnSiteBinarySensorDescription(
        key="active_alerts",
        translation_key="site_active_alerts",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: (d.landing_page.get("activeAlertsCount") or 0) > 0,
    ),
    InstantOnSiteBinarySensorDescription(
        key="update_in_progress",
        translation_key="update_in_progress",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.landing_page.get("updateInProgress")),
    ),
    InstantOnSiteBinarySensorDescription(
        key="maintenance_mode",
        translation_key="maintenance_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.site.get("isMaintenanceMode")),
    ),
)

DEVICE_BINARY_SENSORS: tuple[InstantOnDeviceBinarySensorDescription, ...] = (
    InstantOnDeviceBinarySensorDescription(
        key="connectivity",
        translation_key="device_connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda dev: dev.get("status") == "up",
    ),
    InstantOnDeviceBinarySensorDescription(
        key="update_available",
        translation_key="device_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda dev: dev.get("isUpToDate") is not None,
        value_fn=lambda dev: not bool(dev.get("isUpToDate")),
    ),
    InstantOnDeviceBinarySensorDescription(
        key="underpowered",
        translation_key="device_underpowered",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda dev: dev.get("isUnderpowered") is not None,
        value_fn=lambda dev: bool(dev.get("isUnderpowered")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InstantOnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Instant On binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        InstantOnSiteBinarySensor(coordinator, desc) for desc in SITE_BINARY_SENSORS
    )

    known_devices: set[str] = set()
    known_networks: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        new_entities: list[BinarySensorEntity] = []
        for dev_id, dev in coordinator.data.devices.items():
            if dev_id not in known_devices:
                known_devices.add(dev_id)
                for desc in DEVICE_BINARY_SENSORS:
                    if desc.exists_fn(dev):
                        new_entities.append(
                            InstantOnDeviceBinarySensor(coordinator, dev_id, desc)
                        )

        for net_id in coordinator.data.networks:
            if net_id not in known_networks:
                known_networks.add(net_id)
                new_entities.append(
                    InstantOnNetworkEnabledBinarySensor(coordinator, net_id)
                )

        if new_entities:
            async_add_entities(new_entities)

    _async_discover_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_discover_entities))


class InstantOnSiteBinarySensor(InstantOnEntity, BinarySensorEntity):
    """Site-level binary sensor."""

    entity_description: InstantOnSiteBinarySensorDescription

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        description: InstantOnSiteBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site_id}_site_{description.key}"
        self._attr_device_info = site_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)


class InstantOnDeviceBinarySensor(InstantOnEntity, BinarySensorEntity):
    """Hardware-device-level binary sensor."""

    entity_description: InstantOnDeviceBinarySensorDescription

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        device_id: str,
        description: InstantOnDeviceBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        dev = self._device
        if dev is None:
            return None
        return self.entity_description.value_fn(dev)


class InstantOnNetworkEnabledBinarySensor(InstantOnEntity, BinarySensorEntity):
    """Binary sensor indicating whether an SSID is enabled."""

    _attr_translation_key = "network_enabled"

    def __init__(
        self,
        coordinator: InstantOnCoordinator,
        network_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._network_id = network_id
        self._attr_unique_id = f"{coordinator.site_id}_net_{network_id}_enabled"
        net = coordinator.data.networks[network_id]
        net_name = net.get("networkName") or network_id
        self._attr_translation_placeholders = {"network": net_name}
        self._attr_device_info = site_device_info(coordinator)

    @property
    def _network(self) -> dict[str, Any] | None:
        return self.coordinator.data.networks.get(self._network_id)

    @property
    def available(self) -> bool:
        return super().available and self._network is not None

    @property
    def is_on(self) -> bool | None:
        net = self._network
        if net is None:
            return None
        return bool(net.get("isEnabled"))
