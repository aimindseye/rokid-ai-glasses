#!/usr/bin/env bash
REPO="";PHONE="";R3341="";R33423="";OUTPUT="";ROOT_MODE="auto"
while [ "$#" -gt 0 ]; do
 case "$1" in
  --repo) REPO="$2";shift 2;;
  --phone) PHONE="$2";shift 2;;
  --r3341-evidence) R3341="$2";shift 2;;
  --r33423-evidence) R33423="$2";shift 2;;
  --output) OUTPUT="$2";shift 2;;
  --root-mode) ROOT_MODE="$2";shift 2;;
  *) echo "ERROR: unknown argument $1";exit 2;;
 esac
done
[ -d "$REPO/.git" ] && [ -d "$R3341/raw/apks" ] && [ -d "$R33423/private/device-origin-collection" ] && [ -n "$OUTPUT" ] || { echo "ERROR: invalid arguments";exit 2; }
case "$ROOT_MODE" in auto|never|required) ;; *) echo "ERROR: --root-mode must be auto, never, or required";exit 2;; esac
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_4_source_contract.py"
ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_4_payload_origin.py"
ROOTCOL="$OUTPUT/private/root-read-only"
mkdir -p "$ROOTCOL/root-artifacts" "$OUTPUT/private/recovered-payloads" "$OUTPUT/sanitized" || exit 1

echo "============================================================"
echo "TEST 21 r3.3.4.2.4 — NON-DEX / PROTECTED PAYLOAD ORIGIN"
echo "============================================================"
echo "MODE=OFFLINE_FIRST_OPTIONAL_ROOT_READ_ONLY"
echo "ROOT_MODE=$ROOT_MODE"
echo "PAYLOAD_EXECUTION=NONE"
echo "DEVICE_MUTATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO" || exit 1

printf 'KIND\tREMOTE_PATH\tLOCAL_REL\tSTATUS\tSHA256\n' >"$ROOTCOL/root-pull-manifest.tsv"
: >"$ROOTCOL/root-code-candidates.txt"
echo "NOT_ATTEMPTED" >"$ROOTCOL/root-status.txt"
echo "NOT_ATTEMPTED" >"$ROOTCOL/root-process-maps-status.txt"

if [ "$ROOT_MODE" != "never" ]; then
 if [ -z "$PHONE" ]; then
   echo "UNAVAILABLE_NO_PHONE_ARGUMENT" >"$ROOTCOL/root-status.txt"
 elif ! command -v adb >/dev/null 2>&1; then
   echo "UNAVAILABLE_ADB_MISSING" >"$ROOTCOL/root-status.txt"
 elif ! adb -s "$PHONE" get-state >/dev/null 2>&1; then
   echo "UNAVAILABLE_DEVICE_OFFLINE" >"$ROOTCOL/root-status.txt"
 else
   # Read-only root capability probe. No root-management state is changed by the harness itself.
   adb -s "$PHONE" shell su -c id >"$ROOTCOL/root-id.txt" 2>"$ROOTCOL/root-id.stderr.txt"; ROOT_RC=$?
   if [ "$ROOT_RC" -eq 0 ] && grep -q 'uid=0' "$ROOTCOL/root-id.txt"; then
     echo "AVAILABLE" >"$ROOTCOL/root-status.txt"
     HI_PACKAGE="com.rokid.sprite.global.aiapp"
     adb -s "$PHONE" shell pidof "$HI_PACKAGE" >"$ROOTCOL/process-id.txt" 2>"$ROOTCOL/process-id.stderr.txt"; PID_RC=$?
     PID="$(tr -d '\r\n ' < "$ROOTCOL/process-id.txt" 2>/dev/null | awk '{print $1}')"
     if [ -n "$PID" ]; then
       adb -s "$PHONE" shell su -c "cat /proc/$PID/maps" >"$ROOTCOL/root-process-maps.txt" 2>"$ROOTCOL/root-process-maps.stderr.txt"; MAP_RC=$?
       if [ "$MAP_RC" -eq 0 ] && [ -s "$ROOTCOL/root-process-maps.txt" ]; then echo "READABLE" >"$ROOTCOL/root-process-maps-status.txt"; else echo "UNAVAILABLE" >"$ROOTCOL/root-process-maps-status.txt"; fi
     else
       : >"$ROOTCOL/root-process-maps.txt";echo "PROCESS_NOT_RUNNING" >"$ROOTCOL/root-process-maps-status.txt"
     fi
     # Bounded private-code inventory. Only code/container extensions are listed; no databases/preferences are read.
     adb -s "$PHONE" shell su -c "find /data/user/0/$HI_PACKAGE/code_cache /data/user_de/0/$HI_PACKAGE/code_cache /data/data/$HI_PACKAGE/code_cache /data/user/0/$HI_PACKAGE/files /data/data/$HI_PACKAGE/files -maxdepth 6 -type f \( -name '*.dex' -o -name '*.jar' -o -name '*.apk' -o -name '*.zip' -o -name '*.odex' -o -name '*.vdex' -o -name '*.so' \) -print 2>/dev/null" >"$ROOTCOL/root-private-code-paths.txt" 2>"$ROOTCOL/root-private-code-paths.stderr.txt"; FIND_RC=$?
     PYTHONDONTWRITEBYTECODE=1 python3 - "$R33423" "$ROOTCOL" <<'PY2'
from pathlib import Path
import re,sys
r=Path(sys.argv[1]);c=Path(sys.argv[2]);vals=[]
for n in ('root-private-code-paths.txt','root-process-maps.txt'):
 p=c/n
 if not p.is_file():continue
 for line in p.read_text(errors='replace').splitlines():
  for x in re.findall(r'/[^\s\],;"\']+\.(?:apk|jar|dex|odex|vdex|so|zip)',line):
   if x not in vals:vals.append(x)
pm=set()
p=r/'private/device-origin-collection/package-paths.txt'
if p.is_file():pm={z[8:].strip() for z in p.read_text(errors='replace').splitlines() if z.startswith('package:')}
# Package APKs are already preserved by r3.3.4.2.3. Keep only extra mapped/private code candidates.
out=[x for x in vals if x not in pm][:64]
(c/'root-code-candidates.txt').write_text('\n'.join(out)+('\n' if out else ''))
PY2
     IDX=0
     while IFS= read -r remote; do
       [ -n "$remote" ] || continue
       IDX=$((IDX+1));ext="${remote##*.}";case "$ext" in apk|jar|dex|odex|vdex|so|zip) ;; *) ext="bin";; esac
       local_rel="root-artifacts/root-$IDX.$ext";local_file="$ROOTCOL/$local_rel"
       escaped="$(printf '%s' "$remote" | sed "s/'/'\\\\''/g")"
       if adb -s "$PHONE" exec-out su -c "cat '$escaped'" >"$local_file" 2>"$ROOTCOL/root-artifacts/root-$IDX.stderr.txt" && [ -s "$local_file" ]; then
         h="$(shasum -a 256 "$local_file" | awk '{print $1}')";printf 'ROOT_READ_ONLY_CODE\t%s\t%s\tPASS\t%s\n' "$remote" "$local_rel" "$h" >>"$ROOTCOL/root-pull-manifest.tsv"
       else
         rm -f "$local_file";printf 'ROOT_READ_ONLY_CODE\t%s\t%s\tFAIL\tNONE\n' "$remote" "$local_rel" >>"$ROOTCOL/root-pull-manifest.tsv"
       fi
     done <"$ROOTCOL/root-code-candidates.txt"
   else
     echo "UNAVAILABLE_OR_NOT_GRANTED" >"$ROOTCOL/root-status.txt"
   fi
 fi
fi

if [ "$ROOT_MODE" = "required" ] && [ "$(cat "$ROOTCOL/root-status.txt" 2>/dev/null)" != "AVAILABLE" ]; then
 echo "ERROR: root was required but read-only uid=0 probe did not succeed";exit 1
fi

PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" --repo "$REPO" --r3341-evidence "$R3341" --r33423-evidence "$R33423" --root-collection "$ROOTCOL" --output "$OUTPUT"
RC=$?
[ "$RC" -eq 0 ] || exit "$RC"
echo "TEST21_R3_3_4_2_4_RUN_RC=0"
echo "OUTPUT=$OUTPUT"
echo "ROOT_COMMAND_SCOPE=READ_ONLY"
echo "PAYLOAD_EXECUTION=NONE"
echo "DEVICE_MUTATION=NONE"
echo "HI_ROKID_FORCE_STOP=NONE"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "NETWORK_CAPTURE=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
