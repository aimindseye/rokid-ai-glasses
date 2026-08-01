#!/bin/bash
# Build and install the mechanically gated Test 20 r3.2.1.3 APK.
# macOS Bash 3.2 compatible. Intentionally does not enable set -e/-u/pipefail.

REPO=""
PHONE=""
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
EXPECTED_VERSION="1.0-test20-r3.2.1.3"
PKG="org.aimindseye.rokid.cxrphotoqualification"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/tests/prepare_test20_r3_2_1_3_apk.sh \
    --repo PATH \
    --phone ADB_SERIAL
EOF
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
CHECKER="$REPO/scripts/tests/check_test20_r3_2_1_source_contract.py"
[ -x "$GRADLEW" ] || die "Gradle wrapper missing or not executable: $GRADLEW"
[ -x "$CHECKER" ] || die "source-contract checker missing: $CHECKER"

python3 "$CHECKER" \
  --repo "$REPO" \
  --output "$HOME/rokid-nettest/tests/test20-r3-2-1-3-source-contract.json"
CHECK_RC=$?
[ "$CHECK_RC" -eq 0 ] || die "r3.2.1.3 source contract failed; APK was not built"

"$ADB" -s "$PHONE" get-state >/dev/null 2>&1
ADB_RC=$?
[ "$ADB_RC" -eq 0 ] || die "phone is unavailable through adb"

(
  cd "$ANDROID_CLIENT" || exit 1
  ./gradlew \
    :test20r32:clean \
    :test20r32:assembleDebug \
    -ProkidCxrLVersion=1.0.1 \
    --no-daemon
)
BUILD_RC=$?
[ "$BUILD_RC" -eq 0 ] || die "Test 20 r3.2.1.3 Gradle build failed"

APK="$ANDROID_CLIENT/test20r32/build/outputs/apk/debug/test20r32-debug.apk"
[ -s "$APK" ] || die "expected debug APK is missing: $APK"

"$ADB" -s "$PHONE" install -r "$APK"
INSTALL_RC=$?
[ "$INSTALL_RC" -eq 0 ] || die "APK installation failed"

DUMP="$HOME/rokid-nettest/tests/test20-r3-2-1-3-installed-package.txt"
mkdir -p "$(dirname "$DUMP")"
"$ADB" -s "$PHONE" shell dumpsys package "$PKG" > "$DUMP" 2>&1
DUMP_RC=$?
[ "$DUMP_RC" -eq 0 ] || die "installed package is not readable"
VERSION="$(grep -m1 'versionName=' "$DUMP" | sed -E 's/.*versionName=([^[:space:]]+).*/\1/')"
[ "$VERSION" = "$EXPECTED_VERSION" ] || die "installed version mismatch: expected $EXPECTED_VERSION, found ${VERSION:-UNRESOLVED}"

echo "TEST20_R3_2_1_3_APK_PREPARE=PASS"
echo "PACKAGE=$PKG"
echo "VERSION_NAME=$VERSION"
echo "APK=$APK"
echo "NEXT=run scripts/tests/run_test20_r3_2_1_photo_repair.sh"
