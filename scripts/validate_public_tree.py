#!/usr/bin/env python3
"""Fail when the public Git tree contains private evidence or secrets."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

FORBIDDEN_SUFFIXES = {
    ".pcap", ".pcapng", ".sslkeylog", ".har", ".mitm", ".apk", ".apks",
    ".aab", ".p12", ".pfx", ".key",
}
FORBIDDEN_NAME_PARTS = ("btsnoop", "bugreport", "sslkeylogfile")
SKIP_DIRS = {".git", ".delivery-backups", "__pycache__"}
TEXT_SUFFIXES = {"", ".md", ".txt", ".tsv", ".csv", ".json", ".py", ".sh", ".example", ".gitignore"}

PATTERNS = [
    ("authorization token", re.compile(r"(?im)^Authorization:\s*(?:Bearer\s+)?(?!\[REDACTED\]\s*$)\S.{7,}$")),
    ("account token", re.compile(r"(?im)^(?:X-Account-Token|access_token|rokidToken):\s*(?!\[REDACTED\]\s*$)\S.{7,}$")),
    ("account identifier", re.compile(r"(?im)^account-id:\s*(?!\[REDACTED\]\s*$)\S.{5,}$")),
    ("device serial", re.compile(r"(?im)^X-Device-SN:\s*(?!\[REDACTED\]\s*$)\S.{5,}$")),
    ("OAuth secret query value", re.compile(r"(?i)clientSecret=(?!\[REDACTED\])[^&\s]{6,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("TLS keylog secret", re.compile(r"(?m)^(?:CLIENT_RANDOM|CLIENT_HANDSHAKE_TRAFFIC_SECRET|SERVER_HANDSHAKE_TRAFFIC_SECRET|CLIENT_TRAFFIC_SECRET_0|SERVER_TRAFFIC_SECRET_0)\s+[0-9A-Fa-f]{16,}")),
    ("Bluetooth MAC", re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")),
]

PRIVATE_IPV4 = re.compile(r"(?<!\d)(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?!\d)")


def iter_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        current_path = Path(current)
        for name in files:
            yield current_path / name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    problems: list[str] = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        lower = path.name.lower()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden file type: {rel}")
            continue
        if any(part in lower for part in FORBIDDEN_NAME_PARTS):
            problems.append(f"forbidden private-evidence filename: {rel}")
            continue
        if path.stat().st_size > 8 * 1024 * 1024:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".env.example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel != "scripts/validate_public_tree.py":
            for label, pattern in PATTERNS:
                if pattern.search(text):
                    problems.append(f"{label}: {rel}")
        if rel.startswith("evidence/") and PRIVATE_IPV4.search(text):
            problems.append(f"private IPv4 address in public evidence: {rel}")
    if problems:
        print("Public-tree validation: FAIL")
        for problem in sorted(set(problems)):
            print(f"- {problem}")
        return 1
    print("Public-tree validation: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
