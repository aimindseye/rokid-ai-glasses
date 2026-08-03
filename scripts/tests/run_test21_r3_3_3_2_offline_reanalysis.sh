#!/usr/bin/env bash
REPO="";R333="";R3331="";CSV="";OUTPUT=""
while [ "$#" -gt 0 ];do
 case "$1" in
  --repo) REPO="$2";shift 2;;
  --r333-evidence) R333="$2";shift 2;;
  --r3331-evidence) R3331="$2";shift 2;;
  --native-csv) CSV="$2";shift 2;;
  --output) OUTPUT="$2";shift 2;;
  *) echo "ERROR: unknown argument $1";exit 2;;
 esac
done
[ -d "$REPO/.git" ]||{ echo "ERROR: --repo must be git repo";exit 2; }
[ -d "$R333/raw" ]||{ echo "ERROR: r3.3.3 private evidence raw directory missing";exit 2; }
[ -d "$R3331/raw" ]||{ echo "ERROR: r3.3.3.1 private evidence raw directory missing";exit 2; }
[ -s "$CSV" ]||{ echo "ERROR: native PCAPdroid CSV missing/empty";exit 2; }
[ -n "$OUTPUT" ]||{ echo "ERROR: --output required";exit 2; }
ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_3_2_offline.py"
CHECK="$REPO/scripts/tests/check_test21_r3_3_3_2_source_contract.py"
python3 "$CHECK" --repo "$REPO"||exit 1
command -v tshark >/dev/null 2>&1||{ echo "ERROR: tshark not found in PATH";exit 1; }
if [ -e "$OUTPUT" ];then echo "ERROR: output already exists: $OUTPUT";exit 1;fi
mkdir -p "$OUTPUT/private" "$OUTPUT/sanitized"||exit 1
printf '%s\n' "R333_EVIDENCE_SHA256S_NOT_COPIED=YES" "R3331_EVIDENCE_SHA256S_NOT_COPIED=YES" "NATIVE_CSV_RAW_NOT_COPIED=YES" >"$OUTPUT/private/provenance-private.txt"
echo "============================================================"
echo "TEST 21 r3.3.3.2 — OFFLINE NATIVE CSV + KNOWN-ENDPOINT REANALYSIS"
echo "============================================================"
echo "DEVICE_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"
echo "PRIVATE_INPUT_COPY=NONE"
python3 "$ANALYZE" --r333-evidence "$R333" --r3331-evidence "$R3331" --native-csv "$CSV" --output "$OUTPUT"
RC=$?
echo "TEST21_R3_3_3_2_RUN_RC=$RC"
echo "OUTPUT=$OUTPUT"
echo "DEVICE_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
exit "$RC"
