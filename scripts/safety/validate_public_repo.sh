#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR/../.." rev-parse --show-toplevel)"
cd "$ROOT"

echo "Public artifact validation"
echo "Repository: $ROOT"

python3 - <<'PY'
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

repo = pathlib.Path.cwd()

# Include files already tracked plus untracked files Git would allow to be
# staged. Exclude ignored local state such as .env.local, private captures,
# caches, and editor files.
result = subprocess.run(
    ["git", "ls-files", "-co", "--exclude-standard", "-z"],
    check=True,
    stdout=subprocess.PIPE,
)
paths = [
    pathlib.Path(item.decode("utf-8", errors="surrogateescape"))
    for item in result.stdout.split(b"\0")
    if item
]

forbidden_suffixes = {
    ".pcap", ".pcapng", ".cap", ".keylog", ".har",
    ".apk", ".apks", ".aab", ".so", ".hci",
}
forbidden_names = [
    re.compile(r"bugreport.*\.zip$", re.IGNORECASE),
]
sensitive_patterns = [
    re.compile(r"/Users/piyushdaiya"),
    re.compile(r"C:\\Users\\piyushdaiya", re.IGNORECASE),
    re.compile(r"\bR5C[A-Z0-9]{8,}\b"),
]

errors: list[str] = []

for relative in paths:
    path = repo / relative
    if not path.is_file():
        continue

    lowered = path.name.lower()
    if path.suffix.lower() in forbidden_suffixes or any(
        pattern.search(lowered) for pattern in forbidden_names
    ):
        errors.append(f"prohibited raw/private artifact: {relative}")
        continue

    # The validator contains the patterns it enforces.
    if relative.as_posix() == "scripts/safety/validate_public_repo.sh":
        continue

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue

    for pattern in sensitive_patterns:
        match = pattern.search(text)
        if match:
            line_number = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"sensitive path/device pattern: {relative}:{line_number}"
            )
            break

if errors:
    print("ERROR: public artifact validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    raise SystemExit(1)
PY

PYCACHE_DIR="$(mktemp -d)"
trap 'rm -rf "$PYCACHE_DIR"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE_DIR" \
  python3 -m py_compile scripts/tests/*.py scripts/recovery/*.py

git diff --check

echo "Public artifact validation: PASS"
