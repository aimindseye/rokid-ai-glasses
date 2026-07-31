#!/usr/bin/env bash
# Separate PCAPdroid gate. No reboot and no terminal shell options.

PHONE_SERIAL=""
FIRMWARE=""
CONNECTION_SUMMARY=""
PCAPDROID_CSV=""
OUTPUT=""
REPO=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --phone) PHONE_SERIAL="$2"; shift 2 ;;
    --firmware) FIRMWARE="$2"; shift 2 ;;
    --connection-summary) CONNECTION_SUMMARY="$2"; shift 2 ;;
    --pcapdroid-csv) PCAPDROID_CSV="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 64 ;;
  esac
done
if [ -z "$REPO" ]; then REPO="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"; fi
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUTPUT" ]; then OUTPUT="$HOME/rokid-nettest/tests/test19-r2-privacy-$FIRMWARE-$STAMP"; fi
mkdir -p "$OUTPUT"

if [ ! -s "$CONNECTION_SUMMARY" ]; then
  echo "TEST19_R2_PRIVACY_GATE=BLOCKED"
  echo "REASON=CONNECTION_SUMMARY_MISSING"
  exit 30
fi
python3 - "$CONNECTION_SUMMARY" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))
raise SystemExit(0 if v.get('qualification_pass') is True else 1)
PY
SUMMARY_RC=$?
if [ "$SUMMARY_RC" -ne 0 ]; then
  echo "TEST19_R2_PRIVACY_GATE=BLOCKED"
  echo "REASON=BASE_CONNECTION_DID_NOT_PASS"
  exit 30
fi

cat <<TXT
Test 19 r2 separate PCAPdroid privacy gate
===========================================

Before continuing:
1. In PCAPdroid, configure the app filter to include BOTH:
   - Test 19 r2 CXR-L (org.aimindseye.rokid.cxrlqualification)
   - Hi Rokid (com.rokid.sprite.global.aiapp)
2. Select CSV/connection metadata capture. Do not enable payload collection.
3. Start capture.
4. Keep the phone and glasses connected; do not reboot or update firmware.

Press Enter after PCAPdroid capture is running.
TXT
read -r _CAPTURE_STARTED

bash "$REPO/scripts/tests/run_test19_r2_connection.sh" \
  --repo "$REPO" \
  --phone "$PHONE_SERIAL" \
  --firmware "$FIRMWARE" \
  --output "$OUTPUT/connection"
CONNECTION_RC=$?
echo "TEST19_R2_PRIVACY_CONNECTION_EXIT_CODE=$CONNECTION_RC"

cat <<TXT

Stop PCAPdroid now and export its Connections CSV to exactly:
$PCAPDROID_CSV

Press Enter after the CSV exists and is non-empty.
TXT
read -r _CSV_EXPORTED

if [ ! -s "$PCAPDROID_CSV" ]; then
  echo "TEST19_R2_NETWORK_PRIVACY_GATE=BLOCKED"
  echo "REASON=PCAPDROID_CSV_MISSING_OR_EMPTY"
  exit 30
fi
cp "$PCAPDROID_CSV" "$OUTPUT/pcapdroid-connections.csv"
python3 "$REPO/scripts/tests/analyze_test19_r2_network.py" \
  --csv "$OUTPUT/pcapdroid-connections.csv" \
  --output "$OUTPUT/network-summary.json"
NETWORK_RC=$?
echo "TEST19_R2_NETWORK_ANALYSIS_EXIT_CODE=$NETWORK_RC"

(
  cd "$OUTPUT" || exit 91
  find . -type f ! -name SHA256SUMS-private.txt -print0 | LC_ALL=C sort -z |
    xargs -0 shasum -a 256 >SHA256SUMS-private.txt
)
HASH_RC=$?
PRIVATE_ZIP="${OUTPUT}-private-evidence.zip"
(
  cd "$(dirname "$OUTPUT")" || exit 91
  zip -qry "$PRIVATE_ZIP" "$(basename "$OUTPUT")"
)
ZIP_RC=$?
if [ "$ZIP_RC" -eq 0 ]; then shasum -a 256 "$PRIVATE_ZIP" | tee "${PRIVATE_ZIP}.sha256.txt"; fi

echo "TEST19_R2_PRIVACY_EVIDENCE_DIRECTORY=$OUTPUT"
echo "TEST19_R2_PRIVACY_PRIVATE_ZIP=$PRIVATE_ZIP"
if [ "$CONNECTION_RC" -eq 0 ] && [ "$NETWORK_RC" -eq 0 ] && [ "$HASH_RC" -eq 0 ] && [ "$ZIP_RC" -eq 0 ]; then
  echo "TEST19_R2_PRIVACY_GATE=PASS"
  exit 0
fi
if [ "$NETWORK_RC" -eq 10 ]; then echo "TEST19_R2_PRIVACY_GATE=FAIL"; exit 10; fi
echo "TEST19_R2_PRIVACY_GATE=BLOCKED"
exit 30
