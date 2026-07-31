#!/usr/bin/env bash

PHONE=""
FIRMWARE=""
FIRMWARE_SCREENSHOT=""
OUTPUT=""
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/tests/run_test20_r2_events.sh \
    --phone <adb-serial> \
    --firmware 1.23.009-20260725-153201 \
    --firmware-screenshot <private screenshot> \
    --output <private evidence directory>
EOF
}

fail() {
  echo "FAIL: $*" >&2
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phone)
      PHONE="$2"
      shift 2
      ;;
    --firmware)
      FIRMWARE="$2"
      shift 2
      ;;
    --firmware-screenshot)
      FIRMWARE_SCREENSHOT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --expected-hi-rokid-version)
      EXPECTED_HI_ROKID_VERSION="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "FAIL: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

echo "Test 20 r2 one-run safe CXR-L event qualification"
echo "=================================================="

if [ -z "$PHONE" ] || [ -z "$FIRMWARE" ] \
   || [ -z "$FIRMWARE_SCREENSHOT" ] || [ -z "$OUTPUT" ]; then
  usage >&2
  exit 2
fi
if [ ! -s "$FIRMWARE_SCREENSHOT" ]; then
  fail "firmware screenshot is missing or empty"
  exit 1
fi

ADB="${ADB:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb}"
if [ ! -x "$ADB" ]; then
  ADB="$(command -v adb 2>/dev/null)"
fi
if [ -z "$ADB" ] || [ ! -x "$ADB" ]; then
  fail "adb is unavailable"
  exit 1
fi

PACKAGE="org.aimindseye.rokid.cxreventqualification"
RUN_ID="cxrl-events-${FIRMWARE}-$(date -u +%Y%m%dT%H%M%SZ)"
REMOTE_EVENT="/sdcard/Android/data/$PACKAGE/files/test20-r2/test20-r2-$RUN_ID.jsonl"

mkdir -p "$OUTPUT"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  fail "cannot create output directory"
  exit 1
fi

echo "RUN_ID=$RUN_ID"
echo "FIRMWARE=$FIRMWARE"
echo "OUTPUT=$OUTPUT"
echo

DEVICE_STATE="$("$ADB" -s "$PHONE" get-state 2>/dev/null)"
if [ "$DEVICE_STATE" != "device" ]; then
  fail "Pixel is not authorized"
  exit 1
fi
echo "PASS: Pixel is authorized"

HI_DUMP="$("$ADB" -s "$PHONE" shell dumpsys package com.rokid.sprite.global.aiapp 2>/dev/null)"
HI_VERSION="$(printf '%s\n' "$HI_DUMP" | sed -n 's/.*versionName=//p' | head -n 1 | tr -d '\r')"
if [ "$HI_VERSION" != "$EXPECTED_HI_ROKID_VERSION" ]; then
  fail "unexpected Hi Rokid version: $HI_VERSION"
  exit 1
fi
echo "HI_ROKID_VERSION=$HI_VERSION"
echo "PASS: exact Hi Rokid version present"

APP_DUMP="$("$ADB" -s "$PHONE" shell dumpsys package "$PACKAGE" 2>/dev/null)"
APP_VERSION="$(printf '%s\n' "$APP_DUMP" | sed -n 's/.*versionName=//p' | head -n 1 | tr -d '\r')"
APP_CODE="$(printf '%s\n' "$APP_DUMP" | sed -n 's/.*versionCode=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
if [ "$APP_VERSION" != "1.0-test20-r2" ] || [ "$APP_CODE" != "1" ]; then
  fail "Test 20 r2 app is missing or has the wrong identity"
  exit 1
fi
echo "PASS: Test 20 r2 app installed"

cp "$FIRMWARE_SCREENSHOT" "$OUTPUT/firmware-screenshot-private.jpg"
COPY_RC=$?
if [ "$COPY_RC" -ne 0 ]; then
  fail "cannot preserve firmware screenshot"
  exit 1
fi
echo "PASS: firmware screenshot preserved"

PHONE_SHA="$(printf '%s' "$PHONE" | shasum -a 256 | awk '{print $1}')"
cat >"$OUTPUT/run-metadata.txt" <<EOF
TEST20_R2_SCHEMA=rokid.test20-r2.run-metadata.v1
RUN_ID=$RUN_ID
FIRMWARE=$FIRMWARE
PHONE_SERIAL_SHA256=$PHONE_SHA
HI_ROKID_VERSION=$HI_VERSION
PACKAGE=$PACKAGE
VERSION_CODE=$APP_CODE
VERSION_NAME=$APP_VERSION
REQUIRED_AI_ASSIST_CYCLES=2
TEST_APP_AI_ASSIST_INVOCATION=NONE
TEST_APP_CLOUD_AI_CLIENT=NONE
TEST_APP_CAMERA_PERMISSION=REMOVED
TEST_APP_RECORD_AUDIO_PERMISSION=REMOVED
TEST_APP_INTERNET_PERMISSION=REMOVED
MEDIA_OPERATION=NONE
CUSTOM_COMMAND=NONE
CUSTOM_VIEW=NONE
GLASS_APP_MANAGEMENT=NONE
HI_ROKID_FORCE_STOP=NONE
BLUETOOTH_PAIRING_MUTATION=NONE
REBOOT_OPERATION=NONE
EOF

echo
echo "Operator checkpoint 1 — stock baseline"
echo "--------------------------------------"
cat <<EOF
1. Open Hi Rokid.
2. Confirm the glasses show Connected.
3. Confirm System shows exactly: $FIRMWARE
4. Keep Hi Rokid installed, signed in, and connected.
5. Do not force-stop Hi Rokid, unpair, reboot, update firmware, or start media.
EOF
echo
printf "Type HI_ROKID_CONNECTED to continue: "
IFS= read -r BASELINE_CONFIRM
if [ "$BASELINE_CONFIRM" != "HI_ROKID_CONNECTED" ]; then
  fail "stock baseline was not confirmed"
  exit 1
fi

"$ADB" -s "$PHONE" shell pm clear "$PACKAGE" >/dev/null
CLEAR_RC=$?
echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
if [ "$CLEAR_RC" -ne 0 ]; then
  fail "could not clear only Test 20 r2 app data"
  exit 1
fi

"$ADB" -s "$PHONE" shell am start \
  -n "$PACKAGE/.MainActivity" \
  --es run_id "$RUN_ID" \
  --es firmware_label "$FIRMWARE"
START_RC=$?
if [ "$START_RC" -ne 0 ]; then
  fail "could not start Test 20 r2 activity"
  exit 1
fi

echo
echo "Operator checkpoint 2 — exactly one connection and two passive cycles"
echo "---------------------------------------------------------------------"
cat <<'EOF'
In Test 20 r2:
1. Tap "1. Authorize through Hi Rokid" once and approve the dialog.
2. Return to Test 20 r2 and wait for the private-token confirmation.
3. Tap "2. Start one event-observer attempt" once.
4. Wait for "EVENT OBSERVATION ARMED".
5. Activate the ordinary stock glasses assistant. Do not ask a question.
6. Cancel immediately before any answer, then wait at least two seconds.
7. Repeat steps 5-6 exactly once.
8. Do not tap either app button again and do not invoke camera or media.
9. Wait for a Terminal outcome and the automatic disconnect.

Press Enter only after the terminal outcome and automatic disconnect appear.
EOF
IFS= read -r _CONTINUE

LOCAL_EVENT="$OUTPUT/test20-r2-events-private.jsonl"
"$ADB" -s "$PHONE" pull "$REMOTE_EVENT" "$LOCAL_EVENT"
PULL_RC=$?
echo "APP_EVENT_PULL_EXIT_CODE=$PULL_RC"
if [ "$PULL_RC" -ne 0 ] || [ ! -s "$LOCAL_EVENT" ]; then
  fail "event stream could not be pulled"
  exit 1
fi

echo
echo "Operator checkpoint 3 — no-query attestation"
echo "--------------------------------------------"
cat <<'EOF'
Confirm both statements:
- You did not ask or dictate an AI question during either cycle.
- No stock AI answer was heard or displayed.

Type NO_SPOKEN_QUERY_NO_AI_RESPONSE to continue:
EOF
IFS= read -r NO_QUERY_CONFIRM

echo
echo "Operator checkpoint 4 — consumer coexistence and recovery"
echo "---------------------------------------------------------"
cat <<'EOF'
Open Hi Rokid. Confirm the glasses still show Connected and an ordinary stock
status page opens normally.

Type HI_ROKID_RECOVERY_PASS to record recovery:
EOF
IFS= read -r RECOVERY_CONFIRM

SPOKEN_QUERY="YES"
STOCK_RESPONSE="YES"
RECOVERY="FAIL"
if [ "$NO_QUERY_CONFIRM" = "NO_SPOKEN_QUERY_NO_AI_RESPONSE" ]; then
  SPOKEN_QUERY="NO"
  STOCK_RESPONSE="NO"
fi
if [ "$RECOVERY_CONFIRM" = "HI_ROKID_RECOVERY_PASS" ]; then
  RECOVERY="PASS"
fi

cat >"$OUTPUT/operator-attestation.txt" <<EOF
TEST20_R2_SCHEMA=rokid.test20-r2.operator-attestation.v1
OPERATOR_SPOKEN_AI_QUERY=$SPOKEN_QUERY
STOCK_AI_RESPONSE_OBSERVED=$STOCK_RESPONSE
HI_ROKID_RECOVERY=$RECOVERY
EOF

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
python3 "$SCRIPT_DIR/analyze_test20_r2_events.py" \
  --events "$LOCAL_EVENT" \
  --operator-attestation "$OUTPUT/operator-attestation.txt" \
  --expected-firmware "$FIRMWARE" \
  --output "$OUTPUT"
ANALYSIS_RC=$?
echo "TEST20_R2_ANALYSIS_EXIT_CODE=$ANALYSIS_RC"
if [ "$ANALYSIS_RC" -ne 0 ]; then
  fail "Test 20 r2 analysis failed"
  exit 1
fi

(
  cd "$OUTPUT" || exit 90
  find . -type f \
    ! -name SHA256SUMS-private.txt \
    ! -name hash-verification.txt \
    -print \
    | LC_ALL=C sort \
    | while IFS= read -r relpath; do
        shasum -a 256 "$relpath"
      done > SHA256SUMS-private.txt
  shasum -a 256 -c SHA256SUMS-private.txt \
    > hash-verification.txt 2>&1
)
HASH_RC=$?
echo "HASH_VERIFICATION_EXIT_CODE=$HASH_RC"
if [ "$HASH_RC" -ne 0 ]; then
  fail "private evidence hash verification failed"
  exit 1
fi

ZIP="${OUTPUT}-private-evidence.zip"
rm -f "$ZIP"
(
  cd "$(dirname "$OUTPUT")" || exit 90
  zip -qry "$ZIP" "$(basename "$OUTPUT")"
)
ZIP_RC=$?
echo "PRIVATE_ZIP_EXIT_CODE=$ZIP_RC"
if [ "$ZIP_RC" -ne 0 ]; then
  fail "private evidence ZIP creation failed"
  exit 1
fi

ZIP_SHA="$(shasum -a 256 "$ZIP" | awk '{print $1}')"
printf '%s  %s\n' "$ZIP_SHA" "$ZIP" >"${ZIP}.sha256.txt"

SANITIZED_ZIP="${OUTPUT}-sanitized-summary.zip"
rm -f "$SANITIZED_ZIP"
(
  cd "$OUTPUT" || exit 90
  zip -qry "$SANITIZED_ZIP" sanitized
)
SANITIZED_RC=$?
if [ "$SANITIZED_RC" -ne 0 ]; then
  fail "sanitized summary ZIP creation failed"
  exit 1
fi
SANITIZED_SHA="$(shasum -a 256 "$SANITIZED_ZIP" | awk '{print $1}')"
printf '%s  %s\n' "$SANITIZED_SHA" "$SANITIZED_ZIP" \
  >"${SANITIZED_ZIP}.sha256.txt"

echo "$ZIP_SHA  $ZIP"
echo
echo "TEST20_R2_EVIDENCE_DIRECTORY=$OUTPUT"
echo "TEST20_R2_PRIVATE_EVIDENCE_ZIP=$ZIP"
echo "TEST20_R2_SANITIZED_SUMMARY_ZIP=$SANITIZED_ZIP"
echo "TEST20_R2_FIRMWARE=$FIRMWARE"
echo "TEST20_R2_TEST_APP_AI_ASSIST_INVOCATION=NONE"
echo "TEST20_R2_TEST_APP_CLOUD_AI_REQUEST=NONE"
echo "TEST20_R2_OPERATOR_SPOKEN_AI_QUERY=NONE"
echo "TEST20_R2_TEST_APP_MEDIA_OPERATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "REBOOT_OPERATION=NONE"
echo "TEST20_R2_CONNECTION_RUN=PASS"
exit 0
