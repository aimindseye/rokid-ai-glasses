#!/usr/bin/env python3
"""Fail-closed privacy and content gate for native-loader public files."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DENIED_SUFFIXES = {".apk", ".so", ".dex", ".pcap", ".pcapng", ".keylog", ".bin", ".img"}
DENIED_NAMES = {"events.jsonl", "logcat.txt", "tombstone.txt", "compiled-agent.js"}
PATTERNS = {
    "device serial": re.compile(r"\b[A-Z0-9]{14,20}\b"),
    "raw absolute pointer": re.compile(r"\b0x[0-9a-fA-F]{10,16}\b"),
    "bearer token": re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".sh", ".ts", ".mmd", ".yaml", ".yml"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    failures: list[str] = []
    checked = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        checked += 1
        if path.suffix.lower() in DENIED_SUFFIXES or path.name in DENIED_NAMES:
            failures.append(f"denied artifact: {rel}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # Hash provenance lines naturally contain long hexadecimal strings; those
        # are allowed. The pointer pattern only targets a 0x prefix.
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{label}: {rel}")

    if failures:
        print("PUBLIC_PRIVACY_GATE=FAIL")
        for failure in failures:
            print(f"ERROR {failure}")
        return 1
    print(f"PUBLIC_FILE_COUNT={checked}")
    print("PUBLIC_PRIVACY_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
