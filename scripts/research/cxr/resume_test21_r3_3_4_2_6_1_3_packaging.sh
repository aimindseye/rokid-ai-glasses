#!/bin/bash
# Resume only the r3.3.4.2.6.1.3 sanitized packaging step after analyzer success.
# Does not enable set -e/-u/pipefail and performs no device operations.
usage(){ echo "Usage: bash resume_test21_r3_3_4_2_6_1_3_packaging.sh --repo /path/to/repo --output /path/to/r3.3.4.2.6.1.3-output-root"; }
REPO=""; OUTPUT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --output) OUTPUT="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2;;
  esac
done
if [ -z "$REPO" ] || [ -z "$OUTPUT" ]; then usage >&2; exit 2; fi
PACKAGER="$REPO/scripts/research/cxr/package_test21_r3_3_4_2_6_1_3_sanitized.py"
SAN_DIR="$OUTPUT/sanitized-summary"
ZIP_PATH="${OUTPUT}-sanitized-summary.zip"
if [ ! -x "$PACKAGER" ]; then echo "ERROR: repaired packager not found: $PACKAGER" >&2; exit 1; fi
if [ ! -d "$SAN_DIR" ]; then echo "ERROR: analyzer sanitized-summary directory not found: $SAN_DIR" >&2; exit 1; fi
python3 "$PACKAGER" --input "$SAN_DIR" --zip "$ZIP_PATH"
RC=$?
echo "TEST21_R3_3_4_2_6_1_3_PACKAGING_RESUME_RC=$RC"
echo "OUTPUT_ROOT=$OUTPUT"
echo "DEVICE_OPERATION=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "NETWORK_CAPTURE=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
exit "$RC"
