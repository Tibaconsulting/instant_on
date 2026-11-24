"""Constants for the HPE Instant On integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "instant_on"

PORTAL_BASE_URL: Final = "https://portal.instant-on.hpe.com"
SETTINGS_PATH: Final = "/settings.json"
API_VERSION_HEADER: Final = "x-ion-api-version"
API_VERSION: Final = "7"

CONF_SITE_ID: Final = "site_id"
CONF_SITE_NAME: Final = "site_name"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_TRACK_CLIENTS: Final = "track_clients"
CONF_CLIENT_FILTER: Final = "client_filter"
CONF_ENABLE_NEW_CLIENTS: Final = "enable_new_clients"

CLIENT_FILTER_ALL: Final = "all"
CLIENT_FILTER_NAMED: Final = "named_only"
CLIENT_FILTER_WIRELESS: Final = "wireless_only"
CLIENT_FILTER_WIRED: Final = "wired_only"

DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 30
MAX_SCAN_INTERVAL: Final = 3600

ATTRIBUTION: Final = "Data provided by HPE Networking Instant On cloud portal"
