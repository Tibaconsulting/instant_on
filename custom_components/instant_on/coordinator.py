"""DataUpdateCoordinator for HPE Networking Instant On."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    InstantOnApiClient,
    InstantOnAuthError,
    InstantOnError,
    InstantOnRateLimitError,
)
from .const import CONF_SCAN_INTERVAL, CONF_SITE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type InstantOnConfigEntry = ConfigEntry[InstantOnCoordinator]


@dataclass(slots=True)
class InstantOnData:
    """Structured snapshot of a single Instant On site."""

    site: dict[str, Any]
    landing_page: dict[str, Any]
    devices: dict[str, dict[str, Any]]
    clients: dict[str, dict[str, Any]]
    networks: dict[str, dict[str, Any]]
    wired_networks: dict[str, dict[str, Any]]
    alerts: list[dict[str, Any]]
    app_usage: list[dict[str, Any]]


class InstantOnCoordinator(DataUpdateCoordinator[InstantOnData]):
    """Coordinator that polls the Instant On cloud portal for one site."""

    config_entry: InstantOnConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: InstantOnConfigEntry,
        client: InstantOnApiClient,
    ) -> None:
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.data[CONF_SITE_ID]}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.config_entry = config_entry
        self.client = client
        self.site_id: str = config_entry.data[CONF_SITE_ID]

    async def _async_update_data(self) -> InstantOnData:
        """Fetch the latest site snapshot from the Instant On API."""
        try:
            raw = await self.client.async_get_site_snapshot(self.site_id)
        except InstantOnAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except InstantOnRateLimitError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err
        except InstantOnError as err:
            raise UpdateFailed(f"Error communicating with Instant On API: {err}") from err

        devices = {
            dev["id"]: dev for dev in raw["inventory"] if dev.get("id")
        }
        clients = {
            (cli.get("macAddress") or cli["id"]).lower(): cli
            for cli in raw["clients"]
            if cli.get("macAddress") or cli.get("id")
        }
        networks = {
            net["id"]: net for net in raw["networks"] if net.get("id")
        }
        wired_networks = {
            net["id"]: net for net in raw["wired_networks"] if net.get("id")
        }

        return InstantOnData(
            site=raw["site"],
            landing_page=raw["landing_page"],
            devices=devices,
            clients=clients,
            networks=networks,
            wired_networks=wired_networks,
            alerts=raw["alerts"],
            app_usage=raw["app_usage"],
        )
