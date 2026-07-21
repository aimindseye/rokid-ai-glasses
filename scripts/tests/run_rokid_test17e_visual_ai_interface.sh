#!/usr/bin/env bash
set -euo pipefail

# Test 17E — passive visual-AI network-interface monitor for Rokid non-display glasses.
# Read-only: does not enable Wi-Fi, wireless ADB, root, remount, or contact port 8341.

DURATION_SECONDS="${DURATION_SECONDS:-180}"
SAMPLE_INTERVAL_SECONDS="${SAMPLE_INTERVAL_SECONDS:-0.5}"
TEST_ROOT="${ROKID_TEST_ROOT:-$HOME/rokid-nettest}"

command -v adb >/dev/null 2>&1 || {
  echo "ERROR: adb was not found in PATH." >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 was not found in PATH." >&2
  exit 1
}

GLASSES_SERIALS="$(
  adb devices -l |
  awk '$2 == "device" && /model:RG_glasses/ {print $1}'
)"
GLASSES_COUNT="$(
  printf '%s\n' "$GLASSES_SERIALS" |
  awk 'NF {count++} END {print count+0}'
)"

if [ "$GLASSES_COUNT" -ne 1 ]; then
  echo "ERROR: expected exactly one connected RG_glasses device; found $GLASSES_COUNT." >&2
  adb devices -l >&2
  exit 1
fi

GLASSES_SERIAL="$GLASSES_SERIALS"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_NAME="test17e-visual-ai-interface-${STAMP}"
PRIVATE_DIR="${TEST_ROOT}/private/${RUN_NAME}"
SANITIZED_DIR="${TEST_ROOT}/sanitized/${RUN_NAME}"

mkdir -p "$PRIVATE_DIR" "$SANITIZED_DIR"
chmod 700 "$PRIVATE_DIR"

RAW_MONITOR="$PRIVATE_DIR/interface-monitor-private.txt"
RAW_LOGCAT="$PRIVATE_DIR/wifi-logcat-private.txt"
RAW_BASELINE="$PRIVATE_DIR/baseline-private.txt"
EVENTS_FILE="$PRIVATE_DIR/operator-events-private.txt"
SUMMARY_JSON="$SANITIZED_DIR/assertions.json"
SUMMARY_MD="$SANITIZED_DIR/summary.md"
MANIFEST="$SANITIZED_DIR/private-evidence-sha256.txt"

cleanup() {
  if [ -n "${MONITOR_PID:-}" ]; then
    kill "$MONITOR_PID" 2>/dev/null || true
  fi
  if [ -n "${LOGCAT_PID:-}" ]; then
    kill "$LOGCAT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

printf 'Rokid glasses selected: YES\n'
printf 'Test: Test 17E — visual-AI passive interface monitor\n'
printf 'Duration: %s seconds; interval: %s seconds\n' \
  "$DURATION_SECONDS" "$SAMPLE_INTERVAL_SECONDS"
printf 'Private output: %s\n' "$PRIVATE_DIR"
printf 'Sanitized output: %s\n\n' "$SANITIZED_DIR"

{
  echo "=== HOST UTC START ==="
  date -u +%Y-%m-%dT%H:%M:%SZ

  echo
  echo "=== DEVICE ==="
  adb -s "$GLASSES_SERIAL" shell getprop ro.product.model
  adb -s "$GLASSES_SERIAL" shell getprop ro.build.fingerprint

  echo
  echo "=== ADB STATE ==="
  printf 'service.adb.tcp.port='
  adb -s "$GLASSES_SERIAL" shell getprop service.adb.tcp.port
  printf 'persist.adb.tcp.port='
  adb -s "$GLASSES_SERIAL" shell getprop persist.adb.tcp.port
  printf 'adb_wifi_enabled='
  adb -s "$GLASSES_SERIAL" shell settings get global adb_wifi_enabled

  echo
  echo "=== BASELINE INTERFACES ==="
  adb -s "$GLASSES_SERIAL" shell ip -br addr

  echo
  echo "=== BASELINE ROUTES ==="
  adb -s "$GLASSES_SERIAL" shell ip -4 route
  adb -s "$GLASSES_SERIAL" shell ip -6 route

  echo
  echo "=== BASELINE LISTENERS ==="
  adb -s "$GLASSES_SERIAL" shell ss -ltn

  echo
  echo "=== GATESERVICED ==="
  adb -s "$GLASSES_SERIAL" shell \
    'ps -A -o USER,PID,PPID,NAME,ARGS | grep -F GateServiced || true'
} >"$RAW_BASELINE" 2>&1

# Capture only Wi-Fi/P2P/server-control-related logs. Keep this private.
adb -s "$GLASSES_SERIAL" shell \
  'logcat -v threadtime -T 1 2>/dev/null |
   grep -iE "WifiP2p|SpriteWifi|WebServerService|controlWebServer|wifi-aware|wlan0|p2p0"' \
  >"$RAW_LOGCAT" 2>&1 &
LOGCAT_PID=$!

SAMPLE_COUNT="$(
  python3 - "$DURATION_SECONDS" "$SAMPLE_INTERVAL_SECONDS" <<'PY'
import math
import sys
duration = float(sys.argv[1])
interval = float(sys.argv[2])
if duration <= 0 or interval <= 0:
    raise SystemExit("duration and interval must be positive")
print(max(1, math.ceil(duration / interval)))
PY
)"

# Run one persistent remote shell to minimize ADB overhead.
adb -s "$GLASSES_SERIAL" shell sh -s -- \
  "$SAMPLE_COUNT" "$SAMPLE_INTERVAL_SECONDS" <<'REMOTE' \
  >"$RAW_MONITOR" 2>&1 &
samples="$1"
interval="$2"
i=1

while [ "$i" -le "$samples" ]; do
  echo "=== SAMPLE $i UTC $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

  echo "-- interfaces --"
  ip -br addr 2>/dev/null || true

  echo "-- ipv4-routes --"
  ip -4 route 2>/dev/null || true

  echo "-- ipv6-routes --"
  ip -6 route 2>/dev/null || true

  echo "-- counters --"
  cat /proc/net/dev 2>/dev/null || true

  echo "-- listeners --"
  ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true

  echo
  i=$((i + 1))
  sleep "$interval"
done
REMOTE
MONITOR_PID=$!

echo "Monitor is running."
echo "Use a non-sensitive scene, such as a household object or blank wall."
echo "Perform exactly ONE visual-AI request that requires a fresh camera image."
echo "Suggested prompt: \"What object am I looking at?\""
echo

read -r -p "Press Enter immediately BEFORE asking the visual question: "
printf 'VISUAL_QUESTION_START_HOST_UTC=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$EVENTS_FILE"

echo "Ask the visual question now and wait for the complete spoken answer."
read -r -p "Press Enter AFTER the complete answer finishes: "
printf 'VISUAL_QUESTION_END_HOST_UTC=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$EVENTS_FILE"

echo
echo "Waiting for the passive monitor to finish..."
wait "$MONITOR_PID"
MONITOR_PID=""

kill "$LOGCAT_PID" 2>/dev/null || true
wait "$LOGCAT_PID" 2>/dev/null || true
LOGCAT_PID=""

python3 - "$RAW_MONITOR" "$EVENTS_FILE" "$SUMMARY_JSON" "$SUMMARY_MD" <<'PY'
import json
import re
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
events_path = Path(sys.argv[2])
json_path = Path(sys.argv[3])
md_path = Path(sys.argv[4])

text = raw_path.read_text(errors="replace")
events = events_path.read_text(errors="replace") if events_path.exists() else ""

target_ifaces = ("wlan0", "p2p0", "wifi-aware0")
sample_count = len(re.findall(r"^=== SAMPLE ", text, flags=re.M))
port_8341_count = len(re.findall(r"(?:0\.0\.0\.0|\*):8341\b", text))

interface_up = {name: False for name in target_ifaces}
ipv4_assigned = {name: False for name in target_ifaces}
ipv6_global_assigned = {name: False for name in target_ifaces}
seen_states = {name: set() for name in target_ifaces}

ipv4_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d+\b")
ipv6_re = re.compile(r"\b[0-9a-fA-F:]+/\d+\b")

for line in text.splitlines():
    for name in target_ifaces:
        if not line.startswith(name):
            continue
        parts = line.split()
        if len(parts) >= 2:
            seen_states[name].add(parts[1])
            if parts[1] == "UP":
                interface_up[name] = True

        for value in ipv4_re.findall(line):
            if not value.startswith("127."):
                ipv4_assigned[name] = True

        for value in ipv6_re.findall(line):
            addr = value.split("/", 1)[0].lower()
            if ":" in addr and not addr.startswith("fe80:") and addr != "::1":
                ipv6_global_assigned[name] = True

# /proc/net/dev byte counters: track min/max for target interfaces.
counter_values = {name: [] for name in target_ifaces}
for line in text.splitlines():
    match = re.match(r"\s*([^:]+):\s*(\d+)(?:\s+\d+){7}\s+(\d+)", line)
    if not match:
        continue
    name, rx, tx = match.group(1).strip(), int(match.group(2)), int(match.group(3))
    if name in counter_values:
        counter_values[name].append((rx, tx))

traffic_delta = {}
for name, values in counter_values.items():
    if values:
        rx_values = [v[0] for v in values]
        tx_values = [v[1] for v in values]
        traffic_delta[name] = {
            "rx_bytes_delta": max(rx_values) - min(rx_values),
            "tx_bytes_delta": max(tx_values) - min(tx_values),
        }
    else:
        traffic_delta[name] = {
            "rx_bytes_delta": None,
            "tx_bytes_delta": None,
        }

# Any non-empty route line that is not one of our section markers.
route_lines = []
capture = False
for line in text.splitlines():
    if line == "-- ipv4-routes --":
        capture = True
        continue
    if line.startswith("-- "):
        capture = False
    if capture and line.strip():
        route_lines.append(line.strip())

assertions = {
    "schema": "rokid.test17e.visual-ai-interface.v1",
    "workflow": "single_visual_ai_question",
    "collection": {
        "sample_count": sample_count,
        "operator_start_marker_present": "VISUAL_QUESTION_START_HOST_UTC=" in events,
        "operator_end_marker_present": "VISUAL_QUESTION_END_HOST_UTC=" in events,
    },
    "interfaces": {
        name: {
            "observed_up": interface_up[name],
            "observed_states": sorted(seen_states[name]),
            "ipv4_assigned": ipv4_assigned[name],
            "non_link_local_ipv6_assigned": ipv6_global_assigned[name],
            **traffic_delta[name],
        }
        for name in target_ifaces
    },
    "network": {
        "ipv4_route_observed": bool(route_lines),
        "gate_service_port_8341_listener_observation_count": port_8341_count,
    },
    "privacy": {
        "raw_addresses_included": False,
        "raw_logs_included": False,
        "device_serial_included": False,
    },
}

json_path.write_text(json.dumps(assertions, indent=2, sort_keys=True) + "\n")

activated = [
    name
    for name in target_ifaces
    if interface_up[name]
    or ipv4_assigned[name]
    or ipv6_global_assigned[name]
    or (traffic_delta[name]["rx_bytes_delta"] or 0) > 0
    or (traffic_delta[name]["tx_bytes_delta"] or 0) > 0
]

lines = [
    "# Test 17E — Visual-AI passive interface summary",
    "",
    f"- Samples collected: **{sample_count}**",
    f"- `wlan0` activated: **{'YES' if 'wlan0' in activated else 'NO'}**",
    f"- `p2p0` activated: **{'YES' if 'p2p0' in activated else 'NO'}**",
    f"- `wifi-aware0` activated: **{'YES' if 'wifi-aware0' in activated else 'NO'}**",
    f"- IPv4 route observed: **{'YES' if route_lines else 'NO'}**",
    f"- Port 8341 remained visible: **{'YES' if port_8341_count else 'NO'}**",
    "",
    "This summary intentionally excludes IP addresses, MAC addresses, device serials, and raw logs.",
]
md_path.write_text("\n".join(lines) + "\n")
PY

{
  for file in "$RAW_BASELINE" "$RAW_MONITOR" "$RAW_LOGCAT" "$EVENTS_FILE"; do
    if [ -f "$file" ]; then
      hash="$(shasum -a 256 "$file" | awk '{print $1}')"
      printf '%s  %s\n' "$hash" "$(basename "$file")"
    fi
  done
} >"$MANIFEST"

echo
echo "=== Sanitized result ==="
cat "$SUMMARY_MD"

echo
echo "Sanitized assertions:"
echo "  $SUMMARY_JSON"
echo "Private evidence manifest:"
echo "  $MANIFEST"
echo "Private raw evidence:"
echo "  $PRIVATE_DIR"
echo
echo "Keep the private directory off GitHub and Reddit."
