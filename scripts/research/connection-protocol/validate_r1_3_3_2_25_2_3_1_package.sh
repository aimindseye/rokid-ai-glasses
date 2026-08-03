#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 c806b97a3149b381539039a64289a13647007f9d30e69d07ef8e803561366f95.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.3.1 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_2_3_1_INSTALLED_SYNTAX_GATE=PASS'
printf '%s\n' 'R25_2_3_1_NO_DEVICE_SETTING_MUTATION_GATE=PASS'
printf '%s\n' 'R25_2_3_1_PIXEL_AOSP_CONTROL_RECOGNITION_GATE=PASS'
printf '%s\n' 'R25_2_3_1_PROVISIONAL_FAIL_CLOSED_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_2_3_1_INSTALLED_VALIDATION=PASS'
exit 0
