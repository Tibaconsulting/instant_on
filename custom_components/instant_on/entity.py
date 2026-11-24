"""Base entity and device info helpers for HPE Networking Instant On."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import InstantOnCoordinator
from .models import resolve_device_model


def site_device_info(coordinator: InstantOnCoordinator) -> DeviceInfo:
    """Return DeviceInfo for the Instant On site (whole home/location)."""
    site = coordinator.data.site
    landing = coordinator.data.landing_page
    site_name = site.get("name") or landing.get("siteName") or coordinator.site_id
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.site_id)},
        name=site_name,
        manufacturer="HPE Networking",
        model="Instant On Site",
        entry_type=DeviceEntryType.SERVICE,
    )


def hardware_device_info(
    coordinator: InstantOnCoordinator, device: dict[str, Any]
) -> DeviceInfo:
    """Return DeviceInfo for an Instant On AP, switch, or gateway."""
    dev_id = device["id"]
    mac = device.get("macAddress")
    connections = {(CONNECTION_NETWORK_MAC, mac)} if mac else set()
    model, model_id = resolve_device_model(
        device.get("sku"), device.get("model"), device.get("deviceType")
    )
    return DeviceInfo(
        identifiers={(DOMAIN, dev_id)},
        connections=connections,
        name=device.get("name") or device.get("defaultName") or dev_id,
        manufacturer="HPE Networking",
        model=model,
        model_id=model_id,
        sw_version=device.get("deviceSoftwareVersion"),
        serial_number=device.get("serialNumber"),
        via_device=(DOMAIN, coordinator.site_id),
    )


class InstantOnEntity(CoordinatorEntity[InstantOnCoordinator]):
    """Base entity for HPE Instant On."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
