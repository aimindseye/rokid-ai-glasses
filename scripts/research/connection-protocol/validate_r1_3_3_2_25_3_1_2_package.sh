#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-}"
[[ -n "$REPO" && -d "$REPO" ]] || {
  echo "Usage: $0 <repo>" >&2
  exit 2
}

ANALYZER="$REPO/scripts/research/connection-protocol/r25_3_1_2_analyze.py"
RUNNER="$REPO/scripts/research/connection-protocol/run_r1_3_3_2_25_3_1_2.sh"
PARSER="$REPO/scripts/research/connection-protocol/r25_2_3_2_capture.py"
DOC="$REPO/docs/research/connection-protocol/r1.3.3.2.25.3.1.2-target-pair-scoped-rfcomm-error-qualification-and-offline-salvage.md"

for path in "$ANALYZER" "$RUNNER" "$PARSER" "$DOC"; do
  [[ -f "$path" && ! -L "$path" ]] || {
    echo "ERROR: missing installed file: $path" >&2
    exit 3
  }
done

[[ "$(shasum -a 256 "$PARSER" | awk '{print $1}')" == "0a126e98fe63a5cc4cc676f5e3bceb3dd6f3b3766efacaba3d05955fa579bc2f" ]] || {
  echo "ERROR: accepted r25.2.3.2 parser hash mismatch" >&2
  exit 3
}

python3 -m py_compile "$ANALYZER"

grep -Fq 'target_pair_scoped_rfcomm_error_qualification' "$ANALYZER"
grep -Fq 'non_target_rfcomm_errors_excluded_from_qualification' "$ANALYZER"
grep -Fq 'target_rfcomm_parse_error_count' "$ANALYZER"
grep -Fq 'DEVICE_CONTACT=NO' "$RUNNER"

if grep -Eiq '^[[:space:]]*(adb|fastboot)[[:space:]]' "$RUNNER"; then
  echo "ERROR: host-only runner contains a device command token" >&2
  exit 4
fi

echo "R25_3_1_2_INSTALLED_ACCEPTED_HCI_PARSER_HASH_GATE=PASS"
echo "R25_3_1_2_INSTALLED_TARGET_PAIR_SCOPING_GATE=PASS"
echo "R25_3_1_2_INSTALLED_NON_TARGET_ERROR_RETENTION_GATE=PASS"
echo "R25_3_1_2_INSTALLED_NO_DEVICE_COMMAND_GATE=PASS"
echo "R1_3_3_2_25_3_1_2_INSTALLED_VALIDATION=PASS"
