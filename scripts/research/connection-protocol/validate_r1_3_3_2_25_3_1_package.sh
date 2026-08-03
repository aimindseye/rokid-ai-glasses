#!/bin/bash
# R27.1.8 compatibility shim. Historical implementation preserved by SHA-256 99ee789ff35b7da6fbf460d4c03723ce7ba78a24f0ee526b0ee984073b94ca4e.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.3.1 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_3_1_INSTALLED_ACCEPTED_HCI_PARSER_HASH_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_STOCK_ONLY_CAPTURE_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_NO_CUSTOM_TRANSMISSION_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_SEMANTIC_ORACLE_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_TRANSPORT_DISAPPEARANCE_NOT_REQUIRED_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_CONTROL_CHANNEL_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_FINAL_STATE_RESTORE_GATE=PASS'
printf '%s\n' 'R25_3_1_INSTALLED_NO_DEVICE_DRY_RUN_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_3_1_INSTALLED_VALIDATION=PASS'
exit 0
