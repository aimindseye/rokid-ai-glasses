#!/usr/bin/env bash
PHONE=""; FIRMWARE=""; FIRMWARE_SCREENSHOT=""; OUTPUT=""; EXPECTED_HI_ROKID_VERSION=G1.11.11.0727
usage(){ echo "Usage: bash scripts/tests/run_test20_r3_2_photo.sh --phone <serial> --firmware <label> --firmware-screenshot <file> --output <dir>"; }
fail(){ echo "FAIL: $*" >&2; return 1; }
while [ "$#" -gt 0 ]; do case "$1" in --phone) PHONE="$2";shift 2;; --firmware) FIRMWARE="$2";shift 2;; --firmware-screenshot) FIRMWARE_SCREENSHOT="$2";shift 2;; --output) OUTPUT="$2";shift 2;; --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2";shift 2;; *) fail "unknown argument: $1";exit 2;; esac; done
echo "Test 20 r3.2 one-run CXR-L one-shot photo qualification"; echo "========================================================="
[ -n "$PHONE" ] && [ -n "$FIRMWARE" ] && [ -s "$FIRMWARE_SCREENSHOT" ] && [ -n "$OUTPUT" ] || { usage >&2; exit 2; }
ADB="${ADB:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb}"; [ -x "$ADB" ] || ADB="$(command -v adb 2>/dev/null)"; [ -x "$ADB" ] || { fail "adb unavailable"; exit 1; }
PACKAGE=org.aimindseye.rokid.cxrphotoqualification; RUN_ID="cxrl-one-shot-photo-${FIRMWARE}-$(date -u +%Y%m%dT%H%M%SZ)"; REMOTE="/sdcard/Android/data/$PACKAGE/files/test20-r3-2/test20-r3-2-$RUN_ID.jsonl"
mkdir -p "$OUTPUT" || exit 1; echo "RUN_ID=$RUN_ID"; echo "FIRMWARE=$FIRMWARE"; echo "OUTPUT=$OUTPUT"; echo
[ "$("$ADB" -s "$PHONE" get-state 2>/dev/null)" = device ] || { fail "Pixel is not authorized"; exit 1; }; echo "PASS: Pixel is authorized"
HD="$("$ADB" -s "$PHONE" shell dumpsys package com.rokid.sprite.global.aiapp 2>/dev/null)"; HI="$(printf '%s\n' "$HD"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; [ "$HI" = "$EXPECTED_HI_ROKID_VERSION" ] || { fail "Hi Rokid version mismatch"; exit 1; }; echo "HI_ROKID_VERSION=$HI"; echo "PASS: exact Hi Rokid version present"
AD="$("$ADB" -s "$PHONE" shell dumpsys package "$PACKAGE" 2>/dev/null)"; VN="$(printf '%s\n' "$AD"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; VC="$(printf '%s\n' "$AD"|sed -n 's/.*versionCode=\([0-9][0-9]*\).*/\1/p'|head -1)"; [ "$VN" = 1.0-test20-r3.2 ] && [ "$VC" = 1 ] || { fail "Test 20 r3.2 app missing/wrong"; exit 1; }; echo "PASS: Test 20 r3.2 app installed"
cp "$FIRMWARE_SCREENSHOT" "$OUTPUT/firmware-screenshot-private.jpg" || exit 1; echo "PASS: firmware screenshot preserved"
PHONE_SHA="$(printf '%s' "$PHONE"|shasum -a 256|awk '{print $1}')"; cat >"$OUTPUT/run-metadata.txt" <<EOF
TEST20_R3_2_SCHEMA=rokid.test20-r3.2.run-metadata.v1
RUN_ID=$RUN_ID
FIRMWARE=$FIRMWARE
PHONE_SERIAL_SHA256=$PHONE_SHA
HI_ROKID_VERSION=$HI
PACKAGE=$PACKAGE
VERSION_CODE=$VC
VERSION_NAME=$VN
PHOTO_ARG_1=1920
PHOTO_ARG_2=1080
PHOTO_ARG_3=80
PHOTO_ARGUMENT_SEMANTICS=WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED
MAX_PHOTO_REQUEST_COUNT=1
IMAGE_PAYLOAD_PERSISTENCE=NONE
IMAGE_PREVIEW=NONE
AUDIO_OPERATION=NONE
CLOUD_REQUEST=NONE
EOF
echo; echo "Operator checkpoint 1 — stock baseline and bounded target"; echo "---------------------------------------------------------"; cat <<EOF
1. Print docs/tests/assets/test20-r3-2-photo-target.svg.
2. Place it against a plain wall with no people, documents, displays, identifiers, windows, or reflections in frame.
3. Open Hi Rokid and confirm the glasses show Connected.
4. Confirm System shows exactly: $FIRMWARE
5. Do not invoke assistant, audio, other camera controls, unpair, reboot, or update firmware.
EOF
printf "Type HI_ROKID_CONNECTED_TARGET_READY to continue: "; IFS= read -r BASE; [ "$BASE" = HI_ROKID_CONNECTED_TARGET_READY ] || { fail "stock baseline and bounded target were not confirmed"; exit 1; }
"$ADB" -s "$PHONE" shell pm clear "$PACKAGE" >/dev/null; RC=$?; echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || exit 1
"$ADB" -s "$PHONE" shell am start -n "$PACKAGE/.MainActivity" --es run_id "$RUN_ID" --es firmware_label "$FIRMWARE"; [ "$?" -eq 0 ] || exit 1
echo; echo "Operator checkpoint 2 — exactly one bounded photo"; echo "------------------------------------------------"; cat <<'EOF'
In Test 20 r3.2:
1. Tap "1. Authorize through Hi Rokid" once and approve.
2. Return and wait for the private-token confirmation.
3. Tap "2. Start one photo connection" once.
4. Wait for "ONE-SHOT PHOTO READY".
5. Confirm only the printed public target is in frame.
6. Tap "3. Capture exactly one bounded photo" once.
7. Keep the target steady. Do not tap any button again.
8. Wait for Terminal: ONE_SHOT_PHOTO_RECEIVED and automatic disconnect.

Press Enter only after the terminal outcome and automatic disconnect appear.
EOF
IFS= read -r _CONTINUE
LOCAL="$OUTPUT/test20-r3-2-events-private.jsonl"; "$ADB" -s "$PHONE" pull "$REMOTE" "$LOCAL"; RC=$?; echo "APP_EVENT_PULL_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] && [ -s "$LOCAL" ] || { fail "event pull failed"; exit 1; }
echo; echo "Operator checkpoint 3 — bounded-target and no-additional-media attestation"; echo "------------------------------------------------------------------------"; echo "Type BOUNDED_TEST_TARGET_ONLY if the callback was generated while only the printed public target was in frame:"; IFS= read -r TARGET_CONFIRM; echo "Type NO_ADDITIONAL_MEDIA_ACTION if no other camera, audio, assistant, or media action was performed:"; IFS= read -r MEDIA_CONFIRM
echo; echo "Operator checkpoint 4 — consumer recovery"; echo "-----------------------------------------"; echo "Open Hi Rokid, confirm Connected and a normal status page, then type HI_ROKID_RECOVERY_PASS:"; IFS= read -r RECOVERY_CONFIRM
TARGET=NO; MEDIA=YES; RECOVERY=FAIL; [ "$TARGET_CONFIRM" = BOUNDED_TEST_TARGET_ONLY ] && TARGET=YES; [ "$MEDIA_CONFIRM" = NO_ADDITIONAL_MEDIA_ACTION ] && MEDIA=NO; [ "$RECOVERY_CONFIRM" = HI_ROKID_RECOVERY_PASS ] && RECOVERY=PASS
cat >"$OUTPUT/operator-attestation.txt" <<EOF
TEST20_R3_2_SCHEMA=rokid.test20-r3.2.operator-attestation.v1
BOUNDED_TEST_TARGET_ONLY=$TARGET
ADDITIONAL_MEDIA_ACTION=$MEDIA
HI_ROKID_RECOVERY=$RECOVERY
EOF
DIR="$(cd "$(dirname "$0")" && pwd)"; python3 "$DIR/analyze_test20_r3_2_photo.py" --events "$LOCAL" --operator-attestation "$OUTPUT/operator-attestation.txt" --expected-firmware "$FIRMWARE" --output "$OUTPUT"; RC=$?; echo "TEST20_R3_2_ANALYSIS_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || exit 1
( cd "$OUTPUT" || exit 90; find . -type f ! -name SHA256SUMS-private.txt ! -name hash-verification.txt -print | LC_ALL=C sort | while IFS= read -r relpath; do shasum -a 256 "$relpath"; done >SHA256SUMS-private.txt; shasum -a 256 -c SHA256SUMS-private.txt >hash-verification.txt 2>&1 ) || exit 1
ZIP="${OUTPUT}-private-evidence.zip"; rm -f "$ZIP"; (cd "$(dirname "$OUTPUT")" && zip -qry "$ZIP" "$(basename "$OUTPUT")") || exit 1; ZSHA="$(shasum -a 256 "$ZIP"|awk '{print $1}')"; printf '%s  %s\n' "$ZSHA" "$ZIP" >"${ZIP}.sha256.txt"
SZ="${OUTPUT}-sanitized-summary.zip"; rm -f "$SZ"; (cd "$OUTPUT" && zip -qry "$SZ" sanitized) || exit 1; SSHA="$(shasum -a 256 "$SZ"|awk '{print $1}')"; printf '%s  %s\n' "$SSHA" "$(basename "$SZ")" >"${SZ}.sha256.txt"
echo "$ZSHA  $ZIP"; echo; echo "TEST20_R3_2_EVIDENCE_DIRECTORY=$OUTPUT"; echo "TEST20_R3_2_PRIVATE_EVIDENCE_ZIP=$ZIP"; echo "TEST20_R3_2_SANITIZED_SUMMARY_ZIP=$SZ"; echo "TEST20_R3_2_FIRMWARE=$FIRMWARE"; echo "TEST20_R3_2_TAKE_PHOTO_REQUEST_COUNT=1"; echo "TEST20_R3_2_IMAGE_PAYLOAD_PERSISTENCE=NONE"; echo "TEST20_R3_2_IMAGE_PREVIEW=NONE"; echo "TEST20_R3_2_AUDIO_OPERATION=NONE"; echo "TEST20_R3_2_CLOUD_REQUEST=NONE"; echo "HI_ROKID_FORCE_STOP=NONE"; echo "BLUETOOTH_PAIRING_MUTATION=NONE"; echo "REBOOT_OPERATION=NONE"; echo "TEST20_R3_2_CONNECTION_RUN=PASS"
