"""Unit tests for the HPE Instant On SKU/model catalog."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_COMP_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "instant_on"

if "custom_components.instant_on.models" not in sys.modules:
    sys.modules.setdefault("custom_components", ModuleType("custom_components"))
    _pkg = sys.modules.setdefault(
        "custom_components.instant_on", ModuleType("custom_components.instant_on")
    )
    _pkg.__path__ = [str(_COMP_DIR)]
    _spec = importlib.util.spec_from_file_location(
        "custom_components.instant_on.models",
        _COMP_DIR / "models.py",
    )
    assert _spec and _spec.loader
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["custom_components.instant_on.models"] = _mod
    _spec.loader.exec_module(_mod)

from custom_components.instant_on.models import resolve_device_model  # noqa: E402


def test_resolve_known_aps() -> None:
    """Known AP SKUs map to Instant On marketing names and preserve model_id."""
    assert resolve_device_model("R4W02A", "AP-505", "accessPoint") == (
        "AP22",
        "AP-505 / R4W02A",
    )
    assert resolve_device_model("R9B28A", "AP-515", "accessPoint") == (
        "AP25",
        "AP-515 / R9B28A",
    )
    assert resolve_device_model("S1T37A", "AP-565", "accessPoint") == (
        "AP27",
        "AP-565 / S1T37A",
    )


def test_resolve_known_switch_dedup_sku() -> None:
    """Switch SKU identical to hw_model deduplicates model_id."""
    assert resolve_device_model("JL813A", "JL813A", "switch") == (
        "1830 24G 12p Class4 PoE 2SFP 195W",
        "JL813A",
    )


def test_resolve_fallback_hw_model_and_unknown() -> None:
    """Unknown regional SKU falls back to hw_model; unknown devices pass through."""
    assert resolve_device_model("R4W99Z", "AP-505", "accessPoint") == (
        "AP22",
        "AP-505 / R4W99Z",
    )
    assert resolve_device_model("UNKNOWN1", "NEW-HW", "switch") == ("NEW-HW", None)
