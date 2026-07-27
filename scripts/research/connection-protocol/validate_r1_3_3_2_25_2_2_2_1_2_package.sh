#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ANALYZER="$SCRIPT_DIR/r25_2_2_2_1_2_offline.py"
RUNNER="$SCRIPT_DIR/run_r1_3_3_2_25_2_2_2_1_2.sh"
DOC="$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.2.2.1.2-bluetooth-scoped-lifecycle-correlation-repair.md"

for path in "$ANALYZER" "$RUNNER" "$DOC"; do
  [[ -s "$path" ]] || { echo "ERROR: missing installed repair file: $path" >&2; exit 1; }
done
python3 -m py_compile "$ANALYZER"
bash -n "$RUNNER"
grep -Fq 'BT_SCOPE_RE' "$ANALYZER"
grep -Fq 'from uid/pid' "$ANALYZER"
grep -Fq 'requested_service_uuid' "$ANALYZER"
grep -Fq 'native_service_class_uuid' "$ANALYZER"
grep -Fq 'rfc_port_event_close' "$ANALYZER"
grep -Fq 'duplicate_semantic_lines' "$ANALYZER"
grep -Fq 'global_zero_payload_evidence' "$ANALYZER"
grep -Fq 'payload_data_event_count' "$ANALYZER"
grep -Fq '35b209ab8243e68a26b3f32ab7f4bfcd111f88ece3d0be05c0a72e095dccf662' "$ANALYZER"
echo "R1_3_3_2_25_2_2_2_1_2_INSTALLED_VALIDATION=PASS"
