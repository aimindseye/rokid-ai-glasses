#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 "$ROOT/scripts/analysis/analyze_canary_matches.py" \
  --websocket-tsv "$ROOT/fixtures/synthetic/sample-websocket-index.tsv" \
  --terms-json "$ROOT/fixtures/synthetic/sample-terms.json" \
  --private-matches "$TMP/matches.tsv" \
  --safe-summary "$TMP/matches.json"

python3 "$ROOT/scripts/analysis/summarize_websocket_traffic.py" \
  --websocket-tsv "$ROOT/fixtures/synthetic/sample-websocket-index.tsv" \
  --timeline "$ROOT/fixtures/synthetic/sample-timeline.tsv" \
  --safe-summary "$TMP/traffic.json"

python3 - "$TMP/matches.json" "$TMP/traffic.json" <<'PY'
import json, sys
matches = json.load(open(sys.argv[1], encoding='utf-8'))
traffic = json.load(open(sys.argv[2], encoding='utf-8'))
assert matches['websocket_record_count'] == 4, matches
assert matches['match_count'] == 3, matches
assert matches['traffic_totals']['client_to_server']['payload_bytes'] > 0
assert matches['traffic_totals']['server_to_client']['payload_bytes'] > 0
assert traffic['schema'] == 'rokid.voice-canary.traffic-summary.v1'
assert 'invocation_and_speech|client_to_server|2' in traffic['groups']
assert 'post_speech_pre_response|server_to_client|2' in traffic['groups']
print('Synthetic fixture assertions: PASS')
PY

python3 "$ROOT/scripts/analysis/compare_controlled_captures.py" \
  --left "$TMP/matches.json" \
  --right "$TMP/matches.json" \
  --left-label baseline \
  --right-label repeat \
  --output "$TMP/comparison.json"

python3 - \
  "$ROOT/scripts/capture/run_voice_marker_controller.py" \
  "$ROOT/scripts/analysis/analyze_canary_matches.py" \
  "$ROOT/scripts/analysis/summarize_websocket_traffic.py" \
  "$ROOT/scripts/analysis/compare_controlled_captures.py" <<'PY'
from pathlib import Path
import sys
for name in sys.argv[1:]:
    source = Path(name).read_text(encoding='utf-8')
    compile(source, name, 'exec')
print('Python syntax checks: PASS')
PY

echo "Synthetic toolkit tests: PASS"
