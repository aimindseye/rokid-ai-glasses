#!/usr/bin/env bash
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$REPO/android-client" || exit 1
./gradlew :test22:assembleDebug
RC=$?
APK="$REPO/android-client/test22/build/outputs/apk/debug/test22-debug.apk"
if [ "$RC" -eq 0 ] && [ -s "$APK" ]; then
  echo "TEST22_BUILD=PASS"
  echo "TEST22_APK=$APK"
  exit 0
fi
echo "TEST22_BUILD=FAIL"
exit 1
