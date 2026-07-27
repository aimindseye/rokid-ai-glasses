#!/usr/bin/env python3
import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    files = [path for path in sorted(run.rglob("*")) if path.is_file() and path.name != "SHA256SUMS-private.json"]
    manifest = {
        str(path.relative_to(run)): {"size": path.stat().st_size, "sha256": sha256(path)}
        for path in files
    }
    (run / "SHA256SUMS-private.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = run.parent / f"{run.name}-private-evidence.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run.rglob("*")):
            if path.is_file():
                archive.write(path, Path(run.name) / path.relative_to(run))
    digest = sha256(output)
    Path(str(output) + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"R25_2_2_PRIVATE_EVIDENCE_ZIP={output}")
    print(f"R25_2_2_PRIVATE_EVIDENCE_SHA256={digest}")
    print("R25_2_2_FINALIZE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
