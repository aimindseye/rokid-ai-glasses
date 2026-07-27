#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ANALYZER="$SCRIPT_DIR/r25_2_2_2_1_3_offline.py"
RUNNER="$SCRIPT_DIR/run_r1_3_3_2_25_2_2_2_1_3.sh"
DOC="$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.2.2.1.3-attempt-gate-zero-payload-census-repair.md"
for path in "$ANALYZER" "$RUNNER" "$DOC"; do
  [[ -s "$path" ]] || { echo "ERROR: missing installed repair file: $path" >&2; exit 1; }
done
python3 -m py_compile "$ANALYZER"
bash -n "$RUNNER"
for marker in \
  'attempt_level_gate_projection' \
  'archive_wide_zero_payload_source_census' \
  'candidate_rejection_diagnostics' \
  'extract_zero_payload_candidates' \
  'correlate_zero_candidates' \
  'rejected_configuration_only' \
  'PASS_BOUNDED_RFCOMM_CLIENT_LIFECYCLE_CLOSURE_ONLY' \
  'payload_data_event_count' \
  '35b209ab8243e68a26b3f32ab7f4bfcd111f88ece3d0be05c0a72e095dccf662'
do
  grep -Fq "$marker" "$ANALYZER" || { echo "ERROR: missing analyzer marker: $marker" >&2; exit 1; }
done
echo "R1_3_3_2_25_2_2_2_1_3_INSTALLED_VALIDATION=PASS"
