#!/usr/bin/env bash
PHONE=""; FIRMWARE=""; FIRMWARE_SCREENSHOT=""; OUTPUT=""; EXPECTED_HI_ROKID_VERSION=G1.11.11.0727
usage(){ echo "Usage: bash scripts/tests/run_test20_r3_1_preflight.sh --phone <serial> --firmware <label> --firmware-screenshot <file> --output <dir>"; }
fail(){ echo "FAIL: $*" >&2; return 1; }
while [ "$#" -gt 0 ]; do case "$1" in --phone) PHONE="$2";shift 2;; --firmware) FIRMWARE="$2";shift 2;; --firmware-screenshot) FIRMWARE_SCREENSHOT="$2";shift 2;; --output) OUTPUT="$2";shift 2;; --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2";shift 2;; *) fail "unknown argument: $1";exit 2;; esac; done
echo "Test 20 r3.1 one-run CXR-L media no-payload preflight"; echo "======================================================"
[ -n "$PHONE" ] && [ -n "$FIRMWARE" ] && [ -s "$FIRMWARE_SCREENSHOT" ] && [ -n "$OUTPUT" ] || { usage >&2; exit 2; }
ADB="${ADB:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb}"; [ -x "$ADB" ] || ADB="$(command -v adb 2>/dev/null)"; [ -x "$ADB" ] || { fail "adb unavailable"; exit 1; }
PACKAGE=org.aimindseye.rokid.cxrmediapreflight; RUN_ID="cxrl-no-payload-${FIRMWARE}-$(date -u +%Y%m%dT%H%M%SZ)"; REMOTE="/sdcard/Android/data/$PACKAGE/files/test20-r3-1/test20-r3-1-$RUN_ID.jsonl"
mkdir -p "$OUTPUT" || exit 1; echo "RUN_ID=$RUN_ID"; echo "FIRMWARE=$FIRMWARE"; echo "OUTPUT=$OUTPUT"; echo
[ "$("$ADB" -s "$PHONE" get-state 2>/dev/null)" = device ] || { fail "Pixel is not authorized"; exit 1; }; echo "PASS: Pixel is authorized"
HD="$("$ADB" -s "$PHONE" shell dumpsys package com.rokid.sprite.global.aiapp 2>/dev/null)"; HI="$(printf '%s\n' "$HD"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; [ "$HI" = "$EXPECTED_HI_ROKID_VERSION" ] || { fail "Hi Rokid version mismatch"; exit 1; }; echo "HI_ROKID_VERSION=$HI"; echo "PASS: exact Hi Rokid version present"
AD="$("$ADB" -s "$PHONE" shell dumpsys package "$PACKAGE" 2>/dev/null)"; VN="$(printf '%s\n' "$AD"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; VC="$(printf '%s\n' "$AD"|sed -n 's/.*versionCode=\([0-9][0-9]*\).*/\1/p'|head -1)"; [ "$VN" = 1.0-test20-r3.1 ] && [ "$VC" = 1 ] || { fail "Test 20 r3.1 app missing/wrong"; exit 1; }; echo "PASS: Test 20 r3.1 app installed"
cp "$FIRMWARE_SCREENSHOT" "$OUTPUT/firmware-screenshot-private.jpg" || exit 1; echo "PASS: firmware screenshot preserved"
PHONE_SHA="$(printf '%s' "$PHONE"|shasum -a 256|awk '{print $1}')"; cat >"$OUTPUT/run-metadata.txt" <<EOF
TEST20_R3_1_SCHEMA=rokid.test20-r3.1.run-metadata.v1
RUN_ID=$RUN_ID
FIRMWARE=$FIRMWARE
PHONE_SERIAL_SHA256=$PHONE_SHA
HI_ROKID_VERSION=$HI
PACKAGE=$PACKAGE
VERSION_CODE=$VC
VERSION_NAME=$VN
OBSERVATION_MS=15000
TAKE_PHOTO_INVOCATION=NONE
START_AUDIO_STREAM_INVOCATION=NONE
STOP_AUDIO_STREAM_INVOCATION=NONE
MEDIA_PAYLOAD_RETENTION=NONE
CLOUD_REQUEST=NONE
EOF
echo; echo "Operator checkpoint 1 — stock baseline"; echo "--------------------------------------"; cat <<EOF
1. Open Hi Rokid and confirm the glasses show Connected.
2. Confirm System shows exactly: $FIRMWARE
3. Keep Hi Rokid installed, signed in, and connected.
4. Do not invoke camera, audio, assistant, media, unpair, reboot, or update firmware.
EOF
printf "Type HI_ROKID_CONNECTED to continue: "; IFS= read -r BASE; [ "$BASE" = HI_ROKID_CONNECTED ] || { fail "stock baseline was not confirmed"; exit 1; }
"$ADB" -s "$PHONE" shell pm clear "$PACKAGE" >/dev/null; RC=$?; echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || exit 1
"$ADB" -s "$PHONE" shell am start -n "$PACKAGE/.MainActivity" --es run_id "$RUN_ID" --es firmware_label "$FIRMWARE"; [ "$?" -eq 0 ] || exit 1
echo; echo "Operator checkpoint 2 — one no-payload preflight"; echo "------------------------------------------------"; cat <<'EOF'
In Test 20 r3.1:
1. Tap "1. Authorize through Hi Rokid" once and approve.
2. Return and wait for the private-token confirmation.
3. Tap "2. Start one no-payload preflight" once.
4. Wait for "NO-PAYLOAD OBSERVATION ARMED".
5. Do not activate camera, audio, assistant, or any media control.
6. Wait for Terminal: NO_PAYLOAD_OBSERVATION_COMPLETE and automatic disconnect.

Press Enter only after the terminal outcome and automatic disconnect appear.
EOF
IFS= read -r _CONTINUE
LOCAL="$OUTPUT/test20-r3-1-events-private.jsonl"; "$ADB" -s "$PHONE" pull "$REMOTE" "$LOCAL"; RC=$?; echo "APP_EVENT_PULL_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] && [ -s "$LOCAL" ] || { fail "event pull failed"; exit 1; }
echo; echo "Operator checkpoint 3 — no-media attestation"; echo "--------------------------------------------"; echo "Type NO_MEDIA_ACTION_PERFORMED if you did not invoke camera, audio, assistant, or media:"; IFS= read -r MEDIA_CONFIRM
echo; echo "Operator checkpoint 4 — consumer recovery"; echo "-----------------------------------------"; echo "Open Hi Rokid, confirm Connected and a normal status page, then type HI_ROKID_RECOVERY_PASS:"; IFS= read -r RECOVERY_CONFIRM
MEDIA=YES; RECOVERY=FAIL; [ "$MEDIA_CONFIRM" = NO_MEDIA_ACTION_PERFORMED ] && MEDIA=NO; [ "$RECOVERY_CONFIRM" = HI_ROKID_RECOVERY_PASS ] && RECOVERY=PASS
cat >"$OUTPUT/operator-attestation.txt" <<EOF
TEST20_R3_1_SCHEMA=rokid.test20-r3.1.operator-attestation.v1
OPERATOR_MEDIA_ACTION=$MEDIA
HI_ROKID_RECOVERY=$RECOVERY
EOF
DIR="$(cd "$(dirname "$0")" && pwd)"; python3 "$DIR/analyze_test20_r3_1_preflight.py" --events "$LOCAL" --operator-attestation "$OUTPUT/operator-attestation.txt" --expected-firmware "$FIRMWARE" --output "$OUTPUT"; RC=$?; echo "TEST20_R3_1_ANALYSIS_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || exit 1
( cd "$OUTPUT" || exit 90; find . -type f ! -name SHA256SUMS-private.txt ! -name hash-verification.txt -print | LC_ALL=C sort | while IFS= read -r relpath; do shasum -a 256 "$relpath"; done >SHA256SUMS-private.txt; shasum -a 256 -c SHA256SUMS-private.txt >hash-verification.txt 2>&1 ) || exit 1
ZIP="${OUTPUT}-private-evidence.zip"; rm -f "$ZIP"; (cd "$(dirname "$OUTPUT")" && zip -qry "$ZIP" "$(basename "$OUTPUT")") || exit 1; ZSHA="$(shasum -a 256 "$ZIP"|awk '{print $1}')"; printf '%s  %s\n' "$ZSHA" "$ZIP" >"${ZIP}.sha256.txt"
SZ="${OUTPUT}-sanitized-summary.zip"; rm -f "$SZ"; (cd "$OUTPUT" && zip -qry "$SZ" sanitized) || exit 1; SSHA="$(shasum -a 256 "$SZ"|awk '{print $1}')"; printf '%s  %s\n' "$SSHA" "$(basename "$SZ")" >"${SZ}.sha256.txt"
echo "$ZSHA  $ZIP"; echo; echo "TEST20_R3_1_EVIDENCE_DIRECTORY=$OUTPUT"; echo "TEST20_R3_1_PRIVATE_EVIDENCE_ZIP=$ZIP"; echo "TEST20_R3_1_SANITIZED_SUMMARY_ZIP=$SZ"; echo "TEST20_R3_1_FIRMWARE=$FIRMWARE"; echo "TEST20_R3_1_TAKE_PHOTO_INVOCATION=NONE"; echo "TEST20_R3_1_START_AUDIO_STREAM_INVOCATION=NONE"; echo "TEST20_R3_1_STOP_AUDIO_STREAM_INVOCATION=NONE"; echo "TEST20_R3_1_MEDIA_PAYLOAD_RETENTION=NONE"; echo "TEST20_R3_1_CLOUD_REQUEST=NONE"; echo "HI_ROKID_FORCE_STOP=NONE"; echo "BLUETOOTH_PAIRING_MUTATION=NONE"; echo "REBOOT_OPERATION=NONE"; echo "TEST20_R3_1_CONNECTION_RUN=PASS"
