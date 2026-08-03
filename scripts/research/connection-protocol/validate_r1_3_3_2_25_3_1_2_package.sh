#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 94c3b103277d621bb14c3a326cd0a1942e247cbcce4d66a13310858a0b98ed1c.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.3.1.2 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_3_1_2_INSTALLED_ACCEPTED_HCI_PARSER_HASH_GATE=PASS'
printf '%s\n' 'R25_3_1_2_INSTALLED_TARGET_PAIR_SCOPING_GATE=PASS'
printf '%s\n' 'R25_3_1_2_INSTALLED_NON_TARGET_ERROR_RETENTION_GATE=PASS'
printf '%s\n' 'R25_3_1_2_INSTALLED_NO_DEVICE_COMMAND_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_3_1_2_INSTALLED_VALIDATION=PASS'
exit 0
