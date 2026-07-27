#!/usr/bin/env python3
"""Classify Android Bluetooth HCI snoop readiness without mutating the device.

Current AOSP uses the global setting bluetooth_btsnoop_default_mode and the
Bluetooth service's applied snoop state. Legacy secure/property keys are only
supplemental. When all readable controls are hidden or unset, readiness is
PROVISIONAL_UNKNOWN and the post-bugreport btsnoop evidence gate is authoritative.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

FULL = {"1", "true", "on", "enabled", "full"}
FILTERED = {"filtered", "filter"}
DISABLED = {"0", "false", "off", "disabled"}
UNKNOWN = {"", "null", "none", "unset", "unknown", "empty", "permission denied"}


def norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def mode(value: Any) -> str:
    value = norm(value)
    if value in FULL:
        return "full"
    if value in FILTERED:
        return "filtered"
    if value in DISABLED:
        return "disabled"
    if value in UNKNOWN or "permission denied" in value:
        return "unknown"
    return "other"


def parse_dumpsys(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for key, label in (
        ("service_active_mode", "mSnoopLogSettingAtEnable"),
        ("service_default_mode", "mDefaultSnoopLogSettingAtEnable"),
    ):
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*=\s*([^\r\n]+)", text or "")
        result[key] = match.group(1).strip() if match else ""
    return result


def classify(probes: Dict[str, Any]) -> Dict[str, Any]:
    service = parse_dumpsys(str(probes.get("dumpsys_bluetooth", "")))
    values = {
        "service_active_mode": service["service_active_mode"],
        "service_default_mode": service["service_default_mode"],
        "property_active_mode": probes.get("persist_btsnooplogmode", ""),
        "global_default_mode": probes.get("global_btsnoop_default_mode", ""),
        "property_default_mode": probes.get("persist_btsnoopdefaultmode", ""),
        "legacy_secure_toggle": probes.get("secure_bluetooth_hci_log", ""),
        "legacy_enable_property": probes.get("persist_btsnoopenable", ""),
    }
    modes = {key: mode(value) for key, value in values.items()}
    active_keys = ("service_active_mode", "property_active_mode")
    configured_keys = ("service_default_mode", "global_default_mode", "property_default_mode")
    legacy_keys = ("legacy_secure_toggle", "legacy_enable_property")

    def keys_with(wanted: str, keys: Iterable[str]) -> List[str]:
        return [key for key in keys if modes[key] == wanted]

    active_full = keys_with("full", active_keys)
    active_filtered = keys_with("filtered", active_keys)
    active_disabled = keys_with("disabled", active_keys)
    config_full = keys_with("full", configured_keys)
    config_filtered = keys_with("filtered", configured_keys)
    config_disabled = keys_with("disabled", configured_keys)
    legacy_full = keys_with("full", legacy_keys)
    legacy_disabled = keys_with("disabled", legacy_keys)

    if active_full:
        status, method, allowed = "CONFIRMED_FULL", "+".join(active_full), True
    elif active_filtered:
        status, method, allowed = "CONFIRMED_FILTERED", "+".join(active_filtered), False
    elif active_disabled:
        if config_full:
            status, method, allowed = "RESTART_REQUIRED", "+".join(active_disabled + config_full), False
        else:
            status, method, allowed = "CONFIRMED_DISABLED", "+".join(active_disabled), False
    elif config_full:
        status, method, allowed = "CONFIRMED_FULL_CONFIGURED", "+".join(config_full), True
    elif config_filtered:
        status, method, allowed = "CONFIRMED_FILTERED", "+".join(config_filtered), False
    elif config_disabled and not legacy_full:
        status, method, allowed = "CONFIRMED_DISABLED", "+".join(config_disabled), False
    elif legacy_full:
        status, method, allowed = "CONFIRMED_FULL_LEGACY", "+".join(legacy_full), True
    elif legacy_disabled and all(modes[k] == "unknown" for k in (*active_keys, *configured_keys)):
        status, method, allowed = "CONFIRMED_DISABLED_LEGACY", "+".join(legacy_disabled), False
    else:
        status, method, allowed = "PROVISIONAL_UNKNOWN", "post_bugreport_btsnoop_required", True

    return {
        "schema": "rokid.r25.2.3.2.hci-preflight.v1",
        "status": status,
        "method": method,
        "capture_allowed": allowed,
        "post_bugreport_required": True,
        "raw_values": values,
        "normalized_modes": modes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    probes = json.loads(args.input.read_text(encoding="utf-8"))
    result = classify(probes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"R25_2_3_2_HCI_PREFLIGHT_STATUS={result['status']}")
    print(f"R25_2_3_2_HCI_PREFLIGHT_METHOD={result['method']}")
    print(f"R25_2_3_2_HCI_CAPTURE_ALLOWED={'YES' if result['capture_allowed'] else 'NO'}")
    return 0 if result["capture_allowed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
