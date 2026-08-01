#!/bin/bash
# Build, inspect and install Test 20 r3.3 callback-closure APK.
# macOS Bash 3.2 compatible. Intentionally does not enable set -e/-u/pipefail.

REPO=""
PHONE=""
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
EXPECTED_VERSION="1.0-test20-r3.3"
PKG="org.aimindseye.rokid.cxrphotoqualification"

usage() {
  cat <<'EOU'
Usage:
  bash scripts/tests/prepare_test20_r3_3_apk.sh \
    --repo PATH \
    --phone ADB_SERIAL
EOU
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

[ -n "$REPO" ] || die "--repo is required"
[ -n "$PHONE" ] || die "--phone is required"
[ -d "$REPO/.git" ] || die "not a git repository: $REPO"
[ -x "$ADB" ] || ADB="$(command -v adb 2>/dev/null)"
[ -n "$ADB" ] && [ -x "$ADB" ] || die "adb is unavailable"

ANDROID_CLIENT="$REPO/android-client"
GRADLEW="$ANDROID_CLIENT/gradlew"
CHECKER="$REPO/scripts/tests/check_test20_r3_3_source_contract.py"
INSPECTOR="$REPO/scripts/tests/inspect_test20_r3_3_sdk_contract.sh"
[ -x "$GRADLEW" ] || die "Gradle wrapper missing or not executable: $GRADLEW"
[ -x "$CHECKER" ] || die "source-contract checker missing: $CHECKER"
[ -x "$INSPECTOR" ] || die "SDK inspector missing: $INSPECTOR"

EVIDENCE_ROOT="$HOME/rokid-nettest/tests"
mkdir -p "$EVIDENCE_ROOT" || die "cannot create evidence root: $EVIDENCE_ROOT"

python3 "$CHECKER" \
  --repo "$REPO" \
  --output "$EVIDENCE_ROOT/test20-r3-3-source-contract.json"
CHECK_RC=$?
[ "$CHECK_RC" -eq 0 ] || die "r3.3 source contract failed; APK was not built"

(
  cd "$ANDROID_CLIENT" || exit 1
  ./gradlew \
    :test20r32:clean \
    :test20r32:assembleDebug \
    -ProkidCxrLVersion=1.0.1 \
    --no-daemon
)
BUILD_RC=$?
[ "$BUILD_RC" -eq 0 ] || die "Test 20 r3.3 Gradle build failed"

"$INSPECTOR" \
  --repo "$REPO" \
  --output "$EVIDENCE_ROOT/test20-r3-3-sdk-contract"
SDK_RC=$?
[ "$SDK_RC" -eq 0 ] || die "client-l:1.0.1 SDK contract inspection failed; APK was not installed"

APK="$ANDROID_CLIENT/test20r32/build/outputs/apk/debug/test20r32-debug.apk"
[ -s "$APK" ] || die "expected debug APK is missing: $APK"

"$ADB" -s "$PHONE" get-state >/dev/null 2>&1
ADB_RC=$?
[ "$ADB_RC" -eq 0 ] || die "phone is unavailable through adb"

"$ADB" -s "$PHONE" install -r "$APK"
INSTALL_RC=$?
[ "$INSTALL_RC" -eq 0 ] || die "APK installation failed"

DUMP="$EVIDENCE_ROOT/test20-r3-3-installed-package.txt"
"$ADB" -s "$PHONE" shell dumpsys package "$PKG" > "$DUMP" 2>&1
DUMP_RC=$?
[ "$DUMP_RC" -eq 0 ] || die "installed package is not readable"
VERSION="$(grep -m1 'versionName=' "$DUMP" | sed -E 's/.*versionName=([^[:space:]]+).*/\1/')"
[ "$VERSION" = "$EXPECTED_VERSION" ] || die "installed version mismatch: expected $EXPECTED_VERSION, found ${VERSION:-UNRESOLVED}"

echo "TEST20_R3_3_APK_PREPARE=PASS"
echo "PACKAGE=$PKG"
echo "VERSION_NAME=$VERSION"
echo "SDK_COORDINATE=com.rokid.cxr:client-l:1.0.1"
echo "APK=$APK"
echo "NEXT_PROFILE=STRONG_REF_PRECONNECT"
echo "NEXT=run scripts/tests/run_test20_r3_3_callback_closure.sh"
