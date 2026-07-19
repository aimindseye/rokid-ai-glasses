#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-.}"
cd "$REPO"

./scripts/tests/validate_10_public_findings.sh "$PWD"

if [[ -x scripts/safety/scan_public_artifacts.sh ]]; then
  ./scripts/safety/scan_public_artifacts.sh --repo "$PWD"
fi

echo "Test 10 documentation gate: PASS"
