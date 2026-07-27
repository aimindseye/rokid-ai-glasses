#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from r25lib import manifest, safe_zip_tree, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.expanduser().resolve()
    manifest_path = run / "SHA256SUMS-private-final.json"
    rows = manifest(run, manifest_path, exclude=[manifest_path])
    output = run.parent / f"{run.name}-private-evidence.zip"
    safe_zip_tree(run, output)
    digest = sha256_file(output)
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"R1_3_3_2_25_PRIVATE_MANIFEST_COUNT={len(rows)}")
    print(f"R1_3_3_2_25_PRIVATE_EVIDENCE_ZIP={output}")
    print(f"R1_3_3_2_25_PRIVATE_EVIDENCE_SHA256={digest}")
    print("R1_3_3_2_25_FINALIZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
