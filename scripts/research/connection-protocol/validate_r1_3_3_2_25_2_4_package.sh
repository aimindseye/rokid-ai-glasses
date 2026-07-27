#!/usr/bin/env bash
set -euo pipefail
REPO=${1:-}
[[ -n "$REPO" && -d "$REPO" ]] || { echo 'Repository path required' >&2; exit 2; }
BASE="$REPO/scripts/research/connection-protocol"
for f in \
  "$BASE/r25_2_4_publish.py" \
  "$BASE/run_r1_3_3_2_25_2_4.sh" \
  "$REPO/docs/research/connection-protocol/r1.3.3.2.25.2.4-publication-integration-method.md"; do
  [[ -f "$f" ]] || { echo "Missing installed file: $f" >&2; exit 1; }
done
bash -n "$BASE/run_r1_3_3_2_25_2_4.sh"
PYCACHE=$(mktemp -d)
trap 'rm -rf "$PYCACHE"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE" python3 -m py_compile "$BASE/r25_2_4_publish.py"
grep -F "EXPECTED_SANITIZED_SHA256='5efaa9c38b8868fb7bc3ae3bb7253790a905d9b6e390df2843bbd00c5728df18'" "$BASE/run_r1_3_3_2_25_2_4.sh" >/dev/null
grep -F "EXPECTED_ANALYSIS_SHA256='21a1b66de908d5284498c5e2868f1dc5b2666b5d2eb3aadfbb0832b7c870fac1'" "$BASE/run_r1_3_3_2_25_2_4.sh" >/dev/null
grep -F "EXPECTED_EVIDENCE_SHA256='37fc0b5f2f8e77282c57dd030f779d2a3fbe60c06783d6c2c5d10af38f8ad54b'" "$BASE/run_r1_3_3_2_25_2_4.sh" >/dev/null
if grep -R -nE '(^|[^[:alnum:]_])adb([^[:alnum:]_]|$)|PHONE_SERIAL|bluetooth_manager|bugreportz' "$BASE/r25_2_4_publish.py" "$BASE/run_r1_3_3_2_25_2_4.sh"; then
  echo 'Device-contact command rejected from offline publication scripts' >&2
  exit 1
fi
printf 'R25_2_4_INSTALLED_INPUT_HASH_LOCK_GATE=PASS\n'
printf 'R25_2_4_INSTALLED_OFFLINE_ONLY_GATE=PASS\n'
printf 'R25_2_4_INSTALLED_SYNTAX_GATE=PASS\n'
printf 'R1_3_3_2_25_2_4_INSTALLED_VALIDATION=PASS\n'
