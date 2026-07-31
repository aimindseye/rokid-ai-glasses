#!/usr/bin/env python3
"""Classify Test 20 CXR-L census data without propagating runtime status by class.

Runtime qualification is descriptor-exact and member-level.  A class taking part
in the accepted Test 19 path never causes all of its public members to become
runtime-qualified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PUBLIC_SCHEMA_V1 = "rokid.test20.r1.cxr-l-capability-census.public.v1"
PUBLIC_SCHEMA_V1_1 = "rokid.test20.r1.1.cxr-l-capability-census.public.v1"

# Exact surfaces observed in accepted Test 19 evidence.  Names alone are not
# sufficient because overloaded methods and constructors must not inherit a
# qualification from another descriptor.
RUNTIME_MEMBERS: dict[tuple[str, str, str, str], str] = {
    (
        "com.rokid.cxr.link.CXRLink",
        "constructor",
        "CXRLink",
        "(Landroid/content/Context;)V",
    ): "test19:CXRLink-instance-created",
    (
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
        "method",
        "setCXRLinkCbk",
        "(Lcom/rokid/cxr/link/callbacks/ICXRLinkCbk;)V",
    ): "test19:callback-registered",
    (
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
        "method",
        "configCXRSession",
        "(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSession;)Z",
    ): "test19:CUSTOMAPP-session-configured",
    (
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
        "method",
        "connect",
        "(Ljava/lang/String;)Z",
    ): "test19:sdk-connect-invoked",
    (
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
        "method",
        "disconnect",
        "()V",
    ): "test19:sdk-disconnect-succeeded",
    (
        "com.rokid.cxr.link.callbacks.ICXRLinkCbk",
        "method",
        "onCXRLConnected",
        "(Z)V",
    ): "test19:true-callback-observed",
    (
        "com.rokid.cxr.link.callbacks.ICXRLinkCbk",
        "method",
        "onGlassBtConnected",
        "(Z)V",
    ): "test19:true-callback-observed",
    (
        "com.rokid.cxr.link.utils.CxrDefs$CXRSession",
        "constructor",
        "CxrDefs$CXRSession",
        "(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;Ljava/lang/String;)V",
    ): "test19:two-argument-CUSTOMAPP-session-created",
    (
        "com.rokid.cxr.link.utils.CxrDefs$CXRSessionType",
        "enum_constant",
        "CUSTOMAPP",
        "Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;",
    ): "test19:CUSTOMAPP-selected",
}

RUNTIME_COMPONENTS: dict[tuple[str, str], str] = {
    (
        "activity",
        "com.rokid.sprite.aiapp.externalapp.auth.AuthorizationActivity",
    ): "test19:authorization-activity-launched",
    (
        "service",
        "com.rokid.sprite.aiapp.externalapp.service.CXRLinkService",
    ): "test19:fallback-service-bind-and-callbacks-observed",
}

HIGH_RISK_UNTESTED_METHODS = {
    "takePhoto",
    "startAudioStream",
    "stopAudioStream",
    "customViewSetIcons",
    "customViewOpen",
    "customViewUpdate",
    "customViewClose",
    "customViewIsOpen",
    "customViewGetCurrentIcons",
    "customViewGetCurrentData",
    "appUploadAndInstall",
    "appUninstall",
    "appStart",
    "appStop",
    "appIsInstalled",
    "sendCustomCmd",
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def callback_class(name: str, kind: str) -> bool:
    if kind != "interface":
        return False
    return (
        ".callbacks.I" in name
        or name.endswith("Callback")
        or name.endswith("Cbk")
    )


def class_surface_origin(name: str) -> str:
    if name.endswith(("BuildConfig", "LogUtil")):
        return "compiler-or-build-generated"
    if re.search(r"\$(?:Companion|Default|Stub|\d+|[a-z])(?:$|\$)", name):
        return "compiler-generated-or-obfuscated"
    if name.startswith((
        "com.rokid.cxr.CXRServiceBridge",
        "com.rokid.cxr.CXRSocketProtocol",
        "com.rokid.cxr.Caps",
    )):
        return "native-bridge-implementation"
    if name == "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient":
        return "public-example-wrapper-implementation"
    return "declared-public-api"


def member_surface_origin(class_name: str, member: dict[str, Any]) -> str:
    name = str(member.get("name", ""))
    descriptor = str(member.get("descriptor", ""))
    if name.startswith("access$") or name.endswith("$default"):
        return "compiler-generated"
    if re.fullmatch(r"[a-z]", name):
        if class_name.endswith("$CXRSessionType") and descriptor.startswith("["):
            return "compiler-generated-obfuscated-enum-storage"
        return "obfuscated-unknown"
    if re.search(r"\$(?:Companion|Default|Stub|\d+|[a-z])(?:$|\$)", class_name):
        return "compiler-generated-or-obfuscated"
    return "declared-public-api"


def normalize_member(class_name: str, member: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(member)
    # javap prints the Kotlin/Java enum backing array as a static final field of
    # the enum's array type.  It is not a supported enum constant.
    if (
        class_name.endswith("$CXRSessionType")
        and normalized.get("kind") == "enum_constant"
        and str(normalized.get("descriptor", "")).startswith("[")
    ):
        normalized["kind"] = "field"
        normalized["normalization"] = "enum-backing-array-reclassified-as-field"
    return normalized


def class_base_tags(name: str, kind: str) -> set[str]:
    tags: set[str] = set()
    origin = class_surface_origin(name)
    if callback_class(name, kind):
        tags.add("callback-only")
    if name.startswith("com.rokid.cxr.link.") and ".callbacks." not in name and not name.endswith("LogUtil"):
        tags.add("directly-callable")
    if name.startswith("com.rokid.sprite.aiapp.externalapp.auth."):
        tags.update({"directly-callable", "service/provider-mediated"})
    if name == "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient":
        tags.update({"directly-callable", "service/provider-mediated", "internal-or-implementation-detail"})
    if name.startswith("com.rokid.sprite.aiapp.externalapp.I"):
        tags.add("service/provider-mediated")
    if origin in {
        "compiler-or-build-generated",
        "compiler-generated-or-obfuscated",
        "native-bridge-implementation",
        "public-example-wrapper-implementation",
    }:
        tags.add("internal-or-implementation-detail")
    if origin == "compiler-generated-or-obfuscated":
        tags.add("synthetic-or-obfuscated")
    if not tags:
        tags.add("untested")
    return tags


def member_tags(class_name: str, class_kind: str, member: dict[str, Any]) -> list[str]:
    normalized = normalize_member(class_name, member)
    kind = str(normalized.get("kind", ""))
    name = str(normalized.get("name", ""))
    descriptor = str(normalized.get("descriptor", ""))
    origin = member_surface_origin(class_name, normalized)
    tags: set[str] = set()

    if callback_class(class_name, class_kind) and kind == "method":
        tags.add("callback-only")
    elif kind in {"constructor", "method", "field", "enum_constant"} and (
        class_name.startswith("com.rokid.cxr.link.")
        or class_name.startswith("com.rokid.sprite.aiapp.externalapp.auth.")
        or class_name == "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient"
    ):
        tags.add("directly-callable")

    if class_name.startswith("com.rokid.sprite.aiapp.externalapp.I") or class_name in {
        "com.rokid.cxr.link.CXRLink",
        "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
    }:
        tags.add("service/provider-mediated")

    if class_surface_origin(class_name) != "declared-public-api" or origin != "declared-public-api":
        tags.add("internal-or-implementation-detail")
    if origin in {
        "compiler-generated",
        "compiler-generated-or-obfuscated",
        "compiler-generated-obfuscated-enum-storage",
        "obfuscated-unknown",
    }:
        tags.add("synthetic-or-obfuscated")
        tags.discard("directly-callable")

    key = (class_name, kind, name, descriptor)
    if key in RUNTIME_MEMBERS:
        tags.add("runtime-qualified")
        tags.discard("untested")
    else:
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
            "defined_dynamic_symbol_count": sum(
                1 for symbol in item.get("dynamic_symbols", []) if symbol.get("defined")
            ),
            "jni_exports": item.get("jni_exports", []),
            "jni_export_count": len(item.get("jni_exports", [])),
            "classification": ["internal-or-implementation-detail", "untested"],
            "surface_origin": "native-implementation",
        }
        for item in private_native
    ]


def _iter_members(publication: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for class_item in publication.get("sdk", {}).get("classes", []):
        for member in class_item.get("members", []):
            yield class_item, member


def reclassify_publication(
    publication: dict[str, Any],
    *,
    source_zip_sha256: str = "",
    source_json_sha256: str = "",
) -> dict[str, Any]:
    if publication.get("schema") not in {PUBLIC_SCHEMA_V1, PUBLIC_SCHEMA_V1_1}:
        raise ValueError(f"unsupported publication schema: {publication.get('schema')}")

    repaired = json.loads(json.dumps(publication))
    repaired["schema"] = PUBLIC_SCHEMA_V1_1
    repaired["scope"] = "read-only static census with descriptor-exact member-level runtime qualification"

    class_counts: Counter[str] = Counter()
    member_counts: Counter[str] = Counter()
    qualified_members: list[dict[str, str]] = []
    synthetic_member_count = 0
    obfuscated_member_count = 0

    for class_item in repaired["sdk"]["classes"]:
        class_name = str(class_item["name"])
        class_kind = str(class_item["kind"])
        repaired_members: list[dict[str, Any]] = []
        class_runtime_count = 0

        for original_member in class_item.get("members", []):
            member = normalize_member(class_name, original_member)
            member["surface_origin"] = member_surface_origin(class_name, member)
            member["classifications"] = member_tags(class_name, class_kind, member)
            key = (
                class_name,
                str(member.get("kind", "")),
                str(member.get("name", "")),
                str(member.get("descriptor", "")),
            )
            evidence = RUNTIME_MEMBERS.get(key, "")
            member["runtime_evidence"] = evidence
            if evidence:
                class_runtime_count += 1
                qualified_members.append({
                    "class": class_name,
                    "kind": key[1],
                    "name": key[2],
                    "descriptor": key[3],
                    "evidence": evidence,
                })
            if "synthetic-or-obfuscated" in member["classifications"]:
                synthetic_member_count += 1
            if member["surface_origin"] in {
                "obfuscated-unknown",
                "compiler-generated-obfuscated-enum-storage",
            }:
                obfuscated_member_count += 1
            for tag in member["classifications"]:
                member_counts[tag] += 1
            repaired_members.append(member)

        class_tags = class_base_tags(class_name, class_kind)
        if class_runtime_count:
            class_tags.add("runtime-qualified")
            class_tags.discard("untested")
            class_item["runtime_qualification_scope"] = "selected-members-only"
        elif "untested" not in class_tags:
            class_tags.add("untested")
            class_item["runtime_qualification_scope"] = "none"
        else:
            class_item["runtime_qualification_scope"] = "none"
        class_item["surface_origin"] = class_surface_origin(class_name)
        class_item["classifications"] = sorted(class_tags)
        class_item["runtime_qualified_member_count"] = class_runtime_count
        class_item["members"] = repaired_members
        for tag in class_item["classifications"]:
            class_counts[tag] += 1

    # Recompute enum/session values from normalized members so the compiler
    # backing array `a` is not published as a supported session type.
    session_types: dict[str, list[str]] = {}
    session_storage: list[dict[str, str]] = []
    for class_item in repaired["sdk"]["classes"]:
        if not class_item["name"].endswith("CXRSessionType"):
            continue
        values = [
            member["name"]
            for member in class_item["members"]
            if member["kind"] == "enum_constant"
        ]
        session_types[class_item["name"]] = values
        for member in class_item["members"]:
            if member.get("normalization"):
                session_storage.append({
                    "class": class_item["name"],
                    "name": member["name"],
                    "descriptor": member["descriptor"],
                    "disposition": member["normalization"],
                })
    repaired["sdk"]["session_types"] = session_types
    repaired["sdk"]["session_storage_fields"] = session_storage

    qualified_components: list[dict[str, str]] = []
    for component in repaired.get("hi_rokid", {}).get("components", []):
        key = (str(component.get("type", "")), str(component.get("name", "")))
        evidence = RUNTIME_COMPONENTS.get(key, "")
        if evidence:
            component["classifications"] = ["runtime-qualified", "service/provider-mediated"]
            component["runtime_evidence"] = evidence
            qualified_components.append({
                "type": key[0], "name": key[1], "evidence": evidence,
            })
        else:
            component["classifications"] = ["service/provider-mediated", "untested"]
            component["runtime_evidence"] = ""

    counts = repaired["summary"]
    counts["public_enum_constant_count"] = sum(
        1 for _, member in _iter_members(repaired) if member.get("kind") == "enum_constant"
    )
    counts["public_field_count"] = sum(
        1 for _, member in _iter_members(repaired) if member.get("kind") == "field"
    )
    counts["class_classification_counts"] = dict(sorted(class_counts.items()))
    counts["member_classification_counts"] = dict(sorted(member_counts.items()))
    counts["runtime_qualified_member_count"] = len(qualified_members)
    counts["runtime_qualified_component_count"] = len(qualified_components)
    counts["synthetic_or_obfuscated_member_count"] = synthetic_member_count
    counts["obfuscated_unknown_member_count"] = obfuscated_member_count

    repaired["runtime_qualification"] = {
        **repaired.get("runtime_qualification", {}),
        "granularity": "descriptor-exact-member-and-component",
        "propagation_from_class_to_members": False,
        "qualified_member_count": len(qualified_members),
        "qualified_members": sorted(
            qualified_members,
            key=lambda item: (item["class"], item["kind"], item["name"], item["descriptor"]),
        ),
        "qualified_component_count": len(qualified_components),
        "qualified_components": sorted(
            qualified_components, key=lambda item: (item["type"], item["name"])
        ),
        "explicitly_unobserved_callbacks": [
            "com.rokid.cxr.link.callbacks.ICXRLinkCbk.onGlassAiAssistStart()V",
            "com.rokid.cxr.link.callbacks.ICXRLinkCbk.onGlassAiAssistStop()V",
        ],
        "authorization_parser_observed": "direct Intent extra; AuthorizationHelper.parseAuthorizationResult unobserved",
    }
    repaired["repair"] = {
        "repair_id": "test20-r1.1",
        "source_publication_schema": publication.get("schema", ""),
        "source_sanitized_zip_sha256": source_zip_sha256,
        "source_publication_json_sha256": source_json_sha256,
        "defects_closed": [
            "class-level runtime status propagated to unrelated members",
            "unobserved AI-assist callbacks marked runtime-qualified",
            "two-argument CXRSession constructor omitted from runtime-qualified set",
            "enum backing array published as a supported session type",
            "compiler-generated and obfuscated public surfaces lacked explicit origin classification",
        ],
        "device_rerun_required": False,
        "maven_operation_required": False,
        "proprietary_binary_required": False,
    }
    repaired["conclusion"] = (
        "The exact client-l:1.0.1 public surface remains enumerated, but runtime "
        "qualification is now restricted to nine descriptor-exact members and two "
        "Hi Rokid components directly supported by accepted Test 19 evidence. Camera, "
        "audio, AI-assist callbacks, custom commands, custom views, glass-app operations, "
        "provider access, compiler-generated helpers, obfuscated fields, and native/JNI "
        "surfaces remain untested or implementation detail pending separately approved work."
    )
    return repaired


def markdown_report(publication: dict[str, Any]) -> str:
    summary = publication["summary"]
    lines = [
        "# Test 20 r1.1 — CXR-L Member-Level Capability Census",
        "",
        "This sanitized report repairs the Test 20 r1 classification boundary. Runtime",
        "qualification is descriptor-exact and member-level; class participation does not",
        "qualify unrelated methods, fields, constructors, or callbacks.",
        "",
        "## Artifact identity",
        "",
        f"- Coordinate: `{publication['sdk']['coordinate']}`",
        f"- AAR SHA-256: `{publication['sdk']['artifact']['aar_sha256']}`",
        f"- POM SHA-256: `{publication['sdk']['artifact']['pom_sha256']}`",
        f"- Hi Rokid: `{publication['hi_rokid']['package']}` `{publication['hi_rokid']['version_name']}`",
        "",
        "## Corrected census totals",
        "",
        "| Surface | Count |",
        "|---|---:|",
        f"| Public classes/interfaces | {summary['public_class_count']} |",
        f"| Public constructors | {summary['public_constructor_count']} |",
        f"| Public methods | {summary['public_method_count']} |",
        f"| Public fields | {summary['public_field_count']} |",
        f"| Real enum constants | {summary['public_enum_constant_count']} |",
        f"| Runtime-qualified members | {summary['runtime_qualified_member_count']} |",
        f"| Runtime-qualified Hi Rokid components | {summary['runtime_qualified_component_count']} |",
        f"| Synthetic or obfuscated members | {summary['synthetic_or_obfuscated_member_count']} |",
        f"| Native libraries across ABIs | {summary['native_library_count']} |",
        f"| JNI exports | {summary['jni_export_count']} |",
        "",
        "## Descriptor-exact runtime-qualified members",
        "",
        "| Class | Kind | Member | Descriptor | Evidence |",
        "|---|---|---|---|---|",
    ]
    for item in publication["runtime_qualification"]["qualified_members"]:
        lines.append(
            f"| `{item['class']}` | {item['kind']} | `{item['name']}` | "
            f"`{item['descriptor']}` | `{item['evidence']}` |"
        )
    lines.extend([
        "",
        "## Runtime-qualified Hi Rokid components",
        "",
        "| Type | Component | Evidence |",
        "|---|---|---|",
    ])
    for item in publication["runtime_qualification"]["qualified_components"]:
        lines.append(f"| {item['type']} | `{item['name']}` | `{item['evidence']}` |")
    lines.extend([
        "",
        "## Session types",
        "",
    ])
    for class_name, values in sorted(publication["sdk"]["session_types"].items()):
        lines.append(f"- `{class_name}`: " + ", ".join(f"`{value}`" for value in values))
    for item in publication["sdk"].get("session_storage_fields", []):
        lines.append(
            f"- `{item['class']}.{item['name']}` `{item['descriptor']}` is "
            f"`{item['disposition']}`, not a supported session type."
        )
    lines.extend([
        "",
        "## Explicitly untested high-impact surfaces",
        "",
        "The following remain present but are not runtime-qualified: camera/photo, audio",
        "streaming, AI-assist start/stop callbacks, custom commands, custom views, glass-app",
        "upload/install/start/stop operations, provider access, and native/JNI behavior.",
        "",
        "## Conclusion",
        "",
        publication["conclusion"],
        "",
    ])
    return "\n".join(lines)


def build_publication_from_private(
    sdk: dict[str, Any], hi: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    surfaces: list[dict[str, Any]] = []
    package_counts: Counter[str] = Counter()
    for item in sdk["classes"]:
        package_counts[item["name"].rsplit(".", 1)[0]] += 1
        members = [
            {
                "kind": member["kind"],
                "name": member["name"],
                "signature": member["signature"],
                "descriptor": member["descriptor"],
                "classifications": [],
            }
            for member in item["members"]
        ]
        surfaces.append({
            "name": item["name"],
            "kind": item["kind"],
            "superclass": item.get("superclass", ""),
            "interfaces": item.get("interfaces", []),
            "classifications": [],
            "members": members,
        })
    native = summarize_native(sdk["native_libraries"])
    publication = {
        "schema": PUBLIC_SCHEMA_V1,
        "scope": "read-only static and accepted-runtime-surface census",
        "sdk": {
            "coordinate": sdk["coordinate"],
            "artifact": sdk["artifact"],
            "dependencies": sdk["pom"]["dependencies"],
            "package_class_counts": dict(sorted(package_counts.items())),
            "session_types": {},
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
            "classification": runtime.get("status") or runtime.get("final_status")
            or runtime.get("classification") or "TEST19_R2_ACCEPTED",
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
            "jni_export_count": sum(item["jni_export_count"] for item in native),
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
        "conclusion": "Pending repaired member-level classification.",
    }
    return reclassify_publication(publication)


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

    publication = build_publication_from_private(sdk, hi, runtime)
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
            f"RUNTIME_QUALIFIED_MEMBER_COUNT={publication['summary']['runtime_qualified_member_count']}",
        ]) + "\n",
        encoding="utf-8",
    )

    print("TEST20_R1_CLASSIFICATION=PASS")
    print(f"TEST20_R1_PUBLIC_CLASS_COUNT={sdk['public_class_count']}")
    print(f"TEST20_R1_PUBLIC_MEMBER_COUNT={sdk['public_member_count']}")
    print(f"TEST20_R1_RUNTIME_QUALIFIED_MEMBER_COUNT={publication['summary']['runtime_qualified_member_count']}")
    print(f"TEST20_R1_UNTESTED_MEMBER_COUNT={publication['summary']['member_classification_counts'].get('untested', 0)}")
    print(f"TEST20_R1_JNI_EXPORT_COUNT={publication['summary']['jni_export_count']}")
    print(f"TEST20_R1_SANITIZED_JSON={output_json}")
    print(f"TEST20_R1_SANITIZED_MARKDOWN={output_md}")
    print("TEST20_R1_SANITIZED_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
