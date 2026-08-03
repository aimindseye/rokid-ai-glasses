#!/usr/bin/env bash

REPO=""
R3341_EVIDENCE=""
OUTPUT=""
FIXTURE_JSON=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --r3341-evidence) R3341_EVIDENCE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --fixture-json) FIXTURE_JSON="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1"; exit 2 ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$OUTPUT" ]; then
  echo "ERROR: required: --repo <repo> --output <output> and, for a real run, --r3341-evidence <private evidence root>"
  exit 2
fi
if [ -z "$FIXTURE_JSON" ] && [ -z "$R3341_EVIDENCE" ]; then
  echo "ERROR: --r3341-evidence is required for a real run"
  exit 2
fi

printf '%s\n' \
  '============================================================' \
  'TEST 21 r3.3.4.2.6 — PRIVILEGE-FREE BINDER CONTRACT' \
  'MODE=HOST_ONLY_EXISTING_EVIDENCE' \
  'ROOT_REQUIRED=NO' \
  'MAGISK_REQUIRED=NO' \
  'ADB_REQUIRED=NO' \
  'FRIDA_REQUIRED=NO' \
  'PHONE_ACTION=NONE' \
  '============================================================'

if [ ! -d "$REPO/.git" ]; then
  echo "ERROR: invalid repository: $REPO"
  exit 2
fi

if [ -z "$FIXTURE_JSON" ]; then
  if [ ! -d "$R3341_EVIDENCE/raw/apks" ]; then
    echo "ERROR: expected prior evidence directory missing: $R3341_EVIDENCE/raw/apks"
    exit 2
  fi
else
  if [ ! -f "$FIXTURE_JSON" ]; then
    echo "ERROR: validation fixture missing: $FIXTURE_JSON"
    exit 2
  fi
  echo "VALIDATION_FIXTURE_MODE=YES"
fi

PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/check_test21_r3_3_4_2_6_source_contract.py" --repo "$REPO"
CHECK_RC=$?
if [ "$CHECK_RC" -ne 0 ]; then
  echo "TEST21_R3_3_4_2_6_SOURCE_CONTRACT=FAIL"
  echo "TERMINAL_REMAINS_OPEN=YES"
  exit "$CHECK_RC"
fi

mkdir -p "$OUTPUT"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  echo "ERROR: unable to create output: $OUTPUT"
  exit "$MKDIR_RC"
fi

if [ -n "$FIXTURE_JSON" ]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/analyze_test21_r3_3_4_2_6_privilege_free_contract.py" \
    --repo "$REPO" \
    --output "$OUTPUT" \
    --fixture-json "$FIXTURE_JSON"
  ANALYZE_RC=$?
else
  PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/analyze_test21_r3_3_4_2_6_privilege_free_contract.py" \
    --repo "$REPO" \
    --r3341-evidence "$R3341_EVIDENCE" \
    --output "$OUTPUT"
  ANALYZE_RC=$?
fi

if [ "$ANALYZE_RC" -eq 0 ]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$REPO/scripts/tests/package_test21_r3_3_4_2_6_sanitized.py" --evidence "$OUTPUT"
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
  'DEVICE_OPERATION=NONE' \
  'PHONE_ACTION=NONE' \
  'PHOTO_OPERATION=NONE' \
  'AUDIO_OPERATION=NONE' \
  'NETWORK_CAPTURE=NONE' \
  'TERMINAL_REMAINS_OPEN=YES' \
  '============================================================'

if [ "$ANALYZE_RC" -ne 0 ]; then
  exit "$ANALYZE_RC"
fi
if [ "$PACKAGE_RC" -ne 0 ]; then
  exit "$PACKAGE_RC"
fi
exit 0
