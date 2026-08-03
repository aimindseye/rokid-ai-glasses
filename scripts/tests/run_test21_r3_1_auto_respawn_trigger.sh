#!/usr/bin/env bash
REPO=""
PHONE=""
OUTPUT=""
PROFILE=""
HI_ROKID="com.rokid.sprite.global.aiapp"
CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_CUSTOM_VERSION="1.0-test20-final"
OBSERVATION_SECONDS="30"
if [ "${TEST21_R3_1_TEST_MODE:-0}" = "1" ]; then OBSERVATION_SECONDS="3"; fi
SUPPORTED_FUTURE_PROFILES="CUSTOM_UNAUTHORIZED_ALIVE CUSTOM_AUTHORIZED_NO_CONNECT CUSTOM_STOPPED_POST_AUTH"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1"; exit 2 ;;
  esac
done

[ "$PROFILE" = "NO_CUSTOM_PROCESS" ] || {
  echo "ERROR: r3.1 physical run currently permits only --profile NO_CUSTOM_PROCESS"
  echo "FUTURE_PROFILES_RESERVED=$SUPPORTED_FUTURE_PROFILES"
  exit 2
}
[ -n "$REPO" ] && [ -d "$REPO/.git" ] || { echo "ERROR: invalid --repo"; exit 2; }
[ -n "$PHONE" ] && [ -n "$OUTPUT" ] || { echo "ERROR: --phone and --output are required"; exit 2; }
ADB="$(command -v adb 2>/dev/null)"
[ -n "$ADB" ] || { echo "ERROR: adb not found"; exit 1; }

CHECK="$REPO/scripts/tests/check_test21_r3_1_source_contract.py"
ANALYZER="$REPO/scripts/tests/analyze_test21_r3_1_auto_respawn.py"
COLLECTOR="$REPO/scripts/tests/collect_test21_r3_1_respawn.py"
mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized" || exit 1

if [ "${TEST21_R3_1_TEST_MODE:-0}" = "1" ]; then
  TTY_IN="/dev/stdin"
  TTY_OUT="/dev/stdout"
else
  TTY_IN="/dev/tty"
  TTY_OUT="/dev/tty"
  if [ ! -r "$TTY_IN" ]; then TTY_IN="/dev/stdin"; TTY_OUT="/dev/stdout"; fi
fi

ACTIVE_USER=""
HI_LAUNCHER=""
HI_FORCE_STOP_ISSUED=0
HI_RESTORED=0
LOGCAT_EVENTS_PID=""
LOGCAT_AM_PID=""
RUN_ID="test21-r3-1-$(date -u +%Y%m%dT%H%M%SZ)"

die() { echo "ERROR: $*"; exit 1; }
utc() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

prompt_exact() {
  expected="$1"
  message="$2"
  echo
  printf '%s\n' "$message" > "$TTY_OUT"
  printf '[TERMINAL ACTION ONLY] Type exactly %s and press Enter: ' "$expected" > "$TTY_OUT"
  IFS= read -r answer < "$TTY_IN"
  [ "$answer" = "$expected" ]
}

resolve_launcher() {
  "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" \
    -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$1" 2>/dev/null |
    tr -d '\r' | awk 'NF{line=$0} END{print line}'
}

snapshot() {
  phase="$1"
  hi="$($ADB -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  custom="$($ADB -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')"
  [ -n "$hi" ] && hi_visible="YES" || hi_visible="NO"
  [ -n "$custom" ] && custom_visible="YES" || custom_visible="NO"
  cat > "$OUTPUT/raw/state-$phase.txt" <<EOF
SCHEMA=rokid.test21-r3-1.runtime-state.v1
PHASE=$phase
UTC=$(utc)
HI_PROCESS_VISIBLE=$hi_visible
CUSTOM_PROCESS_VISIBLE=$custom_visible
EOF
}

stop_observers() {
  for pid in "$LOGCAT_EVENTS_PID" "$LOGCAT_AM_PID"; do
    if [ -n "$pid" ]; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  done
  LOGCAT_EVENTS_PID=""
  LOGCAT_AM_PID=""
}

restore_hi_rokid() {
  if [ "$HI_FORCE_STOP_ISSUED" -ne 1 ] || [ "$HI_RESTORED" -eq 1 ]; then return 0; fi
  "$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" \
    >> "$OUTPUT/raw/restoration-private.txt" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then HI_RESTORED=1; fi
  return "$rc"
}

cleanup() {
  stop_observers
  restore_hi_rokid >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'cleanup; trap - EXIT; exit 130' INT
trap 'cleanup; trap - EXIT; exit 143' TERM

echo "============================================================"
echo "TEST 21 r3.1 — AUTO-RESPAWN TRIGGER CHARACTERIZATION"
echo "============================================================"
echo "PROFILE=NO_CUSTOM_PROCESS"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"

echo
echo "=== SOURCE SAFETY PREFLIGHT ==="
python3 "$CHECK" --repo "$REPO" || die "r3.1 source contract failed"

"$ADB" -s "$PHONE" get-state >/dev/null 2>&1 || die "phone unavailable through adb"
ACTIVE_USER="$($ADB -s "$PHONE" shell am get-current-user 2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
case "$ACTIVE_USER" in ''|*[!0-9]*) die "could not resolve active Android user" ;; esac
"$ADB" -s "$PHONE" shell pm path "$HI_ROKID" >/dev/null 2>&1 || die "Hi Rokid package missing"
"$ADB" -s "$PHONE" shell pm path "$CUSTOM_PACKAGE" >/dev/null 2>&1 || die "custom package missing"
CUSTOM_VERSION="$($ADB -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r' | awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}')"
[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ] || die "custom companion must be exactly $EXPECTED_CUSTOM_VERSION"
HI_LAUNCHER="$(resolve_launcher "$HI_ROKID")"
case "$HI_LAUNCHER" in "$HI_ROKID"/*) ;; *) die "Hi Rokid launcher unresolved" ;; esac

if ! prompt_exact "HI_ROKID_CONNECTED" \
  "[PHONE CHECK ONLY] Hi Rokid must be open and show the glasses connected normally. Do not use camera, Assistant, translation, recording, or any media function."; then
  die "baseline not confirmed"
fi
snapshot baseline
grep -q '^HI_PROCESS_VISIBLE=YES$' "$OUTPUT/raw/state-baseline.txt" || die "Hi Rokid process not visible at baseline"

echo
echo "=== PROFILE PREPARATION: NO_CUSTOM_PROCESS ==="
echo "[HOST ACTION] The script will force-stop ONLY the custom companion first."
echo "[PHONE ACTION] NONE. Do not touch the phone."
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" > "$OUTPUT/raw/custom-force-stop-private.txt" 2>&1
[ "$?" -eq 0 ] || die "custom companion force-stop failed"
sleep 1
snapshot profile-state-before-hi-force-stop
cp "$OUTPUT/raw/state-profile-state-before-hi-force-stop.txt" "$OUTPUT/raw/profile-state-before-hi-force-stop.txt"
grep -q '^CUSTOM_PROCESS_VISIBLE=NO$' "$OUTPUT/raw/profile-state-before-hi-force-stop.txt" || die "custom companion is still running"

echo
echo "=== START PASSIVE OBSERVERS ==="
"$ADB" -s "$PHONE" logcat -T 1 -b events -v epoch > "$OUTPUT/raw/activity-events-private.txt" 2>&1 &
LOGCAT_EVENTS_PID=$!
"$ADB" -s "$PHONE" logcat -T 1 -v epoch ActivityManager:I ActivityTaskManager:I '*:S' > "$OUTPUT/raw/activity-manager-private.txt" 2>&1 &
LOGCAT_AM_PID=$!

echo
echo "=== CONTROLLED HI ROKID FORCE-STOP ==="
echo "[HOST ACTION] The script now force-stops Hi Rokid ONCE."
echo "[PHONE ACTION] NONE. Do not touch the phone."
"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" > "$OUTPUT/raw/hi-force-stop-private.txt" 2>&1
FORCE_RC=$?
[ "$FORCE_RC" -eq 0 ] || die "Hi Rokid force-stop failed"
HI_FORCE_STOP_ISSUED=1
ABSENT="NO"
attempt=1
while [ "$attempt" -le 10 ]; do
  current="$($ADB -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  if [ -z "$current" ]; then ABSENT="YES"; break; fi
  sleep 1
  attempt=$((attempt + 1))
done
cat > "$OUTPUT/raw/force-stop-observation.txt" <<EOF
SCHEMA=rokid.test21-r3-1.force-stop-observation.v1
FORCE_STOP_COMMAND_RC=$FORCE_RC
HI_PROCESS_ABSENT_OBSERVED=$ABSENT
OBSERVATION_ATTEMPTS=$attempt
EOF
[ "$ABSENT" = "YES" ] || die "Hi Rokid process absence not observed"

echo
echo "=== 30-SECOND HANDS-OFF RESPAWN WINDOW ==="
echo "[PHONE ACTION] NONE FOR 30 SECONDS."
echo "Do NOT tap, swipe, authorize, connect, reopen Hi Rokid, or open the custom app."
python3 "$COLLECTOR" \
  --adb "$ADB" --phone "$PHONE" --hi-package "$HI_ROKID" --custom-package "$CUSTOM_PACKAGE" \
  --output "$OUTPUT/raw" --duration-seconds "$OBSERVATION_SECONDS" --poll-seconds 0.20 \
  > "$OUTPUT/raw/collector-console-private.txt" 2>&1
COLLECT_RC=$?
cat "$OUTPUT/raw/collector-console-private.txt"
[ "$COLLECT_RC" -eq 0 ] || die "respawn collector failed"
stop_observers

echo
echo "=== MANDATORY HI ROKID RESTORATION ==="
restore_hi_rokid
RESTORE_RC=$?
sleep 5
snapshot restored
if [ "$RESTORE_RC" -eq 0 ] && prompt_exact "HI_ROKID_RECOVERY_PASS" \
  "[PHONE CHECK ONLY] Hi Rokid should now be open again. Confirm the glasses are back to their normal usable/connected state. Do not perform a media action."; then
  RECOVERY="PASS"
  HI_RESTORED=1
else
  RECOVERY="FAIL"
fi
echo "OPERATOR_HI_ROKID_RECOVERY=$RECOVERY" >> "$OUTPUT/raw/state-restored.txt"

cat > "$OUTPUT/run-metadata.txt" <<EOF
SCHEMA=rokid.test21-r3-1.run-metadata.v1
RUN_ID=$RUN_ID
PROFILE=NO_CUSTOM_PROCESS
HI_ROKID_PACKAGE=$HI_ROKID
CUSTOM_PACKAGE=$CUSTOM_PACKAGE
CUSTOM_VERSION=$CUSTOM_VERSION
OBSERVATION_SECONDS=$OBSERVATION_SECONDS
CXR_L_CONNECTION_ATTEMPT=NONE
HI_ROKID_FORCE_STOP=ONE_CONTROLLED_ATTEMPT
CUSTOM_COMPANION_FORCE_STOP=ONE_CONTROLLED_ATTEMPT
PACKAGE_DISABLE_OR_UNINSTALL=NONE
PACKAGE_DATA_CLEAR=NONE
PHOTO_OPERATION=NONE
AUDIO_OPERATION=NONE
AUTHORIZATION_TOKEN_HOST_EXPORT=NONE
EOF

python3 "$ANALYZER" --repo "$REPO" --evidence "$OUTPUT"
ANALYZE_RC=$?
echo
echo "============================================================"
echo "TEST21_R3_1_RUN_RC=$ANALYZE_RC"
echo "PROFILE=NO_CUSTOM_PROCESS"
echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT"
echo "HI_ROKID_RESTORATION=$RECOVERY"
echo "CXR_L_CONNECTION_ATTEMPT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
echo "============================================================"
exit "$ANALYZE_RC"
