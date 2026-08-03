#!/usr/bin/env bash

REPO=""
PHONE=""
OUTPUT=""
HI_ROKID_PACKAGE=""
CUSTOM_PACKAGE=""
EXPECTED_AAR_SHA="c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
EXPECTED_GLOBAL_HI_ROKID_PACKAGE="com.rokid.sprite.global.aiapp"

usage() {
  cat <<'USAGE'
Usage:
  run_test21_r1_discovery.sh --repo <repo> --phone <adb-serial> --output <dir> [options]

Options:
  --hi-rokid-package <pkg>   Operator-resolved Hi Rokid package hint.
  --custom-package <pkg>     Operator-resolved custom companion package hint.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --hi-rokid-package) HI_ROKID_PACKAGE="$2"; shift 2 ;;
    --custom-package) CUSTOM_PACKAGE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1"; usage; exit 2 ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$PHONE" ] || [ -z "$OUTPUT" ]; then
  echo "ERROR: --repo, --phone, and --output are required"
  usage
  exit 2
fi

REPO="$(cd "$REPO" 2>/dev/null && pwd)"
if [ -z "$REPO" ]; then
  echo "ERROR: repo path cannot be resolved"
  exit 2
fi

mkdir -p "$OUTPUT/raw/package-dumps" "$OUTPUT/sanitized"
RAW="$OUTPUT/raw"
STATUS="$RAW/collection-status.txt"
: > "$STATUS"

record_rc() {
  printf 'RC_%s=%s\n' "$1" "$2" >> "$STATUS"
}

run_capture() {
  label="$1"
  outfile="$2"
  shift 2
  "$@" > "$outfile" 2>&1
  rc=$?
  record_rc "$label" "$rc"
  return 0
}

adb_cmd() {
  adb -s "$PHONE" "$@"
}

echo "============================================================"
echo "TEST 21 r1 — READ-ONLY RUNTIME DEPENDENCY DISCOVERY"
echo "============================================================"
echo "REPO=$REPO"
echo "OUTPUT=$OUTPUT"
echo "DEVICE_MUTATION=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "AIUI_OPERATION=STATIC_ELIGIBILITY_CENSUS_ONLY"

echo
echo "=== HOST PREFLIGHT ==="
command -v adb >/dev/null 2>&1
ADB_PRESENT_RC=$?
record_rc "ADB_PRESENT" "$ADB_PRESENT_RC"
if [ "$ADB_PRESENT_RC" -ne 0 ]; then
  echo "ERROR: adb not found"
  echo "TEST21_R1_DISCOVERY=FAIL"
  exit 1
fi

python3 "$REPO/scripts/tests/check_test21_r1_source_contract.py" --repo "$REPO"
SOURCE_RC=$?
record_rc "SOURCE_CONTRACT" "$SOURCE_RC"
if [ "$SOURCE_RC" -ne 0 ]; then
  echo "ERROR: Test21 r1 source contract failed"
  echo "TEST21_R1_DISCOVERY=FAIL"
  exit 1
fi

adb -s "$PHONE" get-state > "$RAW/adb-state.txt" 2>&1
ADB_STATE_RC=$?
record_rc "ADB_STATE" "$ADB_STATE_RC"
if [ "$ADB_STATE_RC" -ne 0 ]; then
  echo "ERROR: phone not reachable over adb"
  cat "$RAW/adb-state.txt"
  echo "TEST21_R1_DISCOVERY=FAIL"
  exit 1
fi

# Selected non-secret device identity. Do not collect ro.serialno.
run_capture "DEVICE_PROPERTIES" "$RAW/device-properties.txt" \
  adb_cmd shell sh -c 'printf "manufacturer="; getprop ro.product.manufacturer; printf "model="; getprop ro.product.model; printf "device="; getprop ro.product.device; printf "android_release="; getprop ro.build.version.release; printf "sdk="; getprop ro.build.version.sdk; printf "build_fingerprint="; getprop ro.build.fingerprint'

# Phone-side inventory. These files are private evidence and are not copied into sanitized outputs.
run_capture "PHONE_PACKAGES" "$RAW/phone-packages.txt" adb_cmd shell pm list packages -f
run_capture "PHONE_PROCESSES" "$RAW/phone-processes.txt" adb_cmd shell ps -A
run_capture "ACTIVITY_SERVICES" "$RAW/activity-services.txt" adb_cmd shell dumpsys activity services
run_capture "ACTIVITY_PROCESSES" "$RAW/activity-processes.txt" adb_cmd shell dumpsys activity processes
run_capture "BLUETOOTH_MANAGER" "$RAW/bluetooth-manager.txt" adb_cmd shell dumpsys bluetooth_manager
run_capture "COMPANION_DEVICE" "$RAW/companion-device.txt" adb_cmd shell dumpsys companiondevice

# Package candidates related to Rokid/CXR/AIUI. Only package names are used for iteration.
awk -F= '/^package:/ {print $NF}' "$RAW/phone-packages.txt" | \
  grep -Ei 'rokid|cxr|lingzhu|rizon|aiui|jsar|yoda|ink' | \
  sed 's/[[:space:]]*$//' | sort -u > "$RAW/relevant-packages.txt" 2>/dev/null || true

printf '%s\n' "$EXPECTED_GLOBAL_HI_ROKID_PACKAGE" >> "$RAW/relevant-packages.txt"
if [ -n "$HI_ROKID_PACKAGE" ]; then
  printf '%s\n' "$HI_ROKID_PACKAGE" >> "$RAW/relevant-packages.txt"
fi
if [ -n "$CUSTOM_PACKAGE" ]; then
  printf '%s\n' "$CUSTOM_PACKAGE" >> "$RAW/relevant-packages.txt"
fi
sort -u "$RAW/relevant-packages.txt" -o "$RAW/relevant-packages.txt" 2>/dev/null || true

while IFS= read -r pkg; do
  [ -z "$pkg" ] && continue
  safe_pkg="$(printf '%s' "$pkg" | tr -c 'A-Za-z0-9._-' '_')"
  run_capture "PACKAGE_${safe_pkg}" "$RAW/package-dumps/${safe_pkg}.txt" adb_cmd shell dumpsys package "$pkg"
done < "$RAW/relevant-packages.txt"

echo
echo "=== LOCAL REPOSITORY CXR-L / AIUI CENSUS ==="
{
  echo "CENSUS_SCOPE=repository_text_only"
  echo "TERMS=client-l|com.rokid.cxr|AIUI|.aix|JSAR|YodaOS|Ink|@yodaos-pkg/aiui"
  grep -RInE \
    --exclude-dir=.git \
    --exclude-dir=build \
    --exclude='*.apk' \
    --exclude='*.aar' \
    'client-l|com\.rokid\.cxr|AIUI|\.aix|JSAR|YodaOS|Ink|@yodaos-pkg/aiui' \
    "$REPO/android-client" "$REPO/docs" "$REPO/scripts" 2>/dev/null || true
} > "$RAW/repo-cxr-aiui-census.txt"
record_rc "REPO_CENSUS" 0

# Locate known CXR-L AAR in Gradle caches without changing dependency state.
AAR_CENSUS="$RAW/aar-census.txt"
: > "$AAR_CENSUS"
AAR_PATH=""
for candidate in \
  "$HOME/.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1"/*/*.aar \
  "$HOME/.gradle/caches"/**/client-l*1.0.1*.aar
do
  if [ -f "$candidate" ]; then
    echo "AAR_PATH=$candidate" >> "$AAR_CENSUS"
    if [ -z "$AAR_PATH" ]; then
      AAR_PATH="$candidate"
    fi
  fi
done

if [ -z "$AAR_PATH" ]; then
  # Portable fallback for shells without recursive glob expansion.
  AAR_PATH="$(find "$HOME/.gradle/caches" -type f -name '*.aar' -path '*com.rokid.cxr*client-l*1.0.1*' -print 2>/dev/null | head -n 1)"
  if [ -n "$AAR_PATH" ]; then
    echo "AAR_PATH=$AAR_PATH" >> "$AAR_CENSUS"
  fi
fi

if [ -n "$AAR_PATH" ] && [ -f "$AAR_PATH" ]; then
  if command -v shasum >/dev/null 2>&1; then
    AAR_SHA="$(shasum -a 256 "$AAR_PATH" | awk '{print $1}')"
  else
    AAR_SHA="$(python3 - "$AAR_PATH" <<'PY'
from pathlib import Path
import hashlib, sys
p=Path(sys.argv[1])
h=hashlib.sha256(p.read_bytes()).hexdigest()
print(h)
PY
)"
  fi
  echo "AAR_SHA256=$AAR_SHA" >> "$AAR_CENSUS"
  echo "EXPECTED_AAR_SHA256=$EXPECTED_AAR_SHA" >> "$AAR_CENSUS"
  if [ "$AAR_SHA" = "$EXPECTED_AAR_SHA" ]; then
    echo "AAR_SHA256_MATCH=YES" >> "$AAR_CENSUS"
  else
    echo "AAR_SHA256_MATCH=NO" >> "$AAR_CENSUS"
  fi

  TMP_AAR="$(mktemp -d "${TMPDIR:-/tmp}/test21-aar.XXXXXX")"
  if command -v unzip >/dev/null 2>&1; then
    unzip -qq "$AAR_PATH" -d "$TMP_AAR" >/dev/null 2>&1
    UNZIP_RC=$?
    record_rc "AAR_UNZIP" "$UNZIP_RC"
    if [ "$UNZIP_RC" -eq 0 ]; then
      {
        echo "AAR_STATIC_STRING_CENSUS=client-l:1.0.1"
        find "$TMP_AAR" -type f -print 2>/dev/null
        grep -RInaE 'AIUI|\.aix|JSAR|YodaOS|Ink|Hi.?Rokid|rokid|cxr' "$TMP_AAR" 2>/dev/null || true
      } > "$RAW/aar-strings.txt"
    fi
  else
    record_rc "AAR_UNZIP" 127
  fi
  rm -rf "$TMP_AAR"
else
  echo "AAR_FOUND=NO" >> "$AAR_CENSUS"
  record_rc "AAR_DISCOVERY" 1
fi

echo
echo "=== ANALYZE ==="
ANALYZE_ARGS=(
  --evidence "$OUTPUT"
)
if [ -n "$HI_ROKID_PACKAGE" ]; then
  ANALYZE_ARGS+=(--hi-rokid-package "$HI_ROKID_PACKAGE")
fi
if [ -n "$CUSTOM_PACKAGE" ]; then
  ANALYZE_ARGS+=(--custom-package "$CUSTOM_PACKAGE")
fi

python3 "$REPO/scripts/tests/analyze_test21_r1_discovery.py" "${ANALYZE_ARGS[@]}"
ANALYZE_RC=$?
record_rc "ANALYZE" "$ANALYZE_RC"

echo
echo "============================================================"
if [ "$ANALYZE_RC" -eq 0 ]; then
  echo "TEST21_R1_DISCOVERY=PASS"
else
  echo "TEST21_R1_DISCOVERY=FAIL"
fi
echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT"
echo "SANITIZED_SUMMARY=$OUTPUT/sanitized/test21-r1-summary.json"
echo "DEVICE_MUTATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "PACKAGE_DISABLE_OR_UNINSTALL=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "FIRMWARE_OPERATION=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
echo "============================================================"

exit "$ANALYZE_RC"
