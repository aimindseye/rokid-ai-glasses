#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scan_public_artifacts.sh [--repo PATH] [--staged]

Scans repository files or staged files for common private-evidence patterns.

Detector implementation files are exempt from content-signature matching
because they necessarily contain the signatures they are designed to detect.
They remain subject to extension and Git-file checks.
EOF
}

REPO="."
STAGED=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --staged) STAGED=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

cd "$REPO"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not a Git repository" >&2
  exit 1
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if [[ "$STAGED" -eq 1 ]]; then
  git diff --cached --name-only --diff-filter=ACMR -z > "$TMP"
else
  git ls-files -co --exclude-standard -z > "$TMP"
fi

python3 - "$TMP" <<'PY'
from pathlib import Path
import re
import sys

list_file = Path(sys.argv[1])
paths = [
    Path(item.decode("utf-8", errors="surrogateescape"))
    for item in list_file.read_bytes().split(b"\0")
    if item
]

blocked_suffixes = {
    ".pcap", ".pcapng", ".sslkeylog", ".har", ".apk", ".apks",
    ".bugreport", ".hci", ".btsnoop"
}

patterns = {
    "macOS absolute private path": re.compile(
        b"/" + b"Users" + rb"/[A-Za-z0-9._-]+/"
    ),
    "private test root": re.compile(b"rokid" + b"-nettest"),
    "TLS traffic secret": re.compile(
        rb"(?:CLIENT|SERVER)_" + rb"(?:HANDSHAKE_)?" + b"TRAFFIC_SECRET"
    ),
    "TLS exporter secret": re.compile(b"EXPORTER" + b"_SECRET"),
    "AWS-style secret label": re.compile(b"AWS_SECRET" + b"_ACCESS_KEY"),
    "private key block": re.compile(
        b"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?" + b"PRIVATE KEY-----"
    ),
}

# Exact detector/validator sources only. No documentation, generator, config,
# evidence, or general script receives an exemption.
content_signature_exemptions = {
    Path("scripts/safety/scan_public_artifacts.sh"),
    Path("scripts/validate_public_tree.py"),
    Path("scripts/tests/validate_06c_public_findings.sh"),
    Path("scripts/tests/validate_10_public_findings.sh"),
}

problems = []

for path in paths:
    if path.suffix.lower() in blocked_suffixes:
        problems.append(f"blocked extension: {path}")
        continue

    if not path.is_file():
        continue

    data = path.read_bytes()
    if b"\x00" in data[:4096]:
        continue

    if path in content_signature_exemptions:
        continue

    for label, pattern in patterns.items():
        if pattern.search(data):
            problems.append(f"{label}: {path}")

if problems:
    print("Public artifact scan: FAIL", file=sys.stderr)
    for item in sorted(set(problems)):
        print(f"- {item}", file=sys.stderr)
    sys.exit(1)

print(f"Public artifact scan: PASS ({len(paths)} files checked)")
PY
