"""Config flow and options flow for HPE Networking Instant On."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    InstantOnApiClient,
    InstantOnAuthError,
    InstantOnConnectionError,
    InstantOnError,
)
from .const import (
    CLIENT_FILTER_ALL,
    CLIENT_FILTER_NAMED,
    CLIENT_FILTER_WIRED,
    CLIENT_FILTER_WIRELESS,
    CONF_CLIENT_FILTER,
    CONF_ENABLE_NEW_CLIENTS,
    CONF_SCAN_INTERVAL,
    CONF_SITE_ID,
    CONF_SITE_NAME,
    CONF_TRACK_CLIENTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class InstantOnConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HPE Instant On."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._sites: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return InstantOnOptionsFlow()

    async def _async_validate_and_fetch_sites(
        self, username: str, password: str
    ) -> list[dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        client = InstantOnApiClient(session, username, password)
        await client.async_authenticate()
        return await client.async_get_sites()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]
            try:
                self._sites = await self._async_validate_and_fetch_sites(
                    self._username, self._password
                )
            except InstantOnAuthError:
                errors["base"] = "invalid_auth"
            except InstantOnConnectionError:
                errors["base"] = "cannot_connect"
            except InstantOnError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error during Instant On login")
                errors["base"] = "unknown"
            else:
                if not self._sites:
                    errors["base"] = "no_sites"
                elif len(self._sites) == 1:
                    site = self._sites[0]
                    return await self._async_create_site_entry(site)
                else:
                    return await self.async_step_site()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select a site when multiple sites exist."""
        site_map = {
            site["id"]: site.get("name") or site["id"]
            for site in self._sites
            if site.get("id")
        }

        if user_input is not None:
            site_id = user_input[CONF_SITE_ID]
            site = next((s for s in self._sites if s.get("id") == site_id), None)
            if site is not None:
                return await self._async_create_site_entry(site)

        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema(
                {vol.Required(CONF_SITE_ID): vol.In(site_map)}
            ),
        )

    async def _async_create_site_entry(
        self, site: dict[str, Any]
    ) -> ConfigFlowResult:
        site_id: str = site["id"]
        site_name: str = site.get("name") or site_id

        await self.async_set_unique_id(site_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=site_name,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_SITE_ID: site_id,
                CONF_SITE_NAME: site_name,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when credentials expire or fail."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await self._async_validate_and_fetch_sites(username, password)
            except InstantOnAuthError:
                errors["base"] = "invalid_auth"
            except InstantOnConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Instant On reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=reauth_entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class InstantOnOptionsFlow(OptionsFlow):
    """Handle options for HPE Instant On."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Required(
                        CONF_TRACK_CLIENTS,
                        default=options.get(CONF_TRACK_CLIENTS, True),
                    ): bool,
                    vol.Required(
                        CONF_CLIENT_FILTER,
                        default=options.get(CONF_CLIENT_FILTER, CLIENT_FILTER_ALL),
                    ): vol.In(
                        [
                            CLIENT_FILTER_ALL,
                            CLIENT_FILTER_NAMED,
                            CLIENT_FILTER_WIRELESS,
                            CLIENT_FILTER_WIRED,
                        ]
                    ),
                    vol.Required(
                        CONF_ENABLE_NEW_CLIENTS,
                        default=options.get(CONF_ENABLE_NEW_CLIENTS, True),
                    ): bool,
                }
            ),
        )
