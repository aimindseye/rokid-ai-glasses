#!/usr/bin/env python3
"""Verify a sha256sum-style manifest rooted at a repository directory."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("--root", type=Path, default=Path.cwd())
    args = p.parse_args()

    root = args.root.resolve()
    manifest = args.manifest.resolve()
    failures: list[str] = []
    checked = 0

    for line_no, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, rel = line.split(None, 1)
        except ValueError:
            failures.append(f"line {line_no}: malformed")
            continue
        rel = rel.lstrip("*")
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            failures.append(f"line {line_no}: path escapes root: {rel}")
            continue
        if not path.is_file():
            failures.append(f"missing: {rel}")
            continue
        actual = sha256(path)
        checked += 1
        if actual != expected.lower():
            failures.append(f"hash mismatch: {rel}: {actual} != {expected}")

    if failures:
        print("PUBLIC_MANIFEST=FAIL")
        for failure in failures:
            print(f"ERROR {failure}")
        return 1
    print(f"PUBLIC_MANIFEST_ENTRY_COUNT={checked}")
    print("PUBLIC_MANIFEST=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
