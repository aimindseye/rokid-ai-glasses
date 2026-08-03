#!/usr/bin/env bash
REPO=""; PHONE=""; OUTPUT=""; PROFILE=""
HI_ROKID="com.rokid.sprite.global.aiapp"; CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification"; EXPECTED_CUSTOM_VERSION="1.0-test20-final"; OBSERVATION_SECONDS="30"
if [ "${TEST21_R3_2_TEST_MODE:-0}" = "1" ]; then OBSERVATION_SECONDS="3"; fi
while [ "$#" -gt 0 ]; do case "$1" in --repo) REPO="$2"; shift 2;; --phone) PHONE="$2"; shift 2;; --output) OUTPUT="$2"; shift 2;; --profile) PROFILE="$2"; shift 2;; *) echo "ERROR: unknown argument $1"; exit 2;; esac; done
[ "$PROFILE" = "CUSTOM_UNAUTHORIZED_ALIVE" ] || { echo "ERROR: only --profile CUSTOM_UNAUTHORIZED_ALIVE is permitted"; exit 2; }
[ -d "$REPO/.git" ] && [ -n "$PHONE" ] && [ -n "$OUTPUT" ] || { echo "ERROR: invalid arguments"; exit 2; }
ADB="$(command -v adb 2>/dev/null)"; [ -n "$ADB" ] || { echo "ERROR: adb not found"; exit 1; }
CHECK="$REPO/scripts/tests/check_test21_r3_2_source_contract.py"; ANALYZER="$REPO/scripts/tests/analyze_test21_r3_2_topology.py"; COLLECTOR="$REPO/scripts/tests/collect_test21_r3_2_topology.py"
mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized" || exit 1
TTY_IN="/dev/tty"; TTY_OUT="/dev/tty"; if [ "${TEST21_R3_2_TEST_MODE:-0}" = "1" ] || [ ! -r "$TTY_IN" ]; then TTY_IN="/dev/stdin"; TTY_OUT="/dev/stdout"; fi
ACTIVE_USER=""; HI_LAUNCHER=""; CUSTOM_LAUNCHER=""; HI_FORCE_STOP_ISSUED=0; HI_RESTORED=0
prompt_exact(){ expected="$1"; message="$2"; echo; printf '%s\n' "$message" >"$TTY_OUT"; printf '[TERMINAL ACTION ONLY] Type exactly %s and press Enter: ' "$expected" >"$TTY_OUT"; IFS= read -r answer <"$TTY_IN"; [ "$answer" = "$expected" ]; }
resolve_launcher(){ "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$1" 2>/dev/null | tr -d '\r' | awk 'NF{line=$0} END{print line}'; }
ps_snapshot(){ name="$1"; "$ADB" -s "$PHONE" shell ps -A -o USER,PID,PPID,NAME,ARGS >"$OUTPUT/raw/ps-$name-private.txt" 2>&1 || "$ADB" -s "$PHONE" shell ps -A >"$OUTPUT/raw/ps-$name-private.txt" 2>&1; }
state(){ phase="$1"; hi="$($ADB -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null|tr -d '\r')"; cu="$($ADB -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null|tr -d '\r')"; [ -n "$hi" ]&&hv=YES||hv=NO; [ -n "$cu" ]&&cv=YES||cv=NO; printf 'PHASE=%s\nHI_PROCESS_VISIBLE=%s\nCUSTOM_PROCESS_VISIBLE=%s\n' "$phase" "$hv" "$cv" >"$OUTPUT/raw/state-$phase.txt"; }
restore_hi(){ [ "$HI_FORCE_STOP_ISSUED" -eq 1 ] && [ "$HI_RESTORED" -eq 0 ] || return 0; "$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" >>"$OUTPUT/raw/restoration-private.txt" 2>&1; rc=$?; [ "$rc" -eq 0 ]&&HI_RESTORED=1; return "$rc"; }
cleanup(){ restore_hi >/dev/null 2>&1 || true; }
trap cleanup EXIT; trap 'cleanup; trap - EXIT; exit 130' INT; trap 'cleanup; trap - EXIT; exit 143' TERM

echo "============================================================"; echo "TEST 21 r3.2 — CUSTOM-UNAUTHORIZED / AI PROCESS TOPOLOGY"; echo "============================================================"
echo "PROFILE=CUSTOM_UNAUTHORIZED_ALIVE"; echo "AUTHORIZATION_OPERATION=NONE"; echo "CXR_L_CONNECTION_ATTEMPT=NONE"; echo "PHOTO_OPERATION=NONE"; echo "AUDIO_OPERATION=NONE"; echo "SECONDARY_PACKAGE_FORCE_STOP=NONE"
python3 "$CHECK" --repo "$REPO" || exit 1
"$ADB" -s "$PHONE" get-state >/dev/null 2>&1 || { echo "ERROR: adb unavailable"; exit 1; }
ACTIVE_USER="$($ADB -s "$PHONE" shell am get-current-user 2>/dev/null|tr -d '\r'|awk 'NF{print;exit}')"
"$ADB" -s "$PHONE" shell pm path "$HI_ROKID" >/dev/null 2>&1 || { echo "ERROR: Hi Rokid missing"; exit 1; }
CUSTOM_VERSION="$($ADB -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null|tr -d '\r'|awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2;exit}')"
[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ] || { echo "ERROR: expected $EXPECTED_CUSTOM_VERSION"; exit 1; }
HI_LAUNCHER="$(resolve_launcher "$HI_ROKID")"; CUSTOM_LAUNCHER="$(resolve_launcher "$CUSTOM_PACKAGE")"; case "$HI_LAUNCHER" in "$HI_ROKID"/*) ;; *) echo "ERROR: Hi Rokid launcher unresolved"; exit 1;; esac; case "$CUSTOM_LAUNCHER" in "$CUSTOM_PACKAGE"/*) ;; *) echo "ERROR: custom launcher unresolved"; exit 1;; esac
if ! prompt_exact HI_ROKID_CONNECTED "[PHONE CHECK ONLY] Hi Rokid must be open and show the glasses connected normally."; then echo "ERROR: baseline not confirmed"; exit 1; fi

echo; echo "=== PREPARE UNAUTHORIZED CUSTOM PROCESS ==="; echo "[PHONE ACTION] NONE. The script restarts the custom app itself. DO NOT tap Authorize or button 2."
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1 || exit 1
"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" >"$OUTPUT/raw/custom-launch-private.txt" 2>&1 || exit 1
sleep 3; state profile-state-before-hi-force-stop; cp "$OUTPUT/raw/state-profile-state-before-hi-force-stop.txt" "$OUTPUT/raw/profile-state-before-hi-force-stop.txt"
grep -q '^CUSTOM_PROCESS_VISIBLE=YES$' "$OUTPUT/raw/profile-state-before-hi-force-stop.txt" || { echo "ERROR: custom process not alive"; exit 1; }
ps_snapshot before-hi-force-stop
"$ADB" -s "$PHONE" shell dumpsys package "$HI_ROKID" >"$OUTPUT/raw/hi-package-private.txt" 2>&1
"$ADB" -s "$PHONE" shell pm list packages -U >"$OUTPUT/raw/packages-u-private.txt" 2>&1

echo; echo "=== CONTROLLED HI ROKID FORCE-STOP ==="; echo "[PHONE ACTION] NONE. Do not touch the phone for the entire 30-second window."
"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" >"$OUTPUT/raw/hi-force-stop-private.txt" 2>&1; FORCE_RC=$?; [ "$FORCE_RC" -eq 0 ] || exit 1; HI_FORCE_STOP_ISSUED=1
ABSENT=NO; attempt=1; while [ "$attempt" -le 10 ]; do current="$($ADB -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null|tr -d '\r')"; [ -z "$current" ] && { ABSENT=YES; break; }; sleep 1; attempt=$((attempt+1)); done
ps_snapshot immediate-post-force
SAME_COUNT="$(grep -F "$HI_ROKID" "$OUTPUT/raw/ps-immediate-post-force-private.txt" 2>/dev/null | wc -l | tr -d ' ')"
printf 'FORCE_STOP_COMMAND_RC=%s\nHI_PROCESS_ABSENT_OBSERVED=%s\nOBSERVATION_ATTEMPTS=%s\nSAME_PACKAGE_PROCESS_COUNT_POST_FORCE=%s\n' "$FORCE_RC" "$ABSENT" "$attempt" "$SAME_COUNT" >"$OUTPUT/raw/force-stop-observation.txt"
[ "$ABSENT" = YES ] && [ "$SAME_COUNT" -eq 0 ] || { echo "ERROR: full Hi Rokid package-process stop not proven"; exit 1; }

echo; echo "=== 30-SECOND HANDS-OFF TOPOLOGY WINDOW ==="; echo "[PHONE ACTION] NONE FOR 30 SECONDS. Do not tap, swipe, authorize, connect, or reopen either app."
python3 "$COLLECTOR" --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" --output "$OUTPUT/raw" --duration-seconds "$OBSERVATION_SECONDS" --poll-seconds .20
COLLECT_RC=$?; [ "$COLLECT_RC" -eq 0 ] || exit 1

echo; echo "=== MANDATORY HI ROKID RESTORATION ==="; restore_hi; RESTORE_RC=$?; sleep 5; state restored
if [ "$RESTORE_RC" -eq 0 ] && prompt_exact HI_ROKID_RECOVERY_PASS "[PHONE CHECK ONLY] Hi Rokid should be open again and the glasses normally usable/connected."; then RECOVERY=PASS; HI_RESTORED=1; else RECOVERY=FAIL; fi
echo "OPERATOR_HI_ROKID_RECOVERY=$RECOVERY" >>"$OUTPUT/raw/state-restored.txt"
printf 'PROFILE=CUSTOM_UNAUTHORIZED_ALIVE\nAUTHORIZATION_OPERATION=NONE\nCXR_L_CONNECTION_ATTEMPT=NONE\nPHOTO_OPERATION=NONE\nAUDIO_OPERATION=NONE\nSECONDARY_PACKAGE_FORCE_STOP=NONE\n' >"$OUTPUT/run-metadata.txt"
python3 "$ANALYZER" --repo "$REPO" --evidence "$OUTPUT"; ANALYZE_RC=$?
echo; echo "TEST21_R3_2_RUN_RC=$ANALYZE_RC"; echo "HI_ROKID_RESTORATION=$RECOVERY"; echo "TERMINAL_REMAINS_OPEN=YES"; exit "$ANALYZE_RC"
