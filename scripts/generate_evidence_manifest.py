#!/usr/bin/env python3
"""Create a public hash-only manifest for private evidence files."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    records = []
    for candidate in args.files:
        path = candidate.resolve()
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.name
        records.append({
            "relative_path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "classification": "private-hash-only",
        })
    if not records:
        raise SystemExit("No manifest input files were found")
    payload = {
        "schema": "rokid.private-evidence-manifest.v1",
        "test_id": args.test_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(records, key=lambda item: item["relative_path"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest entries: {len(records)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
