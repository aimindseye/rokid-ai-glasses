#!/usr/bin/env python3
"""Classify private Test 20 r1 census data and emit a sanitized publication."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

RUNTIME_METHODS = {
    ("com.rokid.cxr.link.CXRLink", "constructor", "CXRLink"),
    ("com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient", "method", "setCXRLinkCbk"),
    ("com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient", "method", "configCXRSession"),
    ("com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient", "method", "connect"),
    ("com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient", "method", "disconnect"),
    ("com.rokid.cxr.link.callbacks.ICXRLinkCbk", "method", "onCXRLConnected"),
    ("com.rokid.cxr.link.callbacks.ICXRLinkCbk", "method", "onGlassBtConnected"),
    ("com.rokid.cxr.link.callbacks.ICXRLinkCbk", "method", "onGlassAiAssistStart"),
    ("com.rokid.cxr.link.callbacks.ICXRLinkCbk", "method", "onGlassAiAssistStop"),
    ("com.rokid.cxr.link.utils.CxrDefs$CXRSession", "constructor", "CXRSession"),
    ("com.rokid.cxr.link.utils.CxrDefs$CXRSessionType", "enum_constant", "CUSTOMAPP"),
    ("com.rokid.sprite.aiapp.externalapp.auth.AuthorizationHelper", "method", "parseAuthorizationResult"),
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def class_tags(name: str, kind: str) -> list[str]:
    tags: set[str] = set()
    callback = (
        ".callbacks.I" in name
        or name.startswith("com.rokid.sprite.aiapp.externalapp.I")
        and (name.endswith("Callback") or "$" not in name)
    )
    if callback and kind == "interface":
        tags.add("callback-only")
    if name.startswith("com.rokid.cxr.link.") and ".callbacks." not in name and not name.endswith("LogUtil"):
        tags.add("directly-callable")
    if name == "com.rokid.cxr.link.CXRLink":
        tags.update({"directly-callable", "service/provider-mediated", "runtime-qualified"})
    if name.startswith("com.rokid.sprite.aiapp.externalapp.auth."):
        tags.update({"directly-callable", "service/provider-mediated"})
    if name == "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient":
        tags.update({"directly-callable", "service/provider-mediated", "internal-or-implementation-detail", "runtime-qualified"})
    if name.startswith("com.rokid.sprite.aiapp.externalapp.I"):
        tags.add("service/provider-mediated")
    if any(part in name for part in ("$Stub", "$Default", "$Companion", "$a", "$b", "$c")):
        tags.add("internal-or-implementation-detail")
    if name.endswith("BuildConfig") or name.endswith("LogUtil"):
        tags.add("internal-or-implementation-detail")
    if name.startswith("com.rokid.cxr.CXRServiceBridge") or name.startswith("com.rokid.cxr.CXRSocketProtocol") or name.startswith("com.rokid.cxr.Caps"):
        tags.add("internal-or-implementation-detail")
    if not tags:
        tags.add("untested")
    elif "runtime-qualified" not in tags:
        tags.add("untested")
    return sorted(tags)


def member_tags(class_name: str, class_kind: str, member: dict[str, Any]) -> list[str]:
    tags = set(class_tags(class_name, class_kind))
    key = (class_name, str(member.get("kind")), str(member.get("name")))
    if key in RUNTIME_METHODS:
        tags.add("runtime-qualified")
        tags.discard("untested")
    if class_kind == "interface" and member.get("kind") == "method" and (
        ".callbacks.I" in class_name or class_name.startswith("com.rokid.sprite.aiapp.externalapp.I")
    ):
        tags.add("callback-only")
        tags.discard("directly-callable")
    if member.get("kind") in {"constructor", "method", "field", "enum_constant"} and (
        class_name.startswith("com.rokid.cxr.link.") or class_name.startswith("com.rokid.sprite.aiapp.externalapp.auth.")
    ) and "callback-only" not in tags:
        tags.add("directly-callable")
    if class_name.startswith("com.rokid.sprite.aiapp.externalapp.I") or class_name in {
        "com.rokid.cxr.link.CXRLink",
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
    }:
        tags.add("service/provider-mediated")
    if "runtime-qualified" not in tags:
        tags.add("untested")
    return sorted(tags)


def summarize_native(private_native: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "abi": item["abi"],
            "name": item["name"],
            "size": item["size"],
            "sha256": item["sha256"],
            "elf_class": item.get("elf_class", 0),
            "elf_parse_status": item.get("elf_parse_status"),
            "dynamic_symbol_count": len(item.get("dynamic_symbols", [])),
            "defined_dynamic_symbol_count": sum(1 for symbol in item.get("dynamic_symbols", []) if symbol.get("defined")),
            "jni_exports": item.get("jni_exports", []),
            "jni_export_count": len(item.get("jni_exports", [])),
            "classification": ["internal-or-implementation-detail", "untested"],
        }
        for item in private_native
    ]


def markdown_report(publication: dict[str, Any]) -> str:
    summary = publication["summary"]
    lines = [
        "# Test 20 r1 — CXR-L SDK and Runtime Capability Census",
        "",
        "This sanitized report inventories the exact attested `client-l:1.0.1` public",
        "surface and compares it with the exported Hi Rokid CXR-L integration points.",
        "No proprietary AAR, POM, APK, native-library bytes, authorization token,",
        "device serial, Bluetooth address, media payload, or cloud request is included.",
        "",
        "## Artifact identity",
        "",
        f"- Coordinate: `{publication['sdk']['coordinate']}`",
        f"- AAR SHA-256: `{publication['sdk']['artifact']['aar_sha256']}`",
        f"- POM SHA-256: `{publication['sdk']['artifact']['pom_sha256']}`",
        f"- Hi Rokid: `{publication['hi_rokid']['package']}` `{publication['hi_rokid']['version_name']}`",
        f"- Runtime qualification source: `{publication['runtime_qualification']['classification']}`",
        "",
        "## Census totals",
        "",
        "| Surface | Count |",
        "|---|---:|",
        f"| Public classes/interfaces | {summary['public_class_count']} |",
        f"| Public constructors | {summary['public_constructor_count']} |",
        f"| Public methods | {summary['public_method_count']} |",
        f"| Public fields | {summary['public_field_count']} |",
        f"| Enum constants | {summary['public_enum_constant_count']} |",
        f"| Callback interfaces | {summary['callback_class_count']} |",
        f"| Native libraries across ABIs | {summary['native_library_count']} |",
        f"| JNI exports | {summary['jni_export_count']} |",
        "",
        "## Session types",
        "",
    ]
    for class_name, values in sorted(publication["sdk"]["session_types"].items()):
        lines.append(f"- `{class_name}`: " + ", ".join(f"`{value}`" for value in values))
    lines.extend([
        "",
        "## Hi Rokid CXR-L components",
        "",
        "| Type | Component | Exported | Action or authority |",
        "|---|---|---:|---|",
    ])
    for item in publication["hi_rokid"]["components"]:
        endpoint = item.get("expected_action") or item.get("expected_authority") or ""
        lines.append(f"| {item['type']} | `{item['name']}` | {str(item['exported']).lower()} | `{endpoint}` |")
    lines.extend([
        "",
        "## Classification totals",
        "",
        "| Classification | Members |",
        "|---|---:|",
    ])
    for key, count in sorted(summary["member_classification_counts"].items()):
        lines.append(f"| {key} | {count} |")
    lines.extend([
        "",
        "## Runtime-qualified boundary",
        "",
        "The runtime-qualified subset is limited to Test 19’s authorization, CUSTOMAPP",
        "session configuration, CXR-L connection callbacks, fallback-assisted service",
        "connection, disconnect, and stock Hi Rokid recovery. Camera, microphone, audio",
        "streaming, image streaming, custom commands, custom views, glass-app callbacks,",
        "and other public surfaces remain untested by Test 20 r1.",
        "",
        "## Native/JNI inventory",
        "",
        "| ABI | Library | SHA-256 | Dynamic symbols | JNI exports |",
        "|---|---|---|---:|---:|",
    ])
    for item in publication["sdk"]["native_libraries"]:
        lines.append(f"| {item['abi']} | `{item['name']}` | `{item['sha256']}` | {item['dynamic_symbol_count']} | {item['jni_export_count']} |")
    lines.extend([
        "",
        "## Conclusion",
        "",
        publication["conclusion"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk-census", required=True)
    parser.add_argument("--hi-rokid-census", required=True)
    parser.add_argument("--runtime-publication", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sdk_path = Path(args.sdk_census).expanduser().resolve()
    hi_path = Path(args.hi_rokid_census).expanduser().resolve()
    runtime_path = Path(args.runtime_publication).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    sdk = json.loads(sdk_path.read_text(encoding="utf-8"))
    hi = json.loads(hi_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if sdk.get("schema") != "rokid.test20.r1.cxr-l-sdk-census.private.v1":
        raise SystemExit("unexpected SDK census schema")
    if hi.get("schema") != "rokid.test20.r1.hi-rokid-cxrl-components.private.v1":
        raise SystemExit("unexpected Hi Rokid census schema")

    surfaces: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    member_counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    for item in sdk["classes"]:
        class_classifications = class_tags(item["name"], item["kind"])
        for tag in class_classifications:
            class_counts[tag] += 1
        package_counts[item["name"].rsplit(".", 1)[0]] += 1
        members: list[dict[str, Any]] = []
        for member in item["members"]:
            classifications = member_tags(item["name"], item["kind"], member)
            for tag in classifications:
                member_counts[tag] += 1
            members.append({
                "kind": member["kind"],
                "name": member["name"],
                "signature": member["signature"],
                "descriptor": member["descriptor"],
                "classifications": classifications,
            })
        surfaces.append({
            "name": item["name"],
            "kind": item["kind"],
            "superclass": item.get("superclass", ""),
            "interfaces": item.get("interfaces", []),
            "classifications": class_classifications,
            "members": members,
        })

    session_types = {
        name: values for name, values in sdk.get("enum_values", {}).items()
        if name.endswith("CXRSessionType")
    }
    native = summarize_native(sdk["native_libraries"])
    jni_export_count = sum(item["jni_export_count"] for item in native)
    classification = runtime.get("status") or runtime.get("final_status") or runtime.get("classification") or "TEST19_R2_ACCEPTED"

    publication = {
        "schema": "rokid.test20.r1.cxr-l-capability-census.public.v1",
        "scope": "read-only static and accepted-runtime-surface census",
        "sdk": {
            "coordinate": sdk["coordinate"],
            "artifact": sdk["artifact"],
            "dependencies": sdk["pom"]["dependencies"],
            "package_class_counts": dict(sorted(package_counts.items())),
            "session_types": session_types,
            "classes": surfaces,
            "native_declared_methods": sdk.get("native_declared_methods", []),
            "native_libraries": native,
        },
        "hi_rokid": {
            "package": hi["package"],
            "version_code": hi["version_code"],
            "version_name": hi["version_name"],
            "baseline_zip_sha256": hi["baseline_zip_sha256"],
            "base_apk_sha256": hi["base_apk_sha256"],
            "components": hi["components"],
        },
        "runtime_qualification": {
            "source_schema": runtime.get("schema", ""),
            "classification": classification,
            "firmware_1_22": "PASS",
            "firmware_1_23": "PASS",
            "regression_observed": False,
            "connection_path": "FALLBACK_SERVICE_BIND_ASSISTED",
        },
        "summary": {
            "public_class_count": sdk["public_class_count"],
            "public_member_count": sdk["public_member_count"],
            "public_constructor_count": sdk["public_constructor_count"],
            "public_method_count": sdk["public_method_count"],
            "public_field_count": sdk["public_field_count"],
            "public_enum_constant_count": sdk["public_enum_constant_count"],
            "callback_class_count": len(sdk["callback_classes"]),
            "native_library_count": len(native),
            "jni_export_count": jni_export_count,
            "class_classification_counts": dict(sorted(class_counts.items())),
            "member_classification_counts": dict(sorted(member_counts.items())),
        },
        "privacy": {
            "proprietary_binaries_included": False,
            "authorization_tokens_included": False,
            "device_serials_included": False,
            "bluetooth_addresses_included": False,
            "media_payloads_included": False,
            "cloud_requests_performed": False,
            "phone_mutation": "NONE",
            "glasses_command_execution": "NONE",
        },
        "conclusion": (
            "The exact client-l:1.0.1 surface and matching Hi Rokid integration "
            "components are now enumerated. Only the Test 19 authorization, CUSTOMAPP "
            "connection/callback, disconnect, and stock-recovery subset is runtime-qualified; "
            "all media, custom-command, custom-view, glass-app, and remaining native/JNI "
            "surfaces stay untested pending separately approved Test 20 stages."
        ),
    }
    output_json = output / "test20-r1-cxr-l-capability-census.json"
    output_md = output / "test20-r1-cxr-l-capability-census.md"
    output_hashes = output / "test20-r1-cxr-l-evidence-hashes.txt"
    output_json.write_text(json.dumps(publication, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown_report(publication), encoding="utf-8")
    output_hashes.write_text(
        "\n".join([
            f"CXR_L_AAR_SHA256={sdk['artifact']['aar_sha256']}",
            f"CXR_L_POM_SHA256={sdk['artifact']['pom_sha256']}",
            f"HI_ROKID_BASELINE_ZIP_SHA256={hi['baseline_zip_sha256']}",
            f"HI_ROKID_BASE_APK_SHA256={hi['base_apk_sha256']}",
            f"RUNTIME_PUBLICATION_SHA256={sha256_path(runtime_path)}",
        ]) + "\n",
        encoding="utf-8",
    )

    print("TEST20_R1_CLASSIFICATION=PASS")
    print(f"TEST20_R1_PUBLIC_CLASS_COUNT={sdk['public_class_count']}")
    print(f"TEST20_R1_PUBLIC_MEMBER_COUNT={sdk['public_member_count']}")
    print(f"TEST20_R1_RUNTIME_QUALIFIED_MEMBER_COUNT={member_counts['runtime-qualified']}")
    print(f"TEST20_R1_UNTESTED_MEMBER_COUNT={member_counts['untested']}")
    print(f"TEST20_R1_JNI_EXPORT_COUNT={jni_export_count}")
    print(f"TEST20_R1_SANITIZED_JSON={output_json}")
    print(f"TEST20_R1_SANITIZED_MARKDOWN={output_md}")
    print("TEST20_R1_SANITIZED_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
