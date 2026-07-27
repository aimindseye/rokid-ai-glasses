#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REQUIRED = (
    "analysis/r25.2.2.1-private-analysis.json",
    "publication/r25.2.2.1-cached-runtime-attribution.json",
    "handoff/r25.2.2.1-connection-only-handoff-private.json",
    "source-lineage-private.json",
)


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
    for relative in REQUIRED:
        path = run / relative
        if not path.is_file():
            raise SystemExit(f"ERROR: required derived evidence missing: {relative}")
        records.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        })

    manifest = {
        "schema": "rokid.r25.2.2.1.private-evidence-manifest.v1",
        "release": "r1.3.3.2.25.2.2.1",
        "files": records,
    }
    manifest_path = run / "SHA256SUMS-private.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    archive = Path(str(run) + "-private-evidence.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative in REQUIRED + ("SHA256SUMS-private.json",):
            output.write(run / relative, run.name + "/" + relative)

    checksum = digest(archive)
    Path(str(archive) + ".sha256").write_text(
        f"{checksum}  {archive.name}\n",
        encoding="utf-8",
    )
    print(f"R25_2_2_1_PRIVATE_EVIDENCE_ZIP={archive}")
    print(f"R25_2_2_1_PRIVATE_EVIDENCE_SHA256={checksum}")
    print("R25_2_2_1_FINALIZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
