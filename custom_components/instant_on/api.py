"""Asynchronous read-only client for the HPE Networking Instant On cloud API."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp

from .const import API_VERSION, API_VERSION_HEADER, PORTAL_BASE_URL, SETTINGS_PATH

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=25)
USER_AGENT = "Mozilla/5.0 (HomeAssistant-InstantOn/0.1.0)"


class InstantOnError(Exception):
    """Base exception for Instant On API errors."""


class InstantOnConnectionError(InstantOnError):
    """Raised when communication with the Instant On portal fails."""


class InstantOnAuthError(InstantOnError):
    """Raised when authentication fails or MFA blocks automated login."""


class InstantOnRateLimitError(InstantOnError):
    """Raised when the portal responds with HTTP 429."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(slots=True)
class PortalSettings:
    """Dynamic portal endpoints discovered from settings.json."""

    rest_api_url: str
    sso_fqdn: str
    sso_client_id: str
    sso_redirect_url: str
    portal_build: str | None = None


class InstantOnApiClient:
    """Read-only async client for HPE Networking Instant On."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._settings: PortalSettings | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0.0
        self._auth_lock = asyncio.Lock()

    async def _fetch_settings(self) -> PortalSettings:
        """Fetch portal settings.json dynamically."""
        url = f"{PORTAL_BASE_URL}{SETTINGS_PATH}"
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    raise InstantOnConnectionError(
                        f"Failed to fetch portal settings (HTTP {resp.status})"
                    )
                portal_build = resp.headers.get("Last-Modified") or resp.headers.get(
                    "ETag"
                )
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InstantOnConnectionError(
                f"Error fetching portal settings: {err}"
            ) from err

        try:
            return PortalSettings(
                rest_api_url=data["restApiUrl"].rstrip("/"),
                sso_fqdn=data["ssoFqdn"].rstrip("/"),
                sso_client_id=data["ssoClientIdAuthZ"],
                sso_redirect_url=data["ssoRedirectUrl"],
                portal_build=portal_build,
            )
        except KeyError as err:
            raise InstantOnConnectionError(
                f"Portal settings.json missing expected key: {err}"
            ) from err

    async def _ensure_settings(self) -> PortalSettings:
        if self._settings is None:
            self._settings = await self._fetch_settings()
        return self._settings

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    async def _login_pkce(self) -> None:
        """Authenticate using OAuth2 Authorization Code + PKCE."""
        settings = await self._ensure_settings()
        verifier, challenge = self._generate_pkce()

        # Step 1: Validate credentials against SSO MFA endpoint
        mfa_url = f"{settings.sso_fqdn}/aio/api/v1/mfa/validate/full"
        try:
            async with self._session.post(
                mfa_url,
                data={"username": self._username, "password": self._password},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise InstantOnAuthError("Invalid username or password")
                if resp.status == 429:
                    retry = _parse_retry_after(resp.headers.get("Retry-After"))
                    raise InstantOnRateLimitError("Rate limited during SSO login", retry)
                if resp.status != 200:
                    raise InstantOnConnectionError(
                        f"SSO login failed with HTTP {resp.status}"
                    )
                mfa_data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InstantOnConnectionError(f"SSO connection error: {err}") from err

        if mfa_data.get("success") is False:
            raise InstantOnAuthError("Authentication rejected by SSO")

        session_token = (
            mfa_data.get("sessionToken")
            or mfa_data.get("access_token")
            or mfa_data.get("token")
        )
        if not session_token:
            raise InstantOnAuthError(
                "SSO did not return a session token (MFA may be enabled on this account)"
            )

        # Step 2: Authorization request without following redirect
        auth_url = f"{settings.sso_fqdn}/as/authorization.oauth2"
        auth_params = {
            "client_id": settings.sso_client_id,
            "redirect_uri": settings.sso_redirect_url,
            "response_type": "code",
            "scope": "profile openid",
            "state": secrets.token_urlsafe(16),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "sessionToken": session_token,
        }
        try:
            async with self._session.get(
                auth_url,
                params=auth_params,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                location = resp.headers.get("Location")
                if not location:
                    raise InstantOnAuthError(
                        f"Authorization redirect missing Location header (HTTP {resp.status})"
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InstantOnConnectionError(
                f"Authorization request failed: {err}"
            ) from err

        query = parse_qs(urlparse(location).query)
        codes = query.get("code")
        if not codes:
            raise InstantOnAuthError("Authorization redirect did not include an auth code")

        # Step 3: Exchange authorization code for bearer & refresh tokens
        await self._exchange_token(
            settings,
            {
                "grant_type": "authorization_code",
                "client_id": settings.sso_client_id,
                "code": codes[0],
                "redirect_uri": settings.sso_redirect_url,
                "code_verifier": verifier,
            },
        )

    async def _refresh_access_token(self) -> bool:
        """Attempt to refresh the bearer token using refresh_token."""
        if not self._refresh_token:
            return False
        settings = await self._ensure_settings()
        try:
            await self._exchange_token(
                settings,
                {
                    "grant_type": "refresh_token",
                    "client_id": settings.sso_client_id,
                    "refresh_token": self._refresh_token,
                },
            )
            return True
        except InstantOnAuthError:
            self._refresh_token = None
            return False

    async def _exchange_token(
        self, settings: PortalSettings, payload: dict[str, str]
    ) -> None:
        token_url = f"{settings.sso_fqdn}/as/token.oauth2"
        try:
            async with self._session.post(
                token_url,
                data=payload,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise InstantOnAuthError(
                        f"Token exchange rejected (HTTP {resp.status})"
                    )
                if resp.status == 429:
                    retry = _parse_retry_after(resp.headers.get("Retry-After"))
                    raise InstantOnRateLimitError("Rate limited during token exchange", retry)
                if resp.status != 200:
                    raise InstantOnConnectionError(
                        f"Token exchange failed with HTTP {resp.status}"
                    )
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InstantOnConnectionError(f"Token exchange error: {err}") from err

        access_token = data.get("access_token")
        if not access_token:
            raise InstantOnAuthError("Token response did not contain access_token")

        self._access_token = access_token
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]
        expires_in = float(data.get("expires_in", 1800))
        self._token_expires_at = time.monotonic() + max(60.0, expires_in - 60.0)

    async def _ensure_token(self, force_refresh: bool = False) -> str:
        async with self._auth_lock:
            now = time.monotonic()
            if not force_refresh and self._access_token and now < self._token_expires_at:
                return self._access_token

            if self._refresh_token and await self._refresh_access_token():
                assert self._access_token is not None
                return self._access_token

            await self._login_pkce()
            assert self._access_token is not None
            return self._access_token

    async def async_authenticate(self) -> None:
        """Validate credentials by obtaining a fresh token."""
        await self._ensure_token(force_refresh=True)

    async def _get_json(self, path: str) -> Any:
        """Perform an authenticated GET request against the portal REST API."""
        settings = await self._ensure_settings()
        url = f"{settings.rest_api_url}{path}"

        for attempt in range(2):
            token = await self._ensure_token(force_refresh=(attempt == 1))
            headers = {
                "Authorization": f"Bearer {token}",
                API_VERSION_HEADER: API_VERSION,
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            }
            try:
                async with self._session.get(
                    url, headers=headers, timeout=REQUEST_TIMEOUT
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        _LOGGER.debug("Instant On token expired on %s, refreshing", path)
                        continue
                    if resp.status == 401:
                        raise InstantOnAuthError("Unauthorized after token refresh")
                    if resp.status == 403:
                        raise InstantOnAuthError(f"Forbidden accessing {path}")
                    if resp.status == 429:
                        retry = _parse_retry_after(resp.headers.get("Retry-After"))
                        raise InstantOnRateLimitError(
                            f"Rate limited on {path}", retry_after=retry
                        )
                    if resp.status != 200:
                        raise InstantOnConnectionError(
                            f"GET {path} failed with HTTP {resp.status}"
                        )
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise InstantOnConnectionError(
                    f"Connection error on {path}: {err}"
                ) from err

        raise InstantOnAuthError("Authentication failed after retry")

    async def _get_optional_json(self, path: str) -> Any | None:
        """Fetch an optional endpoint; log and return None on non-auth errors."""
        try:
            return await self._get_json(path)
        except InstantOnAuthError:
            raise
        except InstantOnRateLimitError:
            raise
        except InstantOnError as err:
            _LOGGER.debug("Optional endpoint %s unavailable: %s", path, err)
            return None

    async def async_get_sites(self) -> list[dict[str, Any]]:
        """Return the list of Instant On sites accessible to the account."""
        data = await self._get_json("/api/sites/")
        return list(data.get("elements", []))

    async def async_get_site_snapshot(self, site_id: str) -> dict[str, Any]:
        """Fetch a complete read-only snapshot for a single Instant On site."""
        sites_task = self.async_get_sites()
        landing_task = self._get_json(f"/api/sites/{site_id}/landingPage")
        inventory_task = self._get_json(f"/api/sites/{site_id}/inventory")
        clients_task = self._get_json(f"/api/sites/{site_id}/clientSummary")
        networks_task = self._get_json(f"/api/sites/{site_id}/networksSummary")
        wired_task = self._get_optional_json(f"/api/sites/{site_id}/wiredNetworks")
        alerts_task = self._get_optional_json(f"/api/sites/{site_id}/alerts")
        app_usage_task = self._get_optional_json(
            f"/api/sites/{site_id}/applicationCategoryUsage"
        )
        topology_task = self._get_optional_json(f"/api/sites/{site_id}/topology")

        (
            sites,
            landing,
            inventory,
            clients,
            networks,
            wired_networks,
            alerts,
            app_usage,
            topology,
        ) = await asyncio.gather(
            sites_task,
            landing_task,
            inventory_task,
            clients_task,
            networks_task,
            wired_task,
            alerts_task,
            app_usage_task,
            topology_task,
        )

        site_info = next((s for s in sites if s.get("id") == site_id), {})
        return {
            "site": site_info,
            "landing_page": landing or {},
            "inventory": list((inventory or {}).get("elements", [])),
            "clients": list((clients or {}).get("elements", [])),
            "networks": list((networks or {}).get("elements", [])),
            "wired_networks": list((wired_networks or {}).get("elements", [])),
            "alerts": list((alerts or {}).get("elements", [])),
            "app_usage": list((app_usage or {}).get("elements", [])),
            "topology": topology or {},
            "portal_build": self._settings.portal_build if self._settings else None,
        }


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(1.0, float(value))
    except ValueError:
        return None
