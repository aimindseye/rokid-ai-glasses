#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()

    run = args.run.expanduser().resolve()
    if not run.is_dir():
        raise SystemExit(f"ERROR: run directory not found: {run}")

    required = (
        run / "client-probe-private.jsonl",
        run / "phone-logcat-private.txt",
        run / "run-metadata-private.json",
        run / "analysis/r25.2.1-private-analysis.json",
        run / "publication/r25.2.1-power-state-attribution.json",
    )
    for path in required:
        if not path.is_file():
            raise SystemExit(f"ERROR: required run artifact missing: {path}")

    manifest = {}
    for path in sorted(run.rglob("*")):
        if path.is_file() and path.name not in {
            "SHA256SUMS-private.json",
        }:
            manifest[str(path.relative_to(run))] = {
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }

    manifest_path = run / "SHA256SUMS-private.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    archive = run.parent / f"{run.name}-private-evidence.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(run.rglob("*")):
            if path.is_file():
                output.write(path, arcname=f"{run.name}/{path.relative_to(run)}")

    archive_hash = sha256(archive)
    checksum = Path(str(archive) + ".sha256")
    checksum.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")

    print(f"R25_2_1_PRIVATE_MANIFEST={manifest_path}")
    print(f"R25_2_1_PRIVATE_ARCHIVE={archive}")
    print(f"R25_2_1_PRIVATE_ARCHIVE_SHA256={archive_hash}")
    print("R1_3_3_2_25_2_1_FINALIZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
