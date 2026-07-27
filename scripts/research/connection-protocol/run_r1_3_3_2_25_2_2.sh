#!/usr/bin/env bash
set -euo pipefail

OUTPUT=""
PHONE_SERIAL=""
REPO=""
BUGREPORT=true
HI_ROKID="com.rokid.sprite.global.aiapp"
PROBE="org.aimindseye.rokid.channelprobe"
LOGCAT_PID=""
STOCK_LAUNCHER=""
STOCK_LAUNCH_VERIFIED=false
STOCK_FOREGROUND_VERIFIED=false
RESTORE_DONE=false

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_2_2.sh --repo PATH --output PATH --phone-serial SERIAL [--skip-bugreport]

Runs three BLE scan-only phases while enabling Hi Rokid only during one bounded
60-second stock-assist window. No independent GATT or RFCOMM action occurs.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:?missing repo}"; shift 2 ;;
    --output) OUTPUT="${2:?missing output}"; shift 2 ;;
    --phone-serial) PHONE_SERIAL="${2:?missing serial}"; shift 2 ;;
    --skip-bugreport) BUGREPORT=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$OUTPUT" && -n "$PHONE_SERIAL" ]] || {
  usage >&2
  exit 2
}

REPO="$(cd "$REPO" && pwd -P)"
OUTPUT="$(python3 - "$OUTPUT" <<'PATH_PY'
import os
import sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PATH_PY
)"

case "$OUTPUT" in
  ""|"."|"/"|"$REPO"|"$REPO"/*)
    echo "ERROR: unsafe output path: $OUTPUT" >&2
    exit 1
    ;;
esac

ADB=(adb -s "$PHONE_SERIAL")
"${ADB[@]}" get-state >/dev/null
USER_ID="$("${ADB[@]}" shell am get-current-user | tr -d '\r')"
[[ "$USER_ID" =~ ^[0-9]+$ ]] || {
  echo "ERROR: invalid Android user: $USER_ID" >&2
  exit 1
}

is_disabled() {
  "${ADB[@]}" shell cmd package list packages -d --user "$USER_ID" |
    tr -d '\r' |
    grep -qx "package:$HI_ROKID"
}

pid_of() {
  "${ADB[@]}" shell pidof "$1" 2>/dev/null | tr -d '\r' || true
}

resolve_stock_launcher() {
  "${ADB[@]}" shell cmd package resolve-activity \
    --brief \
    --user "$USER_ID" \
    -a android.intent.action.MAIN \
    -c android.intent.category.LAUNCHER \
    "$HI_ROKID" 2>&1 |
    tr -d '\r' |
    awk 'NF { line=$0 } END { print line }'
}

stock_top_activity() {
  "${ADB[@]}" shell dumpsys activity activities 2>/dev/null |
    tr -d '\r' |
    grep -E 'mResumedActivity|topResumedActivity|ResumedActivity' |
    head -n 5 || true
}

mark_invalid() {
  local reason="$1"
  printf '%s\n' \
    'R25_2_2_CAPTURE_VALID=NO' \
    "R25_2_2_INVALID_REASON=$reason" \
    'R25_2_2_ENDPOINT_HANDOFF_ALLOWED=NO' \
    > "$OUTPUT/INVALID-RUN.txt"
  echo "R25_2_2_CAPTURE_VALID=NO"
  echo "R25_2_2_INVALID_REASON=$reason"
  echo "R25_2_2_ENDPOINT_HANDOFF_ALLOWED=NO"
}

launch_stock_fail_closed() {
  local launch_output="$OUTPUT/stock-launch-private.txt"
  local launcher=""
  local command_output=""
  local launch_rc=0
  local pid=""
  local top=""

  launcher="$(resolve_stock_launcher)"
  echo "R25_2_2_RESOLVED_LAUNCHER=$launcher"
  if [[ -z "$launcher" || "$launcher" == "No activity found" || "$launcher" != "$HI_ROKID/"* ]]; then
    mark_invalid "STOCK_LAUNCHER_RESOLUTION_FAILED"
    return 1
  fi

  STOCK_LAUNCHER="$launcher"
  "${ADB[@]}" shell am force-stop "$HI_ROKID"

  set +e
  command_output="$(
    "${ADB[@]}" shell am start -W \
      --user "$USER_ID" \
      -n "$launcher" 2>&1 |
      tr -d '\r'
  )"
  launch_rc=$?
  set -e
  printf '%s\n' "$command_output" > "$launch_output"

  echo "R25_2_2_EXPLICIT_STOCK_LAUNCH_EXIT=$launch_rc"
  if [[ "$launch_rc" -ne 0 ]] || ! grep -qx 'Status: ok' "$launch_output"; then
    mark_invalid "STOCK_EXPLICIT_LAUNCH_FAILED"
    return 1
  fi

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pid="$(pid_of "$HI_ROKID")"
    [[ -n "$pid" ]] && break
    sleep 1
  done
  top="$(stock_top_activity)"

  echo "R25_2_2_STOCK_PID_AFTER_LAUNCH=${pid:-NONE}"
  echo "R25_2_2_STOCK_TOP_ACTIVITY_BEGIN"
  printf '%s\n' "$top"
  echo "R25_2_2_STOCK_TOP_ACTIVITY_END"

  if [[ -z "$pid" ]]; then
    mark_invalid "STOCK_PROCESS_NOT_STARTED"
    return 1
  fi
  if [[ "$top" != *"$HI_ROKID"* ]]; then
    mark_invalid "STOCK_APP_NOT_FOREGROUND"
    return 1
  fi

  STOCK_LAUNCH_VERIFIED=true
  STOCK_FOREGROUND_VERIFIED=true
  echo "R25_2_2_EXPLICIT_STOCK_LAUNCH=PASS"
  return 0
}

restore() {
  if [[ "$RESTORE_DONE" == true ]]; then
    return
  fi
  RESTORE_DONE=true
  set +e
  if [[ -n "$LOGCAT_PID" ]]; then
    kill "$LOGCAT_PID" >/dev/null 2>&1
    wait "$LOGCAT_PID" >/dev/null 2>&1
    LOGCAT_PID=""
  fi
  "${ADB[@]}" shell pm enable --user "$USER_ID" "$HI_ROKID" >/dev/null 2>&1
  "${ADB[@]}" shell am force-stop "$PROBE" >/dev/null 2>&1
  local launcher="${STOCK_LAUNCHER:-}"
  if [[ -z "$launcher" ]]; then
    launcher="$(resolve_stock_launcher 2>/dev/null || true)"
  fi
  if [[ "$launcher" == "$HI_ROKID/"* ]]; then
    "${ADB[@]}" shell am start -W \
      --user "$USER_ID" \
      -n "$launcher" >/dev/null 2>&1 || true
  fi
  echo "R25_2_2_STOCK_RESTORE_ATTEMPTED=YES"
}

on_signal() {
  trap - EXIT INT TERM
  restore
  exit 130
}

trap restore EXIT
trap on_signal INT TERM

mkdir -p "$OUTPUT/analysis" "$OUTPUT/publication" "$OUTPUT/handoff"

"${ADB[@]}" shell am force-stop "$HI_ROKID"
"${ADB[@]}" shell pm disable-user --user "$USER_ID" "$HI_ROKID" >/dev/null
"${ADB[@]}" shell am force-stop "$PROBE"
"${ADB[@]}" shell run-as "$PROBE" sh -c \
  'rm -f ./files/r25/r25-client-*.jsonl ./files/r25/r25.2.2-correlation-key-private.hex' \
  >/dev/null 2>&1 || true
"${ADB[@]}" logcat -c

is_disabled || {
  echo "ERROR: Hi Rokid is not disabled before baseline" >&2
  exit 1
}
[[ -z "$(pid_of "$HI_ROKID")" ]] || {
  echo "ERROR: Hi Rokid is running before baseline" >&2
  exit 1
}

"${ADB[@]}" shell am start -W -n "$PROBE/.MainActivity" >/dev/null
sleep 2

cat <<'EOF'

R25.2.2 OPERATOR PHASE 1 — STOCK-DISABLED BASELINE

1. Keep the glasses bonded and account-bound. Leave them powered ON.
2. Hi Rokid is disabled and stopped.
3. In Rokid Stock-Assisted BLE Correlation, tap:
     1. Capture stock-disabled baseline — 20 seconds
4. Wait for automatic completion.
5. Return here and press Enter.
EOF
read -r

cat <<'EOF'

R25.2.2 OPERATOR PHASE 2 — STOCK ASSIST

1. In the probe app tap:
     2. Capture stock-assist window — 60 seconds
2. Immediately return here and press Enter.
3. The runner will enable and launch Hi Rokid.
4. In Hi Rokid, power-cycle the glasses once and wait for one successful reconnect.
5. Do not toggle Developer Mode or invoke unrelated features.
EOF
read -r

"${ADB[@]}" logcat -b all -v epoch > "$OUTPUT/stock-assist-logcat-private.txt" &
LOGCAT_PID=$!

"${ADB[@]}" shell pm enable --user "$USER_ID" "$HI_ROKID" >/dev/null
STOCK_ASSIST_START_EPOCH="$(date +%s)"
launch_stock_fail_closed || exit 1

STOCK_UID="$(
  "${ADB[@]}" shell pm list packages -U --user "$USER_ID" "$HI_ROKID" 2>/dev/null |
    tr -d '\r' |
    sed -n 's/^package:.* uid:\([0-9][0-9]*\)$/\1/p' |
    head -n1
)"
if [[ -z "$STOCK_UID" ]]; then
  STOCK_UID="$(
    "${ADB[@]}" shell dumpsys package "$HI_ROKID" 2>/dev/null |
      sed -n 's/.*userId=\([0-9][0-9]*\).*/\1/p' |
      head -n1 |
      tr -d '\r'
  )"
fi
if [[ ! "$STOCK_UID" =~ ^[0-9]+$ ]]; then
  mark_invalid "STOCK_UID_RESOLUTION_FAILED"
  exit 1
fi
echo "R25_2_2_STOCK_UID_RESOLUTION=PASS"

PIDS=()
MISSING_PID_STREAK=0
ASSIST_DEADLINE=$((STOCK_ASSIST_START_EPOCH + 60))
while (( $(date +%s) < ASSIST_DEADLINE )); do
  VALUE="$(pid_of "$HI_ROKID")"
  if [[ -z "$VALUE" ]]; then
    MISSING_PID_STREAK=$((MISSING_PID_STREAK + 1))
  else
    MISSING_PID_STREAK=0
    for PID in $VALUE; do
      if [[ " ${PIDS[*]-} " != *" $PID "* ]]; then
        PIDS+=("$PID")
      fi
    done
  fi

  if (( MISSING_PID_STREAK >= 3 )); then
    mark_invalid "STOCK_PROCESS_LOST_DURING_ASSIST"
    exit 1
  fi

  REMAINING=$((ASSIST_DEADLINE - $(date +%s)))
  (( REMAINING > 0 )) || break
  if (( REMAINING < 2 )); then
    sleep "$REMAINING"
  else
    sleep 2
  fi
done

kill "$LOGCAT_PID" >/dev/null 2>&1 || true
wait "$LOGCAT_PID" >/dev/null 2>&1 || true
LOGCAT_PID=""
STOCK_ASSIST_END_EPOCH="$(date +%s)"

if [[ "$STOCK_LAUNCH_VERIFIED" != true || "$STOCK_FOREGROUND_VERIFIED" != true ]]; then
  mark_invalid "STOCK_LAUNCH_GATE_NOT_SATISFIED"
  exit 1
fi
if [[ ${#PIDS[@]} -eq 0 ]]; then
  mark_invalid "STOCK_PID_EVIDENCE_EMPTY"
  exit 1
fi

echo "R25_2_2_STOCK_ASSIST_PROCESS_GATE=PASS"

"${ADB[@]}" shell am force-stop "$HI_ROKID"
"${ADB[@]}" shell pm disable-user --user "$USER_ID" "$HI_ROKID" >/dev/null

is_disabled || {
  echo "ERROR: Hi Rokid was not disabled after stock assist" >&2
  exit 1
}
[[ -z "$(pid_of "$HI_ROKID")" ]] || {
  echo "ERROR: Hi Rokid is still running after stock assist" >&2
  exit 1
}

"${ADB[@]}" shell am start -W -n "$PROBE/.MainActivity" >/dev/null
sleep 2

cat <<'EOF'

R25.2.2 OPERATOR PHASE 3 — POST-STOCK HANDOFF

1. Hi Rokid is disabled again.
2. In the probe app tap:
     3. Capture post-stock handoff — 20 seconds
3. Wait until the status says all three phases are complete.
4. Return here and press Enter.
EOF
read -r

REL="$(
  "${ADB[@]}" shell run-as "$PROBE" find ./files/r25 -type f -name 'r25-client-*.jsonl' -print |
    tr -d '\r' |
    tail -n1
)"
[[ -n "$REL" ]] || {
  echo "ERROR: client log not found" >&2
  exit 1
}

"${ADB[@]}" exec-out run-as "$PROBE" cat "$REL" > "$OUTPUT/client-probe-private.jsonl"
"${ADB[@]}" exec-out run-as "$PROBE" cat \
  ./files/r25/r25.2.2-correlation-key-private.hex \
  > "$OUTPUT/correlation-key-private.hex"
chmod 600 "$OUTPUT/correlation-key-private.hex"

if [[ "$BUGREPORT" == true ]]; then
  echo "R25_2_2_BUGREPORT_CAPTURE=STARTED"
  "${ADB[@]}" bugreport "$OUTPUT/phone-bugreport-private.zip"
  echo "R25_2_2_BUGREPORT_CAPTURE=COMPLETE"
else
  echo "R25_2_2_BUGREPORT_CAPTURE=SKIPPED"
fi

FINISHED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - \
  "$OUTPUT/run-metadata-private.json" \
  "$PHONE_SERIAL" \
  "$USER_ID" \
  "$STOCK_UID" \
  "$STOCK_ASSIST_START_EPOCH" \
  "$STOCK_ASSIST_END_EPOCH" \
  "$FINISHED_UTC" \
  "${PIDS[*]-}" \
  "$STOCK_LAUNCHER" \
  "$STOCK_LAUNCH_VERIFIED" \
  "$STOCK_FOREGROUND_VERIFIED" <<'METADATA_PY'
import hashlib
import json
import sys

out, serial, user, uid, start, end, finished, pids, launcher, launch_verified, foreground_verified = sys.argv[1:]
value = {
    "schema": "rokid.r25.2.2.run-metadata.v1",
    "release": "r1.3.3.2.25.2.2",
    "phone_serial_sha256": hashlib.sha256(serial.encode()).hexdigest(),
    "android_user": int(user),
    "stock_package": "com.rokid.sprite.global.aiapp",
    "stock_uid": int(uid) if uid.strip().isdigit() else None,
    "stock_pids": [int(item) for item in pids.split() if item.isdigit()],
    "stock_launcher_component": launcher,
    "stock_launch_verified": launch_verified == "true",
    "stock_foreground_verified": foreground_verified == "true",
    "stock_enabled_for_assist": True,
    "stock_disabled_after_assist": True,
    "stock_assist_start_epoch": int(start),
    "stock_assist_end_epoch": int(end),
    "finished_utc": finished,
    "phase_durations_seconds": {
        "stock_disabled_baseline": 20,
        "stock_assist_window": 60,
        "post_stock_handoff": 20,
    },
    "probe_gatt_in_scope": False,
    "probe_rfcomm_in_scope": False,
    "developer_mode_in_scope": False,
}
with open(out, "w", encoding="utf-8") as handle:
    json.dump(value, handle, indent=2, sort_keys=True)
    handle.write("\n")
METADATA_PY

SCRIPT_DIR="$REPO/scripts/research/connection-protocol"
ANALYZE_ARGS=(
  --client-log "$OUTPUT/client-probe-private.jsonl"
  --stock-logcat "$OUTPUT/stock-assist-logcat-private.txt"
  --correlation-key "$OUTPUT/correlation-key-private.hex"
  --run-metadata "$OUTPUT/run-metadata-private.json"
  --private-output "$OUTPUT/analysis/r25.2.2-private-analysis.json"
  --public-output "$OUTPUT/publication/r25.2.2-stock-assisted-attribution.json"
  --handoff-output "$OUTPUT/handoff/r25.2.2-endpoint-handoff-private.json"
)
if [[ -f "$OUTPUT/phone-bugreport-private.zip" ]]; then
  ANALYZE_ARGS+=(--bugreport "$OUTPUT/phone-bugreport-private.zip")
fi

python3 "$SCRIPT_DIR/analyze_r25_2_2_stock_assist.py" "${ANALYZE_ARGS[@]}"
python3 "$SCRIPT_DIR/verify_r25_2_2_publication.py" \
  --publication "$OUTPUT/publication/r25.2.2-stock-assisted-attribution.json"
python3 "$SCRIPT_DIR/finalize_r25_2_2.py" --run "$OUTPUT"

ACCEPTANCE="$(python3 - "$OUTPUT/publication/r25.2.2-stock-assisted-attribution.json" <<'ACCEPTANCE_PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["acceptance"])
ACCEPTANCE_PY
)"

echo "R1_3_3_2_25_2_2_RUN=PASS"
echo "R1_3_3_2_25_2_2_ACCEPTANCE=$ACCEPTANCE"
