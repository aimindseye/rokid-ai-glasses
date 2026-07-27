#!/usr/bin/env bash
set -euo pipefail
REPO=${1:-$(pwd)}
BASE="$REPO/scripts/research/connection-protocol"
DOC="$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.3-instrumented-rfcomm-hci-zero-payload-capture.md"
for f in \
  "$BASE/run_r1_3_3_2_25_2_3.sh" \
  "$BASE/r25_2_3_capture.py" \
  "$DOC"; do
  test -f "$f" || { echo "Missing installed file: $f" >&2; exit 1; }
done
bash -n "$BASE/run_r1_3_3_2_25_2_3.sh"
PYCACHE=$(mktemp -d)
trap 'rm -rf "$PYCACHE"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE" python3 -m py_compile "$BASE/r25_2_3_capture.py"
if grep -nE 'settings[[:space:]]+put|setprop|adb[[:space:]]+root|rm[[:space:]]+-rf[[:space:]]+/' "$BASE/run_r1_3_3_2_25_2_3.sh"; then
  echo "Forbidden device mutation or destructive pattern found" >&2
  exit 1
fi
grep -F 'PASS_FULL_RFCOMM_HCI_ZERO_PAYLOAD_CLOSURE' "$BASE/r25_2_3_capture.py" >/dev/null
grep -F 'PASS_BOUNDED_RFCOMM_CLIENT_LIFECYCLE_CLOSURE_ONLY' "$BASE/r25_2_3_capture.py" >/dev/null
grep -F 'FAIL_POSITIVE_RFCOMM_PAYLOAD_OBSERVED' "$BASE/r25_2_3_capture.py" >/dev/null
grep -F 'Logcat silence alone is not proof' "$BASE/r25_2_3_capture.py" >/dev/null
printf 'R25_2_3_INSTALLED_SYNTAX_GATE=PASS\n'
printf 'R25_2_3_NO_DEVICE_SETTING_MUTATION_GATE=PASS\n'
printf 'R25_2_3_FAIL_CLOSED_PROOF_POLICY_GATE=PASS\n'
printf 'R1_3_3_2_25_2_3_INSTALLED_VALIDATION=PASS\n'
