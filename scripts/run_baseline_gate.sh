#!/bin/bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
python3 -m unittest scripts/tests/test_sanitizers.py -v
./scripts/generate_03b_public_evidence.sh
python3 scripts/validate_public_tree.py --root .
git status --short
