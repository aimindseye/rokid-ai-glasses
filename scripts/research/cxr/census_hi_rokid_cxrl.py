#!/usr/bin/env python3
"""Verify a private Hi Rokid baseline and census exported CXR-L components.

No APK bytes are emitted. The base APK is extracted only into a temporary
folder for AndroidManifest.xml inspection with aapt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

EXPECTED_BASELINE_ZIP_SHA256 = "b75e7ea3da7c164493c24efdcd411ef70d51c214e82f2b99af7a69ab2cab134e"
EXPECTED_PACKAGE = "com.rokid.sprite.global.aiapp"
EXPECTED_VERSION_CODE = "10110011"
EXPECTED_VERSION_NAME = "G1.11.11.0727"
TARGETS = {
    "activity": "com.rokid.sprite.aiapp.externalapp.auth.AuthorizationActivity",
    "service": "com.rokid.sprite.aiapp.externalapp.service.CXRLinkService",
    "provider": "com.rokid.sprite.aiapp.external.CXRLinkProvider",
}
EXPECTED_ACTIONS = {
    TARGETS["activity"]: "com.rokid.sprite.aiapp.externalapp.AUTHORIZATION",
    TARGETS["service"]: "com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE",
}
EXPECTED_PROVIDER_AUTHORITY = "com.rokid.sprite.global.aiapp.cxrl.provider"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_member(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one {suffix}, found {len(matches)}")
    return matches[0]


def verify_internal_manifest(archive: zipfile.ZipFile, manifest_name: str) -> tuple[int, list[str]]:
    text = archive.read(manifest_name).decode("utf-8", errors="strict")
    root = manifest_name.rsplit("/", 1)[0]
    checked = 0
    failures: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(None, 1)
        relative = relative.lstrip("* ")
        while relative.startswith("./"):
            relative = relative[2:]
        candidates = [relative, f"{root}/{relative}"]
        member = next((item for item in candidates if item in archive.namelist()), "")
        if not member:
            failures.append(f"missing:{relative}")
            continue
        actual = sha256_bytes(archive.read(member))
        checked += 1
        if actual != expected:
            failures.append(f"hash:{relative}:{actual}")
    return checked, failures


def parse_metadata(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def aapt_value(raw: str) -> Any:
    raw = raw.strip()
    quoted = re.search(r'="([^"]*)"', raw)
    if quoted:
        return quoted.group(1)
    raw_value = re.search(r'\(Raw:\s*"([^"]*)"\)', raw)
    if raw_value:
        return raw_value.group(1)
    typed_bool = re.search(r'\(type 0x12\)0x([0-9a-fA-F]+)', raw)
    if typed_bool:
        return int(typed_bool.group(1), 16) != 0
    typed_int = re.search(r'\(type 0x10\)0x([0-9a-fA-F]+)', raw)
    if typed_int:
        return int(typed_int.group(1), 16)
    after = raw.split("=", 1)[1].strip() if "=" in raw else raw
    return after


def parse_aapt_xmltree(text: str) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_indent = -1
    element_stack: list[tuple[int, str]] = []

    for line in text.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while element_stack and element_stack[-1][0] >= indent:
            element_stack.pop()
        if stripped.startswith("E: "):
            element = stripped[3:].split(" ", 1)[0]
            element_stack.append((indent, element))
            if element in {"activity", "activity-alias", "service", "provider"}:
                if current is not None:
                    components.append(current)
                current = {
                    "type": element,
                    "name": "",
                    "exported": None,
                    "permission": "",
                    "authorities": "",
                    "grant_uri_permissions": None,
                    "actions": [],
                }
                current_indent = indent
            elif current is not None and indent <= current_indent:
                components.append(current)
                current = None
                current_indent = -1
            continue
        if current is None or not stripped.startswith("A: "):
            continue
        attribute_match = re.match(r"A:\s+(?:android:)?([A-Za-z0-9_]+)(?:\([^)]*\))?=(.*)$", stripped)
        if not attribute_match:
            continue
        key = attribute_match.group(1)
        value = aapt_value("=" + attribute_match.group(2))
        parent_element = element_stack[-1][1] if element_stack else ""
        if parent_element in {"activity", "activity-alias", "service", "provider"}:
            if key == "name":
                current["name"] = value
            elif key == "exported":
                current["exported"] = value if isinstance(value, bool) else str(value).lower() == "true"
            elif key == "permission":
                current["permission"] = value
            elif key == "authorities":
                current["authorities"] = value
            elif key == "grantUriPermissions":
                current["grant_uri_permissions"] = value if isinstance(value, bool) else str(value).lower() == "true"
        elif parent_element == "action" and key == "name":
            current["actions"].append(value)
    if current is not None:
        components.append(current)
    for component in components:
        component["actions"] = sorted(set(str(value) for value in component["actions"]))
    return components


def normalize_component_name(package: str, name: str) -> str:
    if name.startswith("."):
        return package + name
    if "." not in name:
        return package + "." + name
    return name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-zip", required=True)
    parser.add_argument("--aapt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-sha256", default=EXPECTED_BASELINE_ZIP_SHA256)
    args = parser.parse_args()

    baseline_zip = Path(args.baseline_zip).expanduser().resolve()
    aapt = Path(args.aapt).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not baseline_zip.is_file() or not aapt.is_file():
        raise SystemExit("baseline ZIP and aapt must exist")

    baseline_hash = sha256_path(baseline_zip)
    if baseline_hash != args.expected_baseline_sha256:
        raise SystemExit(f"Hi Rokid baseline ZIP SHA-256 mismatch: {baseline_hash}")
    with zipfile.ZipFile(baseline_zip) as archive:
        names = archive.namelist()
        manifest_name = locate_member(names, "/SHA256SUMS-private.txt")
        metadata_name = locate_member(names, "/baseline-metadata.txt")
        dumpsys_name = locate_member(names, "/dumpsys-package.txt")
        candidates_name = locate_member(names, "/cxr-l-component-candidates.txt")
        base_apk_name = locate_member(names, "/apks/01-base.apk")
        manifest_text = archive.read(manifest_name).decode("utf-8", errors="strict")
        checked, failures = verify_internal_manifest(archive, manifest_name)
        if failures:
            raise SystemExit("private baseline internal hashes failed: " + ", ".join(failures[:8]))
        metadata_text = archive.read(metadata_name).decode("utf-8", errors="strict")
        dumpsys_text = archive.read(dumpsys_name).decode("utf-8", errors="replace")
        candidates_text = archive.read(candidates_name).decode("utf-8", errors="replace")
        metadata = parse_metadata(metadata_text)
        if metadata.get("PACKAGE") != EXPECTED_PACKAGE:
            raise SystemExit("unexpected Hi Rokid package")
        if metadata.get("VERSION_CODE") != EXPECTED_VERSION_CODE:
            raise SystemExit("unexpected Hi Rokid versionCode")
        if metadata.get("VERSION_NAME") != EXPECTED_VERSION_NAME:
            raise SystemExit("unexpected Hi Rokid versionName")
        with tempfile.TemporaryDirectory(prefix="test20-r1-hi-rokid-") as temp_value:
            base_apk = Path(temp_value) / "base.apk"
            base_apk.write_bytes(archive.read(base_apk_name))
            completed = subprocess.run(
                [str(aapt), "dump", "xmltree", str(base_apk), "AndroidManifest.xml"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if completed.returncode != 0:
                raise SystemExit("aapt manifest inspection failed: " + completed.stdout[-1000:])
            aapt_text = completed.stdout

    all_components = parse_aapt_xmltree(aapt_text)
    selected: list[dict[str, Any]] = []
    for component_type, expected_name in TARGETS.items():
        matches = []
        for item in all_components:
            normalized = normalize_component_name(EXPECTED_PACKAGE, str(item.get("name", "")))
            if item.get("type") == component_type and normalized == expected_name:
                copy = dict(item)
                copy["name"] = normalized
                matches.append(copy)
        if len(matches) != 1:
            raise SystemExit(f"expected one manifest {component_type} {expected_name}, found {len(matches)}")
        item = matches[0]
        item["observed_in_dumpsys"] = expected_name in dumpsys_text
        item["observed_in_candidate_summary"] = expected_name in candidates_text
        if expected_name in EXPECTED_ACTIONS:
            expected_action = EXPECTED_ACTIONS[expected_name]
            item["expected_action"] = expected_action
            item["expected_action_present"] = expected_action in item["actions"] and expected_action in dumpsys_text
        if expected_name == TARGETS["provider"]:
            item["expected_authority"] = EXPECTED_PROVIDER_AUTHORITY
            item["expected_authority_present"] = item.get("authorities") == EXPECTED_PROVIDER_AUTHORITY and EXPECTED_PROVIDER_AUTHORITY in dumpsys_text
        selected.append(item)

    if any(item.get("exported") is None for item in selected):
        raise SystemExit("manifest exported attribute unresolved for one or more CXR-L components")
    if not all(item["observed_in_dumpsys"] and item["observed_in_candidate_summary"] for item in selected):
        raise SystemExit("CXR-L component was not corroborated by baseline dumpsys and candidate summary")
    if not all(item.get("expected_action_present", True) for item in selected):
        raise SystemExit("expected CXR-L intent action is missing")
    if not all(item.get("expected_authority_present", True) for item in selected):
        raise SystemExit("expected CXR-L provider authority is missing")

    result = {
        "schema": "rokid.test20.r1.hi-rokid-cxrl-components.private.v1",
        "baseline_zip_sha256": baseline_hash,
        "internal_hash_count": checked,
        "internal_hash_verification": "PASS",
        "package": EXPECTED_PACKAGE,
        "version_code": int(EXPECTED_VERSION_CODE),
        "version_name": EXPECTED_VERSION_NAME,
        "apk_path_count": int(metadata.get("APK_PATH_COUNT", "0")),
        "base_apk_sha256": next(
            line.split()[0] for line in manifest_text.splitlines()
            if line.strip().endswith("apks/01-base.apk")
        ),
        "components": selected,
        "component_count": len(selected),
        "phone_operation": "NONE",
        "artifact_publication_allowed": False,
    }
    output_json = output / "test20-r1-hi-rokid-cxrl-private.json"
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "test20-r1-hi-rokid-aapt-manifest-private.txt").write_text(aapt_text, encoding="utf-8")

    print("TEST20_R1_HI_ROKID_BASELINE_HASHES=PASS")
    print(f"TEST20_R1_HI_ROKID_INTERNAL_HASH_COUNT={checked}")
    print("TEST20_R1_HI_ROKID_PACKAGE_IDENTITY=PASS")
    print("TEST20_R1_HI_ROKID_CXR_L_COMPONENTS=PASS")
    for item in selected:
        key = item["type"].upper().replace("-", "_")
        print(f"TEST20_R1_{key}_EXPORTED={str(item['exported']).upper()}")
        print(f"TEST20_R1_{key}_NAME={item['name']}")
    print(f"TEST20_R1_HI_ROKID_CENSUS={output_json}")
    print("TEST20_R1_HI_ROKID_CENSUS_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
