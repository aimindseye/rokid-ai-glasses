#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
APP_DIR="$ROOT/android-client"
APP_PACKAGE="org.aimindseye.rokid.cxrqualification"
APP_ACTIVITY="$APP_PACKAGE/.MainActivity"
HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"
PHONE_SERIAL=""
SDK_VERSION=""
PCAPDROID_CSV=""
OUTPUT=""

usage() {
  cat <<'USAGE'
Usage:
  run_test19_cxr_qualification.sh \
    --phone SERIAL \
    [--sdk-version VERSION] \
    [--pcapdroid-csv PATH] \
    [--hi-rokid-package PACKAGE] \
    [--output PATH]

The runner resolves com.rokid.cxr:client-m from Rokid's Maven repository,
attests the downloaded POM/AAR, builds the connection-only Test 19 app, and
collects ownership evidence. A complete privacy gate requires a PCAPdroid CSV
export covering the qualification run.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --sdk-version) SDK_VERSION="$2"; shift 2 ;;
    --pcapdroid-csv) PCAPDROID_CSV="$2"; shift 2 ;;
    --hi-rokid-package) HI_ROKID_PACKAGE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$PHONE_SERIAL" ]] || { echo "ERROR: --phone is required" >&2; exit 2; }
[[ -z "$SDK_VERSION" || "$SDK_VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]*$ ]] || {
  echo "ERROR: invalid --sdk-version token" >&2; exit 2;
}
for tool in adb bash python3 shasum tar zip git; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: required command unavailable: $tool" >&2; exit 1; }
done
if [[ -n "$PCAPDROID_CSV" ]]; then
  PCAPDROID_DIR="$(dirname "$PCAPDROID_CSV")"
  [[ -d "$PCAPDROID_DIR" ]] || {
    echo "ERROR: PCAPdroid CSV parent directory not found: $PCAPDROID_DIR" >&2
    exit 1
  }
  PCAPDROID_CSV="$(cd "$PCAPDROID_DIR" && pwd)/$(basename "$PCAPDROID_CSV")"
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="$HOME/rokid-nettest/tests/test19-cxr-m-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$OUTPUT/private/app-files" "$OUTPUT/private/system" "$OUTPUT/sanitized"

ADB=(adb -s "$PHONE_SERIAL")
HOST_EVENTS="$OUTPUT/private/host-events.jsonl"
SDK_REPORT="$OUTPUT/private/cxr-artifact-inventory.json"

append_host_event() {
  local event_type="$1"
  local phase="$2"
  local details_file="${3:-}"
  python3 - "$HOST_EVENTS" "$event_type" "$phase" "$details_file" <<'PY'
from __future__ import annotations
import json, sys, time
from pathlib import Path
path = Path(sys.argv[1])
event_type = sys.argv[2]
phase = sys.argv[3]
details_path = Path(sys.argv[4]) if sys.argv[4] else None
details = {}
if details_path and details_path.is_file():
    details = {"snapshot_file": details_path.name}
record = {
    "schema": "rokid.test19.host-event.v1",
    "time_epoch_ms": int(time.time() * 1000),
    "event_type": event_type,
    "phase": phase,
    "details": details,
}
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
PY
}

snapshot_phase() {
  local phase="$1"
  local file="$OUTPUT/private/system/${phase}-$(date -u +%Y%m%dT%H%M%SZ).txt"
  {
    echo "PHASE=$phase"
    echo "TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "PHONE_SERIAL=$PHONE_SERIAL"
    echo
    echo "== packages =="
    "${ADB[@]}" shell dumpsys package "$HI_ROKID_PACKAGE" 2>/dev/null || true
    echo
    "${ADB[@]}" shell dumpsys package "$APP_PACKAGE" 2>/dev/null || true
    echo
    echo "== processes =="
    "${ADB[@]}" shell pidof "$HI_ROKID_PACKAGE" 2>/dev/null || true
    "${ADB[@]}" shell pidof "$APP_PACKAGE" 2>/dev/null || true
    echo
    echo "== bluetooth manager =="
    "${ADB[@]}" shell dumpsys bluetooth_manager 2>/dev/null || true
  } > "$file"
  append_host_event "phase_snapshot" "$phase" "$file"
}

mark_phase() {
  local phase="$1"
  "${ADB[@]}" shell am start -W -n "$APP_ACTIVITY" --es phase "$phase" >/dev/null
  append_host_event "phase_started" "$phase"
  snapshot_phase "$phase"
}

pause_phase() {
  local phase="$1"
  local message="$2"
  echo
  echo "================================================================"
  echo "TEST 19 PHASE: $phase"
  echo "$message"
  echo
  echo "In the Test 19 app, perform only the phase-directed actions."
  read -r -p "Press Enter after the phase is complete... " _
  snapshot_phase "$phase"
  append_host_event "phase_completed" "$phase"
}

wait_for_device() {
  echo "Waiting for phone $PHONE_SERIAL..."
  "${ADB[@]}" wait-for-device
  for _ in $(seq 1 120); do
    if [[ "$("${ADB[@]}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "ERROR: phone did not complete boot" >&2
  return 1
}

echo "Test 19 r1 — Maven-resolved CXR-M compatibility, ownership, and privacy"
echo "Repository: $ROOT"
echo "Phone:      $PHONE_SERIAL"
echo "Output:     $OUTPUT"
echo

[[ -x "$APP_DIR/gradlew" ]] || chmod +x "$APP_DIR/gradlew"
"${ADB[@]}" get-state >/dev/null

MAVEN_DIR="$OUTPUT/private/maven"
RESOLVE_ARGS=(--output "$MAVEN_DIR")
if [[ -n "$SDK_VERSION" ]]; then RESOLVE_ARGS+=(--version "$SDK_VERSION"); fi
python3 "$ROOT/scripts/research/cxr/resolve_cxr_m_maven.py" "${RESOLVE_ARGS[@]}" \
  | tee "$OUTPUT/private/maven-resolution-console.json"
SDK_VERSION="$(python3 - "$MAVEN_DIR/resolution.json" <<'PY2'
import json,sys
r=json.load(open(sys.argv[1])); print(r.get('version',''))
PY2
)"
[[ -n "$SDK_VERSION" ]] || { echo "ERROR: Maven resolver did not produce a version" >&2; exit 1; }
SDK_AAR="$MAVEN_DIR/client-m-$SDK_VERSION.aar"
python3 "$ROOT/scripts/research/cxr/analyze_cxr_artifact.py" \
  --artifact "$SDK_AAR" --output "$SDK_REPORT"
SDK_GRADLE_ARG="-ProkidCxrVersion=$SDK_VERSION"

(
  cd "$APP_DIR"
  ./gradlew --no-daemon clean :test19:assembleDebug "$SDK_GRADLE_ARG"
)
APK="$APP_DIR/test19/build/outputs/apk/debug/test19-debug.apk"
[[ -s "$APK" ]] || { echo "ERROR: Test 19 APK was not produced" >&2; exit 1; }

"${ADB[@]}" install -r "$APK" >/dev/null
"${ADB[@]}" shell pm clear "$APP_PACKAGE" >/dev/null
"${ADB[@]}" install -r "$APK" >/dev/null

if "${ADB[@]}" shell pm grant "$APP_PACKAGE" android.permission.BLUETOOTH_SCAN 2>/dev/null; then :; fi
if "${ADB[@]}" shell pm grant "$APP_PACKAGE" android.permission.BLUETOOTH_CONNECT 2>/dev/null; then :; fi
if "${ADB[@]}" shell pm grant "$APP_PACKAGE" android.permission.ACCESS_FINE_LOCATION 2>/dev/null; then :; fi


"${ADB[@]}" logcat -c || true
append_host_event "test_started" "unassigned"
mark_phase "baseline_stock_connected"

pause_phase \
  "baseline_stock_connected" \
  "Open Hi Rokid, confirm the glasses are connected, leave Hi Rokid in the foreground, then use Test 19 to discover and attempt one CXR-M connection. Query status and disconnect if connected."

"${ADB[@]}" shell monkey -p "$HI_ROKID_PACKAGE" 1 >/dev/null 2>&1 || true
read -r -p "Confirm Hi Rokid is connected, then press Enter to background it... " _
"${ADB[@]}" shell input keyevent KEYCODE_HOME
mark_phase "stock_background"
pause_phase \
  "stock_background" \
  "Hi Rokid has been backgrounded without force-stop. Attempt one CXR-M connection, query status, and disconnect if connected."

"${ADB[@]}" shell am force-stop "$HI_ROKID_PACKAGE"
mark_phase "stock_force_stopped"
pause_phase \
  "stock_force_stopped" \
  "Hi Rokid is force-stopped. Attempt one CXR-M connection, query status, and disconnect cleanly."

mark_phase "custom_only"
pause_phase \
  "custom_only" \
  "Keep Hi Rokid force-stopped. Repeat one clean discovery/connect/status/disconnect cycle to establish the custom-only baseline."

mark_phase "glasses_reboot_reconnect"
pause_phase \
  "glasses_reboot_reconnect" \
  "Power-cycle the glasses, wait for them to become available, then repeat discovery/connect/status/disconnect with Hi Rokid still force-stopped."

PHONE_REBOOT=""
read -r -p "Type REBOOT_PHONE_TEST19 to include the phone-reboot reconnect phase, or press Enter to skip: " PHONE_REBOOT
if [[ "$PHONE_REBOOT" == "REBOOT_PHONE_TEST19" ]]; then
  append_host_event "phone_reboot_requested" "phone_reboot_reconnect"
  "${ADB[@]}" reboot
  wait_for_device
  echo "Unlock the phone if required."
  read -r -p "Press Enter after the phone is unlocked and Bluetooth is ready... " _
  mark_phase "phone_reboot_reconnect"
  pause_phase \
    "phone_reboot_reconnect" \
    "With Hi Rokid still force-stopped, repeat discovery/connect/status/disconnect after the phone reboot."
else
  append_host_event "phase_skipped" "phone_reboot_reconnect"
fi

"${ADB[@]}" shell am force-stop "$APP_PACKAGE"
"${ADB[@]}" shell monkey -p "$HI_ROKID_PACKAGE" 1 >/dev/null 2>&1 || true
read -r -p "Confirm Hi Rokid can reconnect to the glasses, then press Enter... " _
"${ADB[@]}" shell am start -W -n "$APP_ACTIVITY" \
  --es phase stock_recovery \
  --ez stock_recovery_confirmed true >/dev/null
snapshot_phase "stock_recovery"
append_host_event "stock_recovery_confirmed" "stock_recovery"

"${ADB[@]}" logcat -d -v epoch > "$OUTPUT/private/system/logcat.txt" || true
"${ADB[@]}" exec-out run-as "$APP_PACKAGE" sh -c \
  'cd files && test -d test19 && tar -cf - test19' \
  > "$OUTPUT/private/app-files/test19-app-files.tar"
(
  cd "$OUTPUT/private/app-files"
  tar -xf test19-app-files.tar
)

if [[ -n "$PCAPDROID_CSV" ]]; then
  echo
  echo "Stop the PCAPdroid capture and export its connections CSV to:"
  echo "  $PCAPDROID_CSV"
  read -r -p "Press Enter after the CSV export is complete... " _
  if [[ -s "$PCAPDROID_CSV" ]]; then
    cp "$PCAPDROID_CSV" "$OUTPUT/private/system/pcapdroid-connections.csv"
    if python3 "$ROOT/scripts/tests/analyze_test19_network.py" \
        --csv "$OUTPUT/private/system/pcapdroid-connections.csv" \
        --output "$OUTPUT/sanitized/test19-network-summary.json" \
        | tee "$OUTPUT/sanitized/test19-network-markers.txt"; then
      append_host_event "network_privacy_gate_pass" "unassigned"
    else
      append_host_event "network_privacy_gate_fail" "unassigned"
    fi
  else
    echo "WARNING: PCAPdroid CSV was not exported or is empty; privacy qualification is incomplete." >&2
    append_host_event "network_privacy_gate_missing" "unassigned"
  fi
else
  append_host_event "network_privacy_gate_missing" "unassigned"
fi

python3 "$ROOT/scripts/tests/analyze_test19_cxr_evidence.py" \
  --evidence-root "$OUTPUT/private" \
  --summary-json "$OUTPUT/sanitized/test19-summary.json" \
  --summary-md "$OUTPUT/sanitized/test19-summary.md" \
  | tee "$OUTPUT/sanitized/test19-terminal-markers.txt"

append_host_event "test_finalized" "unassigned"

(
  cd "$OUTPUT"
  find private sanitized -type f -print | LC_ALL=C sort | xargs shasum -a 256 \
    > SHA256SUMS-private.txt
)

PRIVATE_ZIP="$OUTPUT-private-evidence.zip"
(
  cd "$(dirname "$OUTPUT")"
  zip -qr "$PRIVATE_ZIP" "$(basename "$OUTPUT")"
)
ZIP_SHA="$(shasum -a 256 "$PRIVATE_ZIP" | awk '{print $1}')"

echo
echo "TEST19_EVIDENCE_DIRECTORY=$OUTPUT"
echo "TEST19_PRIVATE_EVIDENCE_ZIP=$PRIVATE_ZIP"
echo "TEST19_PRIVATE_EVIDENCE_ZIP_SHA256=$ZIP_SHA"
echo "TEST19_R1_DEVICE_OPERATION=BLUETOOTH_AND_LOCAL_NETWORK_QUALIFICATION_ONLY"
echo "TEST19_R1_FIRMWARE_MUTATION=NONE"
echo "TEST19_R1_DEVELOPER_MODE_MUTATION=NONE"
echo "TEST19_R1_CAPTURED_PAYLOAD_REPLAY=NONE"
