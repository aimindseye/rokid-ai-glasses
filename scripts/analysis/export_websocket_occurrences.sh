#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  export_websocket_occurrences.sh --pcap FILE --keylog FILE --output PRIVATE_TSV
EOF
}

PCAP=""; KEYLOG=""; OUTPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pcap) PCAP="$2"; shift 2 ;;
    --keylog) KEYLOG="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$PCAP" && -n "$KEYLOG" && -n "$OUTPUT" ]] || { usage >&2; exit 2; }
[[ -s "$PCAP" ]] || { echo "ERROR: missing PCAP" >&2; exit 1; }
[[ -s "$KEYLOG" ]] || { echo "ERROR: missing key log" >&2; exit 1; }

if command -v tshark >/dev/null 2>&1; then
  TSHARK="$(command -v tshark)"
elif [[ -x /Applications/Wireshark.app/Contents/MacOS/tshark ]]; then
  TSHARK=/Applications/Wireshark.app/Contents/MacOS/tshark
else
  echo "ERROR: tshark not found" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"
"$TSHARK" \
  -o "tls.keylog_file:$KEYLOG" \
  -r "$PCAP" \
  -Y websocket \
  -T fields \
  -E separator=$'\t' \
  -E occurrence=a \
  -E aggregator='|' \
  -e frame.number \
  -e frame.time_epoch \
  -e tcp.stream \
  -e ip.src \
  -e tcp.srcport \
  -e ip.dst \
  -e tcp.dstport \
  -e websocket.opcode \
  -e websocket.payload_length \
  -e websocket.payload \
  > "$OUTPUT"

[[ -s "$OUTPUT" ]] || { echo "ERROR: empty WebSocket export" >&2; exit 1; }
echo "Occurrence-aware WebSocket export: PASS"
