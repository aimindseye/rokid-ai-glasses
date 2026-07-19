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
ANALYSIS="$PRIVATE_ROOT/decrypted/03b/analysis"
RAW_EXPORTS="$PRIVATE_ROOT/decrypted/03b/raw-exports"
PUBLIC="$REPO/evidence/sanitized/03b"
MANIFEST="$REPO/evidence/manifests/03b-private-evidence-sha256.json"

HTTP_INPUT="$ANALYSIS/http-requests-private.txt"
PROTOCOL_INPUT="$ANALYSIS/protocol-summary.txt"

CSV_INPUT=""
if [[ -d "$RAW_EXPORTS" ]]; then
  CSV_INPUT="$(find "$RAW_EXPORTS" -maxdepth 1 -type f -name 'PCAPdroid*.csv' -print | sort | tail -1)"
fi

[[ -f "$HTTP_INPUT" ]] || { echo "Missing: $HTTP_INPUT" >&2; exit 1; }
[[ -f "$PROTOCOL_INPUT" ]] || { echo "Missing: $PROTOCOL_INPUT" >&2; exit 1; }
[[ -n "$CSV_INPUT" && -f "$CSV_INPUT" ]] || { echo "Missing PCAPdroid CSV under: $RAW_EXPORTS" >&2; exit 1; }

mkdir -p "$PUBLIC" "$(dirname "$MANIFEST")"

python3 scripts/sanitize_http_requests.py \
  "$HTTP_INPUT" \
  --tsv "$PUBLIC/http-request-paths.tsv" \
  --markdown "$PUBLIC/http-request-paths.md"

python3 scripts/sanitize_pcapdroid_csv.py \
  "$CSV_INPUT" \
  --csv "$PUBLIC/connection-summary.csv" \
  --markdown "$PUBLIC/connection-summary.md"

cp "$PROTOCOL_INPUT" "$PUBLIC/protocol-summary.txt"

manifest_files=("$HTTP_INPUT" "$PROTOCOL_INPUT" "$CSV_INPUT")
for candidate in \
  "$PRIVATE_ROOT/pcap/03b-tls-hi-rokid-idle-model-menu.pcap" \
  "$PRIVATE_ROOT/pcap/03b-tls-hi-rokid-idle-model-menu.sslkeylog" \
  "$PRIVATE_ROOT/logcat/03b-tls-hi-rokid-idle-model-menu-logcat.txt"; do
  [[ -f "$candidate" ]] && manifest_files+=("$candidate")
done

python3 scripts/generate_evidence_manifest.py \
  --root "$PRIVATE_ROOT" \
  --test-id "03b-tls-hi-rokid-idle-model-menu" \
  --output "$MANIFEST" \
  "${manifest_files[@]}"

python3 scripts/validate_public_tree.py --root "$REPO"

echo "Generated:"
echo "  $PUBLIC"
echo "  $MANIFEST"
