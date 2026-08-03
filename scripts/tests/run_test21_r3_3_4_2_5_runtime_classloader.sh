#!/usr/bin/env bash
REPO="";PHONE="";OUTPUT="";R33424="";INSTRUMENTATION_MODE="auto";FRIDA_SERVER_MODE="existing"
while [ "$#" -gt 0 ]; do
 case "$1" in
  --repo) REPO="$2";shift 2;; --phone) PHONE="$2";shift 2;; --r33424-evidence) R33424="$2";shift 2;; --output) OUTPUT="$2";shift 2;;
  --instrumentation-mode) INSTRUMENTATION_MODE="$2";shift 2;; --frida-server-mode) FRIDA_SERVER_MODE="$2";shift 2;; *) echo "ERROR: unknown argument $1";exit 2;; esac
done
[ -d "$REPO/.git" ] && [ -d "$R33424/private" ] && [ -n "$PHONE" ] && [ -n "$OUTPUT" ] || { echo "ERROR: invalid arguments";exit 2; }
case "$INSTRUMENTATION_MODE" in auto|required) ;; *) echo "ERROR: --instrumentation-mode auto|required";exit 2;; esac
case "$FRIDA_SERVER_MODE" in existing|start-if-present) ;; *) echo "ERROR: --frida-server-mode existing|start-if-present";exit 2;; esac
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_5_source_contract.py";COLLECT="$REPO/scripts/tests/collect_test21_r3_3_4_2_5_frida.py";AGENT="$REPO/scripts/tests/test21_r3_3_4_2_5_frida_agent.js";ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_5_runtime.py"
RT="$OUTPUT/private/runtime";ROOTCOL="$OUTPUT/private/root";mkdir -p "$RT/file-backed" "$ROOTCOL" "$OUTPUT/sanitized" || exit 1
STARTED_PID=""
cleanup(){ if [ -n "$STARTED_PID" ]; then adb -s "$PHONE" shell su -c "kill $STARTED_PID" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT INT TERM

echo "============================================================";echo "TEST 21 r3.3.4.2.5 — ROOT-ASSISTED RUNTIME CLASSLOADER";echo "============================================================"
echo "INSTRUMENTATION_MODE=$INSTRUMENTATION_MODE";echo "FRIDA_SERVER_MODE=$FRIDA_SERVER_MODE";echo "PAYLOAD_EXECUTION=NONE";echo "METHOD_REPLACEMENT=NONE";echo "BINDER_RETURN_MODIFICATION=NONE";echo "DEVICE_PERSISTENT_MUTATION=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "CXR_L_CONNECTION_ATTEMPT=NONE"
PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO" || exit 1
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb missing";exit 1; };adb -s "$PHONE" get-state >/dev/null 2>&1 || { echo "ERROR: device offline";exit 1; }
adb -s "$PHONE" shell su -c id >"$ROOTCOL/root-id.txt" 2>"$ROOTCOL/root-id.stderr.txt";ROOT_RC=$?
if [ "$ROOT_RC" -ne 0 ] || ! grep -q 'uid=0' "$ROOTCOL/root-id.txt"; then echo "ROOT_PROBE=UNAVAILABLE";exit 1; fi
echo "ROOT_PROBE=AVAILABLE"
PID="$(adb -s "$PHONE" shell pidof com.rokid.sprite.global.aiapp 2>/dev/null | tr -d '\r' | awk '{print $1}')"
if [ -z "$PID" ]; then echo "HI_ROKID_PROCESS_VISIBLE=NO";echo "ERROR: Hi Rokid must already be running; harness will not launch it";exit 1; fi
echo "HI_ROKID_PROCESS_VISIBLE=YES";echo "$PID" >"$ROOTCOL/process-id.txt"
adb -s "$PHONE" shell su -c "cat /proc/$PID/maps" >"$ROOTCOL/process-maps.txt" 2>"$ROOTCOL/process-maps.stderr.txt";MAP_RC=$?
if [ "$MAP_RC" -eq 0 ] && [ -s "$ROOTCOL/process-maps.txt" ]; then echo "ROOT_PROCESS_MAPS_ACCESS=READABLE"; else echo "ROOT_PROCESS_MAPS_ACCESS=UNAVAILABLE"; fi

FRIDA_HOST="NO";PYTHONDONTWRITEBYTECODE=1 python3 -c 'import frida' >/dev/null 2>&1 && FRIDA_HOST="YES";echo "FRIDA_HOST_MODULE=$FRIDA_HOST"
SERVER_PID="$(adb -s "$PHONE" shell su -c "pidof frida-server 2>/dev/null" 2>/dev/null | tr -d '\r' | awk '{print $1}')"
TRANSIENT="NO"
if [ -z "$SERVER_PID" ] && [ "$FRIDA_SERVER_MODE" = "start-if-present" ]; then
 FS_PATH="$(adb -s "$PHONE" shell su -c "find /data/local/tmp -maxdepth 1 -type f -name 'frida-server*' -print 2>/dev/null | head -1" 2>/dev/null | tr -d '\r')"
 if [ -n "$FS_PATH" ]; then
  ESC="$(printf '%s' "$FS_PATH" | sed "s/'/'\\\\''/g")";adb -s "$PHONE" shell su -c "'$ESC' >/dev/null 2>&1 &" >/dev/null 2>&1;sleep 2
  SERVER_PID="$(adb -s "$PHONE" shell su -c "pidof frida-server 2>/dev/null" 2>/dev/null | tr -d '\r' | awk '{print $1}')"
  if [ -n "$SERVER_PID" ]; then STARTED_PID="$SERVER_PID";TRANSIENT="YES"; fi
 fi
fi
echo "TRANSIENT_FRIDA_SERVER_STARTED=$TRANSIENT"
if [ -n "$SERVER_PID" ]; then echo "FRIDA_SERVER_REACHABILITY=CANDIDATE_RUNNING"; else echo "FRIDA_SERVER_REACHABILITY=NOT_RUNNING"; fi
FRIDA_RC=1
if [ "$FRIDA_HOST" = "YES" ] && [ -n "$SERVER_PID" ]; then
 PYTHONDONTWRITEBYTECODE=1 python3 "$COLLECT" --pid "$PID" --agent "$AGENT" --output "$RT";FRIDA_RC=$?
else
 echo "FRIDA_RUNTIME_SNAPSHOT=SKIPPED_PREREQUISITE_UNAVAILABLE"
fi
if [ "$INSTRUMENTATION_MODE" = "required" ] && [ "$FRIDA_RC" -ne 0 ]; then echo "ERROR: Frida runtime observation required but unavailable";exit 1; fi

# Pull only file-backed DexFile paths named by the private Frida snapshot; no arbitrary app data traversal.
if [ -s "$RT/frida-runtime-private.json" ]; then
 PYTHONDONTWRITEBYTECODE=1 python3 - "$RT/frida-runtime-private.json" "$RT/dex-paths.txt" <<'PY2'
import json,re,sys
j=json.load(open(sys.argv[1]));out=[]
for t in (j.get('targets') or {}).values():
 for e in ((t.get('loader') or {}).get('dex_elements') or []):
  for k in ('dex_name','dex_file','element'):
   v=e.get(k)
   if not isinstance(v,str):continue
   for x in re.findall(r'/[^\s\],;"\']+\.(?:apk|jar|dex)',v):
    if x not in out:out.append(x)
open(sys.argv[2],'w').write('\n'.join(out[:32])+('\n' if out else ''))
PY2
 IDX=0
 while IFS= read -r remote; do
  [ -n "$remote" ] || continue;IDX=$((IDX+1));ext="${remote##*.}";local="$RT/file-backed/file-$IDX.$ext";esc="$(printf '%s' "$remote" | sed "s/'/'\\\\''/g")"
  adb -s "$PHONE" exec-out su -c "cat '$esc'" >"$local" 2>"$RT/file-backed/file-$IDX.stderr.txt" || rm -f "$local"
 done <"$RT/dex-paths.txt"
fi
PYTHONDONTWRITEBYTECODE=1 python3 "$ANALYZE" --repo "$REPO" --runtime-dir "$RT" --root-collection "$ROOTCOL" --output "$OUTPUT";RC=$?
[ "$RC" -eq 0 ] || exit "$RC"
echo "TEST21_R3_3_4_2_5_RUN_RC=0";echo "OUTPUT=$OUTPUT";echo "ROOT_ASSIST=READ_ONLY";echo "FRIDA_OBSERVATION=NO_METHOD_REPLACEMENT";echo "PAYLOAD_EXECUTION=NONE";echo "DEVICE_PERSISTENT_MUTATION=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "CXR_L_CONNECTION_ATTEMPT=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
