#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import uuid
import zipfile

RELEASE = "r1.3.3.2.25.2.2.2"
SOURCE_RELEASE = "r1.3.3.2.25.2.2.1"
SOURCE_HANDOFF_SCHEMA = "rokid.r25.2.2.1.connection-only-handoff-private.v1"
INPUT_SCHEMA = "rokid.r25.2.2.2.connection-only-input-private.v1"
EXPECTED_ACCEPTANCE = (
    "PASS_UNIQUE_CACHED_RUNTIME_ENDPOINT_ATTRIBUTED_"
    "CONNECTION_ONLY_HANDOFF_READY"
)
ADDRESS_RE = re.compile(r"(?i)^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_members(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe ZIP member: {info.filename}")
        if info.is_dir():
            continue
        names.append(info.filename)
    return names


def verify_private_zip(path: Path) -> tuple[dict, dict, str, str]:
    archive_sha = digest_bytes(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        names = safe_members(archive)
        manifests = [name for name in names if name.endswith("/SHA256SUMS-private.json")]
        if len(manifests) != 1:
            raise ValueError("expected exactly one private manifest")
        manifest = json.loads(archive.read(manifests[0]))
        prefix = manifests[0].rsplit("/", 1)[0] + "/"
        for record in manifest.get("files", []):
            relative = record.get("path")
            member = prefix + str(relative)
            if member not in names:
                raise ValueError(f"manifest member missing: {relative}")
            raw = archive.read(member)
            if len(raw) != record.get("size_bytes"):
                raise ValueError(f"size mismatch: {relative}")
            if digest_bytes(raw) != record.get("sha256"):
                raise ValueError(f"hash mismatch: {relative}")

        handoffs = [
            name for name in names
            if name.endswith("/handoff/r25.2.2.1-connection-only-handoff-private.json")
        ]
        analyses = [
            name for name in names
            if name.endswith("/analysis/r25.2.2.1-private-analysis.json")
        ]
        if len(handoffs) != 1 or len(analyses) != 1:
            raise ValueError("required r25.2.2.1 evidence files missing")
        handoff_raw = archive.read(handoffs[0])
        analysis_raw = archive.read(analyses[0])
        return (
            json.loads(handoff_raw),
            json.loads(analysis_raw),
            digest_bytes(handoff_raw),
            archive_sha,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-private-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.source_private_zip.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"ERROR: source private ZIP not found: {source}")

    try:
        handoff, analysis, handoff_sha, source_zip_sha = verify_private_zip(source)
    except Exception as exc:
        raise SystemExit(f"ERROR: private ZIP verification failed: {exc}") from exc

    if handoff.get("schema") != SOURCE_HANDOFF_SCHEMA:
        raise SystemExit("ERROR: unexpected source handoff schema")
    if handoff.get("release") != SOURCE_RELEASE:
        raise SystemExit("ERROR: unexpected source handoff release")
    if analysis.get("acceptance") != EXPECTED_ACCEPTANCE:
        raise SystemExit("ERROR: source analysis acceptance is not handoff-ready")
    if handoff.get("available") is not True:
        raise SystemExit("ERROR: private handoff unavailable")
    if handoff.get("ready_for_independent_connection_only_qualification") is not True:
        raise SystemExit("ERROR: source handoff is not connection-only ready")
    if handoff.get("application_payload_operation_authorized") is not False:
        raise SystemExit("ERROR: payload operation authorization must be false")
    if handoff.get("automatic_connection_performed") is not False:
        raise SystemExit("ERROR: source handoff reports an automatic connection")
    if handoff.get("endpoint_type") != "cached_classic_runtime_endpoint":
        raise SystemExit("ERROR: source endpoint is not cached Classic runtime")

    address = str(handoff.get("runtime_address", "")).upper()
    if not ADDRESS_RE.fullmatch(address) or address in {
        "00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"
    }:
        raise SystemExit("ERROR: invalid runtime address")
    try:
        runtime_uuid = str(uuid.UUID(str(handoff.get("runtime_uuid")))).lower()
    except ValueError as exc:
        raise SystemExit("ERROR: invalid runtime UUID") from exc

    address_sha = digest_bytes(address.encode("utf-8"))
    uuid_sha = digest_bytes(runtime_uuid.encode("utf-8"))
    binding_sha = digest_bytes(f"{address}|{runtime_uuid}".encode("utf-8"))
    for key, actual in (
        ("runtime_address_sha256", address_sha),
        ("runtime_uuid_sha256", uuid_sha),
        ("endpoint_binding_sha256", binding_sha),
    ):
        if handoff.get(key) != actual:
            raise SystemExit(f"ERROR: source handoff {key} mismatch")

    rfcomm = handoff.get("rfcomm")
    if not isinstance(rfcomm, dict):
        raise SystemExit("ERROR: source RFCOMM contract missing")
    if not (
        rfcomm.get("client") is True
        and rfcomm.get("scn") == 3
        and rfcomm.get("dlci") == 6
        and rfcomm.get("mtu") == 990
    ):
        raise SystemExit("ERROR: source RFCOMM contract is not SCN3/DLCI6/MTU990")

    value = {
        "schema": INPUT_SCHEMA,
        "release": RELEASE,
        "source_release": SOURCE_RELEASE,
        "source_acceptance": EXPECTED_ACCEPTANCE,
        "source_handoff_schema": SOURCE_HANDOFF_SCHEMA,
        "source_private_zip_sha256": source_zip_sha,
        "source_handoff_sha256": handoff_sha,
        "endpoint_type": "cached_classic_runtime_endpoint",
        "runtime_address": address,
        "runtime_address_sha256": address_sha,
        "runtime_uuid": runtime_uuid,
        "runtime_uuid_sha256": uuid_sha,
        "endpoint_binding_sha256": binding_sha,
        "expected_rfcomm": {
            "client": True,
            "scn": 3,
            "dlci": 6,
            "mtu": 990,
        },
        "ready_for_independent_connection_only_qualification": True,
        "application_payload_operation_authorized": False,
        "automatic_connection_performed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.chmod(stat.S_IRUSR | stat.S_IWUSR)

    print(f"R25_2_2_2_SOURCE_PRIVATE_ZIP_SHA256={source_zip_sha}")
    print(f"R25_2_2_2_SOURCE_HANDOFF_SHA256={handoff_sha}")
    print("R25_2_2_2_SOURCE_HANDOFF_AVAILABLE=YES")
    print("R25_2_2_2_SOURCE_RFCOMM_SCN=3")
    print("R25_2_2_2_SOURCE_RFCOMM_DLCI=6")
    print("R25_2_2_2_SOURCE_RFCOMM_MTU=990")
    print("R25_2_2_2_APPLICATION_PAYLOAD_AUTHORIZED=NO")
    print("R25_2_2_2_HANDOFF_PREPARE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
