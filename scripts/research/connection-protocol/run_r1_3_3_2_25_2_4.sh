#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SANITIZED_SHA256='5efaa9c38b8868fb7bc3ae3bb7253790a905d9b6e390df2843bbd00c5728df18'
EXPECTED_ANALYSIS_SHA256='21a1b66de908d5284498c5e2868f1dc5b2666b5d2eb3aadfbb0832b7c870fac1'
EXPECTED_EVIDENCE_SHA256='37fc0b5f2f8e77282c57dd030f779d2a3fbe60c06783d6c2c5d10af38f8ad54b'

REPO=''
SANITIZED=''
ANALYSIS=''
EVIDENCE=''
OUTPUT=''

while (($#)); do
  case "$1" in
    --repo) REPO=${2:-}; shift 2 ;;
    --sanitized-publication-zip) SANITIZED=${2:-}; shift 2 ;;
    --private-analysis-zip) ANALYSIS=${2:-}; shift 2 ;;
    --private-evidence-zip) EVIDENCE=${2:-}; shift 2 ;;
    --output) OUTPUT=${2:-}; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: run_r1_3_3_2_25_2_4.sh \
  --repo PATH \
  --sanitized-publication-zip PATH \
  --private-analysis-zip PATH \
  --private-evidence-zip PATH \
  --output PATH
EOF
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

for pair in "REPO:$REPO" "SANITIZED:$SANITIZED" "ANALYSIS:$ANALYSIS" "EVIDENCE:$EVIDENCE" "OUTPUT:$OUTPUT"; do
  name=${pair%%:*}; value=${pair#*:}
  [[ -n "$value" ]] || { echo "Missing required argument: $name" >&2; exit 2; }
done

REPO=$(cd "$REPO" && pwd -P)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)

python3 "$SCRIPT_DIR/r25_2_4_publish.py" \
  --repo "$REPO" \
  --sanitized-publication-zip "$SANITIZED" \
  --private-analysis-zip "$ANALYSIS" \
  --private-evidence-zip "$EVIDENCE" \
  --output "$OUTPUT" \
  --expected-sanitized-sha256 "$EXPECTED_SANITIZED_SHA256" \
  --expected-analysis-sha256 "$EXPECTED_ANALYSIS_SHA256" \
  --expected-evidence-sha256 "$EXPECTED_EVIDENCE_SHA256"
