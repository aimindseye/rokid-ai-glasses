#!/usr/bin/env bash

REPO=""
PHONE=""
OUTPUT=""

HI_ROKID="com.rokid.sprite.global.aiapp"
CUSTOM_PACKAGE="org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_CUSTOM_VERSION="1.0-test20-final"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) echo "ERROR: unknown argument: $1"; exit 2 ;;
  esac
done

if [ -z "$REPO" ] || [ ! -d "$REPO/.git" ]; then
  echo "ERROR: --repo must point to the rokid-ai-glasses git repository"
  exit 2
fi
if [ -z "$PHONE" ]; then
  echo "ERROR: --phone is required"
  exit 2
fi
if [ -z "$OUTPUT" ]; then
  echo "ERROR: --output is required"
  exit 2
fi

ADB="$(command -v adb 2>/dev/null)"
[ -n "$ADB" ] || { echo "ERROR: adb not found"; exit 1; }

SOURCE_CHECK="$REPO/scripts/tests/check_test21_r3_source_contract.py"
R2_ANALYZER="$REPO/scripts/tests/analyze_test21_r2_ownership.py"
ANALYZER="$REPO/scripts/tests/analyze_test21_r3_respawn.py"
COLLECTOR="$REPO/scripts/tests/collect_test21_r3_timeline.py"

mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized"
[ "$?" -eq 0 ] || { echo "ERROR: could not create evidence directory"; exit 1; }

COLLECT_DURATION="20"
COLLECT_POLL="0.25"
if [ "${TEST21_R3_TEST_MODE:-0}" = "1" ]; then
  TTY_IN="/dev/stdin"
  TTY_OUT="/dev/stdout"
  COLLECT_DURATION="3"
  COLLECT_POLL="0.10"
else
  TTY_IN="/dev/tty"
  TTY_OUT="/dev/tty"
  if [ ! -r "$TTY_IN" ]; then
    TTY_IN="/dev/stdin"
    TTY_OUT="/dev/stdout"
  fi
fi

ACTIVE_USER=""
HI_LAUNCHER=""
CUSTOM_LAUNCHER=""
RUN_ID=""
REMOTE_EVENTS=""
HI_FORCE_STOP_ISSUED=0
HI_RESTORED=0
LOGCAT_EVENTS_PID=""
LOGCAT_AM_PID=""
COLLECTOR_PID=""
ABNORMAL_RESTORE_LOG="$OUTPUT/raw/emergency-restoration-private.txt"

die() {
  echo "ERROR: $*"
  exit 1
}

utc_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

prompt_exact() {
  expected="$1"
  message="$2"
  echo
  printf '%s\n' "$message" > "$TTY_OUT"
  printf 'Type exactly %s to confirm: ' "$expected" > "$TTY_OUT"
  IFS= read -r answer < "$TTY_IN"
  [ "$answer" = "$expected" ]
}

pause_enter() {
  message="$1"
  echo
  printf '%s\n' "$message" > "$TTY_OUT"
  printf 'Press Enter only when complete: ' > "$TTY_OUT"
  IFS= read -r _ < "$TTY_IN"
}

resolve_launcher() {
  pkg="$1"
  "$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" \
    -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$pkg" 2>/dev/null |
    tr -d '\r' | awk 'NF{line=$0} END{print line}'
}

stop_observers() {
  for pid in "$COLLECTOR_PID" "$LOGCAT_EVENTS_PID" "$LOGCAT_AM_PID"; do
    if [ -n "$pid" ]; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  done
  COLLECTOR_PID=""
  LOGCAT_EVENTS_PID=""
  LOGCAT_AM_PID=""
}

restore_hi_rokid() {
  if [ "$HI_FORCE_STOP_ISSUED" -ne 1 ] || [ "$HI_RESTORED" -eq 1 ]; then
    return 0
  fi
  {
    echo "RESTORE_ATTEMPT_UTC=$(utc_now)"
    echo "HI_LAUNCHER=$HI_LAUNCHER"
  } >> "$ABNORMAL_RESTORE_LOG"
  if [ -n "$HI_LAUNCHER" ]; then
    "$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" \
      >> "$ABNORMAL_RESTORE_LOG" 2>&1
    rc=$?
    echo "RESTORE_AM_START_RC=$rc" >> "$ABNORMAL_RESTORE_LOG"
    if [ "$rc" -eq 0 ]; then
      HI_RESTORED=1
      return 0
    fi
  fi
  return 1
}

cleanup() {
  stop_observers
  restore_hi_rokid >/dev/null 2>&1
}

trap cleanup EXIT
trap 'cleanup; trap - EXIT; exit 130' INT
trap 'cleanup; trap - EXIT; exit 143' TERM

snapshot_runtime() {
  phase="$1"
  state="$OUTPUT/raw/state-${phase}.txt"
  services_hi="$OUTPUT/raw/${phase}-hi-services-private.txt"
  services_custom="$OUTPUT/raw/${phase}-custom-services-private.txt"

  "$ADB" -s "$PHONE" shell dumpsys activity services "$HI_ROKID" > "$services_hi" 2>&1
  hi_svc_rc=$?
  "$ADB" -s "$PHONE" shell dumpsys activity services "$CUSTOM_PACKAGE" > "$services_custom" 2>&1
  custom_svc_rc=$?

  hi_pids="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  custom_pids="$("$ADB" -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')"

  [ -n "$hi_pids" ] && hi_visible="YES" || hi_visible="NO"
  [ -n "$custom_pids" ] && custom_visible="YES" || custom_visible="NO"

  cat > "$state" <<EOF
SCHEMA=rokid.test21-r3.runtime-state.v1
PHASE=$phase
UTC=$(utc_now)
HI_PROCESS_VISIBLE=$hi_visible
CUSTOM_PROCESS_VISIBLE=$custom_visible
HI_SERVICE_COLLECTION_RC=$hi_svc_rc
CUSTOM_SERVICE_COLLECTION_RC=$custom_svc_rc
EOF
}

resolve_remote_events() {
  if [ -n "$REMOTE_EVENTS" ] &&
     "$ADB" -s "$PHONE" shell "test -s '$REMOTE_EVENTS'" >/dev/null 2>&1; then
    printf '%s' "$REMOTE_EVENTS"
    return 0
  fi
  candidate="$("$ADB" -s "$PHONE" shell \
    "find /sdcard/Android/data/$CUSTOM_PACKAGE/files -type f -name '*$RUN_ID*.jsonl' 2>/dev/null | head -n 1" \
    2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
  [ -n "$candidate" ] || return 1
  REMOTE_EVENTS="$candidate"
  printf '%s' "$candidate"
  return 0
}

pull_events() {
  target="$1"
  actual="$(resolve_remote_events)"
  [ -n "$actual" ] || return 1
  "$ADB" -s "$PHONE" pull "$actual" "$target" > "$OUTPUT/raw/events-pull-private.txt" 2>&1
  rc=$?
  [ "$rc" -eq 0 ] && [ -s "$target" ]
}

echo "============================================================"
echo "TEST 21 r3 — BOUND-SERVICE RESPAWN DEPENDENCY CHARACTERIZATION"
echo "============================================================"
echo "HI_ROKID_PACKAGE=$HI_ROKID"
echo "CUSTOM_PACKAGE=$CUSTOM_PACKAGE"
echo "NO PHOTO"
echo "NO AUDIO"
echo "LOGCAT_CLEAR=NONE"
echo "PACKAGE_DISABLE_OR_UNINSTALL=NONE"
echo "PACKAGE_DATA_CLEAR=NONE"

echo
echo "=== SOURCE SAFETY PREFLIGHT ==="
python3 "$SOURCE_CHECK" --repo "$REPO"
SOURCE_RC=$?
[ "$SOURCE_RC" -eq 0 ] || die "Test21 r3 source contract failed"

echo
echo "=== ADB PREFLIGHT ==="
"$ADB" -s "$PHONE" get-state > "$OUTPUT/raw/adb-state-private.txt" 2>&1
[ "$?" -eq 0 ] || die "phone is not available through adb"

ACTIVE_USER="$("$ADB" -s "$PHONE" shell am get-current-user 2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
case "$ACTIVE_USER" in ''|*[!0-9]*) die "could not resolve active Android user" ;; esac
echo "ACTIVE_USER=$ACTIVE_USER"

"$ADB" -s "$PHONE" shell pm path "$HI_ROKID" > "$OUTPUT/raw/hi-package-path-private.txt" 2>&1
[ "$?" -eq 0 ] || die "exact global Hi Rokid package is not installed"
"$ADB" -s "$PHONE" shell pm path "$CUSTOM_PACKAGE" > "$OUTPUT/raw/custom-package-path-private.txt" 2>&1
[ "$?" -eq 0 ] || die "canonical custom companion is not installed"

CUSTOM_VERSION="$("$ADB" -s "$PHONE" shell dumpsys package "$CUSTOM_PACKAGE" 2>/dev/null |
  tr -d '\r' | awk -F= '/versionName=/{gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}')"
echo "CUSTOM_VERSION=$CUSTOM_VERSION"
[ "$CUSTOM_VERSION" = "$EXPECTED_CUSTOM_VERSION" ] ||
  die "installed custom companion must be exactly $EXPECTED_CUSTOM_VERSION"

HI_LAUNCHER="$(resolve_launcher "$HI_ROKID")"
CUSTOM_LAUNCHER="$(resolve_launcher "$CUSTOM_PACKAGE")"
case "$HI_LAUNCHER" in "$HI_ROKID"/*) ;; *) die "could not resolve exact Hi Rokid launcher" ;; esac
case "$CUSTOM_LAUNCHER" in "$CUSTOM_PACKAGE"/*) ;; *) die "could not resolve custom companion launcher" ;; esac

if ! prompt_exact "HI_ROKID_CONNECTED" \
  "Confirm Hi Rokid currently shows the glasses connected and stable. Do not use camera, Assistant, translation, recording, or any other media function."; then
  die "normal connected baseline was not explicitly confirmed"
fi

snapshot_runtime "baseline"
if ! grep -q '^HI_PROCESS_VISIBLE=YES$' "$OUTPUT/raw/state-baseline.txt"; then
  die "Hi Rokid process is not visible in the required baseline"
fi

echo
echo "=== STATIC HI ROKID COMPONENT CENSUS ==="
"$ADB" -s "$PHONE" shell dumpsys package "$HI_ROKID" \
  > "$OUTPUT/raw/hi-package-dumpsys-private.txt" 2>&1
"$ADB" -s "$PHONE" shell cmd package query-services --user "$ACTIVE_USER" \
  -a android.intent.action.MAIN "$HI_ROKID" \
  > "$OUTPUT/raw/hi-query-services-private.txt" 2>&1 || true

RUN_ID="test21-r3-$(date -u +%Y%m%dT%H%M%SZ)"
INERT_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
[ -n "$INERT_TOKEN" ] || die "could not create inert operator token"

echo
echo "=== CUSTOM APP AUTHORIZATION BASELINE ==="
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1
"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" \
  --es run_id "$RUN_ID" \
  --es firmware_label "test21-r3-bound-service-respawn" \
  --es operator_gate_token "$INERT_TOKEN" \
  > "$OUTPUT/raw/custom-launch-private.txt" 2>&1
[ "$?" -eq 0 ] || die "failed to launch custom companion"

pause_enter "AUTHORIZATION BASELINE

On the phone:
  1. Tap '1. Authorize through Hi Rokid' once.
  2. Complete/approve authorization.
  3. Return to the custom app and wait until the connection button is enabled.

DO NOT tap the connection button yet.
DO NOT touch capture.
DO NOT perform a media action."

PRE_EVENTS="$OUTPUT/raw/pre-force-events-private.jsonl"
pull_events "$PRE_EVENTS" || die "could not pull event stream after authorization"

python3 "$R2_ANALYZER" --mode preforce --evidence "$OUTPUT" \
  > "$OUTPUT/preforce-gate.txt" 2>&1
PREFORCE_RC=$?
cat "$OUTPUT/preforce-gate.txt"
[ "$PREFORCE_RC" -eq 0 ] || die "accepted r2 pre-force safety gate failed"

snapshot_runtime "pre-force"
[ -n "$("$ADB" -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')" ] ||
  die "custom companion is not alive before force-stop"

echo
echo "=== START PASSIVE ACTIVITY-MANAGER OBSERVERS ==="
"$ADB" -s "$PHONE" logcat -T 1 -b events -v epoch \
  > "$OUTPUT/raw/activity-events-private.txt" 2>&1 &
LOGCAT_EVENTS_PID=$!

"$ADB" -s "$PHONE" logcat -T 1 -v epoch \
  ActivityManager:I ActivityTaskManager:I '*:S' \
  > "$OUTPUT/raw/activity-manager-private.txt" 2>&1 &
LOGCAT_AM_PID=$!

echo
echo "=== CONTROLLED HI ROKID FORCE-STOP ==="
"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" \
  > "$OUTPUT/raw/hi-force-stop-private.txt" 2>&1
FORCE_RC=$?
[ "$FORCE_RC" -eq 0 ] || die "Hi Rokid force-stop failed"
HI_FORCE_STOP_ISSUED=1

ABSENT="NO"
attempt=1
while [ "$attempt" -le 10 ]; do
  current="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  if [ -z "$current" ]; then
    ABSENT="YES"
    break
  fi
  sleep 1
  attempt=$((attempt + 1))
done

cat > "$OUTPUT/raw/force-stop-observation.txt" <<EOF
SCHEMA=rokid.test21-r3.force-stop-observation.v1
FORCE_STOP_COMMAND_RC=$FORCE_RC
HI_PROCESS_ABSENT_OBSERVED=$ABSENT
OBSERVATION_ATTEMPTS=$attempt
EOF

[ "$ABSENT" = "YES" ] || die "Hi Rokid process absence was not observed"

sleep 3
snapshot_runtime "pre-connect"

grep -q '^HI_PROCESS_VISIBLE=NO$' "$OUTPUT/raw/state-pre-connect.txt" ||
  die "Hi Rokid respawned before the r3 connection window"
grep -q '^CUSTOM_PROCESS_VISIBLE=YES$' "$OUTPUT/raw/state-pre-connect.txt" ||
  die "custom companion did not survive force-stop"

REMOTE_EVENTS="$(resolve_remote_events)" || die "could not resolve live custom-app event stream"

if ! prompt_exact "READY_FOR_R3_CONNECTION" \
  "Prepare to characterize the respawn. Keep the phone on the custom app. After confirming, the host starts the high-resolution observer; then tap ONLY '2. Start one photo connection' once when instructed. Do not touch capture."; then
  die "operator was not ready for bounded r3 connection attempt"
fi

echo
echo "=== HIGH-RESOLUTION RESPAWN WINDOW ==="
python3 "$COLLECTOR" \
  --adb "$ADB" \
  --phone "$PHONE" \
  --hi-package "$HI_ROKID" \
  --custom-package "$CUSTOM_PACKAGE" \
  --remote-events "$REMOTE_EVENTS" \
  --output "$OUTPUT/raw" \
  --duration-seconds "$COLLECT_DURATION" \
  --poll-seconds "$COLLECT_POLL" \
  > "$OUTPUT/raw/collector-console-private.txt" 2>&1 &
COLLECTOR_PID=$!

pause_enter "NOW perform exactly one action on the phone:
  - Tap '2. Start one photo connection' ONCE.
Then immediately return to this terminal and press Enter.

Do not tap authorization again.
Do not touch capture.
Do not perform any other app action."

wait "$COLLECTOR_PID"
COLLECTOR_RC=$?
COLLECTOR_PID=""
cat "$OUTPUT/raw/collector-console-private.txt"
[ "$COLLECTOR_RC" -eq 0 ] || die "timeline collector failed"

snapshot_runtime "post-observation"

FINAL_EVENTS="$OUTPUT/raw/final-events-private.jsonl"
pull_events "$FINAL_EVENTS" || die "could not pull final custom-app event stream"

echo
echo "=== CUSTOM APP CLEAN DISCONNECT ==="
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" \
  > "$OUTPUT/raw/custom-force-stop-private.txt" 2>&1
echo "CUSTOM_APP_FORCE_STOP_RC=$?"

stop_observers

echo
echo "=== MANDATORY HI ROKID RESTORATION ==="
restore_hi_rokid
RESTORE_START_RC=$?
sleep 5
snapshot_runtime "restored"

if [ "$RESTORE_START_RC" -eq 0 ] &&
   prompt_exact "HI_ROKID_RECOVERY_PASS" \
     "Confirm Hi Rokid is open again and the glasses are back to their normal usable/connected state. Do not perform a media action."; then
  OPERATOR_RECOVERY="PASS"
else
  OPERATOR_RECOVERY="FAIL"
fi
echo "OPERATOR_HI_ROKID_RECOVERY=$OPERATOR_RECOVERY" >> "$OUTPUT/raw/state-restored.txt"
[ "$OPERATOR_RECOVERY" = "PASS" ] && HI_RESTORED=1

cat > "$OUTPUT/run-metadata.txt" <<EOF
SCHEMA=rokid.test21-r3.run-metadata.v1
RUN_ID=$RUN_ID
HI_ROKID_PACKAGE=$HI_ROKID
CUSTOM_PACKAGE=$CUSTOM_PACKAGE
CUSTOM_VERSION=$CUSTOM_VERSION
R2_ACCEPTED_PREREQUISITE=CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED
HI_ROKID_FORCE_STOP=ONE_CONTROLLED_ATTEMPT
LOGCAT_CLEAR=NONE
AUTHORIZATION_TOKEN_HANDLING=IN_MEMORY_ONLY
AUTHORIZATION_TOKEN_HOST_EXPORT=NONE
PACKAGE_DISABLE_OR_UNINSTALL=NONE
PACKAGE_DATA_CLEAR=NONE
PHOTO_OPERATION=NONE
AUDIO_OPERATION=NONE
FIRMWARE_OPERATION=NONE
EOF

echo
echo "=== FINAL R3 ANALYSIS ==="
python3 "$ANALYZER" --repo "$REPO" --evidence "$OUTPUT"
ANALYZE_RC=$?

echo
echo "============================================================"
echo "TEST21_R3_RUN_RC=$ANALYZE_RC"
echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT"
echo "HI_ROKID_FORCE_STOP=ONE_CONTROLLED_ATTEMPT"
echo "HI_ROKID_RESTORATION=$OPERATOR_RECOVERY"
echo "LOGCAT_CLEAR=NONE"
echo "PACKAGE_DISABLE_OR_UNINSTALL=NONE"
echo "PACKAGE_DATA_CLEAR=NONE"
echo "AUTHORIZATION_TOKEN_HOST_EXPORT=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "FIRMWARE_OPERATION=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
echo "============================================================"

exit "$ANALYZE_RC"
