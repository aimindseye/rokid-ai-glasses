#!/bin/bash
# R27.1.6 compatibility shim. Historical implementation preserved by SHA-256 f3e8a2b7702f73d8cb0030e811fc5e0929dcb3ae73eea99bf2cb896c90e04e36.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO="${1:-$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" "$REPO/scripts/research/canonical/connection_validator.py" --repo "$REPO" --revision r25.2.4 --quiet
RC=$?
if [ "$RC" -ne 0 ]; then
  exit "$RC"
fi
printf '%s\n' 'R25_2_4_INSTALLED_INPUT_HASH_LOCK_GATE=PASS'
printf '%s\n' 'R25_2_4_INSTALLED_OFFLINE_ONLY_GATE=PASS'
printf '%s\n' 'R25_2_4_INSTALLED_SYNTAX_GATE=PASS'
printf '%s\n' 'R1_3_3_2_25_2_4_INSTALLED_VALIDATION=PASS'
exit 0
