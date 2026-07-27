#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m py_compile "$SCRIPT_DIR/r25_2_2_2_1_offline.py"
bash -n "$SCRIPT_DIR/run_r1_3_3_2_25_2_2_2_1.sh"
echo "R1_3_3_2_25_2_2_2_1_REPOSITORY_SCRIPTS=PASS"
