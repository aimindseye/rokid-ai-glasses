#!/usr/bin/env bash
REPO="";PHONE="";R3341="";OUTPUT="";PROFILE="RUNTIME_CODE_ORIGIN_READ_ONLY"
while [ "$#" -gt 0 ]; do
 case "$1" in
  --repo) REPO="$2";shift 2;;
  --phone) PHONE="$2";shift 2;;
  --r3341-evidence) R3341="$2";shift 2;;
  --output) OUTPUT="$2";shift 2;;
  --profile) PROFILE="$2";shift 2;;
  *) echo "ERROR: unknown argument $1";exit 2;;
 esac
done
[ -d "$REPO/.git" ] && [ -n "$PHONE" ] && [ -d "$R3341/raw/apks" ] && [ -n "$OUTPUT" ] || { echo "ERROR: invalid arguments";exit 2; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_3_source_contract.py"
ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_3_code_origin.py"
COL="$OUTPUT/private/device-origin-collection"
mkdir -p "$COL/package-code" "$COL/runtime-artifacts" "$OUTPUT/sanitized" || exit 1

echo "============================================================"
echo "TEST 21 r3.3.4.2.3 — READ-ONLY RUNTIME CODE-ORIGIN CLOSURE"
echo "============================================================"
echo "PROFILE=$PROFILE"
echo "DEVICE_ACCESS=ADB_READ_ONLY"
echo "DEVICE_MUTATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO" || exit 1
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb unavailable";exit 1; }
adb -s "$PHONE" get-state >/dev/null 2>&1 || { echo "ERROR: device unavailable";exit 1; }
HI_PACKAGE="com.rokid.sprite.global.aiapp"

adb -s "$PHONE" shell pm path "$HI_PACKAGE" >"$COL/package-paths.txt" 2>"$COL/package-paths.stderr.txt"; PM_RC=$?
adb -s "$PHONE" shell dumpsys package "$HI_PACKAGE" >"$COL/dumpsys-package.txt" 2>"$COL/dumpsys-package.stderr.txt"; DUMP_RC=$?
adb -s "$PHONE" shell cmd package list libraries >"$COL/shared-libraries.txt" 2>"$COL/shared-libraries.stderr.txt"; LIB_RC=$?
adb -s "$PHONE" shell pidof "$HI_PACKAGE" >"$COL/process-id.txt" 2>"$COL/process-id.stderr.txt"; PID_RC=$?
PID="$(tr -d '\r\n ' < "$COL/process-id.txt" 2>/dev/null | awk '{print $1}')"
if [ -n "$PID" ]; then
  adb -s "$PHONE" shell cat "/proc/$PID/maps" >"$COL/process-maps.txt" 2>"$COL/process-maps.stderr.txt"; MAP_RC=$?
  if [ "$MAP_RC" -eq 0 ] && [ -s "$COL/process-maps.txt" ]; then echo "READABLE" >"$COL/process-maps-status.txt"; else
    if grep -Eiq 'permission|denied' "$COL/process-maps.stderr.txt"; then echo "DENIED_BY_ANDROID" >"$COL/process-maps-status.txt"; else echo "UNAVAILABLE" >"$COL/process-maps-status.txt"; fi
  fi
  adb -s "$PHONE" shell dumpsys meminfo "$PID" >"$COL/process-meminfo.txt" 2>"$COL/process-meminfo.stderr.txt"; MEM_RC=$?
else
  : >"$COL/process-maps.txt"; echo "PROCESS_NOT_RUNNING" >"$COL/process-maps-status.txt"; MAP_RC=0; MEM_RC=0
fi
printf 'PM_PATH_RC=%s\nDUMPSYS_PACKAGE_RC=%s\nSHARED_LIBRARIES_RC=%s\nPIDOF_RC=%s\nPROCESS_MAPS_RC=%s\nMEMINFO_RC=%s\n' "$PM_RC" "$DUMP_RC" "$LIB_RC" "$PID_RC" "$MAP_RC" "$MEM_RC" >"$COL/collection-status.txt"
[ "$PM_RC" -eq 0 ] && [ -s "$COL/package-paths.txt" ] && [ "$DUMP_RC" -eq 0 ] || { echo "ERROR: required read-only package metadata unavailable";exit 1; }

# Pull every PackageManager-reported code APK. This is read-only and private.
MAN="$COL/pull-manifest.tsv"
printf 'KIND\tREMOTE_PATH\tLOCAL_REL\tSTATUS\tSHA256\n' >"$MAN"
sed -n 's/^package://p' "$COL/package-paths.txt" | tr -d '\r' >"$COL/package-code-paths.txt"
IDX=0
while IFS= read -r remote; do
 [ -n "$remote" ] || continue
 IDX=$((IDX+1)); local_rel="package-code/code-$IDX.apk"; local_file="$COL/$local_rel"
 if adb -s "$PHONE" pull "$remote" "$local_file" >/dev/null 2>"$COL/package-code/code-$IDX.pull.stderr.txt"; then
   h="$(shasum -a 256 "$local_file" | awk '{print $1}')"; printf 'PACKAGE_CODE\t%s\t%s\tPASS\t%s\n' "$remote" "$local_rel" "$h" >>"$MAN"
 else
   printf 'PACKAGE_CODE\t%s\t%s\tFAIL\tNONE\n' "$remote" "$local_rel" >>"$MAN"
 fi
done < "$COL/package-code-paths.txt"

# Discover additional code containers from package metadata and readable process maps.
PYTHONDONTWRITEBYTECODE=1 python3 - "$COL" <<'PY2'
from pathlib import Path
import re,sys
c=Path(sys.argv[1]);text=''
for n in ('dumpsys-package.txt','process-maps.txt'):
 p=c/n
 if p.is_file():text+='\n'+p.read_text(errors='replace')
rx=re.compile(r'/(?:[^\s\],;"\']+/)*[^\s\],;"\']+\.(?:apk|jar|dex)')
vals=[]
for x in rx.findall(text):
 x=x.rstrip(':)')
 if x not in vals: vals.append(x)
pm=set()
p=c/'package-paths.txt'
if p.is_file():pm={z[8:].strip() for z in p.read_text(errors='replace').splitlines() if z.startswith('package:')}
# Keep package paths separately; additional pulls are bounded to relevant/shared-looking code containers.
extra=[x for x in vals if x not in pm and any(k in x.lower() for k in ('rokid','cxr','sprite','aiapp','externalapp'))][:48]
(c/'additional-artifact-candidates.txt').write_text('\n'.join(extra)+('\n' if extra else ''))
PY2
IDX=0
while IFS= read -r remote; do
 [ -n "$remote" ] || continue
 IDX=$((IDX+1)); ext="${remote##*.}"; case "$ext" in apk|jar|dex) ;; *) ext="bin";; esac
 local_rel="runtime-artifacts/artifact-$IDX.$ext"; local_file="$COL/$local_rel"
 if adb -s "$PHONE" pull "$remote" "$local_file" >/dev/null 2>"$COL/runtime-artifacts/artifact-$IDX.pull.stderr.txt"; then
   h="$(shasum -a 256 "$local_file" | awk '{print $1}')"; printf 'RUNTIME_OR_SHARED_CODE\t%s\t%s\tPASS\t%s\n' "$remote" "$local_rel" "$h" >>"$MAN"
 else
   printf 'RUNTIME_OR_SHARED_CODE\t%s\t%s\tFAIL\tNONE\n' "$remote" "$local_rel" >>"$MAN"
 fi
done < "$COL/additional-artifact-candidates.txt"

PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" --repo "$REPO" --r3341-evidence "$R3341" --collection "$COL" --output "$OUTPUT"
RC=$?
[ "$RC" -eq 0 ] || exit "$RC"
echo "TEST21_R3_3_4_2_3_RUN_RC=0"
echo "OUTPUT=$OUTPUT"
echo "ADB_READ_ONLY=YES"
echo "DEVICE_MUTATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
