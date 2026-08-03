#!/usr/bin/env bash
REPO=""
R333=""
R3331=""
CSV=""
OUTPUT=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --r333-evidence) R333="$2"; shift 2 ;;
    --r3331-evidence) R3331="$2"; shift 2 ;;
    --native-csv) CSV="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument $1"; exit 2 ;;
  esac
done

[ -d "$REPO/.git" ] || { echo "ERROR: --repo must be git repo"; exit 2; }
[ -d "$R333/raw" ] || { echo "ERROR: r3.3.3 private evidence raw directory missing"; exit 2; }
[ -d "$R3331/raw" ] || { echo "ERROR: r3.3.3.1 private evidence raw directory missing"; exit 2; }
[ -s "$CSV" ] || { echo "ERROR: native PCAPdroid CSV missing/empty"; exit 2; }
[ -n "$OUTPUT" ] || { echo "ERROR: --output required"; exit 2; }

ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_3_2_1_offline.py"
CHECK="$REPO/scripts/tests/check_test21_r3_3_3_2_1_source_contract.py"

python3 "$CHECK" --repo "$REPO"
CHECK_RC=$?
if [ "$CHECK_RC" -ne 0 ]; then
  exit "$CHECK_RC"
fi

command -v tshark >/dev/null 2>&1
TSHARK_RC=$?
if [ "$TSHARK_RC" -ne 0 ]; then
  echo "ERROR: tshark not found in PATH"
  exit 1
fi

if [ -e "$OUTPUT" ]; then
  echo "ERROR: output already exists: $OUTPUT"
  exit 1
fi

mkdir -p "$OUTPUT/private" "$OUTPUT/sanitized"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  echo "ERROR: unable to create output directory"
  exit "$MKDIR_RC"
fi

printf '%s\n' \
  "MODE=OFFLINE_EXISTING_EVIDENCE_ONLY" \
  "R333_PRIVATE_INPUT_NOT_COPIED=YES" \
  "R3331_PRIVATE_INPUT_NOT_COPIED=YES" \
  "NATIVE_CSV_RAW_NOT_COPIED=YES" \
  "DEVICE_OPERATION=NONE" \
  "ADB_OPERATION=NONE" \
  "NEW_CAPTURE=NONE" \
  > "$OUTPUT/private/provenance-private.txt"

echo "============================================================"
echo "TEST 21 r3.3.3.2.1 — TSHARK SEPARATOR REPAIR + OFFLINE REANALYSIS"
echo "============================================================"
echo "MODE=OFFLINE_EXISTING_EVIDENCE_ONLY"
echo "TSHARK_FIELD_SEPARATOR_REPAIR=separator=/t"
echo "GROUND_TRUTH_GATE=REQUIRE_EXACT_4_OF_4"
echo "DEVICE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"

python3 "$ANALYZE" \
  --r333-evidence "$R333" \
  --r3331-evidence "$R3331" \
  --native-csv "$CSV" \
  --output "$OUTPUT"
RUN_RC=$?

echo "TEST21_R3_3_3_2_1_RUN_RC=$RUN_RC"
echo "OUTPUT=$OUTPUT"
echo "DEVICE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
exit "$RUN_RC"
