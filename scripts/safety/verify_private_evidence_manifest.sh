#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  verify_private_evidence_manifest.sh PRIVATE_CAPTURE_ROOT [MANIFEST]
EOF
}

ROOT="${1:-}"
MANIFEST="${2:-manifests/raw-evidence-sha256.txt}"
[[ -n "$ROOT" ]] || { usage >&2; exit 2; }
[[ -d "$ROOT" ]] || { echo "ERROR: missing root: $ROOT" >&2; exit 1; }
[[ -s "$ROOT/$MANIFEST" ]] || { echo "ERROR: missing manifest: $ROOT/$MANIFEST" >&2; exit 1; }

(
  cd "$ROOT"
  shasum -a 256 -c "$MANIFEST"
)
echo "Private evidence manifest verification: PASS"
