#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "rokid.test20.r3.cxr-l-media-plane-feasibility.public.v1"
COORDINATE = "com.rokid.cxr:client-l:1.0.1"
AAR_SHA256 = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
POM_SHA256 = "d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a"
CENSUS_SHA256 = "a3f261e830910a1664e004feb91af339ea1518230a4c1c6bc8d2205e1075dcc9"

CLIENT = "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient"
AUDIO_CBK = "com.rokid.cxr.link.callbacks.IAudioStreamCbk"
IMAGE_CBK = "com.rokid.cxr.link.callbacks.IImageStreamCbk"
SERVICE = "com.rokid.sprite.aiapp.externalapp.IMediaStreamService"

REQUIRED: dict[str, list[tuple[str, str, str]]] = {
    "client_entrypoints": [
        (CLIENT, "setCXRAudioCbk", "(Lcom/rokid/cxr/link/callbacks/IAudioStreamCbk;)V"),
        (CLIENT, "setCXRImageCbk", "(Lcom/rokid/cxr/link/callbacks/IImageStreamCbk;)V"),
        (CLIENT, "takePhoto", "(III)Z"),
        (CLIENT, "startAudioStream", "(I)Z"),
        (CLIENT, "stopAudioStream", "()Z"),
        (CLIENT, "getServiceVersion", "()Ljava/lang/String;"),
        (CLIENT, "getServiceVersionCode", "()Ljava/lang/Integer;"),
        (CLIENT, "isGlassBtConnected", "()Z"),
    ],
    "callbacks": [
        (AUDIO_CBK, "onAudioReceived", "([BII)V"),
        (AUDIO_CBK, "onAudioError", "(ILjava/lang/String;)V"),
        (AUDIO_CBK, "onAudioStreamStateChanged", "(Z)V"),
        (IMAGE_CBK, "onImageReceived", "([B)V"),
        (IMAGE_CBK, "onImageError", "(ILjava/lang/String;)V"),
    ],
    "service_contract": [
        (SERVICE, "registerImageCallback", "(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z"),
        (SERVICE, "unregisterImageCallback", "(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z"),
        (SERVICE, "takePhoto", "(III)Z"),
        (SERVICE, "registerAudioCallback", "(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z"),
        (SERVICE, "unregisterAudioCallback", "(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z"),
        (SERVICE, "startAudioStream", "(I)Z"),
        (SERVICE, "stopAudioStream", "()Z"),
        (SERVICE, "isAudioStreaming", "()Z"),
        (SERVICE, "getServiceVersion", "()Ljava/lang/String;"),
        (SERVICE, "getServiceVersionCode", "()I"),
    ],
}

class AnalysisError(RuntimeError):
    pass

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AnalysisError("census root is not an object")
    return data

def flatten(data: dict[str, Any]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    classes = data.get("sdk", {}).get("classes", [])
    if not isinstance(classes, list):
        raise AnalysisError("sdk.classes is not an array")
    for cls in classes:
        if not isinstance(cls, dict):
            continue
        class_name = cls.get("name")
        for member in cls.get("members", []) if isinstance(cls.get("members", []), list) else []:
            if not isinstance(member, dict):
                continue
            key = (str(class_name), str(member.get("name")), str(member.get("descriptor")))
            index.setdefault(key, []).append(member)
    return index

def validate_member(category: str, spec: tuple[str, str, str], index: dict[tuple[str, str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    matches = index.get(spec, [])
    if len(matches) != 1:
        raise AnalysisError(f"expected exactly one {category} member {spec}, found {len(matches)}")
    member = matches[0]
    origin = member.get("surface_origin")
    classifications = member.get("classifications", [])
    if origin != "declared-public-api":
        raise AnalysisError(f"unstable surface origin for {spec}: {origin}")
    if not isinstance(classifications, list) or "untested" not in classifications:
        raise AnalysisError(f"member is not explicitly untested: {spec}")
    if "runtime-qualified" in classifications:
        raise AnalysisError(f"media member already runtime-qualified without Test 20 r3 evidence: {spec}")
    if "synthetic-or-obfuscated" in classifications:
        raise AnalysisError(f"synthetic or obfuscated member entered stable boundary: {spec}")
    return {
        "class": spec[0],
        "name": spec[1],
        "descriptor": spec[2],
        "kind": member.get("kind", ""),
        "signature": member.get("signature", ""),
        "surface_origin": origin,
        "runtime_status": "STATICALLY_CONFIRMED_RUNTIME_UNTESTED",
    }

def find_media_service(data: dict[str, Any]) -> dict[str, Any]:
    components = data.get("hi_rokid", {}).get("components", [])
    for component in components if isinstance(components, list) else []:
        if not isinstance(component, dict):
            continue
        if component.get("name") == "com.rokid.sprite.aiapp.externalapp.service.CXRLinkService":
            actions = component.get("actions", [])
            if "com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE" not in actions:
                raise AnalysisError("Hi Rokid media service action is missing")
            if component.get("exported") is not True:
                raise AnalysisError("Hi Rokid media service is not exported in census")
            return component
    raise AnalysisError("Hi Rokid CXRLinkService component not found")

def analyze(census_path: Path, enforce_hash: bool = True) -> dict[str, Any]:
    census_sha = sha256_file(census_path)
    if enforce_hash and census_sha != CENSUS_SHA256:
        raise AnalysisError(f"census SHA-256 mismatch: expected {CENSUS_SHA256}, got {census_sha}")
    data = load_json(census_path)
    artifact = data.get("sdk", {}).get("artifact", {})
    if data.get("sdk", {}).get("coordinate") != COORDINATE:
        raise AnalysisError("CXR-L coordinate mismatch")
    if artifact.get("aar_sha256") != AAR_SHA256:
        raise AnalysisError("CXR-L AAR identity mismatch")
    if artifact.get("pom_sha256") != POM_SHA256:
        raise AnalysisError("CXR-L POM identity mismatch")
    if data.get("hi_rokid", {}).get("package") != "com.rokid.sprite.global.aiapp":
        raise AnalysisError("Hi Rokid package mismatch")
    if data.get("hi_rokid", {}).get("version_name") != "G1.11.11.0727":
        raise AnalysisError("Hi Rokid version mismatch")
    component = find_media_service(data)
    index = flatten(data)
    surfaces: dict[str, list[dict[str, Any]]] = {}
    for category, specs in REQUIRED.items():
        surfaces[category] = [validate_member(category, spec, index) for spec in specs]
    counts = {key: len(value) for key, value in surfaces.items()}
    counts["total"] = sum(counts.values())
    return {
        "schema": SCHEMA,
        "source": {"census_schema": str(data.get("schema", "")), "census_sha256": census_sha},
        "sdk": {"coordinate": COORDINATE, "aar_sha256": AAR_SHA256, "pom_sha256": POM_SHA256},
        "hi_rokid": {
            "package": data.get("hi_rokid", {}).get("package"),
            "version_name": data.get("hi_rokid", {}).get("version_name"),
            "media_service_action": "com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE",
            "media_service_exported": component.get("exported") is True,
            "component_runtime_boundary": "CONNECTION_LIFECYCLE_QUALIFIED_MEDIA_OPERATIONS_UNTESTED",
        },
        "surface_counts": counts,
        "surfaces": surfaces,
        "feasibility": {
            "image_control_path": "STATICALLY_PRESENT",
            "image_callback_path": "STATICALLY_PRESENT",
            "audio_control_path": "STATICALLY_PRESENT",
            "audio_callback_path": "STATICALLY_PRESENT",
            "service_contract": "STATICALLY_PRESENT",
            "parameter_semantics": "UNRESOLVED",
            "payload_formats": "UNRESOLVED",
            "runtime_qualification": "NOT_GRANTED",
        },
        "privacy": {
            "authorization_token_value_present": False,
            "bluetooth_address_present": False,
            "device_serial_present": False,
            "media_payload_present": False,
            "local_user_path_present": False,
            "proprietary_binary_present": False,
        },
        "safety": {
            "runtime_media_invocation": "NONE",
            "phone_operation": "NONE",
            "glasses_operation": "NONE",
            "adb_operation": "NONE",
            "maven_operation": "NONE",
            "gradle_operation": "NONE",
            "cloud_request": "NONE",
        },
        "next_step": {
            "classification": "READY_FOR_BOUNDED_MEDIA_TEST_DESIGN",
            "recommended_stage": "TEST20_R3_1_SERVICE_STATUS_AND_NO_PAYLOAD_PREFLIGHT",
            "runtime_media_test_authorized": False,
        },
    }

def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Test 20 r3 — CXR-L media-plane feasibility census",
        "",
        "## Disposition",
        "",
        "The accepted static census contains descriptor-exact image, audio, and media-service contracts. No media API was invoked and no runtime qualification is granted.",
        "",
        "```text",
        "IMAGE_CONTROL_PATH=STATICALLY_PRESENT",
        "IMAGE_CALLBACK_PATH=STATICALLY_PRESENT",
        "AUDIO_CONTROL_PATH=STATICALLY_PRESENT",
        "AUDIO_CALLBACK_PATH=STATICALLY_PRESENT",
        "MEDIA_SERVICE_CONTRACT=STATICALLY_PRESENT",
        "PARAMETER_SEMANTICS=UNRESOLVED",
        "PAYLOAD_FORMATS=UNRESOLVED",
        "RUNTIME_QUALIFICATION=NOT_GRANTED",
        "```",
        "",
        "## Stable declared public surfaces",
        "",
    ]
    for category in ("client_entrypoints", "callbacks", "service_contract"):
        lines.append(f"### {category.replace('_', ' ').title()}")
        lines.append("")
        for member in result["surfaces"][category]:
            lines.append(f"- `{member['class']}.{member['name']}{member['descriptor']}`")
        lines.append("")
    lines += [
        "## Safety boundary",
        "",
        "```text",
        "RUNTIME_MEDIA_INVOCATION=NONE",
        "PHONE_OPERATION=NONE",
        "GLASSES_OPERATION=NONE",
        "ADB_OPERATION=NONE",
        "MAVEN_OPERATION=NONE",
        "GRADLE_OPERATION=NONE",
        "CLOUD_REQUEST=NONE",
        "```",
        "",
        "## Next step",
        "",
        "`TEST20_R3_1_SERVICE_STATUS_AND_NO_PAYLOAD_PREFLIGHT` may be designed next. This census does not authorize photo capture or audio streaming.",
        "",
    ]
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--allow-noncanonical-hash-for-tests", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.census, enforce_hash=not args.allow_noncanonical_hash_for_tests)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        json_path = args.output_dir / "test20-r3-cxr-l-media-plane-feasibility.json"
        md_path = args.output_dir / "test20-r3-cxr-l-media-plane-feasibility.md"
        json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_path.write_text(render_markdown(result), encoding="utf-8")
    except (AnalysisError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("TEST20_R3_MEDIA_CONTRACT_ANALYSIS=PASS")
    print(f"TEST20_R3_MEDIA_SURFACE_COUNT={result['surface_counts']['total']}")
    print("TEST20_R3_RUNTIME_MEDIA_INVOCATION=NONE")
    print("TEST20_R3_READY_FOR_BOUNDED_MEDIA_TEST_DESIGN=YES")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
