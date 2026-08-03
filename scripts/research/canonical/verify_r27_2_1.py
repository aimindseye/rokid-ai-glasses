#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

try:
    from primitives import sha256_file
    from r25_finalizer import load_profiles as load_finalizer_profiles
    from r25_publication_verifier import load_profiles as load_publication_profiles
except ImportError:
    from scripts.research.canonical.primitives import sha256_file
    from scripts.research.canonical.r25_finalizer import load_profiles as load_finalizer_profiles
    from scripts.research.canonical.r25_publication_verifier import load_profiles as load_publication_profiles

SHA_RE = re.compile(r"\b[0-9a-f]{64}\b")


def run_cmd(argv: list[str], *, cwd: Path, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def normalize_stdout(text: str) -> str:
    return SHA_RE.sub("<SHA256>", text)


def write_fixture_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, 0o644)
    os.utime(path, (1760000000, 1760000000))


def build_run_fixture(run: Path, profile: dict, *, missing_first_required: bool = False) -> None:
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    write_fixture_file(run / "alpha.txt", b"alpha\n")
    write_fixture_file(run / "nested/beta.bin", b"\x00beta\x01")
    required = list(profile.get("requirements", {}).get("required", []))
    optional = list(profile.get("requirements", {}).get("optional", []))
    for index, rel in enumerate(required):
        if missing_first_required and index == 0:
            continue
        payload = (json.dumps({"fixture": rel}, sort_keys=True) + "\n").encode("utf-8")
        if rel.endswith(".jsonl"):
            payload = b'{"fixture":true}\n'
        elif rel.endswith(".txt"):
            payload = b"fixture text\n"
        write_fixture_file(run / rel, payload)
    for rel in optional:
        write_fixture_file(run / rel, b"PK\x03\x04synthetic-optional")
    # Selective finalizers must prove that unrelated files are excluded.
    if profile["manifest"]["selection"] == "required_plus_optional":
        write_fixture_file(run / "unrelated/private-extra.txt", b"must not be archived\n")


def output_paths(run: Path, profile: dict) -> tuple[Path, Path, Path]:
    manifest = run / profile["manifest"]["filename"]
    archive = run.parent / f"{run.name}{profile['archive']['suffix']}"
    sidecar = Path(str(archive) + ".sha256")
    return manifest, archive, sidecar


def capture_outputs(run: Path, profile: dict) -> dict:
    manifest, archive, sidecar = output_paths(run, profile)
    result = {
        "manifest": manifest.read_bytes() if manifest.is_file() else None,
        "archive": archive.read_bytes() if archive.is_file() else None,
        "sidecar": sidecar.read_text(encoding="utf-8") if sidecar.is_file() else None,
        "members": {},
        "metadata": {},
    }
    if archive.is_file():
        with zipfile.ZipFile(archive) as z:
            result["members"] = {name: z.read(name) for name in z.namelist()}
            result["metadata"] = {
                info.filename: {
                    "compress_type": info.compress_type,
                    "external_attr": info.external_attr,
                    "create_system": info.create_system,
                    "flag_bits": info.flag_bits,
                    "date_time": info.date_time,
                }
                for info in z.infolist()
            }
    return result


def valid_sidecar(archive: Path, sidecar: Path) -> bool:
    if not archive.is_file() or not sidecar.is_file():
        return False
    parts = sidecar.read_text(encoding="utf-8").strip().split()
    return len(parts) >= 2 and parts[0] == sha256_file(archive) and parts[-1] == archive.name


def legacy_finalizer(repo: Path, profile: dict, run: Path):
    script = repo / profile["legacy_path"]
    return run_cmd(["python3", str(script), "--run", str(run)], cwd=repo)


def canonical_finalizer(repo: Path, profile: dict, run: Path):
    return run_cmd([
        str(repo / "scripts/rokid-research"), "--repo", str(repo), "connection", "finalize",
        "--revision", profile["revision"], "--run", str(run)
    ], cwd=repo)


def finalizer_equivalence(repo: Path, scratch: Path) -> list[dict]:
    rows = []
    for profile in load_finalizer_profiles():
        run = scratch / "finalizer" / profile["revision"].replace(".", "_") / "fixture-run"
        build_run_fixture(run, profile)
        legacy = legacy_finalizer(repo, profile, run)
        legacy_out = capture_outputs(run, profile) if legacy.returncode == 0 else {}
        _m, legacy_archive, legacy_sidecar = output_paths(run, profile)
        legacy_sidecar_valid = valid_sidecar(legacy_archive, legacy_sidecar)

        # Reset the same path so dynamic absolute paths in stdout remain equivalent.
        for path in (legacy_archive, legacy_sidecar):
            if path.exists(): path.unlink()
        build_run_fixture(run, profile)
        canonical = canonical_finalizer(repo, profile, run)
        canonical_out = capture_outputs(run, profile) if canonical.returncode == 0 else {}
        _m, canonical_archive, canonical_sidecar = output_paths(run, profile)
        canonical_sidecar_valid = valid_sidecar(canonical_archive, canonical_sidecar)

        stdout_equal = normalize_stdout(legacy.stdout) == normalize_stdout(canonical.stdout)
        manifest_equal = legacy_out.get("manifest") == canonical_out.get("manifest")
        members_equal = legacy_out.get("members") == canonical_out.get("members")
        legacy_meta = deepcopy(legacy_out.get("metadata", {}))
        canonical_meta = deepcopy(canonical_out.get("metadata", {}))
        manifest_member = f"{run.name}/{profile['manifest']['filename']}"
        if profile["archive"]["zip_mode"] == "source_metadata":
            # Generated manifest write-time is intentionally not an identity contract.
            if manifest_member in legacy_meta: legacy_meta[manifest_member].pop("date_time", None)
            if manifest_member in canonical_meta: canonical_meta[manifest_member].pop("date_time", None)
        metadata_equal = legacy_meta == canonical_meta
        # Only the base r25 finalizer promises deterministic whole-container identity.
        if profile["archive"]["zip_mode"] == "r25_deterministic_tree":
            archive_exact_required = legacy_out.get("archive") == canonical_out.get("archive")
            archive_exact_field = "YES" if archive_exact_required else "NO"
        else:
            archive_exact_required = True
            archive_exact_field = "NA"

        required_negative = "NA"
        if profile.get("requirements", {}).get("required"):
            for path in (canonical_archive, canonical_sidecar):
                if path.exists(): path.unlink()
            build_run_fixture(run, profile, missing_first_required=True)
            legacy_bad = legacy_finalizer(repo, profile, run)
            for path in (canonical_archive, canonical_sidecar):
                if path.exists(): path.unlink()
            build_run_fixture(run, profile, missing_first_required=True)
            canonical_bad = canonical_finalizer(repo, profile, run)
            required_negative = "YES" if legacy_bad.returncode != 0 and canonical_bad.returncode != 0 else "NO"

        equivalent = (
            legacy.returncode == 0 and canonical.returncode == 0 and stdout_equal and manifest_equal and members_equal and
            metadata_equal and archive_exact_required and legacy_sidecar_valid and canonical_sidecar_valid and required_negative != "NO"
        )
        rows.append({
            "revision": profile["revision"],
            "legacy_rc": legacy.returncode,
            "canonical_rc": canonical.returncode,
            "stdout_equivalent": "YES" if stdout_equal else "NO",
            "manifest_equivalent": "YES" if manifest_equal else "NO",
            "zip_members_equivalent": "YES" if members_equal else "NO",
            "zip_metadata_equivalent": "YES" if metadata_equal else "NO",
            "whole_zip_exact_when_deterministic": archive_exact_field,
            "legacy_sidecar_valid": "YES" if legacy_sidecar_valid else "NO",
            "canonical_sidecar_valid": "YES" if canonical_sidecar_valid else "NO",
            "required_file_rejection_equivalent": required_negative,
            "equivalent": "YES" if equivalent else "NO",
        })
    return rows


def valid_publication(revision: str) -> dict:
    if revision == "r25.1":
        return {
            "closure": {
                "ble_to_rfcomm_bootstrap_attributed": True,
                "sdp_service_channel_attributed": True,
                "rfcomm_scn_dlci_reconstructed": True,
                "stock_session_establishment_sequence_closed": True,
                "application_message_framing_closed": False,
                "session_authentication_semantics_closed": False,
                "independent_client_rfcomm_session_implemented": False,
                "developer_mode_remote_invocation_closed": False,
            },
            "rfcomm_session": {"sdp_server_channel": 3, "dlci": 6, "mtu": 990},
            "public_safety": {
                "raw_hci_published": False,
                "bluetooth_address_published": False,
                "runtime_uuid_published": False,
                "account_material_published": False,
            },
            "allowed_service_uuid": "00009301-0000-1000-8000-00805f9b34fb",
        }
    if revision == "r25.2":
        return {
            "schema": "rokid.r25.2.connection-only-public.v1",
            "runtime_uuid_published": False,
            "classic_address_published": False,
            "account_material_published": False,
            "application_payload_reads": 0,
            "application_payload_writes": 0,
        }
    if revision == "r25.2.1":
        return {
            "schema": "rokid.r25.2.1.publication.v1",
            "release": "r1.3.3.2.25.2.1",
            "private_device_ids_published": False,
            "private_fingerprint_hashes_published": False,
            "raw_advertisement_bytes_published": False,
            "raw_bluetooth_addresses_published": False,
            "capture_model": {
                "gatt_attempted": False,
                "rfcomm_attempted": False,
                "application_payload_reads": 0,
                "application_payload_writes": 0,
            },
        }
    if revision == "r25.2.2":
        return {
            "endpoint_address_published": False,
            "public_safety": {"correlation_key_published": False},
            "connection_boundary": {"probe_gatt_attempted": False, "probe_rfcomm_attempted": False},
        }
    if revision == "r25.2.2.1":
        return {
            "runtime_address_published": False,
            "runtime_uuid_published": False,
            "connection_boundary": {
                "offline_reanalysis_only": True,
                "independent_gatt_attempted": False,
                "independent_rfcomm_attempted": False,
                "automatic_connection_performed": False,
                "application_payload_reads": 0,
                "application_payload_writes": 0,
                "developer_mode_action_performed": False,
            },
        }
    if revision == "r25.2.2.2":
        return {
            "endpoint": {"address_published": False, "runtime_uuid_published": False},
            "connection_boundary": {
                "application_payload_reads": 0,
                "application_payload_writes": 0,
                "application_data_streams_obtained": False,
                "independent_gatt_attempted": False,
            },
        }
    raise KeyError(revision)


def set_dotted(value: dict, dotted: str, replacement) -> None:
    cur = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = replacement


def legacy_publication(repo: Path, profile: dict, publication: Path):
    return run_cmd(["python3", str(repo / profile["legacy_path"]), "--publication", str(publication)], cwd=repo)


def canonical_publication(repo: Path, profile: dict, publication: Path):
    return run_cmd([
        str(repo / "scripts/rokid-research"), "--repo", str(repo), "connection", "verify-publication",
        "--revision", profile["revision"], "--publication", str(publication)
    ], cwd=repo)


def publication_equivalence(repo: Path, scratch: Path) -> list[dict]:
    rows = []
    for profile in load_publication_profiles():
        directory = scratch / "publication" / profile["revision"].replace(".", "_")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "publication.json"
        good = valid_publication(profile["revision"])
        path.write_text(json.dumps(good, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        legacy = legacy_publication(repo, profile, path)
        canonical = canonical_publication(repo, profile, path)
        stdout_equal = legacy.stdout == canonical.stdout

        bad_privacy = deepcopy(good)
        bad_privacy["privacy_probe"] = "AA:BB:CC:DD:EE:FF"
        path.write_text(json.dumps(bad_privacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        legacy_privacy = legacy_publication(repo, profile, path)
        canonical_privacy = canonical_publication(repo, profile, path)
        privacy_equal = legacy_privacy.returncode != 0 and canonical_privacy.returncode != 0

        bad_semantic = deepcopy(good)
        first_path, expected = profile["equals"][0]
        replacement = (not expected) if isinstance(expected, bool) else (expected + 1 if isinstance(expected, int) else "WRONG")
        set_dotted(bad_semantic, first_path, replacement)
        path.write_text(json.dumps(bad_semantic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        legacy_semantic = legacy_publication(repo, profile, path)
        canonical_semantic = canonical_publication(repo, profile, path)
        semantic_equal = legacy_semantic.returncode != 0 and canonical_semantic.returncode != 0

        extra_privacy = True
        if profile["revision"] == "r25.1":
            bad = deepcopy(good); bad["blob"] = "A" * 40 + "="
            path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            extra_privacy = legacy_publication(repo, profile, path).returncode != 0 and canonical_publication(repo, profile, path).returncode != 0
        elif profile["revision"] == "r25.2.1":
            bad = deepcopy(good); bad["device_id"] = "synthetic"
            path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            extra_privacy = legacy_publication(repo, profile, path).returncode != 0 and canonical_publication(repo, profile, path).returncode != 0

        equivalent = legacy.returncode == 0 and canonical.returncode == 0 and stdout_equal and privacy_equal and semantic_equal and extra_privacy
        rows.append({
            "revision": profile["revision"],
            "legacy_rc": legacy.returncode,
            "canonical_rc": canonical.returncode,
            "stdout_equivalent": "YES" if stdout_equal else "NO",
            "privacy_rejection_equivalent": "YES" if privacy_equal else "NO",
            "semantic_rejection_equivalent": "YES" if semantic_equal else "NO",
            "special_privacy_rejection_equivalent": "YES" if extra_privacy else "NO",
            "equivalent": "YES" if equivalent else "NO",
        })
    return rows


def source_locks(repo: Path) -> list[dict]:
    rows = []
    for family, profiles in (("finalizer", load_finalizer_profiles()), ("publication-verifier", load_publication_profiles())):
        for profile in profiles:
            path = repo / profile["legacy_path"]
            actual = sha256_file(path) if path.is_file() else ""
            rows.append({
                "family": family,
                "revision": profile["revision"],
                "path": profile["legacy_path"],
                "expected_sha256": profile["legacy_sha256"],
                "actual_sha256": actual,
                "locked": "YES" if actual == profile["legacy_sha256"] else "NO",
            })
    return rows


def write_tsv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.expanduser().resolve(); output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    locks = source_locks(repo)
    with tempfile.TemporaryDirectory(prefix="r2721-") as tmp:
        scratch = Path(tmp)
        with ThreadPoolExecutor(max_workers=2) as pool:
            final_future = pool.submit(finalizer_equivalence, repo, scratch)
            publication_future = pool.submit(publication_equivalence, repo, scratch)
            finalizers = final_future.result()
            publications = publication_future.result()
    write_tsv(output / "source-locks.tsv", locks)
    write_tsv(output / "finalizer-equivalence.tsv", finalizers)
    write_tsv(output / "publication-verifier-equivalence.tsv", publications)

    source_fail = sum(row["locked"] != "YES" for row in locks)
    final_eq = sum(row["equivalent"] == "YES" for row in finalizers)
    pub_eq = sum(row["equivalent"] == "YES" for row in publications)
    summary = {
        "schema": "rokid.r27.2.1.r25-finalization-publication-equivalence.v1",
        "status": "PASS" if source_fail == 0 and final_eq == 7 and pub_eq == 6 else "FAIL",
        "target_member_count": 13,
        "finalizer_profile_count": len(finalizers),
        "finalizer_equivalent_count": final_eq,
        "publication_verifier_profile_count": len(publications),
        "publication_verifier_equivalent_count": pub_eq,
        "legacy_source_changed_count": source_fail,
        "historical_file_action": "NONE",
        "repository_deletion": "NONE",
        "device_operation": "NONE",
        "privileged_operation": "NONE",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("R27_2_1_EQUIVALENCE=" + summary["status"])
    print(f"R25_FINALIZER_PROFILE_COUNT={len(finalizers)}")
    print(f"R25_FINALIZER_EQUIVALENT_COUNT={final_eq}")
    print(f"R25_PUBLICATION_VERIFIER_PROFILE_COUNT={len(publications)}")
    print(f"R25_PUBLICATION_VERIFIER_EQUIVALENT_COUNT={pub_eq}")
    print(f"LEGACY_SOURCE_CHANGED_COUNT={source_fail}")
    print("HISTORICAL_FILE_ACTION=NONE")
    print("REPOSITORY_DELETION=NONE")
    print("DEVICE_OPERATION=NONE")
    print("PRIVILEGED_OPERATION=NONE")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
