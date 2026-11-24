"""Diagnostics support for HPE Networking Instant On."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import InstantOnConfigEntry

TO_REDACT: set[str] = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "account",
    "macAddress",
    "ipAddress",
    "managementIpAddress",
    "reservedIpAddress",
    "defaultGateway",
    "primaryDns",
    "secondaryDns",
    "preSharedKey",
    "serialNumber",
    "configuredLocation",
    "detectedLocation",
    "hostName",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InstantOnConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry with sensitive fields redacted."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "data": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
