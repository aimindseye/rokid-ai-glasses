#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 9f3d8d589c62295ac40812291a75011492ac1b77a965064eb24114f390cf46f6.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.2.2.1 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R1_3_3_2_25_2_2_2_1_REPOSITORY_SCRIPTS=PASS'
exit 0
