#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin${PATH:+:$PATH}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

python3 -m unittest scripts/tests/test_sanitizers.py -v
./scripts/generate_03b_public_evidence.sh
./scripts/generate_04ab_manifests.sh
python3 scripts/validate_public_tree.py --root .
git diff --check
git status --short
