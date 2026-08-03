#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 fd33ceb8aa1be8439de82522eb59e67529a58ca6fefe32f00669da0456f07174.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.2.2.1.3 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R1_3_3_2_25_2_2_2_1_3_INSTALLED_VALIDATION=PASS'
exit 0
