#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-}"
[[ -n "$REPO" ]] || { echo "ERROR: repository path required" >&2; exit 2; }
REPO="$(cd "$REPO" && pwd -P)"
FILES=(
  scripts/research/connection-protocol/r25_3_1_3_analyze.py
  scripts/research/connection-protocol/run_r1_3_3_2_25_3_1_3.sh
  scripts/research/connection-protocol/validate_r1_3_3_2_25_3_1_3_package.sh
  docs/research/connection-protocol/r1.3.3.2.25.3.1.3-exact-adb-toggle-frame-grammar-and-field-role-closure.md
)
for rel in "${FILES[@]}"; do
  [[ -f "$REPO/$rel" && ! -L "$REPO/$rel" ]] || {
    echo "ERROR: missing installed file: $rel" >&2
    exit 3
  }
done
python3 - "$REPO/scripts/research/connection-protocol/r25_3_1_3_analyze.py" <<'PY_SYNTAX'
from pathlib import Path
import sys
path = Path(sys.argv[1])
compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("R25_3_1_3_INSTALLED_IN_MEMORY_SYNTAX_COMPILE=PASS")
PY_SYNTAX
if grep -Eiq '^[[:space:]]*(adb|fastboot)[[:space:]]' \
  "$REPO/scripts/research/connection-protocol/run_r1_3_3_2_25_3_1_3.sh"; then
  echo "ERROR: device command found in host-only runner" >&2
  exit 4
fi
grep -Fq 'captured_payload_replay_attempted' \
  "$REPO/scripts/research/connection-protocol/r25_3_1_3_analyze.py"
grep -Fq 'nested_total_length_self_inclusive' \
  "$REPO/scripts/research/connection-protocol/r25_3_1_3_analyze.py"
echo "R25_3_1_3_INSTALLED_SYNTAX_GATE=PASS"
echo "R25_3_1_3_INSTALLED_NO_DEVICE_COMMAND_GATE=PASS"
echo "R25_3_1_3_INSTALLED_NO_REPLAY_BOUNDARY_GATE=PASS"
echo "R1_3_3_2_25_3_1_3_INSTALLED_VALIDATION=PASS"
