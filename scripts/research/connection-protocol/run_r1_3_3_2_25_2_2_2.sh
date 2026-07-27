#!/usr/bin/env bash
set -euo pipefail

REPO=""
SOURCE_PRIVATE_ZIP=""
OUTPUT=""
PHONE_SERIAL=""
SKIP_BUGREPORT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --source-private-zip) SOURCE_PRIVATE_ZIP="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --phone-serial) PHONE_SERIAL="$2"; shift 2 ;;
    --skip-bugreport) SKIP_BUGREPORT=true; shift ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$SOURCE_PRIVATE_ZIP" && -n "$OUTPUT" && -n "$PHONE_SERIAL" ]] || {
  echo "ERROR: --repo, --source-private-zip, --output, and --phone-serial are required" >&2
  exit 2
}

REPO="$(cd "$REPO" && pwd -P)"
SOURCE_PRIVATE_ZIP="$(cd "$(dirname "$SOURCE_PRIVATE_ZIP")" && pwd -P)/$(basename "$SOURCE_PRIVATE_ZIP")"
mkdir -p "$OUTPUT/input" "$OUTPUT/analysis" "$OUTPUT/publication"
OUTPUT="$(cd "$OUTPUT" && pwd -P)"

PACKAGE="org.aimindseye.rokid.channelprobe"
HI_ROKID="com.rokid.sprite.global.aiapp"
INPUT_NAME="r25.2.2.2-connection-only-input-private.json"
ADB=(adb -s "$PHONE_SERIAL")
LOGCAT_PID=""
USER_ID=""
RESTORE_DONE=false

resolve_launcher() {
  local package="$1"
  "${ADB[@]}" shell cmd package resolve-activity \
    --brief --user "$USER_ID" \
    -a android.intent.action.MAIN \
    -c android.intent.category.LAUNCHER \
    "$package" 2>/dev/null | tr -d '\r' | awk 'NF { line=$0 } END { print line }'
}

restore() {
  if [[ "$RESTORE_DONE" == true ]]; then return; fi
  RESTORE_DONE=true
  set +e
  if [[ -n "$LOGCAT_PID" ]]; then
    kill "$LOGCAT_PID" >/dev/null 2>&1
    wait "$LOGCAT_PID" >/dev/null 2>&1
    LOGCAT_PID=""
  fi
  "${ADB[@]}" shell am force-stop "$PACKAGE" >/dev/null 2>&1
  "${ADB[@]}" shell run-as "$PACKAGE" rm -f "files/r25/$INPUT_NAME" >/dev/null 2>&1
  "${ADB[@]}" shell pm enable --user "$USER_ID" "$HI_ROKID" >/dev/null 2>&1
  local stock_launcher
  stock_launcher="$(resolve_launcher "$HI_ROKID" || true)"
  if [[ "$stock_launcher" == "$HI_ROKID/"* ]]; then
    "${ADB[@]}" shell am start -W --user "$USER_ID" -n "$stock_launcher" >/dev/null 2>&1 || true
  fi
  echo "R25_2_2_2_STOCK_RESTORE_ATTEMPTED=YES"
}

on_signal() {
  trap - EXIT INT TERM
  restore
  exit 130
}
trap restore EXIT
trap on_signal INT TERM

"${ADB[@]}" get-state >/dev/null
USER_ID="$("${ADB[@]}" shell am get-current-user | tr -d '\r')"
[[ "$USER_ID" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid Android user" >&2; exit 1; }

SCRIPTS="$REPO/scripts/research/connection-protocol"
INPUT="$OUTPUT/input/$INPUT_NAME"
python3 "$SCRIPTS/prepare_r25_2_2_2_handoff.py" \
  --source-private-zip "$SOURCE_PRIVATE_ZIP" \
  --output "$INPUT"

"${ADB[@]}" shell pm list packages --user "$USER_ID" | tr -d '\r' | grep -qx "package:$PACKAGE" || {
  echo "ERROR: probe package is not installed" >&2
  exit 1
}

PROBE_UID="$(
  "${ADB[@]}" shell pm list packages -U --user "$USER_ID" 2>/dev/null |
    tr -d '\r' |
    sed -n "s/^package:$PACKAGE uid:\([0-9][0-9]*\)$/\1/p" |
    head -n1
)"
if [[ ! "$PROBE_UID" =~ ^[0-9]+$ ]]; then
  echo "ERROR: unable to resolve probe UID" >&2
  exit 1
fi
echo "R25_2_2_2_PROBE_UID=$PROBE_UID"

"${ADB[@]}" shell am force-stop "$HI_ROKID"
"${ADB[@]}" shell pm disable-user --user "$USER_ID" "$HI_ROKID" >/dev/null
sleep 1
if [[ -n "$("${ADB[@]}" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r' || true)" ]]; then
  echo "ERROR: Hi Rokid process remains active" >&2
  exit 1
fi
echo "R25_2_2_2_STRICT_STOCK_ISOLATION=PASS"

list_private_client_logs() {
  "${ADB[@]}" shell run-as "$PACKAGE" ls -1t files/r25 2>/dev/null |
    tr -d '\r' |
    awk '
      substr($0, 1, 11) == "r25-client-" &&
      index($0, "/") == 0 &&
      length($0) > 17 &&
      substr($0, length($0) - 5) == ".jsonl" {
        print "files/r25/" $0
      }
    '
}

"${ADB[@]}" shell am force-stop "$PACKAGE"
"${ADB[@]}" shell run-as "$PACKAGE" mkdir -p files/r25

while IFS= read -r STALE_LOG; do
  [[ -n "$STALE_LOG" ]] || continue
  "${ADB[@]}" shell run-as "$PACKAGE" rm -f "$STALE_LOG"
done < <(list_private_client_logs)

"${ADB[@]}" shell run-as "$PACKAGE" tee "files/r25/$INPUT_NAME" \
  < "$INPUT" >/dev/null
"${ADB[@]}" shell run-as "$PACKAGE" chmod 600 "files/r25/$INPUT_NAME"

LOCAL_INPUT_SHA256="$(shasum -a 256 "$INPUT" | awk '{print $1}')"
REMOTE_INPUT_SHA256="$(
  "${ADB[@]}" exec-out run-as "$PACKAGE" cat "files/r25/$INPUT_NAME" |
    shasum -a 256 |
    awk '{print $1}'
)"
if [[ "$REMOTE_INPUT_SHA256" != "$LOCAL_INPUT_SHA256" ]]; then
  echo "ERROR: staged private handoff hash mismatch" >&2
  exit 1
fi

echo "R25_2_2_2_PRIVATE_HANDOFF_STAGED=YES"
echo "R25_2_2_2_PRIVATE_HANDOFF_STAGE_HASH=PASS"

"${ADB[@]}" logcat -c
"${ADB[@]}" logcat -b all -v epoch > "$OUTPUT/phone-logcat-private.txt" &
LOGCAT_PID=$!
START_EPOCH="$(date +%s)"
STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PROBE_LAUNCHER="$(resolve_launcher "$PACKAGE")"
if [[ "$PROBE_LAUNCHER" != "$PACKAGE/"* ]]; then
  echo "ERROR: probe launcher resolution failed: $PROBE_LAUNCHER" >&2
  exit 1
fi
"${ADB[@]}" shell am start -W --user "$USER_ID" -n "$PROBE_LAUNCHER" >/dev/null

PROBE_PIDS=()
for _ in 1 2 3 4 5; do
  VALUE="$("${ADB[@]}" shell pidof "$PACKAGE" 2>/dev/null | tr -d '\r' || true)"
  for PID in $VALUE; do
    if [[ " ${PROBE_PIDS[*]-} " != *" $PID "* ]]; then PROBE_PIDS+=("$PID"); fi
  done
  [[ ${#PROBE_PIDS[@]} -gt 0 ]] && break
  sleep 1
done
[[ ${#PROBE_PIDS[@]} -gt 0 ]] || { echo "ERROR: probe process not started" >&2; exit 1; }

echo
cat <<'ACTIONS'
R25.2.2.2 STRICT OPERATOR ACTIONS

1. Keep the glasses bonded and powered ON.
2. Hi Rokid is disabled and stopped for this test.
3. In Rokid RFCOMM Connection-Only, confirm the status says:
     Private handoff validated; connection-only probe ready
4. Tap exactly once:
     Open RFCOMM socket — zero payload
5. Wait until status says either:
     zero-payload socket lifecycle complete
   or:
     bounded RFCOMM failure; see private log
6. Return here and press Enter.
ACTIONS
read -r

END_EPOCH="$(date +%s)"
FINISHED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kill "$LOGCAT_PID" >/dev/null 2>&1 || true
wait "$LOGCAT_PID" >/dev/null 2>&1 || true
LOGCAT_PID=""

LATEST="$(list_private_client_logs | head -n1)"
[[ -n "$LATEST" && "$LATEST" == files/r25/r25-client-*.jsonl ]] || {
  echo "ERROR: private client evidence log not found" >&2
  exit 1
}
"${ADB[@]}" exec-out run-as "$PACKAGE" cat "$LATEST" > "$OUTPUT/client-probe-private.jsonl"
"${ADB[@]}" shell run-as "$PACKAGE" rm -f "$LATEST" "files/r25/$INPUT_NAME" >/dev/null

echo "R25_2_2_2_CLIENT_LOG_PULL=PASS"

if [[ "$SKIP_BUGREPORT" == false ]]; then
  echo "R25_2_2_2_BUGREPORT_CAPTURE=STARTED"
  "${ADB[@]}" bugreport "$OUTPUT/phone-bugreport-private.zip" >/dev/null
  echo "R25_2_2_2_BUGREPORT_CAPTURE=COMPLETE"
fi

python3 - \
  "$OUTPUT/run-metadata-private.json" \
  "$PHONE_SERIAL" "$USER_ID" "$PROBE_UID" \
  "$START_EPOCH" "$END_EPOCH" "$STARTED_UTC" "$FINISHED_UTC" \
  "${PROBE_PIDS[*]-}" <<'PY'
import hashlib, json, sys
out, serial, user, uid, start, end, started, finished, pids = sys.argv[1:]
value = {
    "schema": "rokid.r25.2.2.2.run-metadata-private.v1",
    "release": "r1.3.3.2.25.2.2.2",
    "phone_serial_sha256": hashlib.sha256(serial.encode()).hexdigest(),
    "android_user": int(user),
    "probe_uid": int(uid),
    "probe_pids": [int(item) for item in pids.split() if item.isdigit()],
    "start_epoch": int(start),
    "end_epoch": int(end),
    "started_utc": started,
    "finished_utc": finished,
    "stock_package_disabled": True,
    "stock_pid_observed": False,
    "private_handoff_staged": True,
    "application_payload_operation_authorized": False,
}
open(out, "w", encoding="utf-8").write(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY

ANALYZE=(
  python3 "$SCRIPTS/analyze_r25_2_2_2_connection_only.py"
  --client-log "$OUTPUT/client-probe-private.jsonl"
  --phone-logcat "$OUTPUT/phone-logcat-private.txt"
  --metadata "$OUTPUT/run-metadata-private.json"
  --input-handoff "$INPUT"
  --private-output "$OUTPUT/analysis/r25.2.2.2-private-analysis.json"
  --public-output "$OUTPUT/publication/r25.2.2.2-connection-only-qualification.json"
)
if [[ -f "$OUTPUT/phone-bugreport-private.zip" ]]; then
  ANALYZE+=(--bugreport "$OUTPUT/phone-bugreport-private.zip")
fi
"${ANALYZE[@]}"

python3 "$SCRIPTS/verify_r25_2_2_2_publication.py" \
  --publication "$OUTPUT/publication/r25.2.2.2-connection-only-qualification.json"
python3 "$SCRIPTS/finalize_r25_2_2_2.py" --run "$OUTPUT"

echo "R1_3_3_2_25_2_2_2_RUN=PASS"
