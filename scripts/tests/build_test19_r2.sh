#!/usr/bin/env bash
# Test 19 r2.4 Stage 1: resolve, attest, build, preserve, and clean.
# This script performs no ADB, phone, Hi Rokid, Bluetooth, or glasses operation.
# It never enables errexit, nounset, or pipefail.

RESULT=0
REPO=""
CXR_L_VERSION="1.0.1"
OUTPUT=""
EXPECTED_APP_PACKAGE="org.aimindseye.rokid.cxrlqualification"
EXPECTED_APP_VERSION_CODE="7"
EXPECTED_APP_VERSION_NAME="2.4-test19-r2.4"
BUILD_SUCCEEDED="NO"
EVIDENCE_SUCCEEDED="NO"
CLEANUP_SUCCEEDED="NO"

usage() {
  cat <<'TXT'
Usage: bash scripts/tests/build_test19_r2.sh [options]

Options:
  --repo PATH          Repository root
  --sdk-version 1.0.1  Exact attested CXR-L version
  --output PATH        New private evidence directory
  --help               Show this help

This stage performs no ADB or device operation. It prints the evidence directory
that must be supplied to install_test19_r2.sh after the build passes.
TXT
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --sdk-version) CXR_L_VERSION="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage; exit 64 ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
fi

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
JAVA_CANDIDATE="${TEST19_JAVA_HOME:-$HOME/Library/Java/JavaVirtualMachines/temurin-23.0.2/Contents/Home}"
if [ ! -x "$JAVA_CANDIDATE/bin/java" ] && [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  JAVA_CANDIDATE="$JAVA_HOME"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUTPUT" ]; then
  OUTPUT="${TEST19_BUILD_EVIDENCE_ROOT:-$HOME/rokid-nettest/private/test19-r2-cxr-l-build-$STAMP}"
fi

MAVEN_DIR="$OUTPUT/maven"
EVIDENCE_DIR="$OUTPUT/governed-build"
BUILD_LOG="$EVIDENCE_DIR/build.log"
BUILD_DIR="$REPO/android-client/test19r2/build"
APK="$BUILD_DIR/outputs/apk/debug/test19r2-debug.apk"
APK_PRIVATE_COPY="$EVIDENCE_DIR/test19r2-debug.apk"
RESUME_JSON="$EVIDENCE_DIR/build-resume.json"
RESOLVER_SCRIPT="${TEST19_CXR_L_RESOLVER:-$REPO/scripts/research/cxr/resolve_cxr_l_maven.py}"
GRADLEW="${TEST19_GRADLEW:-$REPO/android-client/gradlew}"
LOCAL_PROPERTIES="$REPO/android-client/local.properties"

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

print_gradle_failure() {
  log="$1"
  echo "First Gradle failure section:"
  awk '
    /^\* What went wrong:/ { printing = 1; remaining = 45 }
    printing { print NR ":" $0; remaining--; if (remaining <= 0) printing = 0 }
  ' "$log"
  echo "Targeted failure lines:"
  grep -nE 'FAILURE:|What went wrong|Script compilation errors|Caused by:|error:|Could not resolve|Could not find|Compilation failed|Pass -P|build\.gradle\.kts:[0-9]+' "$log" | head -n 180
  echo "Last 120 build-log lines:"
  tail -n 120 "$log"
}

finalize_build_hashes() {
  rm -f "$EVIDENCE_DIR/SHA256SUMS-build.txt" "$EVIDENCE_DIR/build-hash-verification.txt"
  (
    cd "$EVIDENCE_DIR" || exit 91
    find . -type f \
      ! -name SHA256SUMS-build.txt \
      ! -name build-hash-verification.txt \
      -print0 |
      LC_ALL=C sort -z |
      xargs -0 shasum -a 256 >SHA256SUMS-build.txt
  ) || return 1
  (
    cd "$EVIDENCE_DIR" || exit 91
    shasum -a 256 -c SHA256SUMS-build.txt
  ) >"$EVIDENCE_DIR/build-hash-verification.txt" 2>&1 || return 1
  return 0
}

cleanup_build_output() {
  if [ -d "$BUILD_DIR" ]; then
    rm -rf "$BUILD_DIR"
    rc=$?
  else
    rc=0
  fi
  echo "BUILD_OUTPUT_CLEANUP_EXIT_CODE=$rc"
  if [ "$rc" -eq 0 ] && [ ! -e "$BUILD_DIR" ]; then
    CLEANUP_SUCCEEDED="YES"
    pass "generated Test 19 r2 build directory removed after private preservation"
  else
    fail "generated Test 19 r2 build directory cleanup failed"
  fi
}

echo "Test 19 r2.4 Stage 1 — governed CXR-L build"
echo "================================================"
echo "REPO=$REPO"
echo "CXR_L_VERSION=$CXR_L_VERSION"
echo "EXPECTED_APP_PACKAGE=$EXPECTED_APP_PACKAGE"
echo "EXPECTED_APP_VERSION_CODE=$EXPECTED_APP_VERSION_CODE"
echo "EXPECTED_APP_VERSION_NAME=$EXPECTED_APP_VERSION_NAME"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME_SELECTED=$JAVA_CANDIDATE"
echo "BUILD_EVIDENCE_ROOT=$OUTPUT"
echo "CXR_M_GRADLE_PROPERTY_SUPPLIED=NO"
echo "CXR_L_GRADLE_PROPERTY_SUPPLIED=YES"
echo "ADB_OPERATION=NONE"
echo

if [ "$CXR_L_VERSION" != "1.0.1" ]; then fail "only CXR-L 1.0.1 is accepted"; fi
if [ ! -d "$REPO/.git" ]; then fail "repository is not a Git worktree"; fi
if [ -n "$(git -C "$REPO" status --porcelain=v1 --untracked-files=no 2>/dev/null)" ]; then
  fail "tracked repository changes are present"
  git -C "$REPO" status --short --untracked-files=no >&2
fi
if [ -e "$OUTPUT" ]; then fail "output already exists: $OUTPUT"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/java" ]; then fail "selected Java runtime is unavailable"; fi
if [ ! -x "$JAVA_CANDIDATE/bin/javap" ]; then fail "selected javap is unavailable"; fi
if [ ! -f "$ANDROID_HOME/platforms/android-36/android.jar" ]; then fail "Android SDK 36 is unavailable"; fi
if [ ! -f "$RESOLVER_SCRIPT" ]; then fail "CXR-L resolver is unavailable: $RESOLVER_SCRIPT"; fi
if [ ! -x "$GRADLEW" ]; then fail "Gradle wrapper is unavailable: $GRADLEW"; fi

AAPT="${TEST19_AAPT:-$(find_aapt)}"
if [ ! -x "$AAPT" ]; then fail "aapt is unavailable under Android build-tools"; fi

if [ "$RESULT" -ne 0 ]; then
  echo "TEST19_R2_BUILD_STAGE=FAIL"
  echo "PHONE_OPERATION=NONE"
  echo "HI_ROKID_OPERATION=NONE"
  echo "BLUETOOTH_PAIRING_MUTATION=NONE"
  echo "GLASSES_OPERATION=NONE"
  exit "$RESULT"
fi

mkdir -p "$MAVEN_DIR" "$EVIDENCE_DIR"
CREATE_RC=$?
echo "BUILD_EVIDENCE_DIRECTORY_CREATE_EXIT_CODE=$CREATE_RC"
if [ "$CREATE_RC" -ne 0 ]; then
  fail "private build evidence directory creation failed"
fi

if [ "$RESULT" -eq 0 ]; then
  python3 "$RESOLVER_SCRIPT" \
    --version "$CXR_L_VERSION" \
    --output "$MAVEN_DIR" \
    --javap "$JAVA_CANDIDATE/bin/javap"
  RESOLVE_RC=$?
  echo "CXR_L_RESOLVER_EXIT_CODE=$RESOLVE_RC"
  if [ "$RESOLVE_RC" -eq 0 ]; then
    pass "CXR-L artifact resolved and attested"
  else
    fail "CXR-L artifact resolution failed"
  fi
fi

printf 'sdk.dir=%s\n' "$ANDROID_HOME" >"$LOCAL_PROPERTIES"
LOCAL_PROPERTIES_RC=$?
echo "LOCAL_PROPERTIES_WRITE_EXIT_CODE=$LOCAL_PROPERTIES_RC"
if [ "$LOCAL_PROPERTIES_RC" -ne 0 ]; then fail "local.properties write failed"; fi
if [ -d "$REPO/.git/info" ]; then
  grep -qxF '/android-client/local.properties' "$REPO/.git/info/exclude" 2>/dev/null ||
    printf '%s\n' '/android-client/local.properties' >>"$REPO/.git/info/exclude"
fi

rm -rf "$BUILD_DIR"

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
    pass "Test 19 r2.4 APK built with the CXR-L property only"
  else
    fail "Test 19 r2.4 APK build failed"
    print_gradle_failure "$BUILD_LOG"
  fi
fi

if [ "$BUILD_SUCCEEDED" = "YES" ]; then
  cp "$APK" "$APK_PRIVATE_COPY"
  COPY_RC=$?
  echo "APK_PRIVATE_COPY_EXIT_CODE=$COPY_RC"
  if [ "$COPY_RC" -ne 0 ]; then fail "APK private preservation failed"; fi

  if [ -f "$BUILD_DIR/outputs/apk/debug/output-metadata.json" ]; then
    cp "$BUILD_DIR/outputs/apk/debug/output-metadata.json" "$EVIDENCE_DIR/output-metadata.json" || fail "output metadata preservation failed"
  fi
  if [ -f "$BUILD_DIR/outputs/logs/manifest-merger-debug-report.txt" ]; then
    cp "$BUILD_DIR/outputs/logs/manifest-merger-debug-report.txt" "$EVIDENCE_DIR/manifest-merger-debug-report.txt" || fail "manifest report preservation failed"
  fi

  APK_SHA256="$(shasum -a 256 "$APK_PRIVATE_COPY" | awk '{print $1}')"
  BADGING="$($AAPT dump badging "$APK_PRIVATE_COPY" 2>&1)"
  AAPT_RC=$?
  printf '%s\n' "$BADGING" >"$EVIDENCE_DIR/aapt-badging.txt"
  echo "AAPT_BADGING_EXIT_CODE=$AAPT_RC"

  AAPT_PACKAGE="$(printf '%s\n' "$BADGING" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -n 1)"
  AAPT_VERSION_CODE="$(printf '%s\n' "$BADGING" | sed -n "s/^package:.*versionCode='\([^']*\)'.*/\1/p" | head -n 1)"
  AAPT_VERSION_NAME="$(printf '%s\n' "$BADGING" | sed -n "s/^package:.*versionName='\([^']*\)'.*/\1/p" | head -n 1)"

  echo "APK_PACKAGE=$AAPT_PACKAGE"
  echo "APK_VERSION_CODE=$AAPT_VERSION_CODE"
  echo "APK_VERSION_NAME=$AAPT_VERSION_NAME"
  echo "TEST19_R2_APK_SHA256=$APK_SHA256"

  if [ "$AAPT_RC" -ne 0 ] ||
     [ "$AAPT_PACKAGE" != "$EXPECTED_APP_PACKAGE" ] ||
     [ "$AAPT_VERSION_CODE" != "$EXPECTED_APP_VERSION_CODE" ] ||
     [ "$AAPT_VERSION_NAME" != "$EXPECTED_APP_VERSION_NAME" ]; then
    fail "built APK identity does not match the governed r2.4 identity"
  else
    pass "built APK identity verified before installation"
  fi

  SOURCE_BRANCH="$(git -C "$REPO" branch --show-current)"
  SOURCE_HEAD="$(git -C "$REPO" rev-parse HEAD)"
  cat >"$EVIDENCE_DIR/build-identity.txt" <<IDENTITY
SCHEMA=rokid.test19.r2.4.governed-build.v1
CAPTURE_UTC=$STAMP
SOURCE_BRANCH=$SOURCE_BRANCH
SOURCE_HEAD=$SOURCE_HEAD
CXR_L_VERSION=$CXR_L_VERSION
APP_PACKAGE=$EXPECTED_APP_PACKAGE
APP_VERSION_CODE=$EXPECTED_APP_VERSION_CODE
APP_VERSION_NAME=$EXPECTED_APP_VERSION_NAME
APK_SHA256=$APK_SHA256
CXR_M_GRADLE_PROPERTY_SUPPLIED=NO
CXR_L_GRADLE_PROPERTY_SUPPLIED=YES
ADB_OPERATION=NONE
PHONE_OPERATION=NONE
GLASSES_OPERATION=NONE
IDENTITY

  python3 - "$RESUME_JSON" "$SOURCE_BRANCH" "$SOURCE_HEAD" "$CXR_L_VERSION" \
    "$EXPECTED_APP_PACKAGE" "$EXPECTED_APP_VERSION_CODE" "$EXPECTED_APP_VERSION_NAME" \
    "$APK_SHA256" <<'PY'
import json, sys
from pathlib import Path
out=Path(sys.argv[1])
value={
    "schema":"rokid.test19.r2.4.build-resume.v1",
    "source_branch":sys.argv[2],
    "source_head":sys.argv[3],
    "cxr_l_version":sys.argv[4],
    "app_package":sys.argv[5],
    "app_version_code":int(sys.argv[6]),
    "app_version_name":sys.argv[7],
    "apk_relative_path":"test19r2-debug.apk",
    "apk_sha256":sys.argv[8],
    "build_stage_pass":True,
    "apk_install_attempted":False,
}
out.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n", encoding="utf-8")
PY
  RESUME_RC=$?
  echo "BUILD_RESUME_RECORD_EXIT_CODE=$RESUME_RC"
  if [ "$RESUME_RC" -ne 0 ]; then fail "build resume record creation failed"; fi
fi

cleanup_build_output

if [ "$BUILD_SUCCEEDED" = "YES" ] && [ "$RESULT" -eq 0 ]; then
  finalize_build_hashes
  HASH_RC=$?
  echo "BUILD_EVIDENCE_HASH_EXIT_CODE=$HASH_RC"
  if [ "$HASH_RC" -eq 0 ]; then
    EVIDENCE_SUCCEEDED="YES"
    pass "governed build evidence finalized and verified"
  else
    fail "governed build evidence hash verification failed"
  fi
fi

echo
echo "TEST19_R2_BUILD_EVIDENCE=$OUTPUT"
echo "GOVERNED_BUILD_EVIDENCE_DIRECTORY=$EVIDENCE_DIR"
echo "BUILD_RESUME_JSON=$RESUME_JSON"
echo "APK_PRIVATE_COPY=$APK_PRIVATE_COPY"

if [ "$BUILD_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_APK_BUILD=PASS"; else echo "TEST19_R2_APK_BUILD=NOT_COMPLETED"; fi
if [ "$EVIDENCE_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_GOVERNED_BUILD_EVIDENCE=PASS"; else echo "TEST19_R2_GOVERNED_BUILD_EVIDENCE=NOT_COMPLETED"; fi
if [ "$CLEANUP_SUCCEEDED" = "YES" ]; then echo "TEST19_R2_BUILD_OUTPUT_CLEANUP=PASS"; else echo "TEST19_R2_BUILD_OUTPUT_CLEANUP=FAIL"; fi

if [ "$RESULT" -eq 0 ] && [ "$BUILD_SUCCEEDED" = "YES" ] && [ "$EVIDENCE_SUCCEEDED" = "YES" ] && [ "$CLEANUP_SUCCEEDED" = "YES" ]; then
  echo "TEST19_R2_READY_FOR_INSTALL_STAGE=YES"
  echo "TEST19_R2_BUILD_STAGE=PASS"
else
  echo "TEST19_R2_READY_FOR_INSTALL_STAGE=NO"
  echo "TEST19_R2_BUILD_STAGE=FAIL"
fi

echo "SOURCE_TRACKED_MUTATION=NONE"
echo "APK_INSTALL_ATTEMPTED=NO"
echo "PHONE_OPERATION=NONE"
echo "HI_ROKID_OPERATION=NONE"
echo "BLUETOOTH_PAIRING_MUTATION=NONE"
echo "GLASSES_OPERATION=NONE"
exit "$RESULT"
