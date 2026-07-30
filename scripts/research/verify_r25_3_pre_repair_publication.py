#!/usr/bin/env python3
"""Validate the sanitized r25.3 pre-repair and boot-chain publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

EXPECTED_FILES = (
    "docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md",
    "docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-runtime-status-summary.json",
    "docs/research/boot-chain/README.md",
    "docs/research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md",
    "docs/research/boot-chain/runtime-status-summary.json",
    "docs/research/boot-chain/evidence-hashes.txt",
    "evidence/manifests/boot-chain-offline-validation-evidence-hashes.txt",
    "evidence/sanitized/boot-chain/summary.txt",
)

PUBLICATION_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "docs/project-status.md",
    "docs/research/README.md",
    "docs/research/connection-protocol/README.md",
    "docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md",
    "docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-runtime-status-summary.json",
    "docs/research/boot-chain/README.md",
    "docs/research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md",
    "docs/research/boot-chain/runtime-status-summary.json",
    "docs/research/boot-chain/evidence-hashes.txt",
    "docs/findings/glasses-android-os-and-adb.md",
    "docs/tests/test-matrix.md",
    "evidence/README.md",
    "evidence/manifests/README.md",
    "evidence/manifests/boot-chain-offline-validation-evidence-hashes.txt",
    "evidence/sanitized/README.md",
    "evidence/sanitized/boot-chain/summary.txt",
    "scripts/README.md",
    "scripts/research/README.md",
    "scripts/research/verify_r25_3_pre_repair_publication.py",
)

FORBIDDEN_PATTERNS = {
    "macOS absolute user path": re.compile(r"/Users/[^\s`'\"]+"),
    "private workspace name": re.compile(r"rokid-nettest", re.IGNORECASE),
    "device serial assignment": re.compile(
        r"(?:phone|glasses|device)_serial\s*[:=]\s*[A-Za-z0-9]{8,}",
        re.IGNORECASE,
    ),
    "private OTA URL": re.compile(r"https?://[^\s]*(?:ota|oss)[^\s]*", re.IGNORECASE),
    "private evidence path": re.compile(r"(?:^|/)private(?:-evidence)?/", re.IGNORECASE),
}

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_HASHES = {
    "stock_boot_img_sha256": "31f071baf83381c78d007b4849944b2778e49899d28beae2734c55b93ec82d3e",
    "live_and_ota_combined_vbmeta_digest_sha256": "438ae266c9a636cb12bee30bf551f7aa78213ef7f9c1f360b9ef24d23172ffab",
    "rejected_magisk_candidate_sha256": "943314b271e83c9298adc9f9451f1fc9ce135efab4a73c3a260d38f3cb4a127d",
    "repaired_offline_boot_candidate_sha256": "83d046ce71f0378d6039f0c93c27845af099cb50760c80c7a305e9e192221482",
    "r25_3_failure_addendum_private_evidence_sha256": "20cc312912fe2e3f3d5d443a9f16e8adcef805827fe525b1d19d95142a6bf480",
}


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def parse_hash_manifest(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_no}: expected key=value")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"{path}:{line_no}: invalid or duplicate key {key!r}")
        if not HASH_RE.fullmatch(value):
            raise ValueError(f"{path}:{line_no}: invalid SHA-256 {value!r}")
        values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    errors: list[str] = []

    for rel in EXPECTED_FILES:
        if not (repo / rel).is_file():
            errors.append(f"missing required publication file: {rel}")

    for rel in PUBLICATION_FILES:
        path = repo / rel
        if not path.is_file():
            errors.append(f"missing publication file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "\r" in text:
            errors.append(f"CR line ending found: {rel}")
        if rel != "scripts/research/verify_r25_3_pre_repair_publication.py":
            for label, pattern in FORBIDDEN_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{label} found in {rel}")

    try:
        r25 = read_json(repo / EXPECTED_FILES[1])
        if r25.get("standing") != "rejected_pre_repair":
            errors.append("r25.3 standing must be rejected_pre_repair")
        if r25.get("physical_run") != "rejected_invalid_disable_oracle":
            errors.append("r25.3 physical_run status mismatch")
        if r25.get("stock_disable_semantic_transition") != "proven":
            errors.append("r25.3 disable semantic transition must be proven")
        payload = r25.get("payload_qualification")
        if not isinstance(payload, dict) or payload.get("custom_transmission_attempted") is not False:
            errors.append("r25.3 custom transmission must be false")
        if r25.get("supersedes_r25_2_4") is not False:
            errors.append("r25.3 pre-repair result must not supersede r25.2.4")
    except (ValueError, OSError) as exc:
        errors.append(str(exc))

    try:
        boot = read_json(repo / EXPECTED_FILES[4])
        live = boot.get("live_vbmeta")
        repaired = boot.get("repaired_candidate")
        rejected = boot.get("rejected_candidate")
        if not isinstance(live, dict) or live.get("ota_chain_digest_match") is not True:
            errors.append("live/OTA vbmeta chain match must be true")
        if not isinstance(repaired, dict):
            errors.append("missing repaired_candidate object")
        else:
            expected = {
                "sha256": EXPECTED_HASHES["repaired_offline_boot_candidate_sha256"],
                "preinitdevice": "metadata",
                "kernel_equals_pristine": True,
                "changed_cpio_member_count": 1,
                "changed_cpio_member": ".backup/.magisk",
                "local_avb_algorithm": "NONE",
                "local_avb_content_validation": "pass",
                "oem_signed": False,
                "offline_validation": "accepted",
            }
            for key, value in expected.items():
                if repaired.get(key) != value:
                    errors.append(f"repaired_candidate.{key} mismatch")
        if not isinstance(rejected, dict) or rejected.get("accepted") is not False:
            errors.append("rejected_candidate must remain rejected")
        if boot.get("device_boot_attempted") is not False:
            errors.append("device_boot_attempted must be false")
        if boot.get("device_flash_attempted") is not False:
            errors.append("device_flash_attempted must be false")
        if boot.get("flash_authorized") is not False:
            errors.append("flash_authorized must be false")
    except (ValueError, OSError) as exc:
        errors.append(str(exc))

    try:
        primary = parse_hash_manifest(repo / EXPECTED_FILES[5])
        mirror = parse_hash_manifest(repo / EXPECTED_FILES[6])
        if primary != mirror:
            errors.append("boot-chain hash manifest mirror differs")
        for key, value in EXPECTED_HASHES.items():
            if primary.get(key) != value:
                errors.append(f"hash manifest mismatch for {key}")
    except (ValueError, OSError) as exc:
        errors.append(str(exc))

    required_snippets = {
        "README.md": (
            "r1.3.3.2.25.3-pre-repair-findings.md",
            "docs/research/boot-chain/README.md",
        ),
        "ARCHITECTURE.md": (
            "11,904-byte vbmeta chain",
            "PREINITDEVICE=metadata",
        ),
        "docs/project-status.md": (
            "r1.3.3.2.25.3.1",
            "offline only",
        ),
        "docs/findings/glasses-android-os-and-adb.md": (
            "## Runtime stock-toggle semantics",
            "## Read-only OTA boot-chain audit",
        ),
    }
    for rel, snippets in required_snippets.items():
        text = (repo / rel).read_text(encoding="utf-8", errors="replace")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"missing required snippet {snippet!r} in {rel}")

    # Prove the verifier itself is part of the publication being checked.
    verifier = repo / "scripts/research/verify_r25_3_pre_repair_publication.py"
    if verifier.is_file():
        digest = hashlib.sha256(verifier.read_bytes()).hexdigest()
        print(f"VERIFIER_SHA256={digest}")

    if errors:
        print("R25_3_PRE_REPAIR_PUBLICATION=FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"PUBLICATION_FILE_COUNT={len(PUBLICATION_FILES)}")
    print("R25_3_PRE_REPAIR_STATUS=REJECTED_INVALID_DISABLE_ORACLE")
    print("BOOT_CHAIN_OFFLINE_CANDIDATE=ACCEPTED")
    print("DEVICE_BOOT_ATTEMPTED=NO")
    print("DEVICE_FLASH_ATTEMPTED=NO")
    print("R25_3_PRE_REPAIR_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
