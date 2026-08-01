#!/usr/bin/env bash
# Build-only verification. No install, ADB, device, or media operation.
REPO=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$REPO" ]; then echo "ERROR: --repo is required" >&2; exit 2; fi
if [ ! -d "$REPO/.git" ]; then echo "ERROR: not a git repository: $REPO" >&2; exit 1; fi
python3 "$REPO/scripts/tests/check_test20_final_source_contract.py" --repo "$REPO"
RC=$?
if [ "$RC" -ne 0 ]; then echo "TEST20_FINAL_BUILD_VERIFY=FAIL_SOURCE_CONTRACT"; exit "$RC"; fi
cd "$REPO/android-client" || exit 1
if [ ! -x ./gradlew ]; then echo "ERROR: android-client/gradlew missing or not executable" >&2; exit 1; fi
./gradlew --no-daemon :test20r32:clean :test20r32:assembleDebug -ProkidCxrLVersion=1.0.1
RC=$?
if [ "$RC" -ne 0 ]; then echo "TEST20_FINAL_BUILD_VERIFY=FAIL_GRADLE"; exit "$RC"; fi
bash "$REPO/scripts/tests/inspect_test20_final_sdk_contract.sh" --repo "$REPO"
RC=$?
if [ "$RC" -ne 0 ]; then echo "TEST20_FINAL_BUILD_VERIFY=FAIL_SDK_CONTRACT"; exit "$RC"; fi
APK="$REPO/android-client/test20r32/build/outputs/apk/debug/test20r32-debug.apk"
if [ ! -s "$APK" ]; then echo "ERROR: expected APK missing: $APK" >&2; exit 1; fi
python3 - "$APK" <<'PY'
from pathlib import Path
import hashlib,sys
p=Path(sys.argv[1]); b=p.read_bytes(); print('APK_SHA256='+hashlib.sha256(b).hexdigest()); print('APK_BYTES='+str(len(b)))
PY
echo "TEST20_FINAL_BUILD_VERIFY=PASS"
echo "EXPECTED_VERSION_NAME=1.0-test20-final"
echo "SDK_COORDINATE=com.rokid.cxr:client-l:1.0.1"
echo "SDK_VERSION_INPUT=-ProkidCxrLVersion=1.0.1"
echo "DEVICE_OPERATION=NONE"
echo "PHOTO_OPERATION=NONE"
echo "APK=$APK"
