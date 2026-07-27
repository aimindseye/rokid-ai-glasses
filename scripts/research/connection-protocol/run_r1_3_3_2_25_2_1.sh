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
  run_r1_3_3_2_25_2_1.sh --repo PATH --output PATH --phone-serial SERIAL

Runs a strict-isolation, three-phase BLE advertisement capture:
  1. glasses OFF baseline — 20 seconds;
  2. power-on transition — 30 seconds;
  3. glasses ON steady state — 30 seconds.

The r25.2.1 application exposes no GATT or RFCOMM action.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:?missing repo}"; shift 2 ;;
    --output) OUTPUT="${2:?missing output}"; shift 2 ;;
    --phone-serial) PHONE_SERIAL="${2:?missing serial}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$OUTPUT" && -n "$PHONE_SERIAL" ]] || {
  usage >&2
  exit 2
}

REPO="$(cd "$REPO" && pwd -P)"
OUTPUT="$(python3 - "$OUTPUT" <<'PY'
import os, sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
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

restore() {
  set +e
  "${ADB[@]}" shell pm enable --user "$USER_ID" "$HI_ROKID" >/dev/null 2>&1
  "${ADB[@]}" shell am force-stop "$PROBE" >/dev/null 2>&1
  "${ADB[@]}" shell monkey -p "$HI_ROKID" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  echo "R25_2_1_STOCK_RESTORE_ATTEMPTED=YES"
}
trap restore EXIT INT TERM

is_disabled() {
  "${ADB[@]}" shell cmd package list packages -d --user "$USER_ID" |
    tr -d '\r' |
    grep -qx "package:$HI_ROKID"
}

pid_of() {
  "${ADB[@]}" shell pidof "$1" 2>/dev/null | tr -d '\r' || true
}

mkdir -p "$OUTPUT/analysis" "$OUTPUT/publication"

"${ADB[@]}" shell am force-stop "$HI_ROKID"
"${ADB[@]}" shell pm disable-user --user "$USER_ID" "$HI_ROKID" >/dev/null
"${ADB[@]}" shell am force-stop "$PROBE"
"${ADB[@]}" shell run-as "$PROBE" sh -c 'rm -f ./files/r25/r25-client-*.jsonl' >/dev/null 2>&1 || true
"${ADB[@]}" logcat -c

is_disabled || {
  echo "ERROR: Hi Rokid is not disabled" >&2
  exit 1
}
[[ -z "$(pid_of "$HI_ROKID")" ]] || {
  echo "ERROR: Hi Rokid is running before capture" >&2
  exit 1
}

"${ADB[@]}" shell am start -W -n "$PROBE/.MainActivity" >/dev/null
sleep 2

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

echo "R25_2_1_PROBE_UID=${PROBE_UID:-UNAVAILABLE}"

cat <<'EOF'

R25.2.1 STRICT OPERATOR ACTIONS

Before beginning:
1. Keep the glasses bonded and account-bound. Do not unpair or unbind them.
2. Confirm the glasses are powered OFF.
3. Do not open Hi Rokid; it is disabled for this test.

On the phone in Rokid BLE Identity Attribution:
4. Tap "1. Capture OFF baseline — 20 seconds" and wait for automatic completion.
5. When the status says the OFF baseline is complete, power the glasses ON.
6. Immediately tap "2. Capture power-on transition — 30 seconds" and wait for automatic completion.
7. Leave the glasses ON.
8. Tap "3. Capture ON steady state — 30 seconds" and wait for automatic completion.
9. Confirm the status says all three phases are complete.
10. Return here and press Enter.

Do not tap a phase twice. Do not use Abort unless the test must be discarded.
EOF
read -r

HI_DISABLED_AFTER=false
HI_RUNNING_AFTER=true
if is_disabled; then HI_DISABLED_AFTER=true; fi
if [[ -z "$(pid_of "$HI_ROKID")" ]]; then HI_RUNNING_AFTER=false; fi

[[ "$HI_DISABLED_AFTER" == true && "$HI_RUNNING_AFTER" == false ]] || {
  echo "ERROR: strict isolation was lost" >&2
  exit 1
}

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
"${ADB[@]}" logcat -d -v epoch > "$OUTPUT/phone-logcat-private.txt"

FINISHED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$OUTPUT/run-metadata-private.json" "$PHONE_SERIAL" "$USER_ID" "$PROBE_UID" "$FINISHED_UTC" <<'PY'
import hashlib
import json
import sys

out, serial, user, uid, finished = sys.argv[1:]
probe_uid = int(uid) if uid.strip().isdigit() else None
value = {
    "schema": "rokid.r25.2.1.run-metadata.v1",
    "release": "r1.3.3.2.25.2.1",
    "phone_serial_sha256": hashlib.sha256(serial.encode()).hexdigest(),
    "android_user": int(user),
    "probe_uid": probe_uid,
    "hi_rokid_disabled_before": True,
    "hi_rokid_running_before": False,
    "hi_rokid_disabled_after": True,
    "hi_rokid_running_after": False,
    "finished_utc": finished,
    "phase_durations_seconds": {
        "off_baseline": 20,
        "power_on_transition": 30,
        "on_steady": 30,
    },
    "gatt_in_scope": False,
    "rfcomm_in_scope": False,
    "developer_mode_in_scope": False,
}
with open(out, "w", encoding="utf-8") as handle:
    json.dump(value, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

SCRIPT_DIR="$REPO/scripts/research/connection-protocol"
python3 "$SCRIPT_DIR/analyze_r25_2_1_power_state.py" \
  --client-log "$OUTPUT/client-probe-private.jsonl" \
  --run-metadata "$OUTPUT/run-metadata-private.json" \
  --private-output "$OUTPUT/analysis/r25.2.1-private-analysis.json" \
  --public-output "$OUTPUT/publication/r25.2.1-power-state-attribution.json"

python3 "$SCRIPT_DIR/verify_r25_2_1_publication.py" \
  --publication "$OUTPUT/publication/r25.2.1-power-state-attribution.json"

python3 "$SCRIPT_DIR/finalize_r25_2_1.py" --run "$OUTPUT"

ACCEPTANCE="$(python3 - "$OUTPUT/publication/r25.2.1-power-state-attribution.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["acceptance"])
PY
)"

echo "R1_3_3_2_25_2_1_RUN=PASS"
echo "R1_3_3_2_25_2_1_ACCEPTANCE=$ACCEPTANCE"
