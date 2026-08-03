#!/usr/bin/env bash
REPO="";PHONE="";R33424="";OUTPUT="";FRIDA_VENV="$HOME/venvs/frida"
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2";shift 2;;--phone) PHONE="$2";shift 2;;--r33424-evidence) R33424="$2";shift 2;;--output) OUTPUT="$2";shift 2;;--frida-venv) FRIDA_VENV="$2";shift 2;;*) echo "ERROR: unknown argument $1";exit 2;;esac;done
[ -d "$REPO/.git" ] || { echo "ERROR: invalid repo";exit 2; };[ -n "$PHONE" ] || { echo "ERROR: --phone required";exit 2; };[ -d "$R33424/private" ] || { echo "ERROR: r3.3.4.2.4 private evidence missing";exit 2; };[ -n "$OUTPUT" ] || { echo "ERROR: --output required";exit 2; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_2_5_1_source_contract.py";PREP="$REPO/scripts/tests/prepare_test21_r3_3_4_2_5_1_frida17_agent.py";COLLECT="$REPO/scripts/tests/collect_test21_r3_3_4_2_5_1_frida17.py";AGENT="$REPO/scripts/tests/test21_r3_3_4_2_5_1_frida17_agent.ts";ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_2_5_1_resume.py"
ROOTCOL="$OUTPUT/private/root-runtime";RT="$OUTPUT/private/frida-runtime";PROJECT="$OUTPUT/private/frida17-agent-project";BUNDLE="$PROJECT/agent.bundle.js";mkdir -p "$ROOTCOL" "$RT" "$PROJECT" || exit 1
STARTED_PID=""
cleanup(){ if [ -n "$STARTED_PID" ]; then adb -s "$PHONE" shell su -c "kill $STARTED_PID" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT INT TERM

echo "============================================================";echo "TEST 21 r3.3.4.2.5.1 — FRIDA 17 COMPILED-AGENT RESUME";echo "============================================================";echo "FRIDA_EXPECTED_VERSION=17.16.4";echo "FRIDA_JAVA_BRIDGE_SPEC=frida-java-bridge@7.0.4";echo "METHOD_REPLACEMENT=NONE";echo "BINDER_RETURN_MODIFICATION=NONE";echo "PAYLOAD_EXECUTION=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "CXR_L_CONNECTION_ATTEMPT=NONE"
PYTHONDONTWRITEBYTECODE=1 python3 "$CHECK" --repo "$REPO" || exit 1
[ -x "$FRIDA_VENV/bin/python3" ] || { echo "ERROR: Frida venv missing: $FRIDA_VENV";exit 1; }
PY="$FRIDA_VENV/bin/python3";HOST_VER="$($PY -c 'import frida;print(frida.__version__)' 2>/dev/null)";echo "FRIDA_HOST_VERSION=${HOST_VER:-UNRESOLVED}";[ "$HOST_VER" = "17.16.4" ] || { echo "FRIDA17_HOST_VERSION_GATE=FAIL";exit 1; };echo "FRIDA17_HOST_VERSION_GATE=PASS"
command -v adb >/dev/null 2>&1 || { echo "ERROR: adb missing";exit 1; };adb -s "$PHONE" get-state >/dev/null 2>&1 || { echo "ERROR: device offline";exit 1; }
ROOT_ID="$(adb -s "$PHONE" shell su -c id 2>/dev/null | tr -d '\r')";printf '%s\n' "$ROOT_ID" >"$ROOTCOL/root-id.txt";printf '%s' "$ROOT_ID" | grep -q 'uid=0' || { echo "ROOT_PROBE=UNAVAILABLE";exit 1; };echo "ROOT_PROBE=AVAILABLE"
SERVER_VER="$(adb -s "$PHONE" shell su -c '/data/local/tmp/frida-server --version 2>/dev/null' 2>/dev/null | tr -d '\r')";echo "FRIDA_SERVER_VERSION=${SERVER_VER:-UNRESOLVED}";[ "$SERVER_VER" = "17.16.4" ] || { echo "FRIDA17_SERVER_VERSION_GATE=FAIL";exit 1; };echo "FRIDA17_SERVER_VERSION_GATE=PASS"
PID="$(adb -s "$PHONE" shell pidof com.rokid.sprite.global.aiapp 2>/dev/null | tr -d '\r' | awk '{print $1}')";[ -n "$PID" ] || { echo "HI_ROKID_PROCESS_VISIBLE=NO";echo "ERROR: Hi Rokid must already be running; harness will not launch it";exit 1; };echo "HI_ROKID_PROCESS_VISIBLE=YES";printf '%s\n' "$PID" >"$ROOTCOL/process-id.txt"
adb -s "$PHONE" shell su -c "cat /proc/$PID/maps" >"$ROOTCOL/process-maps.txt" 2>"$ROOTCOL/process-maps.stderr.txt";MAP_RC=$?;if [ "$MAP_RC" -eq 0 ] && [ -s "$ROOTCOL/process-maps.txt" ];then echo "ROOT_PROCESS_MAPS_ACCESS=READABLE";else echo "ROOT_PROCESS_MAPS_ACCESS=UNAVAILABLE";fi

echo "=== FRIDA 17 JAVA-BRIDGE COMPILE QUALIFICATION ==="
PYTHONDONTWRITEBYTECODE=1 "$PY" "$PREP" --agent-ts "$AGENT" --project-root "$PROJECT" --bundle-out "$BUNDLE" --expected-frida 17.16.4 --bridge-spec frida-java-bridge@7.0.4;PREP_RC=$?;[ "$PREP_RC" -eq 0 ] || { echo "ERROR: compiled-agent qualification failed";exit 1; }
SERVER_PID="$(adb -s "$PHONE" shell su -c 'pidof frida-server 2>/dev/null' 2>/dev/null | tr -d '\r' | awk '{print $1}')";TRANSIENT="NO"
if [ -z "$SERVER_PID" ];then FS_PATH="$(adb -s "$PHONE" shell su -c "find /data/local/tmp -maxdepth 1 -type f -name 'frida-server*' -print 2>/dev/null | head -1" 2>/dev/null | tr -d '\r')";if [ -n "$FS_PATH" ];then ESC="$(printf '%s' "$FS_PATH" | sed "s/'/'\\\\''/g")";adb -s "$PHONE" shell su -c "'$ESC' >/dev/null 2>&1 &" >/dev/null 2>&1;sleep 2;SERVER_PID="$(adb -s "$PHONE" shell su -c 'pidof frida-server 2>/dev/null' 2>/dev/null | tr -d '\r' | awk '{print $1}')";if [ -n "$SERVER_PID" ];then STARTED_PID="$SERVER_PID";TRANSIENT="YES";fi;fi;fi
echo "TRANSIENT_FRIDA_SERVER_STARTED=$TRANSIENT";[ -n "$SERVER_PID" ] || { echo "FRIDA_SERVER_REACHABILITY=NOT_RUNNING";exit 1; };echo "FRIDA_SERVER_REACHABILITY=CANDIDATE_RUNNING"
PYTHONDONTWRITEBYTECODE=1 "$PY" "$COLLECT" --pid "$PID" --bundle "$BUNDLE" --output "$RT" --expected-frida 17.16.4;FRIDA_RC=$?;[ "$FRIDA_RC" -eq 0 ] || { echo "ERROR: repaired Frida runtime observation failed";exit 1; }
if [ -s "$RT/frida-runtime-private.json" ];then
 PYTHONDONTWRITEBYTECODE=1 "$PY" - "$RT/frida-runtime-private.json" "$RT/dex-paths.txt" <<'PY2'
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
 IDX=0;while IFS= read -r remote;do [ -n "$remote" ] || continue;IDX=$((IDX+1));ext="${remote##*.}";local="$RT/file-backed/file-$IDX.$ext";mkdir -p "$RT/file-backed";esc="$(printf '%s' "$remote" | sed "s/'/'\\\\''/g")";adb -s "$PHONE" exec-out su -c "cat '$esc'" >"$local" 2>"$RT/file-backed/file-$IDX.stderr.txt" || rm -f "$local";done <"$RT/dex-paths.txt"
fi
PYTHONDONTWRITEBYTECODE=1 "$PY" "$ANALYZE" --repo "$REPO" --runtime-dir "$RT" --root-collection "$ROOTCOL" --output "$OUTPUT" --compiler-project "$PROJECT";RC=$?;[ "$RC" -eq 0 ] || exit "$RC"
echo "TEST21_R3_3_4_2_5_1_RUN_RC=0";echo "OUTPUT=$OUTPUT";echo "ROOT_ASSIST=READ_ONLY";echo "FRIDA_INSTRUMENTATION=OBSERVATION_ONLY";echo "PAYLOAD_EXECUTION=NONE";echo "METHOD_REPLACEMENT=NONE";echo "BINDER_RETURN_MODIFICATION=NONE";echo "DEVICE_PERSISTENT_MUTATION=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "CXR_L_CONNECTION_ATTEMPT=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
