#!/usr/bin/env bash
# Governed build/install preparation for Test 19 r2.3.1. This script never
# enables errexit, nounset, or pipefail. Invoke it as a child Bash process.

RESULT=0
PHONE_SERIAL=""
CXR_L_VERSION="1.0.1"
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
EXPECTED_TEST_APP_VERSION="2.3.1-test19-r2.3.1"
RESET_APP_DATA="NO"
REPO=""
RESOLVE_SUCCEEDED="NO"
BUILD_SUCCEEDED="NO"
BUILD_EVIDENCE_SUCCEEDED="NO"
INSTALL_SUCCEEDED="NO"
PACKAGE_IDENTITY_SUCCEEDED="NO"
DATA_CLEAR_SUCCEEDED="NO"
BUILD_OUTPUT_CLEANUP_SUCCEEDED="NO"

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
PRIVATE_ROOT="${TEST19_PRIVATE_ROOT:-$HOME/rokid-nettest/private/test19-r2-cxr-l-maven-$STAMP}"
BUILD_LOG="${TEST19_BUILD_LOG:-$HOME/Downloads/test19-r2-cxr-l-build-$STAMP.log}"
INSTALL_LOG="${TEST19_INSTALL_LOG:-$HOME/Downloads/test19-r2-cxr-l-install-$STAMP.log}"
BUILD_DIR="$REPO/android-client/test19r2/build"
APK="$BUILD_DIR/outputs/apk/debug/test19r2-debug.apk"
EVIDENCE_DIR="$PRIVATE_ROOT/governed-build"
RESOLVER_SCRIPT="${TEST19_CXR_L_RESOLVER:-$REPO/scripts/research/cxr/resolve_cxr_l_maven.py}"
GRADLEW="${TEST19_GRADLEW:-$REPO/android-client/gradlew}"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; RESULT=1; }

extract_package_version() {
  package_name="$1"
  "$ADB" -s "$PHONE_SERIAL" shell dumpsys package "$package_name" 2>/dev/null |
    sed -n 's/.*versionName=\([^[:space:]]*\).*/\1/p' |
    head -n 1
}

preserve_build_evidence() {
  mkdir -p "$EVIDENCE_DIR" || return 1

  cp "$APK" "$EVIDENCE_DIR/test19r2-debug.apk" || return 1
  if [ -f "$BUILD_LOG" ]; then
    cp "$BUILD_LOG" "$EVIDENCE_DIR/build.log" || return 1
  fi
  if [ -f "$INSTALL_LOG" ]; then
    cp "$INSTALL_LOG" "$EVIDENCE_DIR/install.log" || return 1
  fi
  if [ -f "$BUILD_DIR/outputs/apk/debug/output-metadata.json" ]; then
    cp "$BUILD_DIR/outputs/apk/debug/output-metadata.json" "$EVIDENCE_DIR/output-metadata.json" || return 1
  fi
  if [ -f "$BUILD_DIR/outputs/logs/manifest-merger-debug-report.txt" ]; then
    cp "$BUILD_DIR/outputs/logs/manifest-merger-debug-report.txt" "$EVIDENCE_DIR/manifest-merger-debug-report.txt" || return 1
  fi

  APK_SHA256="$(shasum -a 256 "$APK" | awk '{print $1}')"
  cat >"$EVIDENCE_DIR/preparation-identity.txt" <<IDENTITY
SCHEMA=rokid.test19.r2.3.1.governed-preparation.v1
CAPTURE_UTC=$STAMP
CXR_L_VERSION=$CXR_L_VERSION
EXPECTED_HI_ROKID_VERSION=$EXPECTED_HI_ROKID_VERSION
EXPECTED_TEST_APP_VERSION=$EXPECTED_TEST_APP_VERSION
APK_SHA256=$APK_SHA256
CXR_M_GRADLE_PROPERTY_SUPPLIED=NO
CXR_L_GRADLE_PROPERTY_SUPPLIED=YES
IDENTITY

  return 0
}

finalize_build_evidence() {
  if [ -f "$INSTALL_LOG" ]; then
    cp "$INSTALL_LOG" "$EVIDENCE_DIR/install.log" || return 1
  fi

  rm -f "$EVIDENCE_DIR/SHA256SUMS-private.txt" "$EVIDENCE_DIR/hash-verification.txt"
  (
    cd "$EVIDENCE_DIR" || exit 91
    find . -type f ! -name SHA256SUMS-private.txt ! -name hash-verification.txt -print0 |
      LC_ALL=C sort -z |
      xargs -0 shasum -a 256 >SHA256SUMS-private.txt
  ) || return 1

  (
    cd "$EVIDENCE_DIR" || exit 91
    shasum -a 256 -c SHA256SUMS-private.txt
  ) >"$EVIDENCE_DIR/hash-verification.txt" 2>&1 || return 1

  return 0
}

echo "Test 19 r2.3.1 CXR-L governed preparation"
echo "========================================="
echo "REPO=$REPO"
echo "PHONE_SERIAL=$PHONE_SERIAL"
echo "CXR_L_VERSION=$CXR_L_VERSION"
echo "EXPECTED_HI_ROKID_VERSION=$EXPECTED_HI_ROKID_VERSION"
echo "EXPECTED_TEST_APP_VERSION=$EXPECTED_TEST_APP_VERSION"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME_SELECTED=$JAVA_CANDIDATE"
echo "CXR_M_GRADLE_PROPERTY_SUPPLIED=NO"
echo "CXR_L_GRADLE_PROPERTY_SUPPLIED=YES"
echo

if [ -z "$PHONE_SERIAL" ]; then fail "--phone is required"; fi
if [ "$CXR_L_VERSION" != "1.0.1" ]; then fail "only CXR-L 1.0.1 is accepted"; fi
if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
if [ ! -x "$ADB" ]; then fail "adb is unavailable: $ADB"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/java" ]; then fail "selected Java runtime is unavailable"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/javap" ]; then fail "selected javap is unavailable"; fi
if [ ! -f "$ANDROID_HOME/platforms/android-36/android.jar" ]; then fail "Android SDK 36 is unavailable"; fi
if [ ! -f "$RESOLVER_SCRIPT" ]; then fail "CXR-L resolver is unavailable: $RESOLVER_SCRIPT"; fi
if [ ! -x "$GRADLEW" ]; then fail "Gradle wrapper is unavailable: $GRADLEW"; fi

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

if [ "$RESULT" -ne 0 ]; then
  echo "TEST19_R2_PREPARE=FAIL"
  exit "$RESULT"
fi

mkdir -p "$PRIVATE_ROOT"
python3 "$RESOLVER_SCRIPT" \
  --version "$CXR_L_VERSION" \
  --output "$PRIVATE_ROOT" \
  --javap "$JAVA_CANDIDATE/bin/javap"
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
    "$GRADLEW" --no-daemon --console=plain --stacktrace \
      "-Dorg.gradle.java.home=$JAVA_CANDIDATE" \
      "-ProkidCxrLVersion=$CXR_L_VERSION" \
      :test19r2:clean :test19r2:assembleDebug
  ) >"$BUILD_LOG" 2>&1
  BUILD_RC=$?
  echo "GRADLE_BUILD_EXIT_CODE=$BUILD_RC"
  if [ "$BUILD_RC" -eq 0 ] && [ -s "$APK" ]; then
    BUILD_SUCCEEDED="YES"
    pass "Test 19 r2.3.1 APK built with the CXR-L property only"
    APK_SHA256="$(shasum -a 256 "$APK" | awk '{print $1}')"
    echo "TEST19_R2_APK_SHA256=$APK_SHA256"
  else
    fail "Test 19 r2.3.1 APK build failed"
    echo "First Gradle failure section:"
    awk '
      /^\* What went wrong:/ { printing = 1; remaining = 35 }
      printing { print NR ":" $0; remaining--; if (remaining <= 0) printing = 0 }
    ' "$BUILD_LOG"
    echo "Targeted failure lines:"
    grep -nE 'FAILURE:|What went wrong|Script compilation errors|Caused by:|error:|Could not resolve|Could not find|Compilation failed|Pass -P|build\.gradle\.kts:[0-9]+' "$BUILD_LOG" | head -n 160
    echo "Last 120 build-log lines:"
    tail -n 120 "$BUILD_LOG"
  fi
fi

if [ "$BUILD_SUCCEEDED" = "YES" ]; then
  preserve_build_evidence
  EVIDENCE_STAGE_RC=$?
  echo "GOVERNED_BUILD_EVIDENCE_STAGE_EXIT_CODE=$EVIDENCE_STAGE_RC"
  if [ "$EVIDENCE_STAGE_RC" -eq 0 ]; then
    pass "governed APK build evidence staged privately"
  else
    fail "governed APK build evidence staging failed"
  fi
fi

if [ "$RESULT" -eq 0 ]; then
  "$ADB" -s "$PHONE_SERIAL" install -r "$APK" >"$INSTALL_LOG" 2>&1
  INSTALL_RC=$?
  cat "$INSTALL_LOG"
  echo "ADB_INSTALL_EXIT_CODE=$INSTALL_RC"
  if [ "$INSTALL_RC" -eq 0 ]; then
    INSTALL_SUCCEEDED="YES"
    pass "Test 19 r2.3.1 APK installed"
  else
    fail "APK installation failed"
  fi
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  PACKAGE_PATH="$($ADB -s "$PHONE_SERIAL" shell pm path "$APP_PACKAGE" 2>/dev/null | tr -d '\r')"
  INSTALLED_TEST_APP_VERSION="$(extract_package_version "$APP_PACKAGE")"
  echo "INSTALLED_TEST_APP_VERSION=$INSTALLED_TEST_APP_VERSION"
  if printf '%s\n' "$PACKAGE_PATH" | grep -q '^package:' && [ "$INSTALLED_TEST_APP_VERSION" = "$EXPECTED_TEST_APP_VERSION" ]; then
    PACKAGE_IDENTITY_SUCCEEDED="YES"
    pass "installed Test 19 r2.3.1 package identity verified"
  else
    fail "installed package identity or version could not be verified"
  fi
else
  echo "TEST19_R2_PACKAGE_IDENTITY_CHECK=NOT_ATTEMPTED"
fi

if [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ] && [ "$RESET_APP_DATA" = "YES" ]; then
  "$ADB" -s "$PHONE_SERIAL" shell pm clear "$APP_PACKAGE" >/dev/null 2>&1
  CLEAR_RC=$?
  echo "TEST_APP_DATA_CLEAR_EXIT_CODE=$CLEAR_RC"
  if [ "$CLEAR_RC" -eq 0 ]; then
    DATA_CLEAR_SUCCEEDED="YES"
    pass "only Test 19 r2 app data was cleared"
  else
    fail "Test 19 r2 data clear failed"
  fi
elif [ "$RESET_APP_DATA" = "NO" ]; then
  DATA_CLEAR_SUCCEEDED="NOT_REQUESTED"
fi

if [ -d "$BUILD_DIR" ]; then
  rm -rf "$BUILD_DIR"
  CLEAN_RC=$?
else
  CLEAN_RC=0
fi
echo "BUILD_OUTPUT_CLEANUP_EXIT_CODE=$CLEAN_RC"
if [ "$CLEAN_RC" -eq 0 ] && [ ! -e "$BUILD_DIR" ]; then
  BUILD_OUTPUT_CLEANUP_SUCCEEDED="YES"
  pass "generated Test 19 r2 build directory removed after private preservation"
else
  fail "generated Test 19 r2 build directory cleanup failed"
fi

if [ "$BUILD_SUCCEEDED" = "YES" ] && [ -d "$EVIDENCE_DIR" ]; then
  finalize_build_evidence
  EVIDENCE_RC=$?
  echo "GOVERNED_BUILD_EVIDENCE_EXIT_CODE=$EVIDENCE_RC"
  if [ "$EVIDENCE_RC" -eq 0 ]; then
    BUILD_EVIDENCE_SUCCEEDED="YES"
    pass "governed APK build evidence finalized and verified"
  else
    fail "governed APK build evidence finalization failed"
  fi
fi

echo
echo "CXR_L_PRIVATE_ARTIFACT_DIRECTORY=$PRIVATE_ROOT"
echo "GOVERNED_BUILD_EVIDENCE_DIRECTORY=$EVIDENCE_DIR"
echo "BUILD_LOG=$BUILD_LOG"
echo "INSTALL_LOG=$INSTALL_LOG"
echo "APK_PRIVATE_COPY=$EVIDENCE_DIR/test19r2-debug.apk"

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
if [ "$BUILD_EVIDENCE_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_GOVERNED_BUILD_EVIDENCE=PASS"
else
  echo "TEST19_R2_GOVERNED_BUILD_EVIDENCE=NOT_COMPLETED"
fi
if [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_APK_INSTALL=PASS"
else
  echo "TEST19_R2_APK_INSTALL=NOT_ATTEMPTED"
fi
if [ "$PACKAGE_IDENTITY_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_PACKAGE_IDENTITY=PASS"
else
  echo "TEST19_R2_PACKAGE_IDENTITY=NOT_COMPLETED"
fi
if [ "$BUILD_OUTPUT_CLEANUP_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_BUILD_OUTPUT_CLEANUP=PASS"
else
  echo "TEST19_R2_BUILD_OUTPUT_CLEANUP=FAIL"
fi

if [ "$INSTALL_SUCCEEDED" = "YES" ] && [ "$DATA_CLEAR_SUCCEEDED" = "YES" ]; then
  PHONE_MUTATION_VALUE="TEST19_R2_3_1_DEBUG_APK_INSTALL_AND_TEST_APP_DATA_CLEAR"
elif [ "$INSTALL_SUCCEEDED" = "YES" ]; then
  PHONE_MUTATION_VALUE="TEST19_R2_3_1_DEBUG_APK_INSTALL_ONLY"
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
