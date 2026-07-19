#!/bin/bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

if [[ -z "${ROKID_PRIVATE_ROOT:-}" ]]; then
  echo "ERROR: ROKID_PRIVATE_ROOT is not configured." >&2
  echo "Copy .env.example to .env.local and set the private evidence root." >&2
  exit 1
fi

PRIVATE_ROOT="$ROKID_PRIVATE_ROOT"
TEST_A="$PRIVATE_ROOT/tests/04a-base-model-select-gemini"
TEST_B="$PRIVATE_ROOT/tests/04b-base-model-select-chatgpt"
MANIFEST_DIR="$REPO/evidence/manifests"

require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "Missing required private evidence: $path" >&2
    exit 1
  }
}

append_if_file() {
  local array_name="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    eval "$array_name+=(\"\$path\")"
  fi
}

[[ -d "$TEST_A" ]] || {
  echo "Missing Test 04a private root: $TEST_A" >&2
  exit 1
}

[[ -d "$TEST_B" ]] || {
  echo "Missing Test 04b private root: $TEST_B" >&2
  exit 1
}

required_a=(
  "$TEST_A/pcap/04a-base-model-select-gemini.pcap"
  "$TEST_A/pcap/04a-base-model-select-gemini.sslkeylog"
  "$TEST_A/decrypted/04a-pcapdroid-connections.csv"
  "$TEST_A/decrypted/protocol-summary.txt"
  "$TEST_A/decrypted/http-requests-private.txt"
  "$TEST_A/decrypted/post-selection-persistence-private.tsv"
  "$TEST_A/logcat/04a-base-model-select-gemini-logcat.txt"
  "$TEST_A/screenshots/04a-before-base-chatgpt-vision-gemini.jpg"
  "$TEST_A/screenshots/04a-after-base-gemini-vision-gemini.jpg"
  "$TEST_A/notes/normalized-action-timeline.tsv"
  "$TEST_A/notes/operator-marker-correction.txt"
)

required_b=(
  "$TEST_B/pcap/04b-base-model-select-chatgpt.pcap"
  "$TEST_B/pcap/04b-base-model-select-chatgpt.sslkeylog"
  "$TEST_B/decrypted/04b-pcapdroid-connections.csv"
  "$TEST_B/decrypted/protocol-summary.txt"
  "$TEST_B/decrypted/http-requests-private.txt"
  "$TEST_B/decrypted/websocket-state-persistence-private.tsv"
  "$TEST_B/logcat/04b-base-model-select-chatgpt-logcat.txt"
  "$TEST_B/screenshots/04b-before-base-gemini-vision-gemini-recovered.png"
  "$TEST_B/screenshots/04b-after-base-chatgpt-vision-gemini-recovered.png"
  "$TEST_B/notes/normalized-action-timeline.tsv"
  "$TEST_B/notes/screenshot-recovery-note.txt"
  "$TEST_B/notes/ui-screenshot-evidence.txt"
)

for path in "${required_a[@]}" "${required_b[@]}"; do
  require_file "$path"
done

manifest_a=("${required_a[@]}")
manifest_b=("${required_b[@]}")

append_if_file manifest_a "$TEST_A/decrypted/websocket-payload-fingerprints-private.tsv"
append_if_file manifest_a "$TEST_A/notes/final-result.txt"
append_if_file manifest_a "$TEST_A/SHA256SUMS"

append_if_file manifest_b "$TEST_B/decrypted/websocket-payload-fingerprints-private.tsv"
append_if_file manifest_b "$TEST_B/notes/final-result.txt"
append_if_file manifest_b "$TEST_B/notes/screenshot-sha256.txt"
append_if_file manifest_b "$TEST_B/SHA256SUMS"

mkdir -p "$MANIFEST_DIR"

python3 scripts/generate_evidence_manifest.py \
  --root "$TEST_A" \
  --test-id "04a-base-model-select-gemini" \
  --output "$MANIFEST_DIR/04a-private-evidence-sha256.json" \
  "${manifest_a[@]}"

python3 scripts/generate_evidence_manifest.py \
  --root "$TEST_B" \
  --test-id "04b-base-model-select-chatgpt" \
  --output "$MANIFEST_DIR/04b-private-evidence-sha256.json" \
  "${manifest_b[@]}"

python3 scripts/validate_public_tree.py --root "$REPO"

echo "Generated:"
echo "  $MANIFEST_DIR/04a-private-evidence-sha256.json"
echo "  $MANIFEST_DIR/04b-private-evidence-sha256.json"
