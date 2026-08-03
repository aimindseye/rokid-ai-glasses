#!/usr/bin/env bash
REPO=""; PHONE=""; OUTPUT=""; PRIOR=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --prior-evidence) PRIOR="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument $1"; exit 2 ;;
  esac
done
[ -d "$REPO/.git" ] || { echo "ERROR: invalid repo"; exit 2; }
[ -n "$PHONE" ] || { echo "ERROR: --phone required"; exit 2; }
[ -n "$OUTPUT" ] || { echo "ERROR: --output required"; exit 2; }

CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_5_2_1_1_source_contract.py"
COLLECT="$REPO/scripts/tests/collect_test21_r3_3_4_2_5_2_1_1_persistent.py"
ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_5_2_1_1_persistent.py"
COL="$OUTPUT/private/external-memory-persistent"
mkdir -p "$COL" || exit 1

echo "============================================================"
echo "TEST 21 r3.3.4.2.5.2.1.1 — PERSISTENT ROOT MEMORY SESSION"
echo "============================================================"
echo "MODE=PERSISTENT_ROOT_EXTERNAL_MEMORY_COVERAGE_REPAIR"
echo "QUALIFICATION_MAX_SECONDS=60"
echo "GLOBAL_RUNTIME_MAX_SECONDS=600"
echo "PROGRESS_TELEMETRY=ENABLED"
echo "DEVICE_TRANSIENT_TEMP_FILES=YES"
echo "DEVICE_PERSISTENT_MUTATION=NONE"
echo "FRIDA_SERVER_START=NONE"
echo "FRIDA_PROCESS_ATTACH=NONE"
echo "INJECTED_AGENT_LOAD=NONE"
echo "PTRACE_ATTACH=NONE"
echo "PROCESS_SIGNAL=NONE"
echo "PAYLOAD_EXECUTION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"

PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO" || exit 1

if [ -n "$PRIOR" ]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$COLLECT" \
    --phone "$PHONE" \
    --output "$COL" \
    --prior-evidence "$PRIOR"
else
  PYTHONDONTWRITEBYTECODE=1 python3 "$COLLECT" \
    --phone "$PHONE" \
    --output "$COL"
fi
COLLECT_RC=$?
[ "$COLLECT_RC" -eq 0 ] || { echo "ERROR: persistent-root collection failed"; exit "$COLLECT_RC"; }

PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" \
  --repo "$REPO" \
  --collection "$COL" \
  --output "$OUTPUT"
ANALYZE_RC=$?
[ "$ANALYZE_RC" -eq 0 ] || exit "$ANALYZE_RC"

echo "TEST21_R3_3_4_2_5_2_1_1_RUN_RC=0"
echo "OUTPUT=$OUTPUT"
echo "DEVICE_MEMORY_READ=BOUNDED_READ_ONLY"
echo "DEVICE_TRANSIENT_TEMP_FILES=YES"
echo "TEMP_CLEANUP_REQUIRED=YES"
echo "DEVICE_PERSISTENT_MUTATION=NONE"
echo "FRIDA_SERVER_START=NONE"
echo "FRIDA_PROCESS_ATTACH=NONE"
echo "INJECTED_AGENT_LOAD=NONE"
echo "PTRACE_ATTACH=NONE"
echo "PROCESS_SIGNAL=NONE"
echo "PAYLOAD_EXECUTION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
