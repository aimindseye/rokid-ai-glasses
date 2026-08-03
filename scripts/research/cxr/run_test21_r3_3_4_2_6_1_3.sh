#!/bin/bash
# Test 21 r3.3.4.2.6.1.3 — host-only callback Stub dispatch closure.
# Intentionally does not enable set -e/-u/pipefail in the caller's shell.

usage() {
  cat <<'EOF'
Usage:
  run_test21_r3_3_4_2_6_1_3.sh \
    --repo /path/to/rokid-ai-glasses \
    --source-summary-zip /path/to/test21-r3-3-4-2-6-1-2-...-sanitized-summary.zip \
    --output /path/to/output-dir \
    [--aar /path/to/client-l-1.0.1.aar]
EOF
}

REPO=""
SOURCE=""
OUTPUT=""
AAR=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --source-summary-zip) SOURCE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --aar) AAR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$SOURCE" ] || [ -z "$OUTPUT" ]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ANALYZER="$SCRIPT_DIR/analyze_test21_r3_3_4_2_6_1_3_callback_stub_dispatch.py"
PACKAGER="$SCRIPT_DIR/package_test21_r3_3_4_2_6_1_3_sanitized.py"

if [ ! -x "$ANALYZER" ] || [ ! -x "$PACKAGER" ]; then
  echo "ERROR: r3.3.4.2.6.1.3 tools are not installed together" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then echo "ERROR: python3 not found" >&2; exit 1; fi
if ! command -v javac >/dev/null 2>&1; then echo "ERROR: javac not found; a JDK is required" >&2; exit 1; fi
if ! command -v java >/dev/null 2>&1; then echo "ERROR: java not found; a JDK is required" >&2; exit 1; fi

SAN_DIR="$OUTPUT/sanitized-summary"
ZIP_PATH="${OUTPUT}-sanitized-summary.zip"
mkdir -p "$(dirname -- "$OUTPUT")"

CMD=(python3 "$ANALYZER" --repo "$REPO" --source-summary-zip "$SOURCE" --output "$SAN_DIR")
if [ -n "$AAR" ]; then CMD+=(--aar "$AAR"); fi

"${CMD[@]}"
ANALYZE_RC=$?
if [ "$ANALYZE_RC" -ne 0 ]; then
  echo "TEST21_R3_3_4_2_6_1_3_ANALYZER_RC=$ANALYZE_RC"
  echo "DEVICE_OPERATION=NONE"
  echo "PHONE_ACTION=NONE"
  exit "$ANALYZE_RC"
fi

python3 "$PACKAGER" --input "$SAN_DIR" --zip "$ZIP_PATH"
PACKAGE_RC=$?

echo "TEST21_R3_3_4_2_6_1_3_ANALYZER_RC=$ANALYZE_RC"
echo "TEST21_R3_3_4_2_6_1_3_PACKAGE_RC=$PACKAGE_RC"
echo "OUTPUT_ROOT=$OUTPUT"
echo "DEVICE_OPERATION=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "NETWORK_CAPTURE=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
exit "$PACKAGE_RC"
