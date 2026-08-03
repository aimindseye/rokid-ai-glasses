#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 5786411aabf56f8445d054b0787eecbd184e0918aae6cc46fef199ffb34b5709.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.2.2.1.2 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R1_3_3_2_25_2_2_2_1_2_INSTALLED_VALIDATION=PASS'
exit 0
