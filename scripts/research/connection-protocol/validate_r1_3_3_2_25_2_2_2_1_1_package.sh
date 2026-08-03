#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 788baae24b6d2b63af7596a1db3130c712d26147ea4ac73f9d814f8e0cadf099.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.2.2.1.1 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R1_3_3_2_25_2_2_2_1_1_REPOSITORY_SCRIPTS=PASS'
exit 0
