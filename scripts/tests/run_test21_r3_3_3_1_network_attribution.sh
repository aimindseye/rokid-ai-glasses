#!/usr/bin/env bash
REPO="";PHONE="";OUTPUT="";PROFILE="PCAPDROID_DUAL_APP_ATTRIBUTION_AUTHORIZED_NO_CONNECT"
HI_ROKID="com.rokid.sprite.global.aiapp";CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification";PCAPDROID_PACKAGE="com.emanuelef.remote_capture";PCAPDROID_MITM_PACKAGE="com.pcapdroid.mitm";EXPECTED_CUSTOM_VERSION="1.0-test20-final"
BASELINE_SECONDS=15;CUSTOM_IDLE_SECONDS=10;AUTHORIZED_SETTLE_SECONDS=20
if [ "${TEST21_R3_3_3_1_TEST_MODE:-0}" = 1 ];then BASELINE_SECONDS=1;CUSTOM_IDLE_SECONDS=1;AUTHORIZED_SETTLE_SECONDS=1;fi
remote_quote(){ value="$1";printf "'%s'" "$(printf '%s' "$value" | sed "s/'/'\\\\''/g")"; }
adb_shell_argv(){ remote_cmd="";for remote_arg in "$@";do remote_q="$(remote_quote "$remote_arg")";if [ -n "$remote_cmd" ];then remote_cmd="$remote_cmd $remote_q";else remote_cmd="$remote_q";fi;done;printf '%s\n' "$remote_cmd" | "$ADB" -s "$PHONE" shell sh; }
pcap_ctrl(){ adb_shell_argv am start -W "$@" -n "$PCAPDROID_PACKAGE/.activities.CaptureCtrl"; }
while [ "$#" -gt 0 ];do case "$1" in --repo)REPO="$2";shift 2;;--phone)PHONE="$2";shift 2;;--output)OUTPUT="$2";shift 2;;--profile)PROFILE="$2";shift 2;;*)echo "ERROR: unknown argument $1";exit 2;;esac;done
[ "$PROFILE" = "PCAPDROID_DUAL_APP_ATTRIBUTION_AUTHORIZED_NO_CONNECT" ]||{ echo "ERROR: unsupported profile";exit 2; }
[ -d "$REPO/.git" ]&&[ -n "$PHONE" ]&&[ -n "$OUTPUT" ]||{ echo "ERROR: invalid arguments";exit 2; }
ADB="$(command -v adb 2>/dev/null)";[ -n "$ADB" ]||{ echo "ERROR: adb not found";exit 1; }
CHECK="$REPO/scripts/tests/check_test21_r3_3_3_1_source_contract.py";PARSE="$REPO/scripts/tests/parse_test21_r3_3_3_1_pcap.py";ANALYZE="$REPO/scripts/tests/analyze_test21_r3_3_3_1_attribution.py"
mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized"||exit 1
TTY_IN=/dev/tty;TTY_OUT=/dev/tty;if [ "${TEST21_R3_3_3_1_TEST_MODE:-0}" = 1 ]||[ ! -r "$TTY_IN" ];then TTY_IN=/dev/stdin;TTY_OUT=/dev/stdout;fi
ACTIVE_USER="";CUSTOM_LAUNCHER="";RUN_ID="";REMOTE_EVENTS="";PCAP_CAPTURE_STARTED=0;PCAP_CAPTURE_STOPPED=0;PCAPDROID_API_KEY_LOCAL="${PCAPDROID_API_KEY:-}"
mark(){ python3 - "$OUTPUT/raw/host-timeline-private.jsonl" "$1" <<'PYM'
import json,sys,time
with open(sys.argv[1],'a') as f:f.write(json.dumps({'kind':'host_marker','name':sys.argv[2],'host_epoch_ms':time.time_ns()//1_000_000},sort_keys=True)+'\n')
PYM
}
prompt(){ exp="$1";msg="$2";echo;printf '%s\n' "$msg" >"$TTY_OUT";printf '[TERMINAL ACTION ONLY] Type exactly %s and press Enter: ' "$exp" >"$TTY_OUT";IFS= read -r ans <"$TTY_IN";[ "$ans" = "$exp" ]; }
pause(){ msg="$1";echo;printf '%s\n' "$msg" >"$TTY_OUT";printf '[TERMINAL ACTION ONLY] Press Enter only after completing the phone action: ' >"$TTY_OUT";IFS= read -r _ <"$TTY_IN"; }
resolve(){ "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$1" 2>/dev/null|tr -d '\r'|awk 'NF{l=$0}END{print l}'; }
stop_pcap(){ [ "$PCAP_CAPTURE_STARTED" -eq 1 ]&&[ "$PCAP_CAPTURE_STOPPED" -eq 0 ]||return 0;pcap_ctrl -e action stop -e api_key "$PCAPDROID_API_KEY_LOCAL" >"$OUTPUT/raw/pcapdroid-stop-private.txt" 2>&1;rc=$?;PCAP_CAPTURE_STOPPED=1;mark pcapdroid_capture_stop;return "$rc"; }
cleanup(){ stop_pcap >/dev/null 2>&1||true;"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1||true;unset PCAPDROID_API_KEY_LOCAL; }
trap cleanup EXIT;trap 'cleanup;trap - EXIT;exit 130' INT;trap 'cleanup;trap - EXIT;exit 143' TERM
resolve_events(){ if [ -n "$REMOTE_EVENTS" ]&&"$ADB" -s "$PHONE" shell "test -s '$REMOTE_EVENTS'" >/dev/null 2>&1;then printf '%s' "$REMOTE_EVENTS";return;fi;c="$($ADB -s "$PHONE" shell "find /sdcard/Android/data/$CUSTOM_PACKAGE/files -type f -name '*$RUN_ID*.jsonl' 2>/dev/null | head -n 1" 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";[ -n "$c" ]||return 1;REMOTE_EVENTS="$c";printf '%s' "$c"; }
pull_events(){ a="$(resolve_events)";[ -n "$a" ]||return 1;"$ADB" -s "$PHONE" pull "$a" "$1" >"$OUTPUT/raw/events-pull-private.txt" 2>&1;[ "$?" -eq 0 ]&&[ -s "$1" ]; }
verify_no_connect(){ python3 - "$1" "$2" <<'PYV'
import json,re,sys
p=sys.argv[1];need_auth=sys.argv[2]=='YES';ev=[]
for x in open(p,errors='replace'):
 try:ev.append(json.loads(x))
 except:pass
def et(e):return str(e.get('event_type','')).strip()
def d(e):return e.get('details',{}) if isinstance(e.get('details',{}),dict) else {}
def b(x):return x is True or str(x).lower() in ('1','true','yes')
if need_auth:
 a=[e for e in ev if et(e)=='authorization_result']
 if not a or not b(d(a[-1]).get('token_present')):raise SystemExit('ERROR: authorization token not proven')
 if b(d(a[-1]).get('token_value_logged')):raise SystemExit('ERROR: token value logged')
for e in ev:
 n=et(e)
 if n in {'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}:raise SystemExit('ERROR: forbidden connection event '+n)
 if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',n):raise SystemExit('ERROR: media event '+n)
print('AUTHORIZED_NO_CONNECT_EVENT_GATE=PASS' if need_auth else 'CUSTOM_IDLE_NO_CONNECT_EVENT_GATE=PASS')
PYV
}
uid_of(){ "$ADB" -s "$PHONE" shell dumpsys package "$1" 2>/dev/null|tr -d '\r'|awk -F= '/^[[:space:]]*userId=/{gsub(/[[:space:]]/,"",$2);print $2;exit}'; }
find_remote(){ name="$1";"$ADB" -s "$PHONE" shell "find /sdcard/Download /sdcard/Downloads /storage/emulated/0/Download /storage/emulated/0/Downloads -type f -name '$name' 2>/dev/null | head -n 1" 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}'; }
echo "============================================================";echo "TEST 21 r3.3.3.1 — PCAPDROID DUAL-APP ATTRIBUTION";echo "============================================================";echo "PROFILE=PCAPDROID_DUAL_APP_ATTRIBUTION_AUTHORIZED_NO_CONNECT";echo "CXR_L_CONNECTION_ATTEMPT=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE"
python3 "$CHECK" --repo "$REPO"||exit 1
"$ADB" -s "$PHONE" get-state >/dev/null 2>&1||{ echo "ERROR: adb unavailable";exit 1; };ACTIVE_USER="$($ADB -s "$PHONE" shell am get-current-user 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')";CUSTOM_VERSION="$($ADB -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null|tr -d '\r'|awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2;exit}')";[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ]||{ echo "ERROR: custom version mismatch";exit 1; }
for p in "$HI_ROKID" "$CUSTOM_PACKAGE" "$PCAPDROID_PACKAGE" "$PCAPDROID_MITM_PACKAGE";do "$ADB" -s "$PHONE" shell pm path "$p" >/dev/null 2>&1||{ echo "ERROR: required package missing: $p";exit 1; };done
PCAP_VERSION_CODE="$($ADB -s "$PHONE" shell dumpsys package "$PCAPDROID_PACKAGE" 2>/dev/null|tr -d '\r'|awk -F= '/versionCode=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);split($2,a," ");print a[1];exit}')";case "$PCAP_VERSION_CODE" in ''|*[!0-9]*)echo "ERROR: PCAPdroid versionCode unresolved";exit 1;;esac;[ "$PCAP_VERSION_CODE" -ge 89 ]||{ echo "ERROR: PCAPdroid versionCode >=89 required";exit 1; };CUSTOM_LAUNCHER="$(resolve "$CUSTOM_PACKAGE")";case "$CUSTOM_LAUNCHER" in "$CUSTOM_PACKAGE"/*);;*)echo "ERROR: custom launcher unresolved";exit 1;;esac
if ! prompt PCAPDROID_DUAL_APP_CONFIG_CONFIRMED "[PHONE CHECK ONLY] Confirm PCAPdroid Target Apps AND TLS Decryption both include Hi Rokid and org.aimindseye.rokid.cxrphotoqualification. Hi Rokid must show the glasses connected normally. PCAPdroid must not already be capturing.";then echo "ERROR: dual-app configuration not confirmed";exit 1;fi
if [ -z "$PCAPDROID_API_KEY_LOCAL" ];then printf '\n[TERMINAL SECRET INPUT] Paste the PCAPdroid API key. It will not be echoed or written to evidence: ' >"$TTY_OUT";stty -echo <"$TTY_IN" 2>/dev/null||true;IFS= read -r PCAPDROID_API_KEY_LOCAL <"$TTY_IN";stty echo <"$TTY_IN" 2>/dev/null||true;printf '\n' >"$TTY_OUT";fi;[ -n "$PCAPDROID_API_KEY_LOCAL" ]||{ echo "ERROR: PCAPdroid API key required";exit 1; }
RUN_ID="test21-r3-3-3-1-$(date -u +%Y%m%dT%H%M%SZ)";PCAP_NAME="$RUN_ID-private.pcap";KEYLOG_NAME="$RUN_ID-private.sslkeylog";RULES='[{"type":"APP","value":"com.rokid.sprite.global.aiapp"},{"type":"APP","value":"org.aimindseye.rokid.cxrphotoqualification"}]'
HI_UID="$(uid_of "$HI_ROKID")";CUSTOM_UID="$(uid_of "$CUSTOM_PACKAGE")";python3 - "$OUTPUT/raw/uid-map-private.json" "$HI_UID" "$CUSTOM_UID" <<'PYU'
import json,sys
json.dump({str(sys.argv[2]):'com.rokid.sprite.global.aiapp',str(sys.argv[3]):'org.aimindseye.rokid.cxrphotoqualification'},open(sys.argv[1],'w'),indent=2,sort_keys=True)
PYU
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1;mark custom_force_stopped_for_baseline
pcap_ctrl -e action start -e api_key "$PCAPDROID_API_KEY_LOCAL" -e pcap_dump_mode pcap_file -e pcap_name "$PCAP_NAME" -e app_filter "$HI_ROKID,$CUSTOM_PACKAGE" -e tls_decryption true -e block_quic to_decrypt -e dump_extensions true -e full_payload true -e sslkeylog_name "$KEYLOG_NAME" -e decryption_rules "$RULES" >"$OUTPUT/raw/pcapdroid-start-private.txt" 2>&1;PCAP_START_RC=$?
if [ "$PCAP_START_RC" -ne 0 ]||grep -qiE 'unable to resolve Intent|Error: Activity not started|Error type [0-9]+' "$OUTPUT/raw/pcapdroid-start-private.txt";then echo "ERROR: PCAPdroid API start failed";sed -E -e 's/(api[_-]?key[=: ]+)[^ ,}"]+/\1<REDACTED>/Ig' -e 's/([A-Fa-f0-9]{48,})/<LONG_HEX_REDACTED>/g' "$OUTPUT/raw/pcapdroid-start-private.txt" 2>/dev/null||true;exit 1;fi
PCAP_CAPTURE_STARTED=1;mark pcapdroid_capture_start;sleep "$BASELINE_SECONDS";mark baseline_end
if ! prompt PCAPDROID_CAPTURE_STABLE "[PHONE CHECK ONLY] Confirm PCAPdroid is actively capturing with TLS decryption and Hi Rokid/glasses remain normally connected.";then echo "ERROR: capture baseline not confirmed";exit 1;fi
TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')";"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" --es run_id "$RUN_ID" --es firmware_label "test21-r3-3-3-1-attribution" --es operator_gate_token "$TOKEN" >"$OUTPUT/raw/custom-launch-private.txt" 2>&1||exit 1;mark custom_launch;sleep "$CUSTOM_IDLE_SECONDS";mark custom_idle_end
REMOTE_EVENTS="$(resolve_events)"||{ echo "ERROR: custom event path unresolved";exit 1; };pull_events "$OUTPUT/raw/custom-idle-events-private.jsonl"||{ echo "ERROR: custom idle event pull failed";exit 1; };verify_no_connect "$OUTPUT/raw/custom-idle-events-private.jsonl" NO||exit 1
printf '\n=== AUTHORIZATION-ONLY NETWORK BASELINE ===\n' >"$TTY_OUT";printf "[PHONE ACTION] Tap ONLY '1. Authorize through Hi Rokid' once, complete authorization, return to the custom app, and DO NOT tap button 2.\n" >"$TTY_OUT";pause "When authorization is complete and you are back in the custom app, press Enter.";mark authorization_complete
pull_events "$OUTPUT/raw/post-auth-events-private.jsonl"||{ echo "ERROR: post-auth event pull failed";exit 1; };verify_no_connect "$OUTPUT/raw/post-auth-events-private.jsonl" YES||exit 1
echo "AUTHORIZED_NO_CONNECT_SETTLE=${AUTHORIZED_SETTLE_SECONDS}s";sleep "$AUTHORIZED_SETTLE_SECONDS";mark authorized_settle_end
pull_events "$OUTPUT/raw/final-events-private.jsonl"||{ echo "ERROR: final event pull failed";exit 1; };verify_no_connect "$OUTPUT/raw/final-events-private.jsonl" YES||exit 1
stop_pcap;PCAP_STOP_RC=$?;[ "$PCAP_STOP_RC" -eq 0 ]||echo "WARNING: PCAPdroid stop returned rc=$PCAP_STOP_RC";sleep 2
PCAP_REMOTE="$(find_remote "$PCAP_NAME")";[ -n "$PCAP_REMOTE" ]||{ echo "ERROR: PCAP file not found";exit 1; };"$ADB" -s "$PHONE" pull "$PCAP_REMOTE" "$OUTPUT/raw/$PCAP_NAME" >"$OUTPUT/raw/pcap-pull-private.txt" 2>&1||exit 1
KEY_REMOTE="$(find_remote "$KEYLOG_NAME")";if [ -n "$KEY_REMOTE" ];then "$ADB" -s "$PHONE" pull "$KEY_REMOTE" "$OUTPUT/raw/$KEYLOG_NAME" >"$OUTPUT/raw/keylog-pull-private.txt" 2>&1||true;fi
KEY_ARG="";[ -s "$OUTPUT/raw/$KEYLOG_NAME" ]&&KEY_ARG="$OUTPUT/raw/$KEYLOG_NAME"
if [ -n "$KEY_ARG" ];then python3 "$PARSE" --pcap "$OUTPUT/raw/$PCAP_NAME" --uid-map "$OUTPUT/raw/uid-map-private.json" --output "$OUTPUT/raw" --sslkeylog "$KEY_ARG";PRC=$?;else python3 "$PARSE" --pcap "$OUTPUT/raw/$PCAP_NAME" --uid-map "$OUTPUT/raw/uid-map-private.json" --output "$OUTPUT/raw";PRC=$?;fi;[ "$PRC" -eq 0 ]||{ echo "ERROR: PCAP parse failed";exit 1; }
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >"$OUTPUT/raw/custom-cleanup-private.txt" 2>&1
cat >"$OUTPUT/run-metadata.txt" <<EOF
SCHEMA=rokid.test21-r3-3-3-1.run-metadata.v1
RUN_ID=$RUN_ID
PROFILE=PCAPDROID_DUAL_APP_ATTRIBUTION_AUTHORIZED_NO_CONNECT
PCAPDROID_VERSION_CODE=$PCAP_VERSION_CODE
PCAPDROID_TARGET_APPS=HI_ROKID_AND_CUSTOM_OPERATOR_CONFIRMED
PCAPDROID_TLS_DECRYPTION_TARGETS=HI_ROKID_AND_CUSTOM_OPERATOR_CONFIRMED
PCAPDROID_API_APP_FILTER=HI_ROKID_AND_CUSTOM
PCAPDROID_API_DECRYPTION_RULES=HI_ROKID_AND_CUSTOM
AUTHORIZATION_TOKEN_HOST_EXPORT=NONE
PCAPDROID_API_KEY_PERSISTENCE=NONE
CXR_L_CONNECTION_ATTEMPT=NONE
HI_ROKID_FORCE_STOP=NONE
PHOTO_OPERATION=NONE
AUDIO_OPERATION=NONE
RAW_PCAP=PRIVATE
SSLKEYLOG=PRIVATE_IF_AVAILABLE
EOF
python3 "$ANALYZE" --evidence "$OUTPUT";ARC=$?;echo "TEST21_R3_3_3_1_RUN_RC=$ARC";echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT";echo "CXR_L_CONNECTION_ATTEMPT=NONE";echo "HI_ROKID_FORCE_STOP=NONE";echo "PHOTO_OPERATION=NONE";echo "AUDIO_OPERATION=NONE";unset PCAPDROID_API_KEY_LOCAL;exit "$ARC"
