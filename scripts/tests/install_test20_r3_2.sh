#!/usr/bin/env bash
REPO=""; PHONE=""; EVIDENCE_DIR=""; EXPECTED_HI_ROKID_VERSION=""; RESET=NO
usage(){ echo "Usage: bash scripts/tests/install_test20_r3_2.sh --repo <repo> --phone <serial> --evidence-dir <dir> --expected-hi-rokid-version G1.11.11.0727 [--reset-app-data]"; }
fail(){ echo "FAIL: $*" >&2; return 1; }
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2";shift 2;; --phone) PHONE="$2";shift 2;; --evidence-dir) EVIDENCE_DIR="$2";shift 2;; --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2";shift 2;; --reset-app-data) RESET=YES;shift;; *) fail "unknown argument: $1";exit 2;; esac; done
echo "Test 20 r3.2 governed install stage"; echo "====================================="
[ -n "$REPO" ] && [ -n "$PHONE" ] && [ -n "$EVIDENCE_DIR" ] && [ -n "$EXPECTED_HI_ROKID_VERSION" ] || { usage >&2; exit 2; }
APK="$EVIDENCE_DIR/apk/test20-r3-2-debug.apk"; ATT="$EVIDENCE_DIR/build-attestation.txt"; [ -s "$APK" ] && [ -s "$ATT" ] || { fail "build evidence incomplete"; exit 1; }
EXP="$(awk -F= '$1=="APK_SHA256"{print $2}' "$ATT")"; ACT="$(shasum -a 256 "$APK"|awk '{print $1}')"; [ -n "$EXP" ] && [ "$EXP" = "$ACT" ] || { fail "APK hash mismatch"; exit 1; }
for expected in 'PHOTO_ARG_1=1920' 'PHOTO_ARG_2=1080' 'PHOTO_ARG_3=80' 'MAX_PHOTO_REQUEST_COUNT=1'; do grep -Fxq "$expected" "$ATT" || { fail "build attestation mismatch: $expected"; exit 1; }; done
ADB="${ADB:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb}"; [ -x "$ADB" ] || ADB="$(command -v adb 2>/dev/null)"; [ -x "$ADB" ] || { fail "adb unavailable"; exit 1; }
[ "$("$ADB" -s "$PHONE" get-state 2>/dev/null)" = device ] || { fail "Pixel unauthorized"; exit 1; }; echo "PASS: Pixel is authorized"
DUMP="$("$ADB" -s "$PHONE" shell dumpsys package com.rokid.sprite.global.aiapp 2>/dev/null)"; HI="$(printf '%s\n' "$DUMP"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; [ "$HI" = "$EXPECTED_HI_ROKID_VERSION" ] || { fail "Hi Rokid version mismatch: $HI"; exit 1; }; echo "PASS: exact Hi Rokid version present"
"$ADB" -s "$PHONE" install -r "$APK"; RC=$?; echo "APK_INSTALL_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || exit 1
PACKAGE=org.aimindseye.rokid.cxrphotoqualification; APP="$("$ADB" -s "$PHONE" shell dumpsys package "$PACKAGE" 2>/dev/null)"; VN="$(printf '%s\n' "$APP"|sed -n 's/.*versionName=//p'|head -1|tr -d '\r')"; VC="$(printf '%s\n' "$APP"|sed -n 's/.*versionCode=\([0-9][0-9]*\).*/\1/p'|head -1)"; [ "$VN" = 1.0-test20-r3.2 ] && [ "$VC" = 1 ] || { fail "installed identity mismatch"; exit 1; }
CLEAR_RC=SKIPPED; if [ "$RESET" = YES ]; then "$ADB" -s "$PHONE" shell pm clear "$PACKAGE" >/dev/null; CLEAR_RC=$?; [ "$CLEAR_RC" -eq 0 ] || exit 1; fi; echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"; OUT="$EVIDENCE_DIR/governed-install-$STAMP"; mkdir -p "$OUT"; printf 'PACKAGE=%s\nVERSION_CODE=%s\nVERSION_NAME=%s\nAPK_SHA256=%s\nHI_ROKID_VERSION=%s\nPHOTO_ARG_1=1920\nPHOTO_ARG_2=1080\nPHOTO_ARG_3=80\nMAX_PHOTO_REQUEST_COUNT=1\n' "$PACKAGE" "$VC" "$VN" "$ACT" "$HI" >"$OUT/install-attestation.txt"
echo "TEST20_R3_2_INSTALLED_PACKAGE_IDENTITY=PASS"; echo "TEST20_R3_2_HI_ROKID_BASELINE=PASS"; echo "TEST20_R3_2_INSTALL=PASS"; echo "TEST20_R3_2_INSTALL_EVIDENCE=$OUT"; echo "HI_ROKID_DATA_MUTATION=NONE"; echo "BLUETOOTH_PAIRING_MUTATION=NONE"; echo "REBOOT_OPERATION=NONE"; echo "AUDIO_OPERATION=NONE"
