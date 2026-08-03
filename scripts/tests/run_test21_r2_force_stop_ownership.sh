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
if [ -z "$ADB" ]; then
  echo "ERROR: adb not found"
  exit 1
fi

ANALYZER="$REPO/scripts/tests/analyze_test21_r2_ownership.py"
SOURCE_CHECK="$REPO/scripts/tests/check_test21_r2_source_contract.py"
mkdir -p "$OUTPUT/raw" "$OUTPUT/sanitized"
MKDIR_RC=$?
if [ "$MKDIR_RC" -ne 0 ]; then
  echo "ERROR: could not create evidence directory"
  exit 1
fi

if [ "${TEST21_R2_TEST_MODE:-0}" = "1" ]; then
  TTY_IN="/dev/stdin"
  TTY_OUT="/dev/stdout"
else
  TTY_IN="/dev/tty"
  TTY_OUT="/dev/tty"
  if [ ! -r "$TTY_IN" ]; then
    TTY_IN="/dev/stdin"
    TTY_OUT="/dev/stdout"
  fi
fi

HI_FORCE_STOP_ISSUED=0
HI_RESTORED=0
HI_LAUNCHER=""
ACTIVE_USER=""
RUN_ID=""
REMOTE_EVENTS=""
OPERATOR_GATE_TOKEN=""
ABNORMAL_RESTORE_LOG="$OUTPUT/raw/emergency-restoration-private.txt"

utc_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

die() {
  echo "ERROR: $*"
  exit 1
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
  restore_hi_rokid >/dev/null 2>&1
}

trap cleanup EXIT
trap 'cleanup; trap - EXIT; exit 130' INT
trap 'cleanup; trap - EXIT; exit 143' TERM

snapshot_runtime() {
  phase="$1"
  process_file="$OUTPUT/raw/${phase}-processes-private.txt"
  services_file="$OUTPUT/raw/${phase}-services-private.txt"
  bluetooth_file="$OUTPUT/raw/${phase}-bluetooth-private.txt"
  state_file="$OUTPUT/raw/state-${phase}.txt"

  "$ADB" -s "$PHONE" shell ps -A > "$process_file" 2>&1
  ps_rc=$?
  "$ADB" -s "$PHONE" shell dumpsys activity services "$HI_ROKID" > "$services_file" 2>&1
  svc_rc=$?
  "$ADB" -s "$PHONE" shell dumpsys bluetooth_manager > "$bluetooth_file" 2>&1
  bt_rc=$?

  hi_pids="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  custom_pids="$("$ADB" -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')"

  if [ -n "$hi_pids" ]; then hi_visible="YES"; else hi_visible="NO"; fi
  if [ -n "$custom_pids" ]; then custom_visible="YES"; else custom_visible="NO"; fi
  if grep -F "$HI_ROKID" "$services_file" >/dev/null 2>&1; then
    service_visible="YES"
  else
    service_visible="NO"
  fi

  cat > "$state_file" <<EOF
SCHEMA=rokid.test21-r2.runtime-state.v1
PHASE=$phase
UTC=$(utc_now)
HI_PROCESS_VISIBLE=$hi_visible
HI_SERVICE_VISIBLE=$service_visible
CUSTOM_PROCESS_VISIBLE=$custom_visible
PROCESS_COLLECTION_RC=$ps_rc
SERVICE_COLLECTION_RC=$svc_rc
BLUETOOTH_COLLECTION_RC=$bt_rc
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
  if [ -z "$candidate" ]; then
    return 1
  fi
  REMOTE_EVENTS="$candidate"
  printf '%s' "$candidate"
  return 0
}

pull_events() {
  target="$1"
  actual="$(resolve_remote_events)"
  if [ -z "$actual" ]; then
    return 1
  fi
  "$ADB" -s "$PHONE" pull "$actual" "$target" > "$OUTPUT/raw/events-pull-private.txt" 2>&1
  rc=$?
  [ "$rc" -eq 0 ] && [ -s "$target" ]
}

echo "============================================================"
echo "TEST 21 r2 — CONTROLLED HI ROKID FORCE-STOP OWNERSHIP PROBE"
echo "============================================================"
echo "HI_ROKID_PACKAGE=$HI_ROKID"
echo "CUSTOM_PACKAGE=$CUSTOM_PACKAGE"
echo "AUTH_TOKEN_HANDLING=IN_MEMORY_ONLY"
echo "NO PHOTO"
echo "NO AUDIO"
echo "PACKAGE_DISABLE_OR_UNINSTALL=NONE"
echo "PACKAGE_DATA_CLEAR=NONE"

echo
echo "=== SOURCE SAFETY PREFLIGHT ==="
python3 "$SOURCE_CHECK" --repo "$REPO"
SOURCE_RC=$?
[ "$SOURCE_RC" -eq 0 ] || die "Test21 r2 source contract failed"

echo
echo "=== ADB PREFLIGHT ==="
"$ADB" -s "$PHONE" get-state > "$OUTPUT/raw/adb-state-private.txt" 2>&1
ADB_STATE_RC=$?
[ "$ADB_STATE_RC" -eq 0 ] || die "phone is not available through adb"

ACTIVE_USER="$("$ADB" -s "$PHONE" shell am get-current-user 2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
case "$ACTIVE_USER" in
  ''|*[!0-9]*) die "could not resolve active Android user" ;;
esac
echo "ACTIVE_USER=$ACTIVE_USER"

"$ADB" -s "$PHONE" shell pm path "$HI_ROKID" > "$OUTPUT/raw/hi-package-path-private.txt" 2>&1
HI_PATH_RC=$?
[ "$HI_PATH_RC" -eq 0 ] || die "exact global Hi Rokid package is not installed"

"$ADB" -s "$PHONE" shell pm path "$CUSTOM_PACKAGE" > "$OUTPUT/raw/custom-package-path-private.txt" 2>&1
CUSTOM_PATH_RC=$?
[ "$CUSTOM_PATH_RC" -eq 0 ] || die "Test20 final custom companion is not installed"

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
  "Confirm Hi Rokid currently shows the glasses connected and stable. Do not use camera, audio, Assistant, translation, or any other media function."; then
  die "normal connected baseline was not explicitly confirmed"
fi

snapshot_runtime "baseline"
cp "$OUTPUT/raw/state-baseline.txt" "$OUTPUT/raw/state-pre-force.txt"
if ! grep -q '^HI_PROCESS_VISIBLE=YES$' "$OUTPUT/raw/state-pre-force.txt"; then
  die "Hi Rokid process is not visible in the required normal baseline"
fi

RUN_ID="test21-r2-$(date -u +%Y%m%dT%H%M%SZ)"
OPERATOR_GATE_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
[ -n "$OPERATOR_GATE_TOKEN" ] || die "could not create inert operator-gate token"

echo
echo "=== CUSTOM APP AUTHORIZATION BASELINE ==="
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" >/dev/null 2>&1
"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$CUSTOM_LAUNCHER" \
  --es run_id "$RUN_ID" \
  --es firmware_label "test21-r2-session-ownership" \
  --es operator_gate_token "$OPERATOR_GATE_TOKEN" \
  > "$OUTPUT/raw/custom-launch-private.txt" 2>&1
LAUNCH_RC=$?
[ "$LAUNCH_RC" -eq 0 ] || die "failed to launch custom companion"

pause_enter "AUTHORIZATION BASELINE

On the phone, perform ONLY this action:
  1. Tap '1. Authorize through Hi Rokid' once.
  2. Complete/approve the Hi Rokid authorization flow.
  3. Return to the custom app and wait until it says the authorization token was received and the connection button is enabled.

DO NOT tap the connection button yet.
DO NOT touch item 3.
DO NOT perform any photo or audio action."

PRE_EVENTS="$OUTPUT/raw/pre-force-events-private.jsonl"
pull_events "$PRE_EVENTS" || die "could not pull custom-app event stream after authorization"

python3 "$ANALYZER" --mode preforce --evidence "$OUTPUT" \
  > "$OUTPUT/preforce-gate.txt" 2>&1
PREFORCE_RC=$?
cat "$OUTPUT/preforce-gate.txt"
[ "$PREFORCE_RC" -eq 0 ] || die "pre-force authorization/media-safety gate failed"

snapshot_runtime "pre-force"
CUSTOM_PID_BEFORE="$("$ADB" -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')"
[ -n "$CUSTOM_PID_BEFORE" ] || die "custom companion process is not alive before Hi Rokid force-stop"

echo
echo "=== CONTROLLED HI ROKID FORCE-STOP ==="
echo "The host will now force-stop only $HI_ROKID."
echo "The custom companion remains alive so its authorization token stays only in memory."

"$ADB" -s "$PHONE" shell am force-stop "$HI_ROKID" \
  > "$OUTPUT/raw/hi-force-stop-private.txt" 2>&1
FORCE_RC=$?
[ "$FORCE_RC" -eq 0 ] || die "Hi Rokid force-stop command failed"
HI_FORCE_STOP_ISSUED=1

ABSENT_OBSERVED="NO"
attempt=1
while [ "$attempt" -le 10 ]; do
  current="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"
  if [ -z "$current" ]; then
    ABSENT_OBSERVED="YES"
    break
  fi
  sleep 1
  attempt=$((attempt + 1))
done
cat > "$OUTPUT/raw/force-stop-observation.txt" <<EOF
SCHEMA=rokid.test21-r2.force-stop-observation.v1
FORCE_STOP_COMMAND_RC=$FORCE_RC
HI_PROCESS_ABSENT_OBSERVED=$ABSENT_OBSERVED
OBSERVATION_ATTEMPTS=$attempt
EOF

snapshot_runtime "post-force-immediate"
sleep 4
snapshot_runtime "post-force-settled"

CUSTOM_PID_SETTLED="$("$ADB" -s "$PHONE" shell pidof "$CUSTOM_PACKAGE" 2>/dev/null | tr -d '\r')"
HI_PID_SETTLED="$("$ADB" -s "$PHONE" shell pidof "$HI_ROKID" 2>/dev/null | tr -d '\r')"

SKIP_CONNECT="NO"
if [ "$ABSENT_OBSERVED" != "YES" ]; then
  echo "STOP: process absence was never observed after the controlled force-stop."
  SKIP_CONNECT="YES"
fi
if [ -z "$CUSTOM_PID_SETTLED" ]; then
  echo "STOP: custom companion process did not survive; in-memory token continuity cannot be assumed."
  SKIP_CONNECT="YES"
fi
if [ -n "$HI_PID_SETTLED" ]; then
  echo "STOP: Hi Rokid respawned before any custom connection attempt."
  SKIP_CONNECT="YES"
fi

if [ "$SKIP_CONNECT" = "NO" ]; then
  pause_enter "SESSION-OWNERSHIP ATTEMPT

Hi Rokid has been force-stopped and its process absence was observed.
The custom companion is still alive with the authorization token only in memory.

On the custom app, perform ONLY this action:
  - Tap '2. Start one photo connection' EXACTLY ONCE.

Then wait until the app either:
  - reports 'PHASE 1 COMPLETE — PHOTO LOCKED', OR
  - reports a terminal connection outcome.

DO NOT tap item 1 again.
DO NOT tap item 3.
DO NOT perform any photo or audio action."

  pause_enter "When the custom app has reached either the PHOTO LOCKED prerequisite-ready state or a terminal connection outcome, return here."
else
  echo "CUSTOM_CONNECTION_ATTEMPT_SKIPPED=YES"
fi

sleep 2
snapshot_runtime "post-connect"

FINAL_EVENTS="$OUTPUT/raw/final-events-private.jsonl"
pull_events "$FINAL_EVENTS" || {
  cp "$PRE_EVENTS" "$FINAL_EVENTS"
  echo "FINAL_EVENT_PULL_FALLBACK=PRE_FORCE_EVENTS" > "$OUTPUT/raw/final-event-fallback.txt"
}

echo
echo "=== CUSTOM APP CLEAN DISCONNECT ==="
"$ADB" -s "$PHONE" shell am force-stop "$CUSTOM_PACKAGE" \
  > "$OUTPUT/raw/custom-force-stop-private.txt" 2>&1
CUSTOM_STOP_RC=$?
echo "CUSTOM_APP_FORCE_STOP_RC=$CUSTOM_STOP_RC"

echo
echo "=== HI ROKID RESTORATION ==="
restore_hi_rokid
RESTORE_START_RC=$?
sleep 5
snapshot_runtime "restored"

if [ "$RESTORE_START_RC" -eq 0 ] &&
   prompt_exact "HI_ROKID_RECOVERY_PASS" \
     "Confirm Hi Rokid is open again and the glasses have returned to the normal usable/connected state. Do not perform a media action."; then
  OPERATOR_RECOVERY="PASS"
else
  OPERATOR_RECOVERY="FAIL"
fi
echo "OPERATOR_HI_ROKID_RECOVERY=$OPERATOR_RECOVERY" >> "$OUTPUT/raw/state-restored.txt"

if [ "$OPERATOR_RECOVERY" = "PASS" ]; then
  HI_RESTORED=1
fi

cat > "$OUTPUT/run-metadata.txt" <<EOF
SCHEMA=rokid.test21-r2.run-metadata.v1
RUN_ID=$RUN_ID
HI_ROKID_PACKAGE=$HI_ROKID
CUSTOM_PACKAGE=$CUSTOM_PACKAGE
CUSTOM_VERSION=$CUSTOM_VERSION
AUTHORIZATION_TOKEN_HANDLING=IN_MEMORY_ONLY
AUTHORIZATION_TOKEN_HOST_EXPORT=NONE
AUTHORIZATION_TOKEN_PERSISTENCE_BY_TEST21=NONE
HI_ROKID_FORCE_STOP=ONE_CONTROLLED_ATTEMPT
PACKAGE_DISABLE_OR_UNINSTALL=NONE
PACKAGE_DATA_CLEAR=NONE
PHOTO_OPERATION=NONE
AUDIO_OPERATION=NONE
FIRMWARE_OPERATION=NONE
EOF

echo
echo "=== FINAL ANALYSIS ==="
python3 "$ANALYZER" --mode final --evidence "$OUTPUT"
ANALYZE_RC=$?

echo
echo "============================================================"
echo "TEST21_R2_RUN_RC=$ANALYZE_RC"
echo "PRIVATE_EVIDENCE_ROOT=$OUTPUT"
echo "HI_ROKID_FORCE_STOP=ONE_CONTROLLED_ATTEMPT"
echo "HI_ROKID_RESTORATION=$OPERATOR_RECOVERY"
echo "AUTHORIZATION_TOKEN_HOST_EXPORT=NONE"
echo "PACKAGE_DISABLE_OR_UNINSTALL=NONE"
echo "PACKAGE_DATA_CLEAR=NONE"
echo "PHOTO_OPERATION=NONE"
echo "AUDIO_OPERATION=NONE"
echo "FIRMWARE_OPERATION=NONE"
echo "TERMINAL_REMAINS_OPEN=YES"
echo "============================================================"

exit "$ANALYZE_RC"
