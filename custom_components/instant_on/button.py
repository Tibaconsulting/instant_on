"""Button platform for HPE Networking Instant On."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import InstantOnConfigEntry, InstantOnCoordinator
from .entity import InstantOnEntity, site_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InstantOnConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Instant On buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([InstantOnRefreshButton(coordinator)])


class InstantOnRefreshButton(InstantOnEntity, ButtonEntity):
    """Button to trigger an immediate data refresh."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "refresh_now"

    def __init__(self, coordinator: InstantOnCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.site_id}_refresh_now"
        self._attr_device_info = site_device_info(coordinator)

    async def async_press(self) -> None:
        """Refresh site data immediately."""
        await self.coordinator.async_request_refresh()
