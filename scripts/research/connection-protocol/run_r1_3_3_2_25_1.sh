#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
exec python3 "$HERE/run_r1_3_3_2_25_1.py" "$@"
