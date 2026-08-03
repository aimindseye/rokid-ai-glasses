#!/usr/bin/env python3
"""Validate the sanitized r25.3.1.2/.3 stock ADB-toggle publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

STOCK = Path("docs/research/connection-protocol/stock-adb-toggle")
EXPECTED = (
    STOCK / "README.md",
    STOCK / "lineage.md",
    STOCK / "findings.md",
    STOCK / "methodology.md",
    STOCK / "limitations.md",
    STOCK / "runtime-status-summary.json",
    STOCK / "r25.3.1.2-runtime-status-summary.json",
    STOCK / "r25.3.1.3-runtime-status-summary.json",
    STOCK / "evidence-hashes.txt",
    Path("evidence/manifests/stock-adb-toggle-evidence-hashes.txt"),
    Path("evidence/sanitized/stock-adb-toggle/summary.txt"),
)


LINEAGE_SOURCE_HASHES = {
    Path("docs/research/connection-protocol/r1.3.3.2.25.3.1-stock-adb-toggle-semantic-oracle-repair-rfcomm-payload-capture.md"): "44daa508fd93b3df7da7864ab4e6adcb81a6e8836dcef919e84b39bd48876337",
    Path("scripts/research/connection-protocol/r25_3_1_analyze.py"): "e9034b209f8abaecea775057910b33ee2e61d64970320cf36bbe2953523d8d5e",
    Path("scripts/research/connection-protocol/r25_3_1_capture.py"): "25aa249b81a999988e1f287b2b9a660f69e074c92ab6ddb96602de0eb3c748d8",
    Path("scripts/research/connection-protocol/run_r1_3_3_2_25_3_1.sh"): "c92f79acaf06d7f1ddf91a833f2077856231e389ff83677798875f736200e594",
    Path("docs/research/connection-protocol/r1.3.3.2.25.3.1.1-stock-adb-toggle-semantic-oracle-repair-rfcomm-payload-capture.md"): "4ab9b5879d6165dc84cf44147878cd10e598106522e2c447c78d673be5e2fbee",
    Path("scripts/research/connection-protocol/r25_3_1_1_analyze.py"): "c1ee9a169360772cb17aff34c72b501aa217b455885492c6581514d04e93301f",
    Path("scripts/research/connection-protocol/r25_3_1_1_capture.py"): "2d78821ba551b0dcd4067ca1f698ec6ee5e8257baf1f9be319bdeec16b3e0c95",
    Path("scripts/research/connection-protocol/run_r1_3_3_2_25_3_1_1.sh"): "0025a3dd25fc650e000b37310af625eff216d0ef527c286185c01f5c097c621a",
}


CANONICAL_VALIDATOR_PROFILE = Path("scripts/research/canonical/profiles/r25-package-validators.json")
HISTORICAL_VALIDATOR_LINEAGE = {
    "r25.3.1": {
        "path": Path("scripts/research/connection-protocol/validate_r1_3_3_2_25_3_1_package.sh"),
        "historical_sha256": "99ee789ff35b7da6fbf460d4c03723ce7ba78a24f0ee526b0ee984073b94ca4e",
    },
    "r25.3.1.1": {
        "path": Path("scripts/research/connection-protocol/validate_r1_3_3_2_25_3_1_1_package.sh"),
        "historical_sha256": "198303ea2c111013ab5dca6a0702f62d0dd7115fce025df3be92f97c02acef01",
    },
}

SOURCE_RUNTIME_HASHES = {
    "r25.3.1.2-runtime-status-summary.json": "6feadfdef9fe1dc8d17805e13e0a7210d5af2d271df66409594f6e0f63a11a0d",
    "r25.3.1.3-runtime-status-summary.json": "c3b1a650e9067860a2a054ee6678c66de81b38d0f3430300285d23e6f2fb1edd",
}

EXPECTED_EVIDENCE = {
    "r25_3_1_2_sanitized_publication_zip_sha256": "0fbe92102f68629dc97b36b1984b656babae8c0e888b7e8e02fb83aa20437051",
    "r25_3_1_2_private_analysis_zip_sha256": "14601a69b0893b4af5d9c0e7d7ae25d8c11e9f01a204352bf7c661c67d04d6de",
    "r25_3_1_2_private_analysis_json_sha256": "61d27a19683207c1d68db733521a6f466ec9022a6b3a88dab7345609dcf34270",
    "r25_3_1_3_sanitized_publication_zip_sha256": "201f08a89751af6a446067331d42ae23e95a2c901e30af12dd73443099428bb5",
    "r25_3_1_3_private_analysis_zip_sha256": "c948f672813e13974b2d6997df0f40cb69991f0ce18268fdb1f1213f48217aa9",
    "r25_3_1_3_private_analysis_json_sha256": "ab7cc542a08bf3b6c5b83058950e78a29140275096923421e7fcd0871613d6ca",
    "r25_3_1_1_hci_qualification_diagnostic_sha256": "ec38cb56db37da46782b904e050e3ac80ee6caf33e4b1f7637ecbc0de33b54b6",
    "r25_3_1_1_rfcomm_error_locality_diagnostic_sha256": "15053f2f8e9444c97cff9374c5e795243e2cf2bd63e9253749b3bb19197ee073",
}

PUBLICATION_FILES = (
    Path("README.md"),
    Path("ARCHITECTURE.md"),
    Path("docs/project-status.md"),
    Path("docs/research/README.md"),
    Path("docs/research/connection-protocol/README.md"),
    Path("docs/findings/glasses-android-os-and-adb.md"),
    Path("docs/tests/test-matrix.md"),
    Path("evidence/README.md"),
    Path("evidence/manifests/README.md"),
    Path("evidence/sanitized/README.md"),
    Path("scripts/README.md"),
    Path("scripts/research/README.md"),
    *LINEAGE_SOURCE_HASHES.keys(),
    CANONICAL_VALIDATOR_PROFILE,
    *(entry["path"] for entry in HISTORICAL_VALIDATOR_LINEAGE.values()),
    *EXPECTED,
)

FORBIDDEN = {
    "absolute macOS user path": re.compile(r"/Users/[^\s`'\"]+"),
    "private workspace name": re.compile(r"rokid-nettest", re.I),
    "Bluetooth address": re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"),
    "device serial assignment": re.compile(r"(?:phone|device|glasses)_serial\s*[:=]\s*[A-Za-z0-9]{8,}", re.I),
    "raw payload field": re.compile(r"(?:payload_hex|raw_payload|payload_bytes_hex)\s*[:=]", re.I),
}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def parse_hashes(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected key=value")
        key, value = line.split("=", 1)
        if key in values or not HASH_RE.fullmatch(value):
            raise ValueError(f"{path}:{number}: invalid entry")
        values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    errors: list[str] = []

    for rel in EXPECTED:
        if not (repo / rel).is_file():
            errors.append(f"missing required file: {rel}")

    for rel in PUBLICATION_FILES:
        path = repo / rel
        if not path.is_file():
            errors.append(f"missing publication file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "\r" in text:
            errors.append(f"CR line ending: {rel}")
        if rel.name != "verify_r25_3_1_4_publication.py":
            for label, pattern in FORBIDDEN.items():
                if pattern.search(text):
                    errors.append(f"{label} found in {rel}")

    for rel, expected in LINEAGE_SOURCE_HASHES.items():
        path = repo / rel
        if not path.is_file():
            errors.append(f"missing lineage file: {rel}")
        elif digest(path) != expected:
            errors.append(f"lineage source hash mismatch: {rel}")

    try:
        registry = load_object(repo / CANONICAL_VALIDATOR_PROFILE)
        profiles = registry.get("profiles")
        if not isinstance(profiles, dict):
            errors.append("canonical r25 validator profile registry missing profiles")
        else:
            for revision, lineage in HISTORICAL_VALIDATOR_LINEAGE.items():
                profile = profiles.get(revision)
                if not isinstance(profile, dict):
                    errors.append(f"canonical validator profile missing: {revision}")
                    continue
                if profile.get("legacy_source_sha256") != lineage["historical_sha256"]:
                    errors.append(f"historical validator lineage hash mismatch in canonical profile: {revision}")
                if profile.get("retirement_state") != "COMPATIBILITY_SHIM":
                    errors.append(f"canonical validator retirement state mismatch: {revision}")
                shim_sha = profile.get("compatibility_shim_sha256")
                current_path = repo / lineage["path"]
                if not isinstance(shim_sha, str) or not HASH_RE.fullmatch(shim_sha):
                    errors.append(f"canonical validator shim hash missing: {revision}")
                elif not current_path.is_file() or digest(current_path) != shim_sha:
                    errors.append(f"canonical validator shim identity mismatch: {revision}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    for name, expected in SOURCE_RUNTIME_HASHES.items():
        path = repo / STOCK / name
        if path.is_file() and digest(path) != expected:
            errors.append(f"source runtime summary hash mismatch: {name}")

    try:
        r312 = load_object(repo / STOCK / "r25.3.1.2-runtime-status-summary.json")
        if r312.get("acceptance") != "PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE":
            errors.append("r25.3.1.2 acceptance mismatch")
        selected = r312.get("selected_hci_member")
        if not isinstance(selected, dict):
            errors.append("r25.3.1.2 selected_hci_member missing")
        else:
            expected = {
                "coverage": True,
                "drops": 0,
                "truncated_record_count": 0,
                "target_frame_count": 8,
                "payload_frame_count": 7,
                "target_rfcomm_parse_error_count": 0,
                "non_target_rfcomm_parse_error_count": 2,
                "non_target_rfcomm_errors_excluded_from_qualification": True,
            }
            for key, value in expected.items():
                if selected.get(key) != value:
                    errors.append(f"r25.3.1.2 selected_hci_member.{key} mismatch")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    try:
        r313 = load_object(repo / STOCK / "r25.3.1.3-runtime-status-summary.json")
        if r313.get("acceptance") != "PASS_EXISTING_CAPTURE_EXACT_ADB_TOGGLE_APPLICATION_FRAME_GRAMMAR_NESTED_LENGTH_SEQUENCE_DISCRIMINATOR_AND_STRUCTURED_PAYLOAD_ROLE_CLOSURE":
            errors.append("r25.3.1.3 acceptance mismatch")
        grammar = r313.get("grammar")
        if not isinstance(grammar, dict):
            errors.append("r25.3.1.3 grammar missing")
        else:
            if grammar.get("outer_total_length_encoding") != "u32be_self_inclusive":
                errors.append("outer length encoding mismatch")
            if grammar.get("nested_total_length_encoding") != "u32be_self_inclusive_from_nested_length_field":
                errors.append("nested length encoding mismatch")
            seq = grammar.get("sequence_candidate")
            if not isinstance(seq, dict) or seq.get("offset") != 12 or seq.get("steps_mod_256") != [1, 1, 1]:
                errors.append("sequence candidate mismatch")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    try:
        integrated = load_object(repo / STOCK / "runtime-status-summary.json")
        required = {
            "schema": "rokid.stock-adb-toggle-publication-status.v1",
            "release": "r1.3.3.2.25.3.1.4",
            "standing": "accepted_sanitized_publication_integration",
        }
        for key, value in required.items():
            if integrated.get(key) != value:
                errors.append(f"integrated {key} mismatch")
        boundaries = integrated.get("boundaries")
        if not isinstance(boundaries, dict):
            errors.append("integrated boundaries missing")
        else:
            for key in ("device_contact", "stock_toggle_attempted", "custom_transmission_attempted", "captured_payload_replay_attempted", "raw_payload_publication", "private_analysis_zip_included"):
                if boundaries.get(key) is not False:
                    errors.append(f"integrated boundary {key} must be false")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    try:
        primary = parse_hashes(repo / STOCK / "evidence-hashes.txt")
        mirror = parse_hashes(repo / "evidence/manifests/stock-adb-toggle-evidence-hashes.txt")
        if primary != mirror:
            errors.append("evidence hash mirror mismatch")
        for key, value in EXPECTED_EVIDENCE.items():
            if primary.get(key) != value:
                errors.append(f"evidence hash mismatch: {key}")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    snippets = {
        Path("ARCHITECTURE.md"): ("Exact observed stock ADB-toggle frame grammar",),
        Path("docs/project-status.md"): ("Stock ADB disable/restore semantics", "r25.3.1.3-runtime-status-summary.json"),
        Path("docs/research/connection-protocol/README.md"): ("Accepted stock ADB-toggle publication", "r25.3.1 semantic-oracle repair", "r25.3.1.1 operator-arm sequencing repair", "stock-adb-toggle/evidence-hashes.txt"),
        Path("docs/findings/glasses-android-os-and-adb.md"): ("Runtime stock-toggle semantics and observed message grammar",),
        Path("docs/tests/test-matrix.md"): ("r1.3.3.2.25.3.1.4", "r1.3.3.2.25.3.1.4.2"),
    }
    for rel, required in snippets.items():
        path = repo / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for snippet in required:
                if snippet not in text:
                    errors.append(f"missing snippet {snippet!r} in {rel}")

    # No private binary artifact may be committed. Prefer the Git-tracked set so
    # ignored Android build/Gradle outputs cannot create false publication failures.
    binary_suffixes = {".zip", ".img", ".apk", ".pcap", ".pcapng", ".bin"}
    tracked_paths: list[Path] = []
    try:
        import subprocess
        cp = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if cp.returncode == 0:
            tracked_paths = [repo / raw.decode("utf-8", errors="surrogateescape") for raw in cp.stdout.split(b"\0") if raw]
    except OSError:
        tracked_paths = []
    if not tracked_paths:
        ignored_parts = {".git", ".gradle", "build", "__pycache__"}
        tracked_paths = [p for p in repo.rglob("*") if p.is_file() and not any(part in ignored_parts for part in p.relative_to(repo).parts)]
    for path in tracked_paths:
        if path.suffix.lower() in binary_suffixes:
            errors.append(f"forbidden binary artifact in repository: {path.relative_to(repo)}")

    verifier = repo / "scripts/research/verify_r25_3_1_4_publication.py"
    if verifier.is_file():
        print(f"R25_3_1_4_VERIFIER_SHA256={digest(verifier)}")

    if errors:
        print("R25_3_1_4_PUBLICATION=FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"R25_3_1_4_PUBLICATION_FILE_COUNT={len(set(PUBLICATION_FILES))}")
    print("R25_3_1_2_TARGET_PAIR_QUALIFICATION=PASS")
    print("R25_3_1_3_EXACT_GRAMMAR_CLOSURE=PASS")
    print("R25_3_1_4_2_FULL_LINEAGE_SOURCE_HASHES=PASS")
    print("R25_3_1_4_CANONICAL_VALIDATOR_LINEAGE=PASS")
    print("R25_3_1_4_EVIDENCE_HASH_MIRROR=PASS")
    print("R25_3_1_4_PRIVATE_ANALYSIS_ZIP_INCLUDED=NO")
    print("R25_3_1_4_DEVICE_OPERATION=NONE")
    print("R25_3_1_4_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
