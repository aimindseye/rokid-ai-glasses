#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 9d62b8f9d596224ff2dc0274a3050dd6c784b449e5534d7156cab81bbf442a6c.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.3.2 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_2_3_2_INSTALLED_STRICT_RUNNER_DEPENDENCY_GATE=PASS'
printf '%s\n' 'R25_2_3_2_INSTALLED_READINESS_BEFORE_INTERVAL_GATE=PASS'
printf '%s\n' 'R25_2_3_2_INSTALLED_SINGLE_TAP_GATE=PASS'
printf '%s\n' 'R25_2_3_2_INSTALLED_POST_ATTEMPT_REVOCATION_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_2_3_2_INSTALLED_VALIDATION=PASS'
exit 0
