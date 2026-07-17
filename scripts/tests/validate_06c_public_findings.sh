#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  validate_06c_public_findings.sh [--repo PATH]
EOF
}

REPO="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || { echo "ERROR: --repo requires a value" >&2; exit 2; }
      REPO="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$REPO"

FILES=(
  "docs/tests/06c-device-connection.md"
  "docs/experiments/06c-device-connection-peripheral-pairing.md"
  "docs/findings/peripheral-pairing-control-path.md"
  "docs/methodology/native-cxr-static-analysis.md"
  "evidence/sanitized/06c/device-connection-summary.md"
)

for path in "${FILES[@]}"
do
  [[ -f "$path" ]] || {
    echo "ERROR: missing required file: $path" >&2
    exit 1
  }
done

required_terms=(
  "startBTPairing"
  "CXRControl"
  "rokid::Caps"
  "RGR06"
  "FE2C"
  "FEAA"
  "FFF6"
  "0x9100"
  "closed"
)

for term in "${required_terms[@]}"
do
  /usr/bin/grep -R -q -F "$term" "${FILES[@]}" || {
    echo "ERROR: required finding term absent: $term" >&2
    exit 1
  }
done

python3 - "${FILES[@]}" <<'PY'
from pathlib import Path
import re
import sys

paths = [Path(value) for value in sys.argv[1:]]

user_root_pattern = "/" + "Users" + r"/[A-Za-z0-9._-]+/"

blocked = {
    "private macOS user path": re.compile(user_root_pattern),
    "Bluetooth MAC address": re.compile(
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"
    ),
    "IPv4 address": re.compile(
        r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
    ),
    "raw Android data path": re.compile(r"/data/(?:app|user|misc|system)/"),
    "TLS secret label": re.compile(
        r"(?:CLIENT|SERVER)_(?:HANDSHAKE_)?TRAFFIC_SECRET"
    ),
}

problems = []
for path in paths:
    text = path.read_text(encoding="utf-8")
    for label, pattern in blocked.items():
        if pattern.search(text):
            problems.append(f"{label}: {path}")

if problems:
    print("06c public findings validation: FAIL", file=sys.stderr)
    for problem in problems:
        print(f"- {problem}", file=sys.stderr)
    raise SystemExit(1)

print(f"06c public findings validation: PASS ({len(paths)} documents)")
PY
