#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER="$SCRIPT_DIR/r25_2_2_2_1_3_offline.py"
DEFAULT_EXPECTED_SHA256="35b209ab8243e68a26b3f32ab7f4bfcd111f88ece3d0be05c0a72e095dccf662"

REPO=""
SOURCE=""
OUTPUT=""
EXPECTED="$DEFAULT_EXPECTED_SHA256"

usage() {
  cat <<'USAGE'
Usage:
  bash run_r1_3_3_2_25_2_2_2_1_3.sh \
    --repo PATH \
    --source-private-zip ZIP \
    --output PATH \
    [--expected-source-sha256 HEX]

This command reads one already-captured private ZIP and writes new private and
sanitized analysis artifacts. It is offline-only and performs no device access.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --source-private-zip) SOURCE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --expected-source-sha256) EXPECTED="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$SOURCE" && -n "$OUTPUT" ]] || { usage >&2; exit 2; }
[[ -d "$REPO/.git" ]] || { echo "ERROR: not a Git repository: $REPO" >&2; exit 2; }
[[ -f "$SOURCE" ]] || { echo "ERROR: source archive not found: $SOURCE" >&2; exit 2; }
[[ ! -e "$OUTPUT" ]] || { echo "ERROR: output already exists: $OUTPUT" >&2; exit 2; }
[[ "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "ERROR: expected SHA-256 must be 64 hexadecimal characters" >&2; exit 2; }
[[ -s "$ANALYZER" ]] || { echo "ERROR: analyzer missing: $ANALYZER" >&2; exit 2; }

exec python3 "$ANALYZER" \
  --repo "$REPO" \
  --source-private-zip "$SOURCE" \
  --expected-source-sha256 "$EXPECTED" \
  --output "$OUTPUT"
