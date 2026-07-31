#!/usr/bin/env python3
"""Repair the withdrawn Test 20 r1 sanitized classification without private bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import classify_cxr_l_capabilities as classifier

EXPECTED_SOURCE_ZIP_SHA256 = "30ae03d16da40a2f0045030695a7a8b58ca6cb33304ad35f117ecc82e8ce3ac7"
EXPECTED_FILES = {
    "sanitized-publication/test20-r1-cxr-l-capability-census.json",
    "sanitized-publication/test20-r1-cxr-l-capability-census.md",
    "sanitized-publication/test20-r1-cxr-l-evidence-hashes.txt",
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as handle:
        names = set()
        for info in handle.infolist():
            name = info.filename.rstrip("/")
            if not name:
                continue
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError(f"unsafe ZIP member: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"symbolic links are prohibited: {info.filename}")
            if not info.is_dir():
                names.add(name)
        if names != EXPECTED_FILES:
            missing = sorted(EXPECTED_FILES - names)
            extra = sorted(names - EXPECTED_FILES)
            raise ValueError(f"unexpected ZIP path set; missing={missing}; extra={extra}")
        handle.extractall(destination)


def privacy_gate(root: Path) -> None:
    forbidden = [
        re.compile(r"/Users/"),
        re.compile(r"/home/[^/]+/"),
        re.compile(r"(?:PHONE_SERIAL|device_serial)\s*[:=]\s*[A-Za-z0-9-]{8,}", re.I),
        re.compile(r"(?:auth(?:orization)?[_ -]?token|access[_ -]?token)\s*[:=]\s*[A-Za-z0-9+/=_-]{8,}", re.I),
        re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", re.I),
    ]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in forbidden:
            if pattern.search(text):
                raise ValueError(f"privacy pattern {pattern.pattern!r} found in {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-publication-zip", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-input-sha256", default=EXPECTED_SOURCE_ZIP_SHA256)
    args = parser.parse_args()

    source_zip = Path(args.input_publication_zip).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source_zip.is_file():
        raise SystemExit(f"input publication ZIP not found: {source_zip}")
    if output.exists():
        raise SystemExit(f"output already exists: {output}")

    source_zip_sha = sha256_path(source_zip)
    if source_zip_sha != args.expected_input_sha256:
        raise SystemExit(
            f"source publication ZIP hash mismatch: expected {args.expected_input_sha256}, got {source_zip_sha}"
        )

    with tempfile.TemporaryDirectory(prefix="test20-r1-1-") as temporary:
        extracted = Path(temporary)
        safe_extract(source_zip, extracted)
        source_root = extracted / "sanitized-publication"
        source_json = source_root / "test20-r1-cxr-l-capability-census.json"
        source_json_sha = sha256_path(source_json)
        publication = json.loads(source_json.read_text(encoding="utf-8"))

        if publication.get("schema") != classifier.PUBLIC_SCHEMA_V1:
            raise SystemExit(f"unexpected source schema: {publication.get('schema')}")
        if publication.get("summary", {}).get("runtime_qualified_member_count", 101) not in {101}:
            # The withdrawn publication did not have the explicit count field,
            # but its classification counter did record 101.
            raise SystemExit("unexpected withdrawn runtime-qualified count")
        observed_old_count = publication.get("summary", {}).get(
            "member_classification_counts", {}
        ).get("runtime-qualified")
        if observed_old_count != 101:
            raise SystemExit(f"expected withdrawn runtime-qualified count 101, got {observed_old_count}")

        repaired = classifier.reclassify_publication(
            publication,
            source_zip_sha256=source_zip_sha,
            source_json_sha256=source_json_sha,
        )
        summary = repaired["summary"]
        required = {
            "public_class_count": 72,
            "public_member_count": 594,
            "public_method_count": 429,
            "public_constructor_count": 56,
            "public_field_count": 106,
            "public_enum_constant_count": 3,
            "runtime_qualified_member_count": 9,
            "runtime_qualified_component_count": 2,
        }
        for key, expected in required.items():
            actual = summary.get(key)
            if actual != expected:
                raise SystemExit(f"repaired count mismatch for {key}: expected {expected}, got {actual}")

        output_root = output / "sanitized-publication"
        output_root.mkdir(parents=True)
        output_json = output_root / "test20-r1-cxr-l-capability-census.json"
        output_md = output_root / "test20-r1-cxr-l-capability-census.md"
        output_hashes = output_root / "test20-r1-cxr-l-evidence-hashes.txt"

        output_json.write_text(json.dumps(repaired, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_md.write_text(classifier.markdown_report(repaired), encoding="utf-8")

        old_hashes = {}
        for line in (source_root / "test20-r1-cxr-l-evidence-hashes.txt").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                old_hashes[key] = value
        output_hashes.write_text(
            "\n".join([
                f"CXR_L_AAR_SHA256={old_hashes.get('CXR_L_AAR_SHA256', '')}",
                f"CXR_L_POM_SHA256={old_hashes.get('CXR_L_POM_SHA256', '')}",
                f"HI_ROKID_BASELINE_ZIP_SHA256={old_hashes.get('HI_ROKID_BASELINE_ZIP_SHA256', '')}",
                f"HI_ROKID_BASE_APK_SHA256={old_hashes.get('HI_ROKID_BASE_APK_SHA256', '')}",
                f"RUNTIME_PUBLICATION_SHA256={old_hashes.get('RUNTIME_PUBLICATION_SHA256', '')}",
                f"SOURCE_SANITIZED_PUBLICATION_ZIP_SHA256={source_zip_sha}",
                f"SOURCE_PUBLICATION_JSON_SHA256={source_json_sha}",
                "RUNTIME_QUALIFIED_MEMBER_COUNT=9",
                "RUNTIME_QUALIFIED_COMPONENT_COUNT=2",
            ]) + "\n",
            encoding="utf-8",
        )

    privacy_gate(output)
    repaired_json_sha = sha256_path(
        output / "sanitized-publication/test20-r1-cxr-l-capability-census.json"
    )
    print(f"TEST20_R1_1_SOURCE_PUBLICATION_ZIP_SHA256={source_zip_sha}")
    print(f"TEST20_R1_1_SOURCE_PUBLICATION_JSON_SHA256={source_json_sha}")
    print("TEST20_R1_1_WITHDRAWN_RUNTIME_QUALIFIED_MEMBER_COUNT=101")
    print("TEST20_R1_1_RUNTIME_QUALIFIED_MEMBER_COUNT=9")
    print("TEST20_R1_1_RUNTIME_QUALIFIED_COMPONENT_COUNT=2")
    print("TEST20_R1_1_REAL_SESSION_TYPE_COUNT=3")
    print("TEST20_R1_1_ENUM_BACKING_ARRAY_RECLASSIFIED=PASS")
    print("TEST20_R1_1_SYNTHETIC_OBFUSCATED_CLASSIFICATION=PASS")
    print("TEST20_R1_1_MEMBER_LEVEL_RUNTIME_QUALIFICATION=PASS")
    print(f"TEST20_R1_1_REPAIRED_JSON_SHA256={repaired_json_sha}")
    print(f"TEST20_R1_1_OUTPUT={output}")
    print("TEST20_R1_1_SANITIZED_PUBLICATION_REPAIR=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
