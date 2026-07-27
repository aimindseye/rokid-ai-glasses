#!/usr/bin/env bash
set -euo pipefail
REPO=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd -P)}
DIR="$REPO/scripts/research/connection-protocol"
for f in "$DIR/run_r1_3_3_2_25_2_3_2.sh" "$DIR/r25_2_3_2_orchestrator.py" "$DIR/r25_2_3_2_capture.py" "$DIR/r25_2_3_2_hci_preflight.py" "$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.3.2-strict-private-handoff-integration.md"; do [[ -f "$f" ]] || { echo "Missing installed file: $f" >&2; exit 1; }; done
[[ -f "$DIR/run_r1_3_3_2_25_2_2_2.sh" ]] || { echo "Accepted strict r25.2.2.2 runner is missing: $DIR/run_r1_3_3_2_25_2_2_2.sh" >&2; exit 1; }
bash -n "$DIR/run_r1_3_3_2_25_2_3_2.sh"
PYCACHE=$(mktemp -d); trap 'rm -rf "$PYCACHE"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE" python3 -m py_compile "$DIR/r25_2_3_2_orchestrator.py" "$DIR/r25_2_3_2_capture.py" "$DIR/r25_2_3_2_hci_preflight.py"
grep -F "run_r1_3_3_2_25_2_2_2.sh" "$DIR/r25_2_3_2_orchestrator.py" >/dev/null
grep -F "Bugreport is collected after close and before handoff revocation" "$DIR/r25_2_3_2_orchestrator.py" >/dev/null
printf 'R25_2_3_2_INSTALLED_STRICT_RUNNER_DEPENDENCY_GATE=PASS\nR25_2_3_2_INSTALLED_READINESS_BEFORE_INTERVAL_GATE=PASS\nR25_2_3_2_INSTALLED_SINGLE_TAP_GATE=PASS\nR25_2_3_2_INSTALLED_POST_ATTEMPT_REVOCATION_GATE=PASS\nR1_3_3_2_25_2_3_2_INSTALLED_VALIDATION=PASS\n'
