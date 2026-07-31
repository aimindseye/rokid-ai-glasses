#!/usr/bin/env bash

REPO=""
PHONE=""
EVIDENCE_DIR=""
EXPECTED_HI_ROKID_VERSION=""
RESET_APP_DATA="NO"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/tests/install_test20_r2.sh \
    --repo <repository> \
    --phone <adb-serial> \
    --evidence-dir <build-evidence-directory> \
    --expected-hi-rokid-version G1.11.11.0727 \
    [--reset-app-data]
EOF
}

fail() {
  echo "FAIL: $*" >&2
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --phone)
      PHONE="$2"
      shift 2
      ;;
    --evidence-dir)
      EVIDENCE_DIR="$2"
      shift 2
      ;;
    --expected-hi-rokid-version)
      EXPECTED_HI_ROKID_VERSION="$2"
      shift 2
      ;;
    --reset-app-data)
      RESET_APP_DATA="YES"
      shift
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

echo "Test 20 r2 governed install stage"
echo "================================="

if [ -z "$REPO" ] || [ -z "$PHONE" ] || [ -z "$EVIDENCE_DIR" ] \
   || [ -z "$EXPECTED_HI_ROKID_VERSION" ]; then
  usage >&2
  exit 2
fi

REPO="$(cd "$REPO" 2>/dev/null && pwd)"
if [ -z "$REPO" ]; then
  fail "repository does not exist"
  exit 1
fi

APK="$EVIDENCE_DIR/apk/test20-r2-debug.apk"
ATTESTATION="$EVIDENCE_DIR/build-attestation.txt"
if [ ! -s "$APK" ] || [ ! -s "$ATTESTATION" ]; then
  fail "preserved APK or build attestation is missing"
  exit 1
fi

EXPECTED_APK_SHA="$(awk -F= '$1=="APK_SHA256"{print $2}' "$ATTESTATION")"
ACTUAL_APK_SHA="$(shasum -a 256 "$APK" | awk '{print $1}')"
if [ -z "$EXPECTED_APK_SHA" ] || [ "$ACTUAL_APK_SHA" != "$EXPECTED_APK_SHA" ]; then
  fail "preserved APK hash does not match the build attestation"
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

DEVICE_STATE="$("$ADB" -s "$PHONE" get-state 2>/dev/null)"
if [ "$DEVICE_STATE" != "device" ]; then
  fail "Pixel is not authorized through adb"
  exit 1
fi
echo "PASS: Pixel is authorized"

HI_DUMP="$("$ADB" -s "$PHONE" shell dumpsys package com.rokid.sprite.global.aiapp 2>/dev/null)"
HI_VERSION="$(printf '%s\n' "$HI_DUMP" | sed -n 's/.*versionName=//p' | head -n 1 | tr -d '\r')"
if [ "$HI_VERSION" != "$EXPECTED_HI_ROKID_VERSION" ]; then
  fail "unexpected Hi Rokid version: $HI_VERSION"
  exit 1
fi
echo "PASS: exact Hi Rokid version present"

"$ADB" -s "$PHONE" install -r "$APK"
INSTALL_RC=$?
echo "APK_INSTALL_EXIT_CODE=$INSTALL_RC"
if [ "$INSTALL_RC" -ne 0 ]; then
  fail "APK installation failed"
  exit 1
fi

PACKAGE="org.aimindseye.rokid.cxreventqualification"
DUMP="$("$ADB" -s "$PHONE" shell dumpsys package "$PACKAGE" 2>/dev/null)"
VERSION_NAME="$(printf '%s\n' "$DUMP" | sed -n 's/.*versionName=//p' | head -n 1 | tr -d '\r')"
VERSION_CODE="$(printf '%s\n' "$DUMP" | sed -n 's/.*versionCode=\([0-9][0-9]*\).*/\1/p' | head -n 1)"

if [ "$VERSION_NAME" != "1.0-test20-r2" ] || [ "$VERSION_CODE" != "1" ]; then
  fail "installed Test 20 r2 package identity is incorrect"
  exit 1
fi

if [ "$RESET_APP_DATA" = "YES" ]; then
  "$ADB" -s "$PHONE" shell pm clear "$PACKAGE" >/dev/null
  CLEAR_RC=$?
  echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
  if [ "$CLEAR_RC" -ne 0 ]; then
    fail "could not clear only the Test 20 r2 app data"
    exit 1
  fi
fi

INSTALL_OUTPUT="$EVIDENCE_DIR/governed-install-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$INSTALL_OUTPUT"
PHONE_SHA="$(printf '%s' "$PHONE" | shasum -a 256 | awk '{print $1}')"
cat >"$INSTALL_OUTPUT/install-attestation.txt" <<EOF
TEST20_R2_SCHEMA=rokid.test20-r2.install-attestation.v1
PHONE_SERIAL_SHA256=$PHONE_SHA
HI_ROKID_VERSION=$HI_VERSION
PACKAGE=$PACKAGE
VERSION_CODE=$VERSION_CODE
VERSION_NAME=$VERSION_NAME
APK_SHA256=$ACTUAL_APK_SHA
TEST_APP_DATA_CLEARED=$RESET_APP_DATA
HI_ROKID_DATA_MUTATION=NONE
BLUETOOTH_PAIRING_MUTATION=NONE
REBOOT_OPERATION=NONE
MEDIA_OPERATION=NONE
EOF
shasum -a 256 "$INSTALL_OUTPUT/install-attestation.txt" \
  >"$INSTALL_OUTPUT/SHA256SUMS-private.txt"
(
  cd "$INSTALL_OUTPUT" || exit 90
  shasum -a 256 -c SHA256SUMS-private.txt \
    > hash-verification.txt 2>&1
)
HASH_RC=$?
if [ "$HASH_RC" -ne 0 ]; then
  fail "install evidence hash verification failed"
  exit 1
fi

echo "TEST20_R2_INSTALLED_PACKAGE_IDENTITY=PASS"
echo "TEST20_R2_HI_ROKID_BASELINE=PASS"
echo "TEST20_R2_INSTALL=PASS"
echo "TEST20_R2_INSTALL_EVIDENCE=$INSTALL_OUTPUT"
echo "HI_ROKID_DATA_MUTATION=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "REBOOT_OPERATION=NONE"
echo "MEDIA_OPERATION=NONE"
exit 0
