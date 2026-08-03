#!/usr/bin/env bash
REPO=""; PHONE=""; OUTPUT=""; PROFILE="AUTHORIZED_FOREGROUND_DELAY_30S"
HI_ROKID="com.rokid.sprite.global.aiapp"; CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification"; EXPECTED_CUSTOM_VERSION="1.0-test20-final"; SETTLE_SECONDS=30; OBSERVATION_SECONDS=30
if [ "${TEST21_R3_3_1_TEST_MODE:-0}" = "1" ]; then SETTLE_SECONDS=3; OBSERVATION_SECONDS=3; fi
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2";shift 2;;--phone) PHONE="$2";shift 2;;--output) OUTPUT="$2";shift 2;;--profile) PROFILE="$2";shift 2;;*)echo "ERROR: unknown argument $1";exit 2;;esac;done
[ "$PROFILE" = "AUTHORIZED_FOREGROUND_DELAY_30S" ] || { echo "ERROR: only AUTHORIZED_FOREGROUND_DELAY_30S is enabled for physical execution"; exit 2; }
[ -d "$REPO/.git" ] && [ -n "$PHONE" ] && [ -n "$OUTPUT" ] || { echo "ERROR: invalid arguments";exit 2; }
ADB="$(command -v adb 2>/dev/null)";[ -n "$ADB" ]||{ echo "ERROR: adb not found";exit 1; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_1_source_contract.py"; STATE="$REPO/scripts/tests/collect_test21_r3_3_1_state.py"; RESP="$REPO/scripts/tests/collect_test21_r3_3_1_respawn.py"; ANALYZER="$REPO/scripts/tests/analyze_test21_r3_3_1_deferred_binding.py"
mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized"||exit 1
TTY_IN=/dev/tty;TTY_OUT=/dev/tty;if [ "${TEST21_R3_3_1_TEST_MODE:-0}" = 1 ]||[ ! -r "$TTY_IN" ];then TTY_IN=/dev/stdin;TTY_OUT=/dev/stdout;fi
ACTIVE_USER="";HI_LAUNCHER="";CUSTOM_LAUNCHER="";RUN_ID="";REMOTE_EVENTS="";HI_FORCE_STOP_ISSUED=0;HI_RESTORED=0;P1="";P2=""
prompt(){ exp="$1";msg="$2";echo;printf '%s\n' "$msg" >"$TTY_OUT";printf '[TERMINAL ACTION ONLY] Type exactly %s and press Enter: ' "$exp" >"$TTY_OUT";IFS= read -r ans <"$TTY_IN";[ "$ans" = "$exp" ];}
resolve(){ "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$1" 2>/dev/null|tr -d '\r'|awk 'NF{l=$0}END{print l}';}
stopobs(){ for p in "$P1" "$P2";do [ -n "$p" ]||continue;kill "$p" >/dev/null 2>&1||true;wait "$p" 2>/dev/null||true;done;P1="";P2="";}
restore(){ [ "$HI_FORCE_STOP_ISSUED" -eq 1 ]&&[ "$HI_RESTORED" -eq 0 ]||return 0;"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" >>"$OUTPUT/raw/restoration-private.txt" 2>&1;rc=$?;[ "$rc" -eq 0 ]&&HI_RESTORED=1;return "$rc";}
cleanup(){ stopobs;restore >/dev/null 2>&1||true;}
trap cleanup EXIT;trap 'cleanup;trap - EXIT;exit 130' INT;trap 'cleanup;trap - EXIT;exit 143' TERM
resolve_events(){ if [ -n "$REMOTE_EVENTS" ]&&"$ADB" -s "$PHONE" shell "test -s '$REMOTE_EVENTS'" >/dev/null 2>&1;then printf '%s' "$REMOTE_EVENTS";return;fi;c="$($ADB -s "$PHONE" shell "find /sdcard/Android/data/$CUSTOM_PACKAGE/files -type f -name '*$RUN_ID*.jsonl' 2>/dev/null | head -n 1" 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";[ -n "$c" ]||return 1;REMOTE_EVENTS="$c";printf '%s' "$c";}
pull_events(){ t="$1";a="$(resolve_events)";[ -n "$a" ]||return 1;"$ADB" -s "$PHONE" pull "$a" "$t" >"$OUTPUT/raw/events-pull-private.txt" 2>&1;[ "$?" -eq 0 ]&&[ -s "$t" ];}
verify_events(){ python3 - "$1" <<'PYEV'
import json,re,sys
ev=[json.loads(x) for x in open(sys.argv[1]) if x.strip()]
def et(e):return str(e.get('event_type','')).strip()
def d(e):return e.get('details',{}) if isinstance(e.get('details',{}),dict) else {}
def b(x):return x is True or str(x).lower() in ('1','yes','true')
a=[e for e in ev if et(e)=='authorization_result']
if not a or not b(d(a[-1]).get('token_present')):raise SystemExit('ERROR: authorization token not proven')
if b(d(a[-1]).get('token_value_logged')):raise SystemExit('ERROR: token value logged')
for e in ev:
 n=et(e)
 if n in {'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}:raise SystemExit('ERROR: forbidden connection event '+n)
 if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',n):raise SystemExit('ERROR: forbidden media event '+n)
print('AUTHORIZED_NO_CONNECT_EVENT_GATE=PASS')
PYEV
}
echo "============================================================";echo "TEST 21 r3.3.1 — POST-AUTHORIZATION DELAY / FOREGROUND / DEFERRED-BINDING";echo "============================================================";echo "PROFILE=AUTHORIZED_FOREGROUND_DELAY_30S";echo "SETTLE_SECONDS=30";echo "CXR_L_CONNECTION_ATTEMPT=NONE";echo "SECONDARY_PACKAGE_FORCE_STOP=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
python3 "$CHECK" --repo "$REPO"||exit 1
"$ADB" -s "$PHONE" get-state >/dev/null 2>&1||{ echo "ERROR: adb unavailable";exit 1;};ACTIVE_USER="$($ADB -s "$PHONE" shell am get-current-user 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";CUSTOM_VERSION="$($ADB -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null|tr -d '\r'|awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2;exit}')";[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ]||{ echo "ERROR: installed custom version mismatch";exit 1;};HI_LAUNCHER="$(resolve "$HI_ROKID")";CUSTOM_LAUNCHER="$(resolve "$CUSTOM_PACKAGE")"
if ! prompt HI_ROKID_CONNECTED "[PHONE CHECK ONLY] Hi Rokid must be open and show the glasses connected normally.";then echo "ERROR: baseline not confirmed";exit 1;fi
RUN_ID="test21-r3-3-1-$(date -u +%Y%m%dT%H%M%SZ)";TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1||exit 1;"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" --es run_id "$RUN_ID" --es firmware_label "test21-r3-3-1-delay" --es operator_gate_token "$TOKEN" >"$OUTPUT/raw/custom-launch-private.txt" 2>&1||exit 1
echo;echo "=== AUTHORIZATION ===";echo "[PHONE ACTION] Tap ONLY '1. Authorize through Hi Rokid' once. Complete authorization, return to the custom app, and leave the custom app visible in the foreground. DO NOT tap any other control."
if ! prompt AUTHORIZED_FOREGROUND_DELAY_READY "[PHONE ACTION BEFORE TYPING] After authorization, return to the custom app. Leave it open in the foreground. DO NOT tap button 2 or capture. Then type the confirmation.";then echo "ERROR: profile not confirmed";exit 1;fi
pull_events "$OUTPUT/raw/pre-force-events-private.jsonl"||{ echo "ERROR: event stream unavailable";exit 1;};verify_events "$OUTPUT/raw/pre-force-events-private.jsonl"||exit 1
python3 "$STATE" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --output "$OUTPUT/raw" --label settle-00||exit 1;grep -q '^CUSTOM_FOREGROUND_PROVEN=YES$' "$OUTPUT/raw/settle-00-state.txt"||{ echo "ERROR: custom app foreground not proven at settle start";exit 1;}
echo;echo "=== 30-SECOND POST-AUTHORIZATION FOREGROUND SETTLE ===";echo "[PHONE ACTION] NONE FOR 30 SECONDS. Keep the custom app visible. Do not tap, swipe, lock the phone, connect, or reopen Hi Rokid."
if [ "$SETTLE_SECONDS" -eq 30 ];then sleep 15;else sleep 1;fi;python3 "$STATE" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --output "$OUTPUT/raw" --label settle-15||exit 1
if [ "$SETTLE_SECONDS" -eq 30 ];then sleep 15;else sleep 2;fi;python3 "$STATE" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --output "$OUTPUT/raw" --label settle-30||exit 1
grep -q '^CUSTOM_FOREGROUND_PROVEN=YES$' "$OUTPUT/raw/settle-15-state.txt"&&grep -q '^CUSTOM_FOREGROUND_PROVEN=YES$' "$OUTPUT/raw/settle-30-state.txt"||{ echo "ERROR: custom app did not remain foreground for controlled settle";exit 1;}
pull_events "$OUTPUT/raw/pre-force-events-private.jsonl"||exit 1;verify_events "$OUTPUT/raw/pre-force-events-private.jsonl"||exit 1
"$ADB" -s "$PHONE" logcat -T 1 -b events -v epoch >"$OUTPUT/raw/activity-events-private.txt" 2>&1 & P1=$!;"$ADB" -s "$PHONE" logcat -T 1 -v epoch ActivityManager:I ActivityTaskManager:I '*:S' >"$OUTPUT/raw/activity-manager-private.txt" 2>&1 & P2=$!
echo;echo "=== CONTROLLED HI ROKID FORCE-STOP ===";echo "[PHONE ACTION] NONE. Keep the phone untouched.";"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" >"$OUTPUT/raw/hi-force-stop-private.txt" 2>&1;rc=$?;[ "$rc" -eq 0 ]||exit 1;HI_FORCE_STOP_ISSUED=1
abs=NO;i=1;while [ "$i" -le 10 ];do p="$($ADB -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null|tr -d '\r')";[ -z "$p" ]&&{ abs=YES;break;};sleep 1;i=$((i+1));done
"$ADB" -s "$PHONE" shell ps -A -o USER,PID,PPID,NAME,ARGS >"$OUTPUT/raw/ps-immediate-post-force-private.txt" 2>&1||"$ADB" -s "$PHONE" shell ps -A >"$OUTPUT/raw/ps-immediate-post-force-private.txt" 2>&1;same="$(grep -F "$HI_ROKID" "$OUTPUT/raw/ps-immediate-post-force-private.txt" 2>/dev/null|wc -l|tr -d ' ')";printf 'HI_PROCESS_ABSENT_OBSERVED=%s\nSAME_PACKAGE_PROCESS_COUNT_POST_FORCE=%s\n' "$abs" "$same" >"$OUTPUT/raw/force-stop-observation.txt";[ "$abs" = YES ]&&[ "$same" -eq 0 ]||{ echo "ERROR: full package stop not proven";exit 1;}
echo;echo "=== 30-SECOND HANDS-OFF POST-FORCE RESPAWN WINDOW ===";echo "[PHONE ACTION] NONE FOR 30 SECONDS.";python3 "$RESP" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --output "$OUTPUT/raw" --duration-seconds "$OBSERVATION_SECONDS"||exit 1;stopobs
pull_events "$OUTPUT/raw/final-events-private.jsonl"||exit 1;verify_events "$OUTPUT/raw/final-events-private.jsonl"||exit 1
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >"$OUTPUT/raw/custom-cleanup-private.txt" 2>&1||true
restore||{ echo "ERROR: Hi Rokid restoration launch failed";exit 1;}
if ! prompt HI_ROKID_RECOVERY_PASS "[PHONE CHECK ONLY] Wait until Hi Rokid is visibly open and the glasses are normally connected again.";then echo "ERROR: recovery not confirmed";exit 1;fi
printf 'OPERATOR_HI_ROKID_RECOVERY=PASS\n' >"$OUTPUT/raw/state-restored.txt"
python3 "$ANALYZER" --repo "$REPO" --evidence "$OUTPUT"||exit 1
trap - EXIT;echo "TEST21_R3_3_1_RUN=PASS";echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
