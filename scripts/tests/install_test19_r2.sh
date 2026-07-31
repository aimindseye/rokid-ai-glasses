#!/usr/bin/env bash
# Test 19 r2.4 Stage 2: verify a preserved Stage 1 build and install it.
# This stage performs no Maven resolution and no Gradle build.
# It never enables errexit, nounset, or pipefail.

RESULT=0
REPO=""
PHONE_SERIAL=""
EVIDENCE_ROOT=""
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
RESET_APP_DATA="NO"
INSTALL_ATTEMPTED="NO"
INSTALL_SUCCEEDED="NO"
PACKAGE_IDENTITY_SUCCEEDED="NO"
DATA_CLEAR_SUCCEEDED="NO"
INSTALL_EVIDENCE_SUCCEEDED="NO"

EXPECTED_APP_PACKAGE="org.aimindseye.rokid.cxrlqualification"
EXPECTED_APP_VERSION_CODE="7"
EXPECTED_APP_VERSION_NAME="2.4-test19-r2.4"

usage() {
  cat <<'TXT'
Usage: bash scripts/tests/install_test19_r2.sh --phone SERIAL --evidence-dir PATH [options]

Required:
  --phone SERIAL                         Authorized Pixel ADB serial
  --evidence-dir PATH                    Successful Stage 1 evidence root

Options:
  --repo PATH                            Repository root (for provenance only)
  --expected-hi-rokid-version VERSION    Exact installed Hi Rokid version
  --reset-app-data                       Clear only the Test 19 r2 app data
  --help                                 Show this help

This stage never contacts Maven and never invokes Gradle.
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --evidence-dir) EVIDENCE_ROOT="$2"; shift 2 ;;
    --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2"; shift 2 ;;
    --reset-app-data) RESET_APP_DATA="YES"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage; exit 64 ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
fi

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUILD_EVIDENCE_DIR="$EVIDENCE_ROOT/governed-build"
RESUME_JSON="$BUILD_EVIDENCE_DIR/build-resume.json"
APK="$BUILD_EVIDENCE_DIR/test19r2-debug.apk"
INSTALL_EVIDENCE_DIR="$EVIDENCE_ROOT/governed-install-$STAMP"
INSTALL_LOG="$INSTALL_EVIDENCE_DIR/install.log"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; RESULT=1; }

find_aapt() {
  python3 - "$ANDROID_HOME" <<'PY'
from pathlib import Path
import re, sys
root=Path(sys.argv[1])/'build-tools'
items=[]
if root.is_dir():
    for child in root.iterdir():
        tool=child/'aapt'
        if tool.is_file():
            parts=tuple(int(x) for x in re.findall(r'\d+', child.name))
            items.append((parts, str(tool)))
if items:
    print(max(items)[1])
PY
}

json_value() {
  key="$1"
  python3 - "$RESUME_JSON" "$key" <<'PY'
import json, sys
value=json.load(open(sys.argv[1], encoding='utf-8'))
item=value.get(sys.argv[2], '')
if isinstance(item, bool):
    print('true' if item else 'false')
else:
    print(item)
PY
}

extract_package_version() {
  package_name="$1"
  "$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$package_name" 2>/dev/null |
    sed -n 's/.*versionName=\([^[:space:]]*\).*/\1/p' |
    head -n 1
}

finalize_install_hashes() {
  rm -f "$INSTALL_EVIDENCE_DIR/SHA256SUMS-install.txt" "$INSTALL_EVIDENCE_DIR/install-hash-verification.txt"
  (
    cd "$INSTALL_EVIDENCE_DIR" || exit 91
    find . -type f \
      ! -name SHA256SUMS-install.txt \
      ! -name install-hash-verification.txt \
      -print0 |
      LC_ALL=C sort -z |
      xargs -0 shasum -a 256 >SHA256SUMS-install.txt
  ) || return 1
  (
    cd "$INSTALL_EVIDENCE_DIR" || exit 91
    shasum -a 256 -c SHA256SUMS-install.txt
  ) >"$INSTALL_EVIDENCE_DIR/install-hash-verification.txt" 2>&1 || return 1
  return 0
}

echo "Test 19 r2.4 Stage 2 — governed APK installation resume"
echo "=========================================================="
echo "REPO=$REPO"
echo "PHONE_SERIAL=$PHONE_SERIAL"
echo "BUILD_EVIDENCE_ROOT=$EVIDENCE_ROOT"
echo "EXPECTED_HI_ROKID_VERSION=$EXPECTED_HI_ROKID_VERSION"
echo "EXPECTED_APP_PACKAGE=$EXPECTED_APP_PACKAGE"
echo "EXPECTED_APP_VERSION_CODE=$EXPECTED_APP_VERSION_CODE"
echo "EXPECTED_APP_VERSION_NAME=$EXPECTED_APP_VERSION_NAME"
echo "MAVEN_OPERATION=NONE"
echo "GRADLE_OPERATION=NONE"
echo

if [ -z "$PHONE_SERIAL" ]; then fail "--phone is required"; fi
if [ -z "$EVIDENCE_ROOT" ]; then fail "--evidence-dir is required"; fi
if [ ! -x "$ADB" ]; then fail "adb is unavailable: $ADB"; fi
if [ ! -d "$BUILD_EVIDENCE_DIR" ]; then fail "governed build evidence directory is missing"; fi
if [ ! -s "$RESUME_JSON" ]; then fail "build resume record is missing"; fi
if [ ! -s "$APK" ]; then fail "preserved APK is missing"; fi
if [ ! -s "$BUILD_EVIDENCE_DIR/SHA256SUMS-build.txt" ]; then fail "build hash manifest is missing"; fi
if [ -e "$INSTALL_EVIDENCE_DIR" ]; then fail "install evidence directory already exists"; fi

AAPT="${TEST19_AAPT:-$(find_aapt)}"
if [ ! -x "$AAPT" ]; then fail "aapt is unavailable under Android build-tools"; fi

if [ "$RESULT" -eq 0 ]; then
  (
    cd "$BUILD_EVIDENCE_DIR" || exit 91
    shasum -a 256 -c SHA256SUMS-build.txt
  ) >"$EVIDENCE_ROOT/build-resume-hash-verification-$STAMP.txt" 2>&1
  BUILD_HASH_RC=$?
  echo "BUILD_EVIDENCE_HASH_VERIFICATION_EXIT_CODE=$BUILD_HASH_RC"
  if [ "$BUILD_HASH_RC" -eq 0 ]; then pass "immutable Stage 1 build evidence verified"; else fail "Stage 1 build evidence hash verification failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  RESUME_SCHEMA="$(json_value schema)"
  RESUME_CXR_L_VERSION="$(json_value cxr_l_version)"
  RESUME_APP_PACKAGE="$(json_value app_package)"
  RESUME_APP_VERSION_CODE="$(json_value app_version_code)"
  RESUME_APP_VERSION_NAME="$(json_value app_version_name)"
  RESUME_APK_SHA256="$(json_value apk_sha256)"
  RESUME_BUILD_PASS="$(json_value build_stage_pass)"
  RESUME_INSTALL_ATTEMPTED="$(json_value apk_install_attempted)"

  echo "RESUME_SCHEMA=$RESUME_SCHEMA"
  echo "RESUME_CXR_L_VERSION=$RESUME_CXR_L_VERSION"
  echo "RESUME_APP_PACKAGE=$RESUME_APP_PACKAGE"
  echo "RESUME_APP_VERSION_CODE=$RESUME_APP_VERSION_CODE"
  echo "RESUME_APP_VERSION_NAME=$RESUME_APP_VERSION_NAME"

  if [ "$RESUME_SCHEMA" != "rokid.test19.r2.4.build-resume.v1" ] ||
     [ "$RESUME_CXR_L_VERSION" != "1.0.1" ] ||
     [ "$RESUME_APP_PACKAGE" != "$EXPECTED_APP_PACKAGE" ] ||
     [ "$RESUME_APP_VERSION_CODE" != "$EXPECTED_APP_VERSION_CODE" ] ||
     [ "$RESUME_APP_VERSION_NAME" != "$EXPECTED_APP_VERSION_NAME" ] ||
     [ "$RESUME_BUILD_PASS" != "true" ] ||
     [ "$RESUME_INSTALL_ATTEMPTED" != "false" ]; then
    fail "build resume contract does not match r2.4"
  else
    pass "build resume contract verified"
  fi

  ACTUAL_APK_SHA256="$(shasum -a 256 "$APK" | awk '{print $1}')"
  echo "PRESERVED_APK_SHA256=$ACTUAL_APK_SHA256"
  if [ "$ACTUAL_APK_SHA256" = "$RESUME_APK_SHA256" ]; then
    pass "preserved APK hash matches the Stage 1 resume record"
  else
    fail "preserved APK hash mismatch"
  fi
fi

if [ "$RESULT" -eq 0 ]; then
  BADGING="$($AAPT dump badging "$APK" 2>&1)"
  AAPT_RC=$?
  AAPT_PACKAGE="$(printf '%s\n' "$BADGING" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -n 1)"
  AAPT_VERSION_CODE="$(printf '%s\n' "$BADGING" | sed -n "s/^package:.*versionCode='\([^']*\)'.*/\1/p" | head -n 1)"
  AAPT_VERSION_NAME="$(printf '%s\n' "$BADGING" | sed -n "s/^package:.*versionName='\([^']*\)'.*/\1/p" | head -n 1)"
  echo "AAPT_BADGING_EXIT_CODE=$AAPT_RC"
  echo "APK_PACKAGE=$AAPT_PACKAGE"
  echo "APK_VERSION_CODE=$AAPT_VERSION_CODE"
  echo "APK_VERSION_NAME=$AAPT_VERSION_NAME"
  if [ "$AAPT_RC" -eq 0 ] &&
     [ "$AAPT_PACKAGE" = "$EXPECTED_APP_PACKAGE" ] &&
     [ "$AAPT_VERSION_CODE" = "$EXPECTED_APP_VERSION_CODE" ] &&
     [ "$AAPT_VERSION_NAME" = "$EXPECTED_APP_VERSION_NAME" ]; then
    pass "preserved APK identity verified before phone mutation"
  else
    fail "preserved APK identity verification failed"
  fi
fi

if [ "$RESULT" -eq 0 ]; then
  ADB_STATE="$($ADB -s "$PHONE_SERIAL" get-state 2>/dev/null)"
  if [ "$ADB_STATE" = "device" ]; then pass "Pixel is authorized"; else fail "ADB state is $ADB_STATE"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  INSTALLED_HI_ROKID_VERSION="$(extract_package_version "$HI_ROKID_PACKAGE")"
  echo "INSTALLED_HI_ROKID_VERSION=$INSTALLED_HI_ROKID_VERSION"
  if [ "$INSTALLED_HI_ROKID_VERSION" = "$EXPECTED_HI_ROKID_VERSION" ]; then
    pass "exact Hi Rokid baseline is installed"
  else
    fail "expected Hi Rokid $EXPECTED_HI_ROKID_VERSION, found $INSTALLED_HI_ROKID_VERSION"
  fi
fi

if [ "$RESULT" -eq 0 ]; then
  mkdir -p "$INSTALL_EVIDENCE_DIR"
  INSTALL_DIR_RC=$?
  echo "INSTALL_EVIDENCE_DIRECTORY_CREATE_EXIT_CODE=$INSTALL_DIR_RC"
  if [ "$INSTALL_DIR_RC" -ne 0 ]; then fail "install evidence directory creation failed"; fi
fi

if [ "$RESULT" -eq 0 ]; then
  INSTALL_ATTEMPTED="YES"
  "$ADB" -s "$PHONE_SERIAL" install -r "$APK" >"$INSTALL_LOG" 2>&1
  INSTALL_RC=$?
  cat "$INSTALL_LOG"
  echo "ADB_INSTALL_EXIT_CODE=$INSTALL_RC"
  if [ "$INSTALL_RC" -eq 0 ]; then
    INSTALL_SUCCEEDED="YES"
    pass "Test 19 r2.4 APK installed"
  else
    fail "APK installation failed"
  fi
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  PACKAGE_PATH="$($ADB -s "$PHONE_SERIAL" shell pm path "$EXPECTED_APP_PACKAGE" 2>/dev/null | tr -d '\r')"
  INSTALLED_TEST_APP_VERSION="$(extract_package_version "$EXPECTED_APP_PACKAGE")"
  echo "INSTALLED_TEST_APP_VERSION=$INSTALLED_TEST_APP_VERSION"
  if printf '%s\n' "$PACKAGE_PATH" | grep -q '^package:' && [ "$INSTALLED_TEST_APP_VERSION" = "$EXPECTED_APP_VERSION_NAME" ]; then
    PACKAGE_IDENTITY_SUCCEEDED="YES"
    pass "installed Test 19 r2.4 package identity verified"
  else
    fail "installed package identity or version could not be verified"
  fi
fi

if [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ] && [ "$RESET_APP_DATA" = "YES" ]; then
  "$ADB" -s "$PHONE_SERIAL" shell pm clear "$EXPECTED_APP_PACKAGE" >"$INSTALL_EVIDENCE_DIR/app-data-clear.log" 2>&1
  CLEAR_RC=$?
  echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
  if [ "$CLEAR_RC" -eq 0 ]; then
    DATA_CLEAR_SUCCEEDED="YES"
    pass "only Test 19 r2 app data was cleared"
  else
    fail "Test 19 r2 app data clear failed"
  fi
elif [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ]; then
  DATA_CLEAR_SUCCEEDED="NOT_REQUESTED"
fi

if [ -d "$INSTALL_EVIDENCE_DIR" ]; then
  cat >"$INSTALL_EVIDENCE_DIR/installation-identity.txt" <<IDENTITY
SCHEMA=rokid.test19.r2.4.governed-install.v1
CAPTURE_UTC=$STAMP
PHONE_SERIAL=$PHONE_SERIAL
EXPECTED_HI_ROKID_VERSION=$EXPECTED_HI_ROKID_VERSION
APP_PACKAGE=$EXPECTED_APP_PACKAGE
APP_VERSION_CODE=$EXPECTED_APP_VERSION_CODE
APP_VERSION_NAME=$EXPECTED_APP_VERSION_NAME
APK_SHA256=${ACTUAL_APK_SHA256:-UNAVAILABLE}
INSTALL_ATTEMPTED=$INSTALL_ATTEMPTED
INSTALL_SUCCEEDED=$INSTALL_SUCCEEDED
PACKAGE_IDENTITY_SUCCEEDED=$PACKAGE_IDENTITY_SUCCEEDED
APP_DATA_CLEAR_REQUESTED=$RESET_APP_DATA
APP_DATA_CLEAR_SUCCEEDED=$DATA_CLEAR_SUCCEEDED
MAVEN_OPERATION=NONE
GRADLE_OPERATION=NONE
HI_ROKID_DATA_MUTATION=NONE
BLUETOOTH_PAIRING_MUTATION=NONE
GLASSES_OPERATION=NONE
IDENTITY

  finalize_install_hashes
  INSTALL_HASH_RC=$?
  echo "INSTALL_EVIDENCE_HASH_EXIT_CODE=$INSTALL_HASH_RC"
  if [ "$INSTALL_HASH_RC" -eq 0 ]; then
    INSTALL_EVIDENCE_SUCCEEDED="YES"
    pass "governed installation evidence finalized and verified"
  else
    fail "governed installation evidence hash verification failed"
  fi
fi

echo
echo "BUILD_EVIDENCE_ROOT=$EVIDENCE_ROOT"
echo "INSTALL_EVIDENCE_DIRECTORY=$INSTALL_EVIDENCE_DIR"
echo "PRESERVED_APK=$APK"

if [ "$INSTALL_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_APK_INSTALL=PASS"; else echo "TEST19_R2_APK_INSTALL=NOT_COMPLETED"; fi
if [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_PACKAGE_IDENTITY=PASS"; else echo "TEST19_R2_PACKAGE_IDENTITY=NOT_COMPLETED"; fi
if [ "$INSTALL_EVIDENCE_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_GOVERNED_INSTALL_EVIDENCE=PASS"; else echo "TEST19_R2_GOVERNED_INSTALL_EVIDENCE=NOT_COMPLETED"; fi

if [ "$RESULT" -eq 0 ] && [ "$INSTALL_SUCCEEDED" = "YES" ] && [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ] && [ "$INSTALL_EVIDENCE_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_READY_FOR_CONNECTION_RUN=YES"
  echo "TEST19_R2_INSTALL_STAGE=PASS"
else
  echo "TEST19_R2_READY_FOR_CONNECTION_RUN=NO"
  echo "TEST19_R2_INSTALL_STAGE=FAIL"
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ] && [ "$DATA_CLEAR_SUCCEEDED" = "YES" ]; then
  echo "PHONE_MUTATION=TEST19_R2_4_DEBUG_APK_INSTALL_AND_TEST_APP_DATA_CLEAR"
elif [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  echo "PHONE_MUTATION=TEST19_R2_4_DEBUG_APK_INSTALL_ONLY"
else
  echo "PHONE_MUTATION=NONE"
fi

echo "MAVEN_OPERATION=NONE"
echo "GRADLE_OPERATION=NONE"
echo "HI_ROKID_DATA_MUTATION=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "GLASSES_OPERATION=NONE"
exit "$RESULT"
