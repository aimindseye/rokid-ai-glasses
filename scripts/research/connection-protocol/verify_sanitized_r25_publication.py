#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FORBIDDEN = [
    re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~-]+"),
    re.compile(r"(?i)(access_token|refresh_token|authorization|cookie)\s*[:=]"),
    re.compile(r"/Users/[^/\s]+"),
    re.compile(r"/home/[^/\s]+"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    files = [path for path in args.publication.rglob("*") if path.is_file()]
    if not files:
        raise SystemExit("publication is empty")
    for path in files:
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                raise SystemExit(f"forbidden public content in {path}: {pattern.pattern}")
        if "payload_sha256" in text or "device_id" in text:
            raise SystemExit(f"private correlation identifier present in {path}")
    print(f"R25_PUBLICATION_FILE_COUNT={len(files)}")
    print("R1_3_3_2_25_SANITIZED_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
