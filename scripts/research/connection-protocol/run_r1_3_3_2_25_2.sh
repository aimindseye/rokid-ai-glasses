#!/usr/bin/env bash
set -euo pipefail

OUTPUT=""
PHONE_SERIAL=""
REPO=""
HI_ROKID="com.rokid.sprite.global.aiapp"
PROBE="org.aimindseye.rokid.channelprobe"

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_2.sh --repo PATH --output PATH --phone-serial SERIAL

Strictly disables Hi Rokid, launches the r25.2 probe, captures a read-only 0x9301
provisioning read and connection-only RFCOMM open/close, verifies zero payload I/O,
and restores Hi Rokid even if the run fails.
EOF
}
while [[ $# -gt 0 ]]; do
 case "$1" in
  --repo) REPO="${2:?missing repo}"; shift 2;;
  --output) OUTPUT="${2:?missing output}"; shift 2;;
  --phone-serial) PHONE_SERIAL="${2:?missing serial}"; shift 2;;
  -h|--help) usage; exit 0;;
  *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2;;
 esac
done
[[ -n "$REPO" && -n "$OUTPUT" && -n "$PHONE_SERIAL" ]] || { usage >&2; exit 2; }
REPO="$(cd "$REPO" && pwd -P)"
OUTPUT="$(python3 - "$OUTPUT" <<'PY'
import os,sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
)"
case "$OUTPUT" in ""|"."|"/"|"$REPO"|"$REPO"/*) echo "ERROR: unsafe output: $OUTPUT" >&2; exit 1;; esac
ADB=(adb -s "$PHONE_SERIAL")
"${ADB[@]}" get-state >/dev/null
USER_ID="$("${ADB[@]}" shell am get-current-user | tr -d '\r')"
[[ "$USER_ID" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid Android user" >&2; exit 1; }

restore() {
 set +e
 "${ADB[@]}" shell pm enable --user "$USER_ID" "$HI_ROKID" >/dev/null 2>&1
 "${ADB[@]}" shell am force-stop "$PROBE" >/dev/null 2>&1
 "${ADB[@]}" shell monkey -p "$HI_ROKID" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
 echo "R25_2_STOCK_RESTORE_ATTEMPTED=YES"
}
trap restore EXIT INT TERM

mkdir -p "$OUTPUT/analysis" "$OUTPUT/publication"
"${ADB[@]}" shell am force-stop "$HI_ROKID"
"${ADB[@]}" shell pm disable-user --user "$USER_ID" "$HI_ROKID" >/dev/null
"${ADB[@]}" shell am force-stop "$PROBE"
"${ADB[@]}" logcat -c
"${ADB[@]}" shell am start -W -n "$PROBE/.MainActivity" >/dev/null
sleep 2

is_disabled() { "${ADB[@]}" shell cmd package list packages -d --user "$USER_ID" | tr -d '\r' | grep -qx "package:$HI_ROKID"; }
pid_of() { "${ADB[@]}" shell pidof "$1" 2>/dev/null | tr -d '\r' || true; }
is_disabled || { echo "ERROR: Hi Rokid is not disabled" >&2; exit 1; }
[[ -z "$(pid_of "$HI_ROKID")" ]] || { echo "ERROR: Hi Rokid is running" >&2; exit 1; }
PROBE_UID="$(
  "${ADB[@]}" shell pm list packages -U "$PROBE" 2>/dev/null |
  tr -d '\r' |
  sed -n 's/^package:.* uid:\([0-9][0-9]*\)$/\1/p' |
  head -n1
)"
if [[ -z "$PROBE_UID" ]]; then
  PROBE_UID="$(
    "${ADB[@]}" shell dumpsys package "$PROBE" 2>/dev/null |
    sed -n 's/.*userId=\([0-9][0-9]*\).*/\1/p' |
    head -n1 |
    tr -d '\r'
  )"
fi
echo "R25_2_PROBE_UID=${PROBE_UID:-UNAVAILABLE}"

cat <<'EOF'

R25.2 STRICT OPERATOR ACTIONS
1. Keep the glasses bonded. Do not unpair or unbind them.
2. Power the glasses off and on once.
3. Do not open Hi Rokid; it is disabled for this test.
4. In Rokid Channel Probe, tap Bonded + SDP for inventory.
5. Tap Start BLE scan and wait for the glasses to appear from a current advertisement.
6. Tap the glasses row once. Confirm the status says it was selected from the current BLE list and that no connection started.
7. Tap "Read 0x9301 + RFCOMM connect-only".
8. Wait until status says "connection-only RFCOMM probe complete" or "r25.2 failed; see private log".
9. Return here and press Enter.
EOF
read -r

HI_DISABLED_AFTER=false; HI_RUNNING_AFTER=true
if is_disabled; then HI_DISABLED_AFTER=true; fi
if [[ -z "$(pid_of "$HI_ROKID")" ]]; then HI_RUNNING_AFTER=false; fi
[[ "$HI_DISABLED_AFTER" == true && "$HI_RUNNING_AFTER" == false ]] || { echo "ERROR: strict isolation lost" >&2; exit 1; }

REL="$("${ADB[@]}" shell run-as "$PROBE" find ./files/r25 -type f -name 'r25-client-*.jsonl' -print | tr -d '\r' | tail -n1)"
[[ -n "$REL" ]] || { echo "ERROR: client log not found" >&2; exit 1; }
"${ADB[@]}" exec-out run-as "$PROBE" cat "$REL" > "$OUTPUT/client-probe-private.jsonl"
"${ADB[@]}" logcat -d -v epoch > "$OUTPUT/phone-logcat-private.txt"

a="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$OUTPUT/run-metadata-private.json" "$PHONE_SERIAL" "$USER_ID" "$PROBE_UID" "$a" <<'PY'
import json,sys
out,serial,user,uid,finished=sys.argv[1:]
probe_uid = int(uid) if uid.strip().isdigit() else None
data={'schema':'rokid.r25.2.run-metadata.v1','phone_serial_sha256':__import__('hashlib').sha256(serial.encode()).hexdigest(),'android_user':int(user),'probe_uid':probe_uid,'hi_rokid_disabled_before':True,'hi_rokid_running_before':False,'hi_rokid_disabled_after':True,'hi_rokid_running_after':False,'finished_utc':finished,'developer_mode_in_scope':False}
open(out,'w').write(json.dumps(data,indent=2,sort_keys=True)+'\n')
PY

SCRIPT_DIR="$REPO/scripts/research/connection-protocol"
python3 "$SCRIPT_DIR/analyze_r25_2_client.py" \
 --client-log "$OUTPUT/client-probe-private.jsonl" \
 --run-metadata "$OUTPUT/run-metadata-private.json" \
 --phone-logcat "$OUTPUT/phone-logcat-private.txt" \
 --private-output "$OUTPUT/analysis/r25.2-connection-only-private.json" \
 --public-output "$OUTPUT/publication/r25.2-connection-only.json"
python3 "$SCRIPT_DIR/verify_r25_2_publication.py" --publication "$OUTPUT/publication/r25.2-connection-only.json"
python3 "$SCRIPT_DIR/finalize_r25_2.py" --run "$OUTPUT"
echo "R1_3_3_2_25_2_ACCEPTANCE=PASS_CONNECTION_ONLY_CLIENT_QUALIFIED"
