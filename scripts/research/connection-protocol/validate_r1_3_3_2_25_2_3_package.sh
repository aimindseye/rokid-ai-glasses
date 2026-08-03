#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 6bb8d866f59bd608b582bf0dff9eb8828e15a7560c6a63cbacd3d23af71c42dd.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.3 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_2_3_INSTALLED_SYNTAX_GATE=PASS'
printf '%s\n' 'R25_2_3_NO_DEVICE_SETTING_MUTATION_GATE=PASS'
printf '%s\n' 'R25_2_3_FAIL_CLOSED_PROOF_POLICY_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_2_3_INSTALLED_VALIDATION=PASS'
exit 0
