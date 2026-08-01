#!/bin/bash
# Test 20 r3.2.1.3 — Script/APK Operator-Gate Synchronization
# and Two-Phase Photo Arming
#
# macOS Bash 3.2 compatible. Intentionally does not enable set -e/-u/pipefail.

RESULT=0
REPO=""
PHONE=""
FIRMWARE=""
FIRMWARE_SCREENSHOT=""
OUTPUT=""
EXPECTED_HI_ROKID_VERSION="G1.11.11.0727"
REMOTE_EVENTS=""
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
PKG="org.aimindseye.rokid.cxrphotoqualification"
HI_ROKID="com.rokid.sprite.global.aiapp"
BASE_VERSION="1.0-test20-r3.2.1.3"
ARM_ACTION="org.aimindseye.rokid.cxrphotoqualification.ARM_ONE_PHOTO"
TTY="/dev/tty"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/tests/run_test20_r3_2_1_photo_repair.sh \
    --repo PATH \
    --phone ADB_SERIAL \
    --firmware EXACT_VERSION \
    --firmware-screenshot IMAGE \
    --output DIR \
    [--expected-hi-rokid-version VERSION] \
    [--remote-events DEVICE_PATH]

This repair uses two mechanical phases. The APK photo control remains disabled
until the host prerequisite analyzer passes and sends a run-scoped tokenized arm.
The controller then permits exactly one request and consumes the arm atomically.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  RESULT=1
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

utc_now() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

sha256_file() {
  /usr/bin/shasum -a 256 "$1" | awk '{print $1}'
}

file_bytes() {
  if stat -f '%z' "$1" >/dev/null 2>&1; then
    stat -f '%z' "$1"
  else
    stat -c '%s' "$1" 2>/dev/null
  fi
}

random_token_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32 2>/dev/null
    return $?
  fi
  python3 - <<'PYTOKEN'
import secrets
print(secrets.token_hex(32))
PYTOKEN
}

prompt_exact() {
  expected="$1"
  message="$2"
  answer=""
  printf '\n%s\n' "$message" > "$TTY"
  printf 'Type exactly: %s\n> ' "$expected" > "$TTY"
  IFS= read -r answer < "$TTY" || return 1
  [ "$answer" = "$expected" ]
}

prompt_text() {
  message="$1"
  answer=""
  printf '\n%s\n> ' "$message" > "$TTY"
  IFS= read -r answer < "$TTY" || return 1
  printf '%s' "$answer"
}

pause_enter() {
  message="$1"
  ignored=""
  printf '\n%s\n' "$message" > "$TTY"
  printf 'Press Enter when complete... ' > "$TTY"
  IFS= read -r ignored < "$TTY" || return 1
  return 0
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --phone) PHONE="$2"; shift 2 ;;
    --firmware) FIRMWARE="$2"; shift 2 ;;
    --firmware-screenshot) FIRMWARE_SCREENSHOT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --expected-hi-rokid-version) EXPECTED_HI_ROKID_VERSION="$2"; shift 2 ;;
    --remote-events) REMOTE_EVENTS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

[ -n "$REPO" ] || die "--repo is required"
[ -n "$PHONE" ] || die "--phone is required"
[ -n "$FIRMWARE" ] || die "--firmware is required"
[ -n "$FIRMWARE_SCREENSHOT" ] || die "--firmware-screenshot is required"
[ -n "$OUTPUT" ] || die "--output is required"
[ -d "$REPO/.git" ] || die "not a git repository: $REPO"
[ -x "$ADB" ] || ADB="$(command -v adb 2>/dev/null)"
[ -n "$ADB" ] && [ -x "$ADB" ] || die "adb is unavailable"
[ -r "$TTY" ] && [ -w "$TTY" ] || die "/dev/tty is unavailable"
[ -s "$FIRMWARE_SCREENSHOT" ] || die "firmware screenshot is missing or empty: $FIRMWARE_SCREENSHOT"

echo "$FIRMWARE" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$' ||
  die "--firmware must be an exact non-whitespace version label"

RUN_ID="cxrl-one-shot-photo-r3.2.1.3-${FIRMWARE}-$(date -u +%Y%m%dT%H%M%SZ)"
ARM_TOKEN="$(random_token_hex)"
[ -n "$ARM_TOKEN" ] || die "could not generate host-arm token"
ARM_TOKEN_HASH="$(printf '%s' "$ARM_TOKEN" | /usr/bin/shasum -a 256 | awk '{print $1}')"
mkdir -p "$OUTPUT/private" "$OUTPUT/sanitized" "$OUTPUT/diagnostics"
MKDIR_RC=$?
[ "$MKDIR_RC" -eq 0 ] || die "cannot create output directory: $OUTPUT"

SOURCE_CHECK="$REPO/scripts/tests/check_test20_r3_2_1_source_contract.py"
ANALYZER="$REPO/scripts/tests/analyze_test20_r3_2_1_photo_repair.py"
[ -x "$SOURCE_CHECK" ] || die "source-contract checker missing: $SOURCE_CHECK"
[ -x "$ANALYZER" ] || die "r3.2.1 analyzer missing: $ANALYZER"

python3 "$SOURCE_CHECK" --repo "$REPO" --output "$OUTPUT/diagnostics/source-contract.json"
SOURCE_RC=$?
[ "$SOURCE_RC" -eq 0 ] || die "r3.2 base source contract is not safe enough to run"

"$ADB" -s "$PHONE" get-state > "$OUTPUT/diagnostics/phone-adb-state.txt" 2>&1
ADB_RC=$?
[ "$ADB_RC" -eq 0 ] || die "phone is not available through adb"

echo "device" | grep -qx "$(tr -d '\r\n' < "$OUTPUT/diagnostics/phone-adb-state.txt")" ||
  die "phone is not in adb state=device"

ACTIVE_USER="$("$ADB" -s "$PHONE" shell am get-current-user 2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
echo "$ACTIVE_USER" | grep -Eq '^[0-9]+$' || die "could not resolve active Android user"

"$ADB" -s "$PHONE" shell dumpsys package "$HI_ROKID" > "$OUTPUT/private/hi-rokid-dumpsys-package.txt" 2>&1
HI_DUMP_RC=$?
[ "$HI_DUMP_RC" -eq 0 ] || die "Hi Rokid package is not readable"
HI_VERSION="$(grep -m1 'versionName=' "$OUTPUT/private/hi-rokid-dumpsys-package.txt" | sed -E 's/.*versionName=([^[:space:]]+).*/\1/')"
[ "$HI_VERSION" = "$EXPECTED_HI_ROKID_VERSION" ] ||
  die "Hi Rokid version mismatch: expected $EXPECTED_HI_ROKID_VERSION, found ${HI_VERSION:-UNRESOLVED}"

"$ADB" -s "$PHONE" shell dumpsys package "$PKG" > "$OUTPUT/private/test-app-dumpsys-package.txt" 2>&1
APP_DUMP_RC=$?
[ "$APP_DUMP_RC" -eq 0 ] || die "r3.2 photo qualification app is not installed"
APP_VERSION="$(grep -m1 'versionName=' "$OUTPUT/private/test-app-dumpsys-package.txt" | sed -E 's/.*versionName=([^[:space:]]+).*/\1/')"
[ "$APP_VERSION" = "$BASE_VERSION" ] ||
  die "r3.2 base app version mismatch: expected $BASE_VERSION, found ${APP_VERSION:-UNRESOLVED}"

PHONE_HASH="$(printf '%s' "$PHONE" | /usr/bin/shasum -a 256 | awk '{print $1}')"
SCREENSHOT_HASH="$(sha256_file "$FIRMWARE_SCREENSHOT")"
SCREENSHOT_BYTES="$(file_bytes "$FIRMWARE_SCREENSHOT")"

case "$(basename "$FIRMWARE_SCREENSHOT")" in
  *.*) SCREENSHOT_EXT=".${FIRMWARE_SCREENSHOT##*.}" ;;
  *) SCREENSHOT_EXT=".bin" ;;
esac
SCREENSHOT_COPY="$OUTPUT/private/firmware-screenshot-private$SCREENSHOT_EXT"
cp "$FIRMWARE_SCREENSHOT" "$SCREENSHOT_COPY"
COPY_RC=$?
[ "$COPY_RC" -eq 0 ] && [ -s "$SCREENSHOT_COPY" ] || die "failed to preserve firmware screenshot"
[ "$(sha256_file "$SCREENSHOT_COPY")" = "$SCREENSHOT_HASH" ] || die "firmware screenshot copy hash mismatch"

printf '\nFirmware attestation repair\n===========================\n' > "$TTY"
printf 'On the phone, open the Hi Rokid firmware/version page that produced the supplied screenshot.\n' > "$TTY"
printf 'Read the COMPLETE firmware string from the UI; do not infer it from the filename or this command.\n' > "$TTY"
VISIBLE_FIRMWARE="$(prompt_text "Enter the complete firmware string exactly as visibly shown in Hi Rokid:")"
[ "$VISIBLE_FIRMWARE" = "$FIRMWARE" ] || die "visible firmware does not exactly match --firmware; photo remains unarmed"

cat > "$OUTPUT/firmware-attestation.txt" <<EOF
TEST20_R3_2_1_SCHEMA=rokid.test20-r3.2.1.firmware-attestation.v1
FIRMWARE_LABEL=$FIRMWARE
OPERATOR_VISIBLE_FIRMWARE=$VISIBLE_FIRMWARE
OPERATOR_EXACT_MATCH=PASS
OCR_USED=NO
SCREENSHOT_SHA256=$SCREENSHOT_HASH
SCREENSHOT_BYTES=$SCREENSHOT_BYTES
ATTESTED_UTC=$(utc_now)
EOF

cat > "$OUTPUT/run-metadata.txt" <<EOF
TEST20_R3_2_1_SCHEMA=rokid.test20-r3.2.1.3.run-metadata.v1
RUN_ID=$RUN_ID
FIRMWARE=$FIRMWARE
PHONE_SERIAL_SHA256=$PHONE_HASH
HI_ROKID_VERSION=$HI_VERSION
PACKAGE=$PKG
BASE_VERSION_NAME=$BASE_VERSION
OPERATOR_GATE_MODE=TWO_PHASE_HOST_TOKENIZED_ARM
OPERATOR_GATE_ACTION=$ARM_ACTION
OPERATOR_GATE_TOKEN_SHA256=$ARM_TOKEN_HASH
OPERATOR_GATE_TOKEN_VALUE_LOGGED=NO
PHOTO_ARG_1=1920
PHOTO_ARG_2=1080
PHOTO_ARG_3=80
PHOTO_ARGUMENT_SEMANTICS=WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED
MAX_PHOTO_REQUEST_COUNT=1
IMAGE_PAYLOAD_PERSISTENCE=NONE
IMAGE_PREVIEW=NONE
AUDIO_OPERATION=NONE
CLOUD_REQUEST=NONE
FIRMWARE_ATTESTATION_MODE=EXACT_OPERATOR_VISIBLE_STRING_PLUS_SCREENSHOT_SHA256
OCR_USED=NO
EOF

if ! prompt_exact "HI_ROKID_CONNECTED" "Confirm Hi Rokid currently shows the glasses connected and stable. Do not perform any media action."; then
  die "stock connection prerequisite was not explicitly attested; photo remains unarmed"
fi

LAUNCHER="$("$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$PKG" 2>/dev/null | tr -d '\r' | awk 'NF{line=$0} END{print line}')"
case "$LAUNCHER" in
  "$PKG"/*) ;;
  *) die "could not resolve r3.2 test app launcher" ;;
esac

"$ADB" -s "$PHONE" shell am force-stop "$PKG" >/dev/null 2>&1
"$ADB" -s "$PHONE" shell pm clear --user "$ACTIVE_USER" "$PKG" > "$OUTPUT/private/app-clear.txt" 2>&1
CLEAR_RC=$?
[ "$CLEAR_RC" -eq 0 ] || die "failed to clear r3.2 app state"

"$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$LAUNCHER" \
  --es run_id "$RUN_ID" \
  --es firmware_label "$FIRMWARE" \
  --es operator_gate_token "$ARM_TOKEN" \
  > "$OUTPUT/private/app-launch.txt" 2>&1
LAUNCH_RC=$?
[ "$LAUNCH_RC" -eq 0 ] || die "failed to launch r3.2 app"

if [ -z "$REMOTE_EVENTS" ]; then
  REMOTE_EVENTS="/sdcard/Android/data/$PKG/files/test20-r3-2/test20-r3-2-$RUN_ID.jsonl"
fi

pause_enter "PHASE 1 — PHOTO MECHANICALLY LOCKED

On the phone, the APK must show a disabled item 3 labeled PHOTO LOCKED.
Perform ONLY these APK actions:
  1. tap '1. Authorize through Hi Rokid' once;
  2. after authorization returns, tap '2. Start one photo connection' once;
  3. wait until the APK says 'PHASE 1 COMPLETE — PHOTO LOCKED'.

Do NOT tap item 3. It must remain disabled throughout Phase 1.
Return here only after the APK explicitly reports PHASE 1 COMPLETE — PHOTO LOCKED."
PREP_RC=$?
[ "$PREP_RC" -eq 0 ] || die "operator interrupted before prerequisite collection"

resolve_remote_events() {
  requested="$1"
  if "$ADB" -s "$PHONE" shell "test -s '$requested'" >/dev/null 2>&1; then
    printf '%s' "$requested"
    return 0
  fi
  candidate="$("$ADB" -s "$PHONE" shell "find /sdcard/Android/data/$PKG/files -type f -name '*$RUN_ID*.jsonl' 2>/dev/null | head -n 1" 2>/dev/null | tr -d '\r' | awk 'NF{print; exit}')"
  [ -n "$candidate" ] || return 1
  printf '%s' "$candidate"
  return 0
}

ACTUAL_REMOTE="$(resolve_remote_events "$REMOTE_EVENTS")"
[ -n "$ACTUAL_REMOTE" ] || die "could not locate r3.2 JSONL event stream; photo remains unarmed"
printf '%s\n' "$ACTUAL_REMOTE" > "$OUTPUT/private/remote-events-path-private.txt"

PRE_EVENTS="$OUTPUT/private/pre-photo-events-private.jsonl"
"$ADB" -s "$PHONE" pull "$ACTUAL_REMOTE" "$PRE_EVENTS" > "$OUTPUT/private/pre-photo-pull.txt" 2>&1
PULL_PRE_RC=$?
[ "$PULL_PRE_RC" -eq 0 ] && [ -s "$PRE_EVENTS" ] || die "failed to pull pre-photo event stream; photo remains unarmed"

python3 "$ANALYZER" \
  --mode prerequisite \
  --events "$PRE_EVENTS" \
  --firmware "$FIRMWARE" \
  --firmware-attestation "$OUTPUT/firmware-attestation.txt" \
  --summary "$OUTPUT/sanitized/prerequisite-summary.json" \
  > "$OUTPUT/prerequisite-gate.txt" 2>&1
PRE_GATE_RC=$?
cat "$OUTPUT/prerequisite-gate.txt"
[ "$PRE_GATE_RC" -eq 0 ] || die "control-path prerequisite gate failed; photo request was NOT armed"

printf '\nPHASE 1 MACHINE GATE=PASS\n'
printf 'Host is now issuing the run-scoped one-photo arm command. Do not touch the APK yet.\n'

"$ADB" -s "$PHONE" shell am broadcast --user "$ACTIVE_USER" \
  -a "$ARM_ACTION" \
  -p "$PKG" \
  --es run_id "$RUN_ID" \
  --es operator_gate_token "$ARM_TOKEN" \
  > "$OUTPUT/private/host-arm-broadcast-private.txt" 2>&1
ARM_BROADCAST_RC=$?
[ "$ARM_BROADCAST_RC" -eq 0 ] || die "host arm broadcast failed; photo remains locked"
sleep 1

ARMED_EVENTS="$OUTPUT/private/armed-events-private.jsonl"
"$ADB" -s "$PHONE" pull "$ACTUAL_REMOTE" "$ARMED_EVENTS" > "$OUTPUT/private/armed-events-pull.txt" 2>&1
ARMED_PULL_RC=$?
[ "$ARMED_PULL_RC" -eq 0 ] && [ -s "$ARMED_EVENTS" ] || die "failed to pull armed-phase event stream; do not tap photo"

python3 "$ANALYZER" \
  --mode armed \
  --events "$ARMED_EVENTS" \
  --firmware "$FIRMWARE" \
  --firmware-attestation "$OUTPUT/firmware-attestation.txt" \
  --summary "$OUTPUT/sanitized/armed-summary.json" \
  > "$OUTPUT/armed-gate.txt" 2>&1
ARMED_GATE_RC=$?
cat "$OUTPUT/armed-gate.txt"
[ "$ARMED_GATE_RC" -eq 0 ] || die "two-phase host/APK armed gate failed; do not tap photo"

if ! prompt_exact "APK_SHOWS_PHASE_2_ARMED" "Look at the APK now. Item 3 must be enabled and must read 'PHASE 2 — ARMED: capture ONE photo'. If it does not, do not continue."; then
  die "operator could not confirm synchronized Phase 2 armed UI"
fi

pause_enter "PHASE 2 — EXACTLY ONE PHOTO

Point the glasses only at the printed Test 20 target.
Tap the enabled '3. PHASE 2 — ARMED: capture ONE photo' button EXACTLY ONCE.
The button must immediately disable and change to PHOTO REQUEST CONSUMED.
Do not tap any other camera/media/audio/Assistant action.
Wait for the APK terminal result, then return here."
PHOTO_RC=$?
[ "$PHOTO_RC" -eq 0 ] || die "operator interrupted during armed photo phase"

FINAL_EVENTS="$OUTPUT/private/final-events-private.jsonl"
"$ADB" -s "$PHONE" pull "$ACTUAL_REMOTE" "$FINAL_EVENTS" > "$OUTPUT/private/final-events-pull.txt" 2>&1
PULL_FINAL_RC=$?
[ "$PULL_FINAL_RC" -eq 0 ] && [ -s "$FINAL_EVENTS" ] || die "failed to pull final event stream"

if prompt_exact "NO_OTHER_MEDIA_ACTION" "Attest only to the concrete operator action: outside the single r3.2 photo action, no other camera, photo, audio, translation, Assistant, or media action was performed during the armed phase."; then
  ADDITIONAL_MEDIA_ACTION="NO"
else
  ADDITIONAL_MEDIA_ACTION="YES_OR_UNRESOLVED"
fi

"$ADB" -s "$PHONE" shell am force-stop "$PKG" >/dev/null 2>&1
HI_LAUNCHER="$("$ADB" -s "$PHONE" shell cmd package resolve-activity --brief --user "$ACTIVE_USER" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$HI_ROKID" 2>/dev/null | tr -d '\r' | awk 'NF{line=$0} END{print line}')"
case "$HI_LAUNCHER" in
  "$HI_ROKID"/*)
    "$ADB" -s "$PHONE" shell am start -W --user "$ACTIVE_USER" -n "$HI_LAUNCHER" > "$OUTPUT/private/hi-rokid-relaunch.txt" 2>&1
    HI_RELAUNCH_RC=$?
    ;;
  *)
    printf 'ERROR: Hi Rokid launcher resolution failed: %s\n' "$HI_LAUNCHER" > "$OUTPUT/private/hi-rokid-relaunch.txt"
    HI_RELAUNCH_RC=1
    ;;
esac

if [ "$HI_RELAUNCH_RC" -eq 0 ] && prompt_exact "HI_ROKID_RECOVERY_PASS" "Confirm Hi Rokid has reopened and recovered to its normal usable/connected state."; then
  HI_RECOVERY="PASS"
else
  HI_RECOVERY="FAIL"
fi

cat > "$OUTPUT/operator-attestation.txt" <<EOF
TEST20_R3_2_1_SCHEMA=rokid.test20-r3.2.1.3.operator-attestation.v1
PREREQUISITE_GATE=PASS
FIRMWARE_EXACT_MATCH=PASS
HOST_ARM_GATE=PASS
APK_ARMED_UI_CONFIRMED=PASS
PHOTO_ARM_GRANTED=YES
ADDITIONAL_MEDIA_ACTION=$ADDITIONAL_MEDIA_ACTION
HI_ROKID_RECOVERY=$HI_RECOVERY
BOUNDING_DECISION_SOURCE=MACHINE_EVIDENCE_PLUS_TWO_PHASE_HOST_APK_GATE_PLUS_CONCRETE_OPERATOR_ATTESTATION
ATTESTED_UTC=$(utc_now)
EOF

python3 "$ANALYZER" \
  --mode final \
  --events "$FINAL_EVENTS" \
  --firmware "$FIRMWARE" \
  --firmware-attestation "$OUTPUT/firmware-attestation.txt" \
  --operator-attestation "$OUTPUT/operator-attestation.txt" \
  --summary "$OUTPUT/sanitized/test20-r3-2-1-summary.json" \
  > "$OUTPUT/final-gate.txt" 2>&1
FINAL_GATE_RC=$?
cat "$OUTPUT/final-gate.txt"

# Build an upload-safe summary bundle without the screenshot, raw JSONL, package
# dumps, paths, tokens, or image payloads.
cp "$OUTPUT/run-metadata.txt" "$OUTPUT/sanitized/run-metadata.txt"
cp "$OUTPUT/firmware-attestation.txt" "$OUTPUT/sanitized/firmware-attestation.txt"
cp "$OUTPUT/operator-attestation.txt" "$OUTPUT/sanitized/operator-attestation.txt"
grep '^TEST20_R3_2_1_' "$OUTPUT/final-gate.txt" > "$OUTPUT/sanitized/final-gate-status.txt" 2>/dev/null || true

SANITIZED_ZIP="${OUTPUT}-sanitized-summary.zip"
rm -f "$SANITIZED_ZIP"
(
  cd "$OUTPUT" || exit 1
  /usr/bin/zip -qry "$SANITIZED_ZIP" sanitized
)
SANITIZED_ZIP_RC=$?
if [ "$SANITIZED_ZIP_RC" -eq 0 ] && [ -s "$SANITIZED_ZIP" ]; then
  SANITIZED_SHA="$(sha256_file "$SANITIZED_ZIP")"
  printf '%s  %s\n' "$SANITIZED_SHA" "$(basename "$SANITIZED_ZIP")" > "${SANITIZED_ZIP}.sha256.txt"
else
  fail "sanitized summary ZIP creation failed"
fi

(
  cd "$OUTPUT" || exit 1
  find . -type f ! -name 'SHA256SUMS-private.txt' ! -name '*-private-evidence.zip' -print | LC_ALL=C sort | while IFS= read -r path; do
    /usr/bin/shasum -a 256 "$path"
  done > SHA256SUMS-private.txt
)
MANIFEST_RC=$?
[ "$MANIFEST_RC" -eq 0 ] || fail "private evidence manifest generation failed"

ZIP_PATH="${OUTPUT}-private-evidence.zip"
rm -f "$ZIP_PATH"
(
  cd "$(dirname "$OUTPUT")" || exit 1
  /usr/bin/zip -qry "$ZIP_PATH" "$(basename "$OUTPUT")"
)
ZIP_RC=$?
if [ "$ZIP_RC" -eq 0 ] && [ -s "$ZIP_PATH" ]; then
  ZIP_SHA="$(sha256_file "$ZIP_PATH")"
  printf '%s  %s\n' "$ZIP_SHA" "$(basename "$ZIP_PATH")" > "${ZIP_PATH}.sha256.txt"
else
  fail "private evidence ZIP creation failed"
fi

printf '\nTest 20 r3.2.1.3 result\n========================\n'
printf 'Prerequisite gate: PASS\n'
printf 'Firmware exact-match gate: PASS\n'
printf 'Two-phase armed gate: PASS\n'
printf 'Final gate: %s\n' "$( [ "$FINAL_GATE_RC" -eq 0 ] && echo PASS || echo FAIL )"
printf 'Evidence directory: %s\n' "$OUTPUT"
if [ -s "$ZIP_PATH" ]; then
  printf 'Private evidence ZIP: %s\n' "$ZIP_PATH"
  printf 'ZIP SHA-256: %s\n' "$(sha256_file "$ZIP_PATH")"
fi
if [ -s "${OUTPUT}-sanitized-summary.zip" ]; then
  printf 'Sanitized upload ZIP: %s\n' "${OUTPUT}-sanitized-summary.zip"
  printf 'Sanitized ZIP SHA-256: %s\n' "$(sha256_file "${OUTPUT}-sanitized-summary.zip")"
fi

[ "$FINAL_GATE_RC" -eq 0 ] || RESULT=1
exit "$RESULT"
