#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REQUIRED = (
    "input/r25.2.2.2-connection-only-input-private.json",
    "client-probe-private.jsonl",
    "phone-logcat-private.txt",
    "run-metadata-private.json",
    "analysis/r25.2.2.2-private-analysis.json",
    "publication/r25.2.2.2-connection-only-qualification.json",
)
OPTIONAL = ("phone-bugreport-private.zip",)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.expanduser().resolve()

    records = []
    included = list(REQUIRED)
    for relative in OPTIONAL:
        if (run / relative).is_file():
            included.append(relative)
    for relative in included:
        path = run / relative
        if not path.is_file():
            raise SystemExit(f"ERROR: required evidence missing: {relative}")
        records.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        })

    manifest = {
        "schema": "rokid.r25.2.2.2.private-evidence-manifest.v1",
        "release": "r1.3.3.2.25.2.2.2",
        "files": records,
    }
    manifest_path = run / "SHA256SUMS-private.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    archive = Path(str(run) + "-private-evidence.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative in tuple(included) + ("SHA256SUMS-private.json",):
            output.write(run / relative, run.name + "/" + relative)
    checksum = digest(archive)
    Path(str(archive) + ".sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"R25_2_2_2_PRIVATE_EVIDENCE_ZIP={archive}")
    print(f"R25_2_2_2_PRIVATE_EVIDENCE_SHA256={checksum}")
    print("R25_2_2_2_FINALIZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
