#!/usr/bin/env bash
# Build/install preparation for Test 19 r2. This script never enables errexit,
# nounset, or pipefail; invoke it as a child process from an interactive shell.

RESULT=0
PHONE_SERIAL=""
CXR_L_VERSION="1.0.1"
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
RESET_APP_DATA="NO"
REPO=""
RESOLVE_SUCCEEDED="NO"
BUILD_SUCCEEDED="NO"
INSTALL_SUCCEEDED="NO"
DATA_CLEAR_SUCCEEDED="NO"

usage() {
  cat <<'TXT'
Usage: bash scripts/tests/prepare_test19_r2.sh --phone SERIAL [options]

Options:
  --repo PATH                         Repository root
  --sdk-version 1.0.1                 Exact CXR-L version
  --expected-hi-rokid-version VERSION Expected Hi Rokid version
  --reset-app-data                    Clear only the Test 19 r2 app data
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --sdk-version) CXR_L_VERSION="$2"; shift 2 ;;
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
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
ADB="${ADB:-$ANDROID_HOME/platform-tools/adb}"
JAVA_CANDIDATE="${TEST19_JAVA_HOME:-$HOME/Library/Java/JavaVirtualMachines/temurin-23.0.2/Contents/Home}"
if [ ! -x "$JAVA_CANDIDATE/bin/java" ] && [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  JAVA_CANDIDATE="$JAVA_HOME"
fi

APP_PACKAGE="org.aimindseye.rokid.cxrlqualification"
HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PRIVATE_ROOT="$HOME/rokid-nettest/private/test19-r2-cxr-l-maven-$STAMP"
BUILD_LOG="$HOME/Downloads/test19-r2-cxr-l-build-$STAMP.log"
INSTALL_LOG="$HOME/Downloads/test19-r2-cxr-l-install-$STAMP.log"
APK="$REPO/android-client/test19r2/build/outputs/apk/debug/test19r2-debug.apk"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; RESULT=1; }

extract_version() {
  "$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$HI_ROKID_PACKAGE" 2>/dev/null |
    sed -n 's/.*versionName=\([^[:space:]]*\).*/\1/p' |
    head -n 1
}

echo "Test 19 r2 CXR-L preparation"
echo "================================"
echo "REPO=$REPO"
echo "PHONE_SERIAL=$PHONE_SERIAL"
echo "CXR_L_VERSION=$CXR_L_VERSION"
echo "EXPECTED_HI_ROKID_VERSION=$EXPECTED_HI_ROKID_VERSION"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME_SELECTED=$JAVA_CANDIDATE"
echo

if [ -z "$PHONE_SERIAL" ]; then fail "--phone is required"; fi
if [ "$CXR_L_VERSION" != "1.0.1" ]; then fail "only CXR-L 1.0.1 is accepted"; fi
if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
if [ ! -x "$ADB" ]; then fail "adb is unavailable: $ADB"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/java" ]; then fail "selected Java runtime is unavailable"; fi
if [ ! -f "$ANDROID_HOME/platforms/android-36/android.jar" ]; then fail "Android SDK 36 is unavailable"; fi
if [ "$RESULT" -eq 0 ]; then
  ADB_STATE="$($ADB -s "$PHONE_SERIAL" get-state 2>/dev/null)"
  if [ "$ADB_STATE" = "device" ]; then pass "Pixel is authorized"; else fail "ADB state is $ADB_STATE"; fi
fi
if [ "$RESULT" -eq 0 ]; then
  INSTALLED_HI_ROKID_VERSION="$(extract_version)"
  echo "INSTALLED_HI_ROKID_VERSION=$INSTALLED_HI_ROKID_VERSION"
  if [ "$INSTALLED_HI_ROKID_VERSION" = "$EXPECTED_HI_ROKID_VERSION" ]; then
    pass "exact Hi Rokid baseline is installed"
  else
    fail "expected Hi Rokid $EXPECTED_HI_ROKID_VERSION, found $INSTALLED_HI_ROKID_VERSION"
  fi
fi

if [ "$RESULT" -ne 0 ]; then
  echo "TEST19_R2_PREPARE=FAIL"
  exit "$RESULT"
fi

mkdir -p "$PRIVATE_ROOT"
python3 "$REPO/scripts/research/cxr/resolve_cxr_l_maven.py" \
  --version "$CXR_L_VERSION" \
  --output "$PRIVATE_ROOT"
RESOLVE_RC=$?
echo "CXR_L_RESOLVER_EXIT_CODE=$RESOLVE_RC"
if [ "$RESOLVE_RC" -eq 0 ]; then
  RESOLVE_SUCCEEDED="YES"
  pass "CXR-L artifact resolved and attested"
else
  fail "CXR-L artifact resolution failed"
fi

LOCAL_PROPERTIES="$REPO/android-client/local.properties"
printf 'sdk.dir=%s\n' "$ANDROID_HOME" >"$LOCAL_PROPERTIES"
if [ -d "$REPO/.git/info" ]; then
  grep -qxF '/android-client/local.properties' "$REPO/.git/info/exclude" 2>/dev/null ||
    printf '%s\n' '/android-client/local.properties' >>"$REPO/.git/info/exclude"
fi

if [ "$RESULT" -eq 0 ]; then
  (
    cd "$REPO/android-client" || exit 91
    JAVA_HOME="$JAVA_CANDIDATE" \
    ANDROID_HOME="$ANDROID_HOME" \
    ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT" \
    PATH="$JAVA_CANDIDATE/bin:$PATH" \
    ./gradlew --no-daemon --console=plain --stacktrace \
      "-Dorg.gradle.java.home=$JAVA_CANDIDATE" \
      "-ProkidCxrLVersion=$CXR_L_VERSION" \
      :test19r2:assembleDebug
  ) >"$BUILD_LOG" 2>&1
  BUILD_RC=$?
  echo "GRADLE_BUILD_EXIT_CODE=$BUILD_RC"
  if [ "$BUILD_RC" -eq 0 ] && [ -s "$APK" ]; then
    BUILD_SUCCEEDED="YES"
    pass "Test 19 r2 APK built"
    shasum -a 256 "$APK"
  else
    fail "Test 19 r2 APK build failed"
    tail -n 180 "$BUILD_LOG"
  fi
fi

if [ "$RESULT" -eq 0 ]; then
  "$ADB" -s "$PHONE_SERIAL" install -r "$APK" >"$INSTALL_LOG" 2>&1
  INSTALL_RC=$?
  cat "$INSTALL_LOG"
  echo "ADB_INSTALL_EXIT_CODE=$INSTALL_RC"
  if [ "$INSTALL_RC" -eq 0 ]; then
    INSTALL_SUCCEEDED="YES"
    pass "Test 19 r2 APK installed"
  else
    fail "APK installation failed"
  fi
fi

if [ "$RESULT" -eq 0 ] && [ "$RESET_APP_DATA" = "YES" ]; then
  "$ADB" -s "$PHONE_SERIAL" shell pm clear "$APP_PACKAGE" >/dev/null 2>&1
  CLEAR_RC=$?
  echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
  if [ "$CLEAR_RC" -eq 0 ]; then
    DATA_CLEAR_SUCCEEDED="YES"
    pass "only Test 19 r2 app data was cleared"
  else
    fail "Test 19 r2 data clear failed"
  fi
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  PACKAGE_PATH="$($ADB -s "$PHONE_SERIAL" shell pm path "$APP_PACKAGE" 2>/dev/null | tr -d '\r')"
  if printf '%s\n' "$PACKAGE_PATH" | grep -q '^package:'; then
    pass "installed package identity verified"
  else
    fail "installed package identity could not be verified after successful adb install"
  fi
else
  echo "TEST19_R2_PACKAGE_IDENTITY_CHECK=NOT_ATTEMPTED"
fi

echo
echo "CXR_L_PRIVATE_ARTIFACT_DIRECTORY=$PRIVATE_ROOT"
echo "BUILD_LOG=$BUILD_LOG"
echo "INSTALL_LOG=$INSTALL_LOG"
echo "APK=$APK"
if [ "$RESOLVE_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_CXR_L_ARTIFACT_AND_API_SURFACE=PASS"
else
  echo "TEST19_R2_CXR_L_ARTIFACT_AND_API_SURFACE=FAIL"
fi
if [ "$BUILD_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_APK_BUILD=PASS"
else
  echo "TEST19_R2_APK_BUILD=NOT_COMPLETED"
fi
if [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_APK_INSTALL=PASS"
else
  echo "TEST19_R2_APK_INSTALL=NOT_ATTEMPTED"
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ] && [ "$DATA_CLEAR_SUCCEEDED" = "YES" ]; then
  PHONE_MUTATION_VALUE="TEST19_R2_DEBUG_APK_INSTALL_AND_TEST_APP_DATA_CLEAR"
elif [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  PHONE_MUTATION_VALUE="TEST19_R2_DEBUG_APK_INSTALL_ONLY"
else
  PHONE_MUTATION_VALUE="NONE"
fi

if [ "$RESULT" -eq 0 ]; then
  echo "TEST19_R2_READY_FOR_CONNECTION_RUN=YES"
  echo "TEST19_R2_PREPARE=PASS"
else
  echo "TEST19_R2_READY_FOR_CONNECTION_RUN=NO"
  echo "TEST19_R2_PREPARE=FAIL"
fi
echo "PHONE_MUTATION=$PHONE_MUTATION_VALUE"
echo "HI_ROKID_DATA_MUTATION=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "GLASSES_OPERATION=NONE"
exit "$RESULT"
