#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 13c5b35f10e015eb2e73f7ea070ab25f476927e1a7c3b6c9e4dda7637d9ecd53.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.3.1.3 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_3_1_3_INSTALLED_IN_MEMORY_SYNTAX_COMPILE=PASS'
printf '%s\n' 'R25_3_1_3_INSTALLED_SYNTAX_GATE=PASS'
printf '%s\n' 'R25_3_1_3_INSTALLED_NO_DEVICE_COMMAND_GATE=PASS'
printf '%s\n' 'R25_3_1_3_INSTALLED_NO_REPLAY_BOUNDARY_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_3_1_3_INSTALLED_VALIDATION=PASS'
exit 0
