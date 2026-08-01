#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PACKAGE = "org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_VERSION = "1.0-test20-r3.2.1.3"
MEDIA_PERMISSIONS = (
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def find_module(repo: Path, seed: Path) -> Path:
    module = seed
    while module != repo and not (module / "build.gradle").exists() and not (module / "build.gradle.kts").exists():
        module = module.parent
    return seed.parent if module == repo else module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed executable and two-phase operator-gate source contract check for Test 20 r3.2.1.3."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").is_dir():
        print(f"ERROR: not a git repository: {repo}", file=sys.stderr)
        return 2

    candidates: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".java", ".kt"}:
            continue
        if any(part in {".git", "build", ".gradle"} for part in path.parts):
            continue
        try:
            text = read_text(path)
        except OSError:
            continue
        if PACKAGE in text:
            candidates.append(path)

    if not candidates:
        print(f"ERROR: could not locate r3.2 photo qualification sources for {PACKAGE}", file=sys.stderr)
        return 1

    modules = sorted({find_module(repo, seed) for seed in candidates})
    source_files: list[Path] = []
    for module in modules:
        for path in module.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".java", ".kt", ".xml", ".gradle", ".kts"}:
                continue
            if any(part in {"build", ".gradle"} for part in path.parts):
                continue
            source_files.append(path)

    source_files = sorted(set(source_files))
    combined = "\n".join(read_text(path) for path in source_files)

    # Executable-call contract. Manifest permissions are intentionally NOT used as
    # proxies for executable behavior: they may be inherited/declared by the base
    # qualification app or dependency surface without this test invoking those APIs.
    take_photo_calls = len(re.findall(r"\.\s*takePhoto\s*\(", combined))
    start_audio_calls = len(re.findall(r"\.\s*startAudioStream\s*\(", combined))
    stop_audio_calls = len(re.findall(r"\.\s*stopAudioStream\s*\(", combined))

    if take_photo_calls != 1:
        print(
            f"ERROR: expected exactly one concrete .takePhoto(...) invocation site in r3.2 source; found {take_photo_calls}",
            file=sys.stderr,
        )
        return 1
    if start_audio_calls or stop_audio_calls:
        print(
            "ERROR: r3.2 source contains executable audio operation call site(s): "
            f"start={start_audio_calls}, stop={stop_audio_calls}",
            file=sys.stderr,
        )
        return 1


    main_sources = [p for p in source_files if p.name == "MainActivity.java"]
    controller_sources = [p for p in source_files if p.name == "CxrLPhotoController.java"]
    if len(main_sources) != 1 or len(controller_sources) != 1:
        print(
            "ERROR: expected exactly one MainActivity.java and one CxrLPhotoController.java "
            f"for the qualification module; found main={len(main_sources)}, controller={len(controller_sources)}",
            file=sys.stderr,
        )
        return 1
    main_text = read_text(main_sources[0])
    controller_text = read_text(controller_sources[0])

    gate_markers = {
        "operator_gate_initialized": "operator_gate_initialized",
        "operator_gate_prerequisite_ready": "operator_gate_prerequisite_ready",
        "operator_gate_host_command": "operator_gate_host_command",
        "operator_gate_arm_result": "operator_gate_arm_result",
        "operator_gate_capture_dispatch": "operator_gate_capture_dispatch",
        "host_arm_action": "ARM_ONE_PHOTO",
        "host_arm_token_extra": "operator_gate_token",
        "host_arm_atomic_grant": "hostArmGranted.compareAndSet(false, true)",
        "host_arm_atomic_consume": "hostArmGranted.compareAndSet(true, false)",
    }
    missing_gate_markers = [name for name, marker in gate_markers.items() if marker not in combined]
    if missing_gate_markers:
        print(
            "ERROR: r3.2.1.3 two-phase operator-gate source markers are missing: "
            + ",".join(missing_gate_markers),
            file=sys.stderr,
        )
        return 1

    photo_control_enable_sites = (
        main_text.count("captureButton.setEnabled(true);")
        + main_text.count("captureButton.setEnabled(granted);")
    )
    if photo_control_enable_sites != 1:
        print(
            "ERROR: photo control must have exactly one enable site, owned by the host-arm handler",
            file=sys.stderr,
        )
        return 1
    photo_ready_match = re.search(
        r"onPhotoReady\s*\(\)\s*\{(?P<body>.*?)\n\s*\}",
        main_text,
        flags=re.DOTALL,
    )
    if not photo_ready_match or "captureButton.setEnabled(false);" not in photo_ready_match.group("body"):
        print(
            "ERROR: onPhotoReady must keep the photo control disabled during prerequisite phase",
            file=sys.stderr,
        )
        return 1
    if main_text.count("controller.requestOnePhoto();") != 1:
        print(
            "ERROR: expected exactly one MainActivity dispatch to controller.requestOnePhoto()",
            file=sys.stderr,
        )
        return 1
    if controller_text.count("hostArmGranted.compareAndSet(false, true)") != 1:
        print("ERROR: controller host-arm grant must be atomic and unique", file=sys.stderr)
        return 1
    if controller_text.count("hostArmGranted.compareAndSet(true, false)") != 1:
        print("ERROR: controller host-arm consumption must be atomic and unique", file=sys.stderr)
        return 1
    if "Context.RECEIVER_EXPORTED" not in main_text:
        print("ERROR: host ADB arm receiver is not explicitly exported for tokenized host delivery", file=sys.stderr)
        return 1

    manifest_files = [p for p in source_files if p.name == "AndroidManifest.xml"]
    declared_media_permissions: list[str] = []
    for manifest in manifest_files:
        text = read_text(manifest)
        for permission in MEDIA_PERMISSIONS:
            if permission in text:
                declared_media_permissions.append(permission)
    declared_media_permissions = sorted(set(declared_media_permissions))

    if EXPECTED_VERSION not in combined:
        print(f"ERROR: expected base app version marker not found: {EXPECTED_VERSION}", file=sys.stderr)
        return 1

    report = {
        "schema": "rokid.test20-r3.2.1.3.source-contract.v1",
        "package": PACKAGE,
        "expected_base_version": EXPECTED_VERSION,
        "source_file_count": len(source_files),
        "take_photo_call_sites": take_photo_calls,
        "audio_start_call_sites": start_audio_calls,
        "audio_stop_call_sites": stop_audio_calls,
        "declared_manifest_media_permissions": declared_media_permissions,
        "manifest_permission_interpretation": "ATTEST_ONLY_NOT_EXECUTION_PROOF",
        "operator_gate": {
            "phase_1_photo_control_disabled": True,
            "host_arm_action": "ARM_ONE_PHOTO",
            "run_scoped_token_required": True,
            "controller_atomic_arm_grant": True,
            "controller_atomic_arm_consumption": True,
            "single_photo_control_enable_site": True,
            "photo_control_enable_sites": photo_control_enable_sites,
        },
        "contract": "PASS",
        "note": (
            "The executable source contract gates concrete CXR-L media operation call sites. "
            "CAMERA/RECORD_AUDIO manifest declarations are recorded but are not treated as proof "
            "that Test 20 executes local camera or audio operations. Runtime qualification still "
            "enforces exactly one photo request and zero audio-operation evidence. "
            "r3.2.1.3 additionally requires a host-tokenized two-phase arm gate in both UI and controller."
        ),
    }
    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    permissions_text = ",".join(declared_media_permissions) if declared_media_permissions else "NONE"
    print("TEST20_R3_2_1_SOURCE_CONTRACT=PASS")
    print(f"TAKE_PHOTO_SOURCE_CALL_SITES={take_photo_calls}")
    print("AUDIO_OPERATION_SOURCE_CALL_SITES=0")
    print(f"DECLARED_MANIFEST_MEDIA_PERMISSIONS={permissions_text}")
    print("MANIFEST_PERMISSION_INTERPRETATION=ATTEST_ONLY_NOT_EXECUTION_PROOF")
    print("TEST20_R3_2_1_3_OPERATOR_GATE_SOURCE_CONTRACT=PASS")
    print(f"PHOTO_CONTROL_ENABLE_SITES={photo_control_enable_sites}")
    print("CONTROLLER_HOST_ARM_ATOMIC_GRANT=PASS")
    print("CONTROLLER_HOST_ARM_ATOMIC_CONSUME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
