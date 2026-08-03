#!/usr/bin/env bash
REPO="";PHONE="";OUTPUT="";PROFILE="CXRLINKSERVICE_BINDING_CONTRACT"
HI_ROKID="com.rokid.sprite.global.aiapp";CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification";EXPECTED_CUSTOM_VERSION="1.0-test20-final"
DURATION=16;POLL=.075;SNAP=.35
if [ "${TEST21_R3_3_4_1_TEST_MODE:-0}" = 1 ];then DURATION=3;POLL=.05;SNAP=.20;fi
while [ "$#" -gt 0 ];do case "$1" in --repo)REPO="$2";shift 2;;--phone)PHONE="$2";shift 2;;--output)OUTPUT="$2";shift 2;;--profile)PROFILE="$2";shift 2;;*)echo "ERROR: unknown argument $1";exit 2;;esac;done
[ "$PROFILE" = CXRLINKSERVICE_BINDING_CONTRACT ]||{ echo "ERROR: unsupported profile";exit 2; }
[ -d "$REPO/.git" ]&&[ -n "$PHONE" ]&&[ -n "$OUTPUT" ]||{ echo "ERROR: invalid arguments";exit 2; }
ADB="$(command -v adb 2>/dev/null)";[ -n "$ADB" ]||{ echo "ERROR: adb not found";exit 1; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_4_1_source_contract.py";COLLECT="$REPO/scripts/tests/collect_test21_r3_3_4_1_binding_contract.py";STATIC="$REPO/scripts/tests/inspect_test21_r3_3_4_1_apk_strings.py";ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_4_1_binding_contract.py"
mkdir -p "$OUTPUT/raw/apks" "$OUTPUT/sanitized"||exit 1
TTY_IN=/dev/tty;TTY_OUT=/dev/tty;if [ "${TEST21_R3_3_4_1_TEST_MODE:-0}" = 1 ]||[ ! -r "$TTY_IN" ];then TTY_IN=/dev/stdin;TTY_OUT=/dev/stdout;fi
ACTIVE_USER="";HI_LAUNCHER="";CUSTOM_LAUNCHER="";RUN_ID="";REMOTE_EVENTS="";HI_FORCE_STOP_ISSUED=0;HI_RESTORED=0;COLLECTOR_PID="";P1="";P2=""
prompt(){ exp="$1";msg="$2";echo;printf '%s\n' "$msg" >"$TTY_OUT";printf '[TERMINAL ACTION ONLY] Type exactly %s and press Enter: ' "$exp" >"$TTY_OUT";IFS= read -r ans <"$TTY_IN";[ "$ans" = "$exp" ];}
pause(){ msg="$1";echo;printf '%s\n' "$msg" >"$TTY_OUT";printf '[TERMINAL ACTION ONLY] Press Enter only after completing the phone action: ' >"$TTY_OUT";IFS= read -r _ <"$TTY_IN";}
resolve(){ "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$1" 2>/dev/null|tr -d '\r'|awk 'NF{l=$0}END{print l}';}
stopobs(){ for p in "$COLLECTOR_PID" "$P1" "$P2";do [ -n "$p" ]||continue;kill "$p" >/dev/null 2>&1||true;wait "$p" >/dev/null 2>&1||true;done;COLLECTOR_PID="";P1="";P2="";}
restore(){ [ "$HI_FORCE_STOP_ISSUED" -eq 1 ]&&[ "$HI_RESTORED" -eq 0 ]||return 0;"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" >>"$OUTPUT/raw/restoration-private.txt" 2>&1;rc=$?;[ "$rc" -eq 0 ]&&HI_RESTORED=1;return "$rc";}
cleanup(){ stopobs;restore >/dev/null 2>&1||true;}
trap cleanup EXIT;trap 'cleanup;trap - EXIT;exit 130' INT;trap 'cleanup;trap - EXIT;exit 143' TERM
resolve_events(){ if [ -n "$REMOTE_EVENTS" ]&&"$ADB" -s "$PHONE" shell "test -s '$REMOTE_EVENTS'" >/dev/null 2>&1;then printf '%s' "$REMOTE_EVENTS";return;fi;c="$("$ADB" -s "$PHONE" shell "find /sdcard/Android/data/$CUSTOM_PACKAGE/files -type f -name '*$RUN_ID*.jsonl' 2>/dev/null | head -n 1" 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";[ -n "$c" ]||return 1;REMOTE_EVENTS="$c";printf '%s' "$c";}
pull_events(){ a="$(resolve_events)";[ -n "$a" ]||return 1;"$ADB" -s "$PHONE" pull "$a" "$1" >"$OUTPUT/raw/events-pull-private.txt" 2>&1;[ "$?" -eq 0 ]&&[ -s "$1" ];}
verify_preforce(){ python3 - "$1" <<'PYV'
import json,re,sys
ev=[json.loads(x) for x in open(sys.argv[1]) if x.strip()]
def b(v):return v is True or str(v).lower() in ('1','true','yes')
a=[e for e in ev if e.get('event_type')=='authorization_result']
if not a or not b((a[-1].get('details') or {}).get('token_present')):raise SystemExit('ERROR: authorization token not proven')
for e in ev:
 n=str(e.get('event_type',''))
 if n in {'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}:raise SystemExit('ERROR: connection already started')
 if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',n):raise SystemExit('ERROR: media event')
print('PREFORCE_AUTHORIZED_NO_CONNECT_GATE=PASS')
PYV
}
logmark(){ "$ADB" -s "$PHONE" shell log -t Test21R3341 "$RUN_ID|$1" >/dev/null 2>&1||true;}
snapshot(){ stem="$1";"$ADB" -s "$PHONE" shell dumpsys activity services >"$OUTPUT/raw/$stem-activity-services-global-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys activity services "$HI_ROKID" >"$OUTPUT/raw/$stem-hi-services-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys activity service "$HI_ROKID/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService" >"$OUTPUT/raw/$stem-cxrlinkservice-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys activity providers "$HI_ROKID" >"$OUTPUT/raw/$stem-hi-providers-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys activity processes >"$OUTPUT/raw/$stem-activity-processes-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys package "$HI_ROKID" >"$OUTPUT/raw/$stem-hi-package-private.txt" 2>&1;"$ADB" -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" >"$OUTPUT/raw/$stem-custom-package-private.txt" 2>&1;}
pull_apks(){ pkg="$1";prefix="$2";paths="$("$ADB" -s "$PHONE" shell pm path "$pkg" 2>/dev/null|tr -d '\r'|sed -n 's/^package://p')";[ -n "$paths" ]||return 1;i=0;ok=0;printf '%s\n' "$paths" >"$OUTPUT/raw/$prefix-apk-paths-private.txt";printf '%s\n' "$paths"|while IFS= read -r remote;do [ -n "$remote" ]||continue;i=$((i+1));name="$prefix-$i-$(basename "$remote")";"$ADB" -s "$PHONE" pull "$remote" "$OUTPUT/raw/apks/$name" >/dev/null 2>&1||exit 9;done;return $?;}

echo "============================================================";echo "TEST 21 r3.3.4.1 — CXRLINKSERVICE BINDING CONTRACT";echo "============================================================";echo "PROFILE=$PROFILE";echo "PCAPDROID_OPERATION=NONE";echo "NETWORK_CAPTURE=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
python3 "$CHECK" --repo "$REPO"||exit 1
"$ADB" -s "$PHONE" get-state >/dev/null 2>&1||{ echo "ERROR: adb unavailable";exit 1; };ACTIVE_USER="$("$ADB" -s "$PHONE" shell am get-current-user 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";CUSTOM_VERSION="$("$ADB" -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null|tr -d '\r'|awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2;exit}')";[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ]||{ echo "ERROR: custom version mismatch";exit 1; }
for p in "$HI_ROKID" "$CUSTOM_PACKAGE";do "$ADB" -s "$PHONE" shell pm path "$p" >/dev/null 2>&1||{ echo "ERROR: package missing $p";exit 1; };done
HI_LAUNCHER="$(resolve "$HI_ROKID")";CUSTOM_LAUNCHER="$(resolve "$CUSTOM_PACKAGE")";case "$HI_LAUNCHER" in "$HI_ROKID"/*);;*)echo "ERROR: Hi Rokid launcher unresolved";exit 1;;esac;case "$CUSTOM_LAUNCHER" in "$CUSTOM_PACKAGE"/*);;*)echo "ERROR: custom launcher unresolved";exit 1;;esac
if ! prompt HI_ROKID_CONNECTED "[PHONE CHECK ONLY] Confirm Hi Rokid is open and the glasses are normally connected. No camera, Assistant, translation, recording, or media operation.";then echo "ERROR: baseline not confirmed";exit 1;fi
snapshot baseline
# APK pulls are read-only and remain private. Static string census is supplementary, not a runtime proof gate.
if pull_apks "$HI_ROKID" hi && pull_apks "$CUSTOM_PACKAGE" custom;then python3 "$STATIC" --apk-dir "$OUTPUT/raw/apks" --output "$OUTPUT/raw/apk-string-census-private.json" >"$OUTPUT/raw/apk-string-census-console-private.txt" 2>&1||true;else echo "APK_STATIC_PULL=UNAVAILABLE" >"$OUTPUT/raw/apk-string-census-console-private.txt";fi
RUN_ID="test21-r3-3-4-1-$(date -u +%Y%m%dT%H%M%SZ)";TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1;"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" --es run_id "$RUN_ID" --es firmware_label test21-r3-3-4-1-binding-contract --es operator_gate_token "$TOKEN" >"$OUTPUT/raw/custom-launch-private.txt" 2>&1||exit 1
pause "[PHONE ACTION] Tap ONLY '1. Authorize through Hi Rokid' once, complete authorization, return to the custom app, and wait until button 2 is enabled. DO NOT tap button 2 yet."
pull_events "$OUTPUT/raw/pre-force-events-private.jsonl"||{ echo "ERROR: event stream unavailable";exit 1; };verify_preforce "$OUTPUT/raw/pre-force-events-private.jsonl"||exit 1
"$ADB" -s "$PHONE" logcat -T 1 -b events -v epoch >"$OUTPUT/raw/activity-events-private.txt" 2>&1 & P1=$!;"$ADB" -s "$PHONE" logcat -T 1 -b system -b main -v epoch ActivityManager:V ActivityTaskManager:V ContentProviderHelper:V PackageManager:V Test21R3341:I '*:S' >"$OUTPUT/raw/activity-manager-private.txt" 2>&1 & P2=$!
logmark BEFORE_HI_FORCE_STOP;"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" >"$OUTPUT/raw/hi-force-stop-private.txt" 2>&1||{ echo "ERROR: Hi Rokid force-stop failed";exit 1; };HI_FORCE_STOP_ISSUED=1;logmark AFTER_HI_FORCE_STOP
ABSENT=NO;i=1;while [ "$i" -le 10 ];do p="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null|tr -d '\r')";if [ -z "$p" ];then ABSENT=YES;break;fi;sleep 1;i=$((i+1));done;[ "$ABSENT" = YES ]||{ echo "ERROR: Hi Rokid absence not proven";exit 1; };sleep 3;[ -z "$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null|tr -d '\r')" ]||{ echo "ERROR: Hi Rokid respawned before connection gate";exit 1; };snapshot pre-connect
REMOTE_EVENTS="$(resolve_events)"||{ echo "ERROR: live event path unresolved";exit 1; }
if ! prompt READY_FOR_R3_3_4_1_CONNECTION "[TERMINAL ACTION ONLY] Keep the custom app visible. The host will start binding/service observers. Do NOT tap button 2 until the NOW instruction.";then echo "ERROR: readiness not confirmed";exit 1;fi
READY_FILE="$OUTPUT/raw/collector-ready.txt";rm -f "$READY_FILE";python3 "$COLLECT" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --remote-events "$REMOTE_EVENTS" --output "$OUTPUT/raw" --duration-seconds "$DURATION" --poll-seconds "$POLL" --snapshot-seconds "$SNAP" --ready-file "$READY_FILE" >"$OUTPUT/raw/collector-console-private.txt" 2>&1 & COLLECTOR_PID=$!;j=1;while [ "$j" -le 60 ]&&[ ! -s "$READY_FILE" ];do sleep .1;j=$((j+1));done;[ -s "$READY_FILE" ]||{ echo "ERROR: collector readiness timeout";exit 1; };grep -q '^HI_PROCESS_VISIBLE=NO$' "$READY_FILE"||{ echo "ERROR: collector started with Hi Rokid visible";exit 1; };echo "COLLECTOR_READY_PRECONNECTION=PASS";logmark BUTTON2_NOW_PROMPT
pause "NOW perform exactly ONE phone action: tap '2. Start one photo connection' ONCE. Immediately return to this terminal and press Enter. DO NOT tap Capture."
logmark BUTTON2_OPERATOR_DONE;wait "$COLLECTOR_PID";CRC=$?;COLLECTOR_PID="";cat "$OUTPUT/raw/collector-console-private.txt";[ "$CRC" -eq 0 ]||{ echo "ERROR: collector failed";exit 1; }
pull_events "$OUTPUT/raw/final-events-private.jsonl"||{ echo "ERROR: final event pull failed";exit 1; };snapshot post-observation
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >"$OUTPUT/raw/custom-force-stop-private.txt" 2>&1;stopobs;restore;RRC=$?;sleep 4
if [ "$RRC" -eq 0 ]&&prompt HI_ROKID_RECOVERY_PASS "[PHONE CHECK ONLY] Confirm Hi Rokid is open again and the glasses are back to normal connected/usable state.";then HI_RESTORED=1;RECOVERY=PASS;else RECOVERY=FAIL;fi
printf 'OPERATOR_HI_ROKID_RECOVERY=%s\n' "$RECOVERY" >"$OUTPUT/raw/state-restored.txt"
python3 "$ANALYZE" --evidence "$OUTPUT";ARC=$?;[ "$ARC" -eq 0 ]||exit "$ARC"
trap - EXIT INT TERM
echo "TEST21_R3_3_4_1_RUN_RC=0";echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT";echo "HI_ROKID_RESTORATION=$RECOVERY";echo "APK_PULL=PRIVATE_ONLY";echo "PCAPDROID_OPERATION=NONE";echo "NETWORK_CAPTURE=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
