#!/usr/bin/env bash

# Governed Test 20 r2 build-only stage. This script runs in a child bash
# process and intentionally does not change the caller's shell options.

REPO=""
SDK_VERSION=""
OUTPUT=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/tests/build_test20_r2.sh \
    --repo <repository> \
    --sdk-version 1.0.1 \
    --output <private-evidence-directory>
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
    --sdk-version)
      SDK_VERSION="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
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

echo "Test 20 r2 governed build-only stage"
echo "===================================="

if [ -z "$REPO" ] || [ -z "$SDK_VERSION" ] || [ -z "$OUTPUT" ]; then
  usage >&2
  exit 2
fi

REPO="$(cd "$REPO" 2>/dev/null && pwd)"
REPO_RC=$?
if [ "$REPO_RC" -ne 0 ] || [ -z "$REPO" ]; then
  fail "repository does not exist"
  exit 1
fi

case "$OUTPUT/" in
  "$REPO"/*)
    fail "output must be outside the repository"
    exit 1
    ;;
esac

if [ "$SDK_VERSION" != "1.0.1" ]; then
  fail "Test 20 r2 requires exact client-l version 1.0.1"
  exit 1
fi

if [ ! -x "$REPO/android-client/gradlew" ]; then
  fail "Android Gradle wrapper is missing"
  exit 1
fi

ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
if [ ! -d "$ANDROID_HOME" ]; then
  fail "Android SDK not found: $ANDROID_HOME"
  exit 1
fi

if [ -z "${JAVA_HOME:-}" ] && [ -x /usr/libexec/java_home ]; then
  JAVA_HOME="$(/usr/libexec/java_home -v 23 2>/dev/null)"
  if [ -z "$JAVA_HOME" ]; then
    JAVA_HOME="$(/usr/libexec/java_home -v 17 2>/dev/null)"
  fi
  export JAVA_HOME
fi

if ! command -v java >/dev/null 2>&1; then
  fail "java is not available"
  exit 1
fi

mkdir -p "$OUTPUT/apk"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  fail "cannot create output directory"
  exit 1
fi

BUILD_LOG="$OUTPUT/gradle-build.log"
(
  cd "$REPO/android-client" || exit 90
  ./gradlew --no-daemon \
    :test20r2:assembleDebug \
    -ProkidCxrLVersion="$SDK_VERSION"
) >"$BUILD_LOG" 2>&1
BUILD_RC=$?

echo "GRADLE_BUILD_EXIT_CODE=$BUILD_RC"
if [ "$BUILD_RC" -ne 0 ]; then
  tail -n 160 "$BUILD_LOG"
  fail "Test 20 r2 APK build failed"
  exit 1
fi

SOURCE_APK="$REPO/android-client/test20r2/build/outputs/apk/debug/test20r2-debug.apk"
PRESERVED_APK="$OUTPUT/apk/test20-r2-debug.apk"
if [ ! -s "$SOURCE_APK" ]; then
  fail "expected APK is missing: $SOURCE_APK"
  exit 1
fi

cp "$SOURCE_APK" "$PRESERVED_APK"
COPY_RC=$?
if [ "$COPY_RC" -ne 0 ]; then
  fail "cannot preserve APK"
  exit 1
fi

EXPECTED_AAR_SHA="c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
EXPECTED_POM_SHA="d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a"
CACHE_ROOT="$HOME/.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/$SDK_VERSION"
AAR_PATH=""
POM_PATH=""

if [ -d "$CACHE_ROOT" ]; then
  while IFS= read -r candidate; do
    candidate_sha="$(shasum -a 256 "$candidate" | awk '{print $1}')"
    if [ "$candidate_sha" = "$EXPECTED_AAR_SHA" ]; then
      AAR_PATH="$candidate"
      break
    fi
  done < <(find "$CACHE_ROOT" -type f -name '*.aar' -print 2>/dev/null)

  while IFS= read -r candidate; do
    candidate_sha="$(shasum -a 256 "$candidate" | awk '{print $1}')"
    if [ "$candidate_sha" = "$EXPECTED_POM_SHA" ]; then
      POM_PATH="$candidate"
      break
    fi
  done < <(find "$CACHE_ROOT" -type f -name '*.pom' -print 2>/dev/null)
fi

if [ -z "$AAR_PATH" ] || [ -z "$POM_PATH" ]; then
  fail "exact AAR/POM identities were not found in the Gradle cache"
  exit 1
fi

AAPT=""
if [ -d "$ANDROID_HOME/build-tools" ]; then
  AAPT="$(find "$ANDROID_HOME/build-tools" -type f -name aapt -print 2>/dev/null | sort | tail -n 1)"
fi
if [ -z "$AAPT" ] || [ ! -x "$AAPT" ]; then
  fail "aapt not found under Android SDK build-tools"
  exit 1
fi

BADGING="$OUTPUT/apk-badging.txt"
"$AAPT" dump badging "$PRESERVED_APK" >"$BADGING" 2>&1
AAPT_RC=$?
if [ "$AAPT_RC" -ne 0 ]; then
  fail "aapt could not inspect APK"
  exit 1
fi

if ! grep -Fq "package: name='org.aimindseye.rokid.cxreventqualification'" "$BADGING"; then
  fail "unexpected APK package identity"
  exit 1
fi
if ! grep -Fq "versionCode='1'" "$BADGING"; then
  fail "unexpected APK versionCode"
  exit 1
fi
if ! grep -Fq "versionName='1.0-test20-r2'" "$BADGING"; then
  fail "unexpected APK versionName"
  exit 1
fi

PERMISSIONS="$OUTPUT/apk-permissions.txt"
"$AAPT" dump permissions "$PRESERVED_APK" >"$PERMISSIONS" 2>&1
PERMISSIONS_RC=$?
if [ "$PERMISSIONS_RC" -ne 0 ]; then
  fail "aapt could not inspect merged APK permissions"
  exit 1
fi
for forbidden_permission in \
  android.permission.INTERNET \
  android.permission.CAMERA \
  android.permission.RECORD_AUDIO
do
  if grep -Fq "$forbidden_permission" "$PERMISSIONS"; then
    fail "forbidden merged APK permission present: $forbidden_permission"
    exit 1
  fi
done
if ! grep -Fq "android.permission.BLUETOOTH_CONNECT" "$PERMISSIONS"; then
  fail "required BLUETOOTH_CONNECT permission is missing"
  exit 1
fi

APK_SHA="$(shasum -a 256 "$PRESERVED_APK" | awk '{print $1}')"
APK_SIZE="$(wc -c < "$PRESERVED_APK" | tr -d ' ')"
HEAD_SHA="$(git -C "$REPO" rev-parse HEAD 2>/dev/null)"
BRANCH="$(git -C "$REPO" branch --show-current 2>/dev/null)"

cat >"$OUTPUT/build-attestation.txt" <<EOF
TEST20_R2_SCHEMA=rokid.test20-r2.build-attestation.v1
REPOSITORY_HEAD=$HEAD_SHA
REPOSITORY_BRANCH=$BRANCH
CXR_L_COORDINATE=com.rokid.cxr:client-l:1.0.1
CXR_L_AAR_SHA256=$EXPECTED_AAR_SHA
CXR_L_POM_SHA256=$EXPECTED_POM_SHA
PACKAGE=org.aimindseye.rokid.cxreventqualification
VERSION_CODE=1
VERSION_NAME=1.0-test20-r2
APK_SHA256=$APK_SHA
APK_SIZE_BYTES=$APK_SIZE
TEST_APP_INTERNET_PERMISSION=ABSENT_FROM_MERGED_APK
TEST_APP_CAMERA_PERMISSION=ABSENT_FROM_MERGED_APK
TEST_APP_RECORD_AUDIO_PERMISSION=ABSENT_FROM_MERGED_APK
PHONE_OPERATION=NONE
GLASSES_OPERATION=NONE
EOF

(
  cd "$OUTPUT" || exit 90
  find . -type f ! -name SHA256SUMS-private.txt -print \
    | LC_ALL=C sort \
    | while IFS= read -r relpath; do
        shasum -a 256 "$relpath"
      done > SHA256SUMS-private.txt
  shasum -a 256 -c SHA256SUMS-private.txt > hash-verification.txt 2>&1
)
HASH_RC=$?
if [ "$HASH_RC" -ne 0 ]; then
  fail "build evidence hash verification failed"
  exit 1
fi

echo "TEST20_R2_EXACT_ARTIFACT_IDENTITY=PASS"
echo "TEST20_R2_APK_BUILD=PASS"
echo "TEST20_R2_APK_IDENTITY=PASS"
echo "TEST20_R2_MERGED_APK_PERMISSION_GATE=PASS"
echo "TEST20_R2_BUILD_EVIDENCE=PASS"
echo "TEST20_R2_APK_SHA256=$APK_SHA"
echo "TEST20_R2_BUILD_OUTPUT=$OUTPUT"
echo "PHONE_OPERATION=NONE"
echo "GLASSES_OPERATION=NONE"
echo "TEST20_R2_READY_FOR_INSTALL_STAGE=YES"
exit 0
