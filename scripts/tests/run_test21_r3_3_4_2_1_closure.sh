#!/usr/bin/env bash
REPO="";R3341="";OUTPUT="";CXRL_AAR=""
while [ "$#" -gt 0 ];do
 case "$1" in
  --repo)REPO="$2";shift 2;;
  --r3341-evidence)R3341="$2";shift 2;;
  --output)OUTPUT="$2";shift 2;;
  --cxrl-aar)CXRL_AAR="$2";shift 2;;
  *)echo "ERROR: unknown argument $1";exit 2;;
 esac
done
[ -d "$REPO/.git" ]&&[ -d "$R3341/raw/apks" ]&&[ -n "$OUTPUT" ]||{ echo "ERROR: invalid arguments";exit 2; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_1_source_contract.py"
ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_1_closure.py"
mkdir -p "$OUTPUT/sanitized"||exit 1
echo "============================================================"
echo "TEST 21 r3.3.4.2.1 — SDK/FALLBACK + GLOBAL INTENT + SERVICE SIDE"
echo "============================================================"
echo "MODE=OFFLINE_EXISTING_EVIDENCE_ONLY"
echo "APK_SCOPE=ALL_PRESERVED_R3_3_4_1_SPLITS"
echo "DEVICE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"
PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO"||exit 1
if [ -n "$CXRL_AAR" ];then
 PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" --repo "$REPO" --r3341-evidence "$R3341" --output "$OUTPUT" --cxrl-aar "$CXRL_AAR"
else
 PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" --repo "$REPO" --r3341-evidence "$R3341" --output "$OUTPUT"
fi
RC=$?
[ "$RC" -eq 0 ]||exit "$RC"
echo "TEST21_R3_3_4_2_1_RUN_RC=0"
echo "OUTPUT=$OUTPUT"
echo "DEVICE_OPERATION=NONE"
echo "ADB_OPERATION=NONE"
echo "NEW_CAPTURE=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
