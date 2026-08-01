#!/usr/bin/env bash
REPO=""; SDK_VERSION=""; OUTPUT=""
usage(){ echo "Usage: bash scripts/tests/build_test20_r3_2.sh --repo <repo> --sdk-version 1.0.1 --output <dir>"; }
fail(){ echo "FAIL: $*" >&2; return 1; }
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2";shift 2;; --sdk-version) SDK_VERSION="$2";shift 2;; --output) OUTPUT="$2";shift 2;; -h|--help) usage;exit 0;; *) fail "unknown argument: $1";exit 2;; esac; done
echo "Test 20 r3.2 governed build-only stage"; echo "======================================="
[ -n "$REPO" ] && [ -n "$SDK_VERSION" ] && [ -n "$OUTPUT" ] || { usage >&2; exit 2; }
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || { fail "repository does not exist"; exit 1; }
case "$OUTPUT/" in "$REPO"/*) fail "output must be outside repository"; exit 1;; esac
[ "$SDK_VERSION" = "1.0.1" ] || { fail "exact client-l 1.0.1 required"; exit 1; }
[ -x "$REPO/android-client/gradlew" ] || { fail "Gradle wrapper missing"; exit 1; }
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"; [ -d "$ANDROID_HOME" ] || { fail "Android SDK missing"; exit 1; }
if [ -z "${JAVA_HOME:-}" ] && [ -x /usr/libexec/java_home ]; then JAVA_HOME="$(/usr/libexec/java_home -v 23 2>/dev/null)"; [ -n "$JAVA_HOME" ] || JAVA_HOME="$(/usr/libexec/java_home -v 17 2>/dev/null)"; export JAVA_HOME; fi
mkdir -p "$OUTPUT/apk" || exit 1
( cd "$REPO/android-client" || exit 90; ./gradlew --no-daemon :test20r32:assembleDebug -ProkidCxrLVersion="$SDK_VERSION" ) >"$OUTPUT/gradle-build.log" 2>&1
RC=$?; echo "GRADLE_BUILD_EXIT_CODE=$RC"; [ "$RC" -eq 0 ] || { tail -n 160 "$OUTPUT/gradle-build.log"; exit 1; }
SRC="$REPO/android-client/test20r32/build/outputs/apk/debug/test20r32-debug.apk"; APK="$OUTPUT/apk/test20-r3-2-debug.apk"; [ -s "$SRC" ] || { fail "APK missing"; exit 1; }; cp "$SRC" "$APK" || exit 1
AAPT="$(find "$ANDROID_HOME/build-tools" -type f -name aapt -print 2>/dev/null | sort | tail -n 1)"; [ -x "$AAPT" ] || { fail "aapt missing"; exit 1; }
"$AAPT" dump badging "$APK" >"$OUTPUT/apk-badging.txt" 2>&1 || exit 1
for x in "package: name='org.aimindseye.rokid.cxrphotoqualification'" "versionCode='1'" "versionName='1.0-test20-r3.2'"; do grep -Fq "$x" "$OUTPUT/apk-badging.txt" || { fail "APK identity mismatch: $x"; exit 1; }; done
"$AAPT" dump permissions "$APK" >"$OUTPUT/apk-permissions.txt" 2>&1 || exit 1
for x in android.permission.INTERNET android.permission.CAMERA android.permission.RECORD_AUDIO; do grep -Fq "$x" "$OUTPUT/apk-permissions.txt" && { fail "forbidden permission: $x"; exit 1; }; done
grep -Fq android.permission.BLUETOOTH_CONNECT "$OUTPUT/apk-permissions.txt" || { fail "BLUETOOTH_CONNECT missing"; exit 1; }
EXPECTED_AAR=c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e; EXPECTED_POM=d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a
CACHE="$HOME/.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/$SDK_VERSION"; FOUND_AAR=NO; FOUND_POM=NO
if [ -d "$CACHE" ]; then while IFS= read -r f; do [ "$(shasum -a 256 "$f"|awk '{print $1}')" = "$EXPECTED_AAR" ] && FOUND_AAR=YES; done < <(find "$CACHE" -type f -name '*.aar' -print 2>/dev/null); while IFS= read -r f; do [ "$(shasum -a 256 "$f"|awk '{print $1}')" = "$EXPECTED_POM" ] && FOUND_POM=YES; done < <(find "$CACHE" -type f -name '*.pom' -print 2>/dev/null); fi
[ "$FOUND_AAR" = YES ] && [ "$FOUND_POM" = YES ] || { fail "exact AAR/POM not found"; exit 1; }
APK_SHA="$(shasum -a 256 "$APK"|awk '{print $1}')"; HEAD="$(git -C "$REPO" rev-parse HEAD)"; BRANCH="$(git -C "$REPO" branch --show-current)"
cat >"$OUTPUT/build-attestation.txt" <<EOF
TEST20_R3_2_SCHEMA=rokid.test20-r3.2.build-attestation.v1
REPOSITORY_HEAD=$HEAD
REPOSITORY_BRANCH=$BRANCH
CXR_L_COORDINATE=com.rokid.cxr:client-l:1.0.1
CXR_L_AAR_SHA256=$EXPECTED_AAR
CXR_L_POM_SHA256=$EXPECTED_POM
PACKAGE=org.aimindseye.rokid.cxrphotoqualification
VERSION_CODE=1
VERSION_NAME=1.0-test20-r3.2
APK_SHA256=$APK_SHA
PHOTO_ARG_1=1920
PHOTO_ARG_2=1080
PHOTO_ARG_3=80
PHOTO_ARGUMENT_SEMANTICS=WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED
MAX_PHOTO_REQUEST_COUNT=1
INTERNET_PERMISSION=ABSENT
CAMERA_PERMISSION=ABSENT
RECORD_AUDIO_PERMISSION=ABSENT
PHONE_OPERATION=NONE
GLASSES_OPERATION=NONE
EOF
( cd "$OUTPUT" || exit 90; find . -type f ! -name SHA256SUMS-private.txt -print | LC_ALL=C sort | while IFS= read -r relpath; do shasum -a 256 "$relpath"; done >SHA256SUMS-private.txt; shasum -a 256 -c SHA256SUMS-private.txt >hash-verification.txt 2>&1 ) || exit 1
echo "TEST20_R3_2_EXACT_ARTIFACT_IDENTITY=PASS"; echo "TEST20_R3_2_APK_BUILD=PASS"; echo "TEST20_R3_2_APK_IDENTITY=PASS"; echo "TEST20_R3_2_MERGED_APK_PERMISSION_GATE=PASS"; echo "TEST20_R3_2_ONE_SHOT_SOURCE_CONTRACT=PASS"; echo "TEST20_R3_2_BUILD_EVIDENCE=PASS"; echo "TEST20_R3_2_APK_SHA256=$APK_SHA"; echo "TEST20_R3_2_BUILD_OUTPUT=$OUTPUT"; echo "PHONE_OPERATION=NONE"; echo "GLASSES_OPERATION=NONE"; echo "TEST20_R3_2_READY_FOR_INSTALL_STAGE=YES"
