"""Unit tests for the HPE Instant On async API client."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# Load api.py and const.py without importing homeassistant
_COMP_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "instant_on"

_pkg = ModuleType("custom_components.instant_on")
_pkg.__path__ = [str(_COMP_DIR)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.instant_on"] = _pkg

for _mod_name in ("const", "api"):
    _spec = importlib.util.spec_from_file_location(
        f"custom_components.instant_on.{_mod_name}",
        _COMP_DIR / f"{_mod_name}.py",
    )
    assert _spec and _spec.loader
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"custom_components.instant_on.{_mod_name}"] = _mod
    _spec.loader.exec_module(_mod)

from custom_components.instant_on.api import (  # noqa: E402
    InstantOnApiClient,
    InstantOnAuthError,
    InstantOnRateLimitError,
    _parse_retry_after,
)


def _mock_response(status: int, json_data=None, headers=None):
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.json = AsyncMock(return_value=json_data)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def test_pkce_generation() -> None:
    """PKCE challenge must match base64url(sha256(verifier)) without padding."""
    verifier, challenge = InstantOnApiClient._generate_pkce()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert challenge == expected
    assert "=" not in challenge


def test_parse_retry_after() -> None:
    """Retry-After header parsing handles valid, small, and invalid values."""
    assert _parse_retry_after("30") == 30.0
    assert _parse_retry_after("0") == 1.0
    assert _parse_retry_after("invalid") is None
    assert _parse_retry_after(None) is None


@pytest.mark.asyncio
async def test_login_and_get_sites() -> None:
    """Full PKCE login flow and sites retrieval."""
    session = MagicMock()
    session.get = MagicMock(
        side_effect=[
            _mock_response(
                200,
                {
                    "restApiUrl": "https://portal.instant-on.hpe.com",
                    "ssoFqdn": "https://sso.arubainstanton.com",
                    "ssoClientIdAuthZ": "client-123",
                    "ssoRedirectUrl": "https://portal.instant-on.hpe.com",
                },
            ),
            _mock_response(
                302,
                headers={
                    "Location": "https://portal.instant-on.hpe.com?code=auth-code-1&state=xyz"
                },
            ),
            _mock_response(
                200,
                {"elements": [{"id": "site-1", "name": "Home"}]},
            ),
        ]
    )
    session.post = MagicMock(
        side_effect=[
            _mock_response(200, {"access_token": "sess-tok", "success": True}),
            _mock_response(
                200,
                {
                    "access_token": "bearer-123",
                    "refresh_token": "refresh-123",
                    "expires_in": 1800,
                },
            ),
        ]
    )

    client = InstantOnApiClient(session, "user@example.com", "secret")
    sites = await client.async_get_sites()
    assert sites == [{"id": "site-1", "name": "Home"}]


@pytest.mark.asyncio
async def test_invalid_credentials_raises_auth_error() -> None:
    """HTTP 401 from SSO raises InstantOnAuthError."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_mock_response(
            200,
            {
                "restApiUrl": "https://portal.instant-on.hpe.com",
                "ssoFqdn": "https://sso.arubainstanton.com",
                "ssoClientIdAuthZ": "client-123",
                "ssoRedirectUrl": "https://portal.instant-on.hpe.com",
            },
        )
    )
    session.post = MagicMock(return_value=_mock_response(401, {}))

    client = InstantOnApiClient(session, "bad@example.com", "wrong")
    with pytest.raises(InstantOnAuthError):
        await client.async_authenticate()


@pytest.mark.asyncio
async def test_rate_limit_raises_with_retry_after() -> None:
    """HTTP 429 propagates Retry-After into InstantOnRateLimitError."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_mock_response(
            200,
            {
                "restApiUrl": "https://portal.instant-on.hpe.com",
                "ssoFqdn": "https://sso.arubainstanton.com",
                "ssoClientIdAuthZ": "client-123",
                "ssoRedirectUrl": "https://portal.instant-on.hpe.com",
            },
        )
    )
    session.post = MagicMock(
        return_value=_mock_response(429, {}, headers={"Retry-After": "45"})
    )

    client = InstantOnApiClient(session, "user@example.com", "secret")
    with pytest.raises(InstantOnRateLimitError) as exc_info:
        await client.async_authenticate()
    assert exc_info.value.retry_after == 45.0
