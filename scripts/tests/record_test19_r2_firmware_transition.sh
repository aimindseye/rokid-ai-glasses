#!/usr/bin/env bash
# Read-only evidence assembly around a firmware update performed manually in Hi Rokid.

PHONE_SERIAL=""
BEFORE_SUMMARY=""
BEFORE_SCREENSHOT=""
AFTER_SCREENSHOT=""
OUTPUT=""
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
BEFORE_FIRMWARE="1.22.009-20260710-151201"
AFTER_FIRMWARE="1.23.009-20260725-153201"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --before-summary) BEFORE_SUMMARY="$2"; shift 2 ;;
    --before-screenshot) BEFORE_SCREENSHOT="$2"; shift 2 ;;
    --after-screenshot) AFTER_SCREENSHOT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 64 ;;
  esac
done
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUTPUT" ]; then OUTPUT="$HOME/rokid-nettest/private/test19-r2-firmware-transition-$STAMP"; fi
mkdir -p "$OUTPUT"

for required in "$BEFORE_SUMMARY" "$BEFORE_SCREENSHOT" "$AFTER_SCREENSHOT"; do
  if [ ! -s "$required" ]; then echo "TEST19_R2_FIRMWARE_TRANSITION=FAIL"; echo "MISSING=$required"; exit 30; fi
done
python3 - "$BEFORE_SUMMARY" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))
raise SystemExit(0 if v.get('qualification_pass') is True else 1)
PY
if [ "$?" -ne 0 ]; then
  echo "TEST19_R2_FIRMWARE_TRANSITION=BLOCKED"
  echo "REASON=PRE_UPDATE_CXR_L_RUN_DID_NOT_PASS"
  exit 30
fi

INSTALLED_VERSION="$($ADB -s "$PHONE_SERIAL" shell dumpsys package "$HI_ROKID_PACKAGE" 2>/dev/null | sed -n 's/.*versionName=\([^[:space:]]*\).*/\1/p' | head -n1)"
if [ "$INSTALLED_VERSION" != "$EXPECTED_HI_ROKID_VERSION" ]; then
  echo "TEST19_R2_FIRMWARE_TRANSITION=FAIL"
  echo "REASON=HI_ROKID_VERSION_CHANGED"
  exit 30
fi

cat <<TXT
Confirm in Hi Rokid that the glasses now show exactly:
$AFTER_FIRMWARE
and that stock connection, camera, audio, and charging status are normal.

Type FIRMWARE_1_23_STOCK_RECOVERY_PASS to continue:
TXT
read -r CONFIRM
if [ "$CONFIRM" != "FIRMWARE_1_23_STOCK_RECOVERY_PASS" ]; then
  echo "TEST19_R2_FIRMWARE_TRANSITION=FAIL"
  exit 20
fi

cp "$BEFORE_SUMMARY" "$OUTPUT/pre-update-connection-summary.json"
cp "$BEFORE_SCREENSHOT" "$OUTPUT/pre-update-firmware.jpg"
cp "$AFTER_SCREENSHOT" "$OUTPUT/post-update-firmware.jpg"
cat >"$OUTPUT/transition.json" <<JSON
{
  "schema": "rokid.test19-r2.firmware-transition.v1",
  "hi_rokid_version": "$INSTALLED_VERSION",
  "before_firmware": "$BEFORE_FIRMWARE",
  "after_firmware": "$AFTER_FIRMWARE",
  "pre_update_cxr_l_pass": true,
  "post_update_stock_recovery": true,
  "update_performed_by_script": false
}
JSON
(
  cd "$OUTPUT" || exit 91
  find . -type f ! -name SHA256SUMS-private.txt -print0 | LC_ALL=C sort -z |
    xargs -0 shasum -a 256 >SHA256SUMS-private.txt
  shasum -a 256 -c SHA256SUMS-private.txt >hash-verification.txt 2>&1
)
RC=$?
ZIP="${OUTPUT}-private-evidence.zip"
(
  cd "$(dirname "$OUTPUT")" || exit 91
  zip -qry "$ZIP" "$(basename "$OUTPUT")"
)
ZIP_RC=$?
if [ "$ZIP_RC" -eq 0 ]; then shasum -a 256 "$ZIP" | tee "${ZIP}.sha256.txt"; fi
if [ "$RC" -eq 0 ] && [ "$ZIP_RC" -eq 0 ]; then
  echo "TEST19_R2_FIRMWARE_TRANSITION=PASS"
  echo "TEST19_R2_FIRMWARE_TRANSITION_EVIDENCE=$OUTPUT"
  exit 0
fi
echo "TEST19_R2_FIRMWARE_TRANSITION=FAIL"
exit 30
