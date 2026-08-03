#!/usr/bin/env bash

REPO=""
AAR=""
OUTPUT=""
FIXTURE_MODE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --aar) AAR="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --fixture-mode) FIXTURE_MODE=1; shift ;;
    *) echo "ERROR: unknown argument: $1"; exit 2 ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$OUTPUT" ]; then
  echo "ERROR: required: --repo <repo> --output <output>; optional --aar <client-l-1.0.1.aar>"
  exit 2
fi

printf '%s\n' \
  '============================================================' \
  'TEST 21 r3.3.4.2.6.1.1 — OBFUSCATION-RESILIENT PROXY CLOSURE' \
  'MODE=HOST_ONLY_LOCAL_AAR' \
  'ROOT_REQUIRED=NO' \
  'MAGISK_REQUIRED=NO' \
  'ADB_REQUIRED=NO' \
  'FRIDA_REQUIRED=NO' \
  'PHONE_ACTION=NONE' \
  'NETWORK_REQUIRED=NO' \
  '============================================================'

if [ ! -d "$REPO/.git" ]; then
  echo "ERROR: invalid repository: $REPO"
  exit 2
fi

PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/check_test21_r3_3_4_2_6_1_1_source_contract.py" --repo "$REPO"
CHECK_RC=$?
if [ "$CHECK_RC" -ne 0 ]; then
  echo "TEST21_R3_3_4_2_6_1_1_SOURCE_CONTRACT=FAIL"
  echo "DEVICE_OPERATION=NONE"
  echo "TERMINAL_REMAINS_OPEN=YES"
  exit "$CHECK_RC"
fi

mkdir -p "$OUTPUT"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  echo "ERROR: unable to create output: $OUTPUT"
  exit "$MKDIR_RC"
fi

ANALYZER="$REPO/scripts/tests/analyze_test21_r3_3_4_2_6_1_1_proxy_closure.py"
if [ "$FIXTURE_MODE" -eq 1 ]; then
  if [ -z "$AAR" ]; then
    echo "ERROR: --fixture-mode requires --aar"
    exit 2
  fi
  PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZER" --aar "$AAR" --fixture-mode --output "$OUTPUT"
  ANALYZE_RC=$?
elif [ -n "$AAR" ]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZER" --aar "$AAR" --output "$OUTPUT"
  ANALYZE_RC=$?
else
  PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZER" --output "$OUTPUT"
  ANALYZE_RC=$?
fi

if [ "$ANALYZE_RC" -eq 0 ]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/package_test21_r3_3_4_2_6_1_1_sanitized.py" --evidence "$OUTPUT"
  PACKAGE_RC=$?
else
  PACKAGE_RC=99
fi

printf '%s\n' \
  '============================================================' \
  "ANALYZE_RC=$ANALYZE_RC" \
  "PACKAGE_RC=$PACKAGE_RC" \
  'ROOT_OPERATION=NONE' \
  'MAGISK_OPERATION=NONE' \
  'ADB_OPERATION=NONE' \
  'FRIDA_OPERATION=NONE' \
  'DEVICE_OPERATION=NONE' \
  'PHONE_ACTION=NONE' \
  'PHOTO_OPERATION=NONE' \
  'AUDIO_OPERATION=NONE' \
  'NETWORK_CAPTURE=NONE' \
  'NETWORK_OPERATION=NONE' \
  'TERMINAL_REMAINS_OPEN=YES' \
  '============================================================'

if [ "$ANALYZE_RC" -ne 0 ]; then exit "$ANALYZE_RC"; fi
if [ "$PACKAGE_RC" -ne 0 ]; then exit "$PACKAGE_RC"; fi
exit 0
