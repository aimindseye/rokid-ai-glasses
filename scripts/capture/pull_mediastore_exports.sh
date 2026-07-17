#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  pull_mediastore_exports.sh --user USER \
    --pcap-id ID --pcap-out FILE [--pcap-size BYTES] \
    --keylog-id ID --keylog-out FILE [--keylog-size BYTES] \
    --csv-id ID --csv-out FILE [--csv-size BYTES]
EOF
}

USER_ID=""
PCAP_ID=""; PCAP_OUT=""; PCAP_SIZE=""
KEYLOG_ID=""; KEYLOG_OUT=""; KEYLOG_SIZE=""
CSV_ID=""; CSV_OUT=""; CSV_SIZE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER_ID="$2"; shift 2 ;;
    --pcap-id) PCAP_ID="$2"; shift 2 ;;
    --pcap-out) PCAP_OUT="$2"; shift 2 ;;
    --pcap-size) PCAP_SIZE="$2"; shift 2 ;;
    --keylog-id) KEYLOG_ID="$2"; shift 2 ;;
    --keylog-out) KEYLOG_OUT="$2"; shift 2 ;;
    --keylog-size) KEYLOG_SIZE="$2"; shift 2 ;;
    --csv-id) CSV_ID="$2"; shift 2 ;;
    --csv-out) CSV_OUT="$2"; shift 2 ;;
    --csv-size) CSV_SIZE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

for value in "$USER_ID" "$PCAP_ID" "$PCAP_OUT" "$KEYLOG_ID" "$KEYLOG_OUT" "$CSV_ID" "$CSV_OUT"; do
  [[ -n "$value" ]] || { usage >&2; exit 2; }
done
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb not found" >&2; exit 1; }

file_size() {
  if stat -f '%z' "$1" >/dev/null 2>&1; then stat -f '%z' "$1"; else stat -c '%s' "$1"; fi
}

pull_one() {
  local media_id="$1" output="$2" expected="$3" temporary="${2}.part"
  mkdir -p "$(dirname "$output")"
  rm -f "$temporary"
  adb exec-out content read \
    --user "$USER_ID" \
    --uri "content://media/external/file/$media_id" \
    > "$temporary"
  [[ -s "$temporary" ]] || { rm -f "$temporary"; echo "ERROR: empty row $media_id" >&2; exit 1; }
  local actual
  actual="$(file_size "$temporary")"
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    rm -f "$temporary"
    echo "ERROR: row $media_id size $actual != expected $expected" >&2
    exit 1
  fi
  mv "$temporary" "$output"
  printf 'Pulled MediaStore row %s: %s bytes\n' "$media_id" "$actual"
}

pull_one "$PCAP_ID" "$PCAP_OUT" "$PCAP_SIZE"
pull_one "$KEYLOG_ID" "$KEYLOG_OUT" "$KEYLOG_SIZE"
pull_one "$CSV_ID" "$CSV_OUT" "$CSV_SIZE"
echo "MediaStore export pull: PASS"
