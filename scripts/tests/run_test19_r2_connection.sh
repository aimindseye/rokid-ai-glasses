#!/usr/bin/env bash
# One bounded CXR-L authorization/connection run. No errexit/nounset/pipefail.

RESULT=0
LOGCAT_PID=""
PHONE_SERIAL=""
FIRMWARE=""
FIRMWARE_SCREENSHOT=""
OUTPUT=""
REPO=""
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"

usage() {
  cat <<'TXT'
Usage: bash scripts/tests/run_test19_r2_connection.sh \
  --phone SERIAL --firmware EXACT_VERSION [options]

Accepted firmware values:
  1.22.009-20260710-151201
  1.23.009-20260725-153201
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --firmware) FIRMWARE="$2"; shift 2 ;;
    --firmware-screenshot) FIRMWARE_SCREENSHOT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage; exit 64 ;;
  esac
done

if [ -z "$REPO" ]; then REPO="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"; fi
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
APP_PACKAGE="org.aimindseye.rokid.cxrlqualification"
HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="cxrl-${FIRMWARE:-unknown}-$STAMP"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9._-' '_')"
if [ -z "$OUTPUT" ]; then OUTPUT="$HOME/rokid-nettest/tests/test19-r2-$RUN_ID"; fi
EVENT_DEVICE_PATH="/sdcard/Android/data/$APP_PACKAGE/files/test19-r2/test19-r2-$RUN_ID.jsonl"
EVENT_LOCAL_PATH="$OUTPUT/app-events.jsonl"
LOGCAT_FILE="$OUTPUT/logcat-test19-r2.txt"
HOST_RECOVERY="$OUTPUT/host-recovery.json"
SUMMARY_JSON="$OUTPUT/summary.json"
SUMMARY_MD="$OUTPUT/summary.md"
PRIVATE_ZIP="${OUTPUT}-private-evidence.zip"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; RESULT=1; }

cleanup_background() {
  if [ -n "$LOGCAT_PID" ]; then
    kill "$LOGCAT_PID" >/dev/null 2>&1 || true
    wait "$LOGCAT_PID" >/dev/null 2>&1 || true
    LOGCAT_PID=""
  fi
}

trap cleanup_background EXIT
trap 'cleanup_background; echo "TEST19_R2_CONNECTION_RUN=INTERRUPTED" >&2; exit 130' INT TERM

version_name() {
  "$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$HI_ROKID_PACKAGE" 2>/dev/null |
    sed -n 's/.*versionName=\([^[:space:]]*\).*/\1/p' | head -n 1
}

case "$FIRMWARE" in
  1.22.009-20260710-151201|1.23.009-20260725-153201) ;;
  *) fail "--firmware must be one of the two exact qualified versions" ;;
esac
if [ -z "$PHONE_SERIAL" ]; then fail "--phone is required"; fi
if [ ! -x "$ADB" ]; then fail "adb is unavailable"; fi
if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
mkdir -p "$OUTPUT"

echo "Test 19 r2 one-run CXR-L qualification"
echo "========================================"
echo "RUN_ID=$RUN_ID"
echo "FIRMWARE=$FIRMWARE"
echo "OUTPUT=$OUTPUT"
echo

if [ "$RESULT" -eq 0 ]; then
  ADB_STATE="$($ADB -s "$PHONE_SERIAL" get-state 2>/dev/null)"
  if [ "$ADB_STATE" = "device" ]; then pass "Pixel is authorized"; else fail "ADB state is $ADB_STATE"; fi
fi
if [ "$RESULT" -eq 0 ]; then
  INSTALLED_VERSION="$(version_name)"
  echo "HI_ROKID_VERSION=$INSTALLED_VERSION"
  if [ "$INSTALLED_VERSION" = "$EXPECTED_HI_ROKID_VERSION" ]; then pass "exact Hi Rokid version present"; else fail "Hi Rokid version mismatch"; fi
fi
if [ "$RESULT" -eq 0 ]; then
  TEST_PATH="$($ADB -s "$PHONE_SERIAL" shell pm path "$APP_PACKAGE" 2>/dev/null | tr -d '\r')"
  if printf '%s\n' "$TEST_PATH" | grep -q '^package:'; then pass "Test 19 r2 app installed"; else fail "Test 19 r2 app not installed"; fi
fi
if [ -n "$FIRMWARE_SCREENSHOT" ]; then
  if [ -s "$FIRMWARE_SCREENSHOT" ]; then
    cp "$FIRMWARE_SCREENSHOT" "$OUTPUT/firmware-screen-$(basename "$FIRMWARE_SCREENSHOT")"
    shasum -a 256 "$OUTPUT/firmware-screen-$(basename "$FIRMWARE_SCREENSHOT")" >"$OUTPUT/firmware-screenshot.sha256.txt"
    pass "firmware screenshot preserved"
  else
    fail "firmware screenshot is missing or empty"
  fi
fi
if [ "$RESULT" -ne 0 ]; then echo "TEST19_R2_CONNECTION_PREFLIGHT=FAIL"; exit 30; fi

cat <<TXT

Operator checkpoint 1 — stock baseline
--------------------------------------
1. Open Hi Rokid.
2. Confirm the glasses show Connected.
3. Confirm the System page shows exactly: $FIRMWARE
4. Keep Hi Rokid installed, signed in, and connected.
5. Do not force-stop Hi Rokid, unpair, reboot, or update firmware during this run.

Type HI_ROKID_CONNECTED to continue:
TXT
read -r BASELINE_CONFIRM
if [ "$BASELINE_CONFIRM" != "HI_ROKID_CONNECTED" ]; then
  echo "TEST19_R2_CONNECTION_RUN=ABORTED_BY_OPERATOR"
  exit 30
fi

"$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$HI_ROKID_PACKAGE" >"$OUTPUT/hi-rokid-package-before.txt" 2>&1
"$ADB" -s "$PHONE_SERIAL" shell dumpsys bluetooth_manager >"$OUTPUT/bluetooth-before.txt" 2>&1
"$ADB" -s "$PHONE_SERIAL" shell pm clear "$APP_PACKAGE" >"$OUTPUT/test-app-clear.txt" 2>&1
CLEAR_RC=$?
echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
if [ "$CLEAR_RC" -ne 0 ]; then fail "could not clear only Test 19 r2 app data"; fi

"$ADB" -s "$PHONE_SERIAL" logcat -c
"$ADB" -s "$PHONE_SERIAL" logcat -v epoch Test19R2:I '*:S' >"$LOGCAT_FILE" 2>&1 &
LOGCAT_PID=$!

"$ADB" -s "$PHONE_SERIAL" shell am start \
  -n "$APP_PACKAGE/.MainActivity" \
  --es run_id "$RUN_ID" \
  --es firmware_label "$FIRMWARE" >"$OUTPUT/app-launch.txt" 2>&1
LAUNCH_RC=$?
cat "$OUTPUT/app-launch.txt"
if [ "$LAUNCH_RC" -ne 0 ]; then fail "Test 19 r2 app launch failed"; fi
if [ "$RESULT" -ne 0 ]; then
  cleanup_background
  echo "TEST19_R2_CONNECTION_RUN=INCOMPLETE"
  exit 30
fi

cat <<'TXT'

Operator checkpoint 2 — exactly one authorization and connection
------------------------------------------------------------------
In Test 19 r2:
1. Tap "1. Authorize through Hi Rokid" once.
2. Approve the Hi Rokid authorization dialog. If it warns that the app is
   unverified, verify the package shown is org.aimindseye.rokid.cxrlqualification.
3. Return to Test 19 r2. Wait for "Authorization token received privately."
4. Tap "2. Start one CXR-L attempt" once.
5. Do not tap either button again and do not switch apps while it waits.
6. Wait for a Terminal outcome. The app automatically disconnects afterward.

Press Enter only after the terminal outcome and automatic disconnect appear.
TXT
read -r _OPERATOR_DONE
sleep 4

"$ADB" -s "$PHONE_SERIAL" pull "$EVENT_DEVICE_PATH" "$EVENT_LOCAL_PATH" >"$OUTPUT/event-pull.txt" 2>&1
PULL_RC=$?
cat "$OUTPUT/event-pull.txt"
echo "APP_EVENT_PULL_EXIT_CODE=$PULL_RC"
if [ "$PULL_RC" -ne 0 ] || [ ! -s "$EVENT_LOCAL_PATH" ]; then fail "app evidence was not pulled"; fi

cleanup_background
"$ADB" -s "$PHONE_SERIAL" shell am force-stop "$APP_PACKAGE" >/dev/null 2>&1
"$ADB" -s "$PHONE_SERIAL" shell monkey -p "$HI_ROKID_PACKAGE" -c android.intent.category.LAUNCHER 1 >"$OUTPUT/hi-rokid-relaunch.txt" 2>&1

cat <<'TXT'

Operator checkpoint 3 — consumer coexistence and recovery
---------------------------------------------------------
Hi Rokid should now be open. Confirm that it still shows the glasses connected
and that an ordinary stock status page opens normally.

Type HI_ROKID_RECOVERY_PASS to record recovery, or anything else to record FAIL:
TXT
read -r RECOVERY_CONFIRM
if [ "$RECOVERY_CONFIRM" = "HI_ROKID_RECOVERY_PASS" ]; then RECOVERY_VALUE=true; else RECOVERY_VALUE=false; fi
cat >"$HOST_RECOVERY" <<JSON
{
  "schema": "rokid.test19-r2.host-recovery.v1",
  "run_id": "$RUN_ID",
  "firmware": "$FIRMWARE",
  "hi_rokid_recovery_confirmed": $RECOVERY_VALUE
}
JSON

"$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$HI_ROKID_PACKAGE" >"$OUTPUT/hi-rokid-package-after.txt" 2>&1
"$ADB" -s "$PHONE_SERIAL" shell dumpsys bluetooth_manager >"$OUTPUT/bluetooth-after.txt" 2>&1

ANALYSIS_RC=30
if [ -s "$EVENT_LOCAL_PATH" ]; then
  python3 "$REPO/scripts/tests/analyze_test19_r2_events.py" \
    --events "$EVENT_LOCAL_PATH" \
    --host-recovery "$HOST_RECOVERY" \
    --summary-json "$SUMMARY_JSON" \
    --summary-md "$SUMMARY_MD"
  ANALYSIS_RC=$?
fi
echo "TEST19_R2_ANALYSIS_EXIT_CODE=$ANALYSIS_RC"

cat >"$OUTPUT/run-metadata.txt" <<TXT
SCHEMA=rokid.test19-r2.connection-run.v1
RUN_ID=$RUN_ID
PHONE_SERIAL_PRIVATE=$PHONE_SERIAL
HI_ROKID_PACKAGE=$HI_ROKID_PACKAGE
HI_ROKID_VERSION=$INSTALLED_VERSION
FIRMWARE=$FIRMWARE
APP_PACKAGE=$APP_PACKAGE
MEDIA_OPERATION=NONE
APK_UPLOAD=NONE
PHONE_REBOOT=NONE
GLASSES_REBOOT=NONE
HI_ROKID_FORCE_STOP=NONE
BLUETOOTH_UNPAIR=NONE
TXT

(
  cd "$OUTPUT" || exit 91
  find . -type f ! -name SHA256SUMS-private.txt -print0 |
    LC_ALL=C sort -z |
    xargs -0 shasum -a 256 >SHA256SUMS-private.txt
)
HASH_RC=$?
echo "HASH_MANIFEST_EXIT_CODE=$HASH_RC"
(
  cd "$OUTPUT" || exit 91
  shasum -a 256 -c SHA256SUMS-private.txt
) >"$OUTPUT/hash-verification.txt" 2>&1
VERIFY_RC=$?
echo "HASH_VERIFICATION_EXIT_CODE=$VERIFY_RC"
(
  cd "$(dirname "$OUTPUT")" || exit 91
  zip -qry "$PRIVATE_ZIP" "$(basename "$OUTPUT")"
)
ZIP_RC=$?
echo "PRIVATE_ZIP_EXIT_CODE=$ZIP_RC"
if [ "$ZIP_RC" -eq 0 ] && [ -s "$PRIVATE_ZIP" ]; then shasum -a 256 "$PRIVATE_ZIP" | tee "${PRIVATE_ZIP}.sha256.txt"; fi

echo
echo "TEST19_R2_EVIDENCE_DIRECTORY=$OUTPUT"
echo "TEST19_R2_PRIVATE_EVIDENCE_ZIP=$PRIVATE_ZIP"
echo "TEST19_R2_FIRMWARE=$FIRMWARE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "REBOOT_OPERATION=NONE"
echo "MEDIA_OPERATION=NONE"
if [ "$ANALYSIS_RC" -eq 0 ] && [ "$HASH_RC" -eq 0 ] && [ "$VERIFY_RC" -eq 0 ] && [ "$ZIP_RC" -eq 0 ]; then
  echo "TEST19_R2_CONNECTION_RUN=PASS"
  exit 0
fi
if [ "$ANALYSIS_RC" -eq 20 ]; then echo "TEST19_R2_CONNECTION_RUN=STOCK_RECOVERY_FAIL"; exit 20; fi
if [ "$ANALYSIS_RC" -eq 10 ]; then echo "TEST19_R2_CONNECTION_RUN=BOUNDED_CXR_L_FAILURE"; exit 10; fi
echo "TEST19_R2_CONNECTION_RUN=INCOMPLETE"
exit 30
