#!/usr/bin/env bash
set -euo pipefail
REPO=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd -P)}
RUN="$REPO/scripts/research/connection-protocol/run_r1_3_3_2_25_2_3_1.sh"
ANALYZER="$REPO/scripts/research/connection-protocol/r25_2_3_1_capture.py"
PREFLIGHT="$REPO/scripts/research/connection-protocol/r25_2_3_1_hci_preflight.py"
DOC="$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.3.1-pixel-aosp-hci-snoop-preflight-repair.md"
for f in "$RUN" "$ANALYZER" "$PREFLIGHT" "$DOC"; do [[ -f "$f" ]] || { echo "Missing installed file: $f" >&2; exit 1; }; done
bash -n "$RUN"
PYCACHE=$(mktemp -d); trap 'rm -rf "$PYCACHE"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE" python3 -m py_compile "$ANALYZER" "$PREFLIGHT"
if grep -nE 'settings[[:space:]]+put|setprop|adb[[:space:]]+root|adb[[:space:]]+reboot|svc[[:space:]]+bluetooth' "$RUN"; then
  echo "Device mutation command found" >&2; exit 1
fi
grep -F 'bluetooth_btsnoop_default_mode' "$RUN" >/dev/null
grep -F 'PROVISIONAL_UNKNOWN' "$PREFLIGHT" >/dev/null
grep -F 'POST_BUGREPORT_BTSNOOP_EVIDENCE' "$RUN" >/dev/null
printf 'R25_2_3_1_INSTALLED_SYNTAX_GATE=PASS\n'
printf 'R25_2_3_1_NO_DEVICE_SETTING_MUTATION_GATE=PASS\n'
printf 'R25_2_3_1_PIXEL_AOSP_CONTROL_RECOGNITION_GATE=PASS\n'
printf 'R25_2_3_1_PROVISIONAL_FAIL_CLOSED_GATE=PASS\n'
printf 'R1_3_3_2_25_2_3_1_INSTALLED_VALIDATION=PASS\n'
