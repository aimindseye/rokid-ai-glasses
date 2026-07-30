#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
exec python3 "$HERE/r25_3_1_1_capture.py" "$@"
