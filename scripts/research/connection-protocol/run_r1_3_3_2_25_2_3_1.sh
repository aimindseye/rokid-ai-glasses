#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_r1_3_3_2_25_2_3.sh \
    --repo PATH \
    --phone-serial SERIAL \
    --output PATH \
    [--manual-trigger | --trigger-script PATH] \
    [--adb PATH]

The manual mode is the default. It starts capture, asks you to trigger exactly
one RFCOMM connection without sending data, and asks you to press Enter after
the socket closes.

A trigger script is executed on the Mac with these environment variables:
  R25_2_3_1_ADB, R25_2_3_1_PHONE_SERIAL, R25_2_3_1_CAPTURE_DIR,
  R25_2_3_1_ATTEMPT_ID.
EOF
}

REPO=""
PHONE_SERIAL=""
OUT=""
ADB_BIN="${ADB:-adb}"
LOGCAT_STARTUP_SECONDS="${R25_2_3_1_LOGCAT_STARTUP_SECONDS:-2}"
POST_TRIGGER_SECONDS="${R25_2_3_1_POST_TRIGGER_SECONDS:-2}"
POST_CLOSE_SECONDS="${R25_2_3_1_POST_CLOSE_SECONDS:-1}"
MODE="manual"
TRIGGER_SCRIPT=""
while (($#)); do
  case "$1" in
    --repo) REPO=${2:?}; shift 2 ;;
    --phone-serial) PHONE_SERIAL=${2:?}; shift 2 ;;
    --output) OUT=${2:?}; shift 2 ;;
    --adb) ADB_BIN=${2:?}; shift 2 ;;
    --manual-trigger) MODE="manual"; shift ;;
    --trigger-script) MODE="script"; TRIGGER_SCRIPT=${2:?}; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$REPO" && -n "$PHONE_SERIAL" && -n "$OUT" ]] || { usage >&2; exit 2; }
REPO=$(cd "$REPO" && pwd -P)
OUT_PARENT=$(dirname "$OUT")
mkdir -p "$OUT_PARENT"
[[ ! -e "$OUT" ]] || { echo "Output already exists: $OUT" >&2; exit 1; }
if [[ "$MODE" == script ]]; then
  [[ -f "$TRIGGER_SCRIPT" && -x "$TRIGGER_SCRIPT" ]] || { echo "Trigger script must exist and be executable: $TRIGGER_SCRIPT" >&2; exit 1; }
fi
command -v "$ADB_BIN" >/dev/null 2>&1 || { echo "ADB not found: $ADB_BIN" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
ANALYZER="$SCRIPT_DIR/r25_2_3_1_capture.py"
PREFLIGHT="$SCRIPT_DIR/r25_2_3_1_hci_preflight.py"
[[ -f "$ANALYZER" ]] || { echo "Missing analyzer: $ANALYZER" >&2; exit 1; }
[[ -f "$PREFLIGHT" ]] || { echo "Missing preflight classifier: $PREFLIGHT" >&2; exit 1; }

adb_cmd() { "$ADB_BIN" -s "$PHONE_SERIAL" "$@"; }
phone_epoch() {
  local value
  value=$(adb_cmd shell date +%s 2>/dev/null | tr -d '\r' | tail -1)
  [[ "$value" =~ ^[0-9]{10,}$ ]] || { echo "Unable to read phone epoch: $value" >&2; return 1; }
  printf '%s\n' "$value"
}
epoch_iso() {
  python3 - "$1" <<'PY'
import datetime as d,sys
print(d.datetime.fromtimestamp(float(sys.argv[1]), tz=d.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'))
PY
}

STATE=$(adb_cmd get-state 2>/dev/null | tr -d '\r' || true)
[[ "$STATE" == device ]] || { echo "Phone is not available through ADB: state=$STATE" >&2; exit 1; }

SERIAL_HASH=$(printf '%s' "$PHONE_SERIAL" | shasum -a 256 | awk '{print $1}')
PREFLIGHT_TMP=$(mktemp -d)
PREFLIGHT_JSON="$PREFLIGHT_TMP/probes.json"
PREFLIGHT_RESULT="$PREFLIGHT_TMP/result.json"
HCI_SECURE=$(adb_cmd shell settings get secure bluetooth_hci_log 2>/dev/null | tr -d '\r' | tail -1 || true)
HCI_GLOBAL_DEFAULT=$(adb_cmd shell settings get global bluetooth_btsnoop_default_mode 2>/dev/null | tr -d '\r' | tail -1 || true)
HCI_MODE=$(adb_cmd shell getprop persist.bluetooth.btsnooplogmode 2>/dev/null | tr -d '\r' | tail -1 || true)
HCI_DEFAULT_MODE=$(adb_cmd shell getprop persist.bluetooth.btsnoopdefaultmode 2>/dev/null | tr -d '\r' | tail -1 || true)
HCI_ENABLE=$(adb_cmd shell getprop persist.bluetooth.btsnoopenable 2>/dev/null | tr -d '\r' | tail -1 || true)
HCI_DUMPSYS=$(adb_cmd shell dumpsys bluetooth_manager 2>/dev/null | tr -d '\r' || true)
printf '%s\n' "$HCI_DUMPSYS" > "$PREFLIGHT_TMP/dumpsys.txt"
python3 - "$PREFLIGHT_JSON" "$PREFLIGHT_TMP/dumpsys.txt" "$HCI_SECURE" "$HCI_GLOBAL_DEFAULT" "$HCI_MODE" "$HCI_DEFAULT_MODE" "$HCI_ENABLE" <<'PY_PREFLIGHT_INPUT'
import json,pathlib,sys
path=pathlib.Path(sys.argv[1])
value={
  "dumpsys_bluetooth":pathlib.Path(sys.argv[2]).read_text(encoding="utf-8",errors="replace"),
  "secure_bluetooth_hci_log":sys.argv[3],
  "global_btsnoop_default_mode":sys.argv[4],
  "persist_btsnooplogmode":sys.argv[5],
  "persist_btsnoopdefaultmode":sys.argv[6],
  "persist_btsnoopenable":sys.argv[7],
}
path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY_PREFLIGHT_INPUT
set +e
python3 "$PREFLIGHT" --input "$PREFLIGHT_JSON" --output "$PREFLIGHT_RESULT"
PREFLIGHT_RC=$?
set -e
HCI_PREFLIGHT_STATUS=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$PREFLIGHT_RESULT")
HCI_PREFLIGHT_METHOD=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["method"])' "$PREFLIGHT_RESULT")
if ((PREFLIGHT_RC != 0)); then
  cat >&2 <<EOF
Bluetooth HCI snoop preflight rejected the capture.
Status: $HCI_PREFLIGHT_STATUS
Method: $HCI_PREFLIGHT_METHOD

Observed controls:
  settings global bluetooth_btsnoop_default_mode: ${HCI_GLOBAL_DEFAULT:-UNSET}
  persist.bluetooth.btsnooplogmode:               ${HCI_MODE:-UNSET}
  persist.bluetooth.btsnoopdefaultmode:           ${HCI_DEFAULT_MODE:-UNSET}
  settings secure bluetooth_hci_log (legacy):     ${HCI_SECURE:-UNSET}
  persist.bluetooth.btsnoopenable (legacy):       ${HCI_ENABLE:-UNSET}

For CONFIRMED_FILTERED, select Full HCI snoop logging. For RESTART_REQUIRED,
restart Bluetooth or reboot after changing the setting. No device setting was changed.
EOF
  rm -rf "$PREFLIGHT_TMP"
  exit 1
fi
if [[ "$HCI_PREFLIGHT_STATUS" == PROVISIONAL_UNKNOWN ]]; then
  cat >&2 <<'EOF'
Bluetooth HCI controls are hidden or unset on this build. Continuing provisionally.
This is not treated as proof that logging is enabled: the resulting bugreport must
contain a parseable btsnoop stream, and full closure remains fail-closed otherwise.
EOF
fi

CAPTURE="$OUT/private-evidence"
ANALYSIS="$OUT/private-analysis"
PUBLICATION="$ANALYSIS/publication"
mkdir -p "$CAPTURE" "$ANALYSIS" "$CAPTURE/hci-preflight"
cp "$PREFLIGHT_JSON" "$CAPTURE/hci-preflight/probes.json"
cp "$PREFLIGHT_RESULT" "$CAPTURE/hci-preflight/result.json"
cp "$PREFLIGHT_TMP/dumpsys.txt" "$CAPTURE/hci-preflight/dumpsys-bluetooth-manager.txt"
ATTEMPT_ID="r25-2-3-1-$(date -u +%Y%m%dT%H%M%SZ)-$$"

cleanup() {
  if [[ -n "${LOGCAT_PID:-}" ]] && kill -0 "$LOGCAT_PID" 2>/dev/null; then
    kill "$LOGCAT_PID" 2>/dev/null || true
    wait "$LOGCAT_PID" 2>/dev/null || true
  fi
  [[ -n "${PREFLIGHT_TMP:-}" ]] && rm -rf "$PREFLIGHT_TMP" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

adb_cmd shell getprop > "$CAPTURE/getprop-before.txt" 2> "$CAPTURE/getprop-before.stderr.txt" || true
adb_cmd shell dumpsys bluetooth_manager > "$CAPTURE/dumpsys-bluetooth-before.txt" 2> "$CAPTURE/dumpsys-bluetooth-before.stderr.txt" || true
adb_cmd shell dumpsys package > "$CAPTURE/dumpsys-package-before.txt" 2> "$CAPTURE/dumpsys-package-before.stderr.txt" || true

"$ADB_BIN" -s "$PHONE_SERIAL" logcat -b all -v epoch > "$CAPTURE/logcat-all-epoch.txt" 2> "$CAPTURE/logcat.stderr.txt" &
LOGCAT_PID=$!
sleep "$LOGCAT_STARTUP_SECONDS"
kill -0 "$LOGCAT_PID" 2>/dev/null || { echo "logcat capture did not stay running" >&2; exit 1; }

if [[ "$MODE" == manual ]]; then
  cat <<'EOF'

R25.2.3.1 is ready.

1. Put the phone and glasses in the same connected state used for r25.2.2.2.
2. Open the existing connection-only probe screen, but do not connect yet.
3. Press Enter here to begin the bounded attempt interval.
4. Trigger exactly one RFCOMM connection.
5. Do not send, type, speak, or stream any application data.
6. Let the probe close the socket normally.
7. Press Enter here only after the socket has closed.
EOF
  read -r -p "Press Enter to START the attempt interval: " _
fi
START_EPOCH=$(phone_epoch)
START_UTC=$(epoch_iso "$START_EPOCH")

if [[ "$MODE" == script ]]; then
  R25_2_3_1_ADB="$ADB_BIN" \
  R25_2_3_1_PHONE_SERIAL="$PHONE_SERIAL" \
  R25_2_3_1_CAPTURE_DIR="$CAPTURE" \
  R25_2_3_1_ATTEMPT_ID="$ATTEMPT_ID" \
    "$TRIGGER_SCRIPT" > "$CAPTURE/trigger.stdout.txt" 2> "$CAPTURE/trigger.stderr.txt"
  sleep "$POST_TRIGGER_SECONDS"
else
  read -r -p "Press Enter after the single attempt has CLOSED: " _
fi
END_EPOCH=$(phone_epoch)
END_UTC=$(epoch_iso "$END_EPOCH")

sleep "$POST_CLOSE_SECONDS"
cleanup
LOGCAT_PID=""

adb_cmd shell getprop > "$CAPTURE/getprop-after.txt" 2> "$CAPTURE/getprop-after.stderr.txt" || true
adb_cmd shell dumpsys bluetooth_manager > "$CAPTURE/dumpsys-bluetooth-after.txt" 2> "$CAPTURE/dumpsys-bluetooth-after.stderr.txt" || true
adb_cmd shell dumpsys package > "$CAPTURE/dumpsys-package-after.txt" 2> "$CAPTURE/dumpsys-package-after.stderr.txt" || true

BUGREPORT="$CAPTURE/bugreport.zip"
adb_cmd bugreport "$BUGREPORT" > "$CAPTURE/bugreport.stdout.txt" 2> "$CAPTURE/bugreport.stderr.txt"
[[ -s "$BUGREPORT" ]] || { echo "Bugreport was not created: $BUGREPORT" >&2; exit 1; }

python3 - "$CAPTURE/metadata.json" <<PY
import json, pathlib
path=pathlib.Path(r'''$CAPTURE/metadata.json''')
value={
  "schema":"rokid.r25.2.3.1.capture-metadata.v1",
  "release":"r1.3.3.2.25.2.3.1",
  "attempt_id":r'''$ATTEMPT_ID''',
  "interval_start_epoch":int(r'''$START_EPOCH'''),
  "interval_end_epoch":int(r'''$END_EPOCH'''),
  "interval_start_utc":r'''$START_UTC''',
  "interval_end_utc":r'''$END_UTC''',
  "phone_serial_sha256":r'''$SERIAL_HASH''',
  "hci_preflight":json.loads(pathlib.Path(r'''$CAPTURE/hci-preflight/result.json''').read_text(encoding="utf-8")),
  "expected_dlci":6,
  "trigger_mode":r'''$MODE'''
}
path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY

python3 "$ANALYZER" --capture-dir "$CAPTURE" --output "$ANALYSIS" | tee "$OUT/qualification.log"
python3 - "$ANALYSIS/analysis/r25.2.3.1-private-analysis.json" <<'PY_POST_HCI'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
members=value.get("hci_member_census",[])
parseable=[m for m in members if m.get("record_count",0)>0 and not any(str(e).startswith("parse_error:") for e in m.get("errors",[]))]
qualifying=[m for m in members if m.get("qualifies")]
print(f"R25_2_3_1_HCI_POST_BUGREPORT_PARSEABLE={'YES' if parseable else 'NO'}")
print(f"R25_2_3_1_HCI_POST_BUGREPORT_QUALIFYING={'YES' if qualifying else 'NO'}")
print("R25_2_3_1_HCI_READINESS_AUTHORITY=POST_BUGREPORT_BTSNOOP_EVIDENCE")
PY_POST_HCI

python3 - "$CAPTURE" "$ANALYSIS" "$OUT" <<'PY'
import hashlib, pathlib, re, sys, zipfile
cap, ana, out = map(pathlib.Path, sys.argv[1:])
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def write_manifest(root, name):
    lines=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name != name:
            lines.append(f"{sha(p)}  {p.relative_to(root).as_posix()}")
    (root/name).write_text("\n".join(lines)+"\n",encoding='utf-8')
def zip_tree(root, dest):
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(root.rglob('*')):
            if p.is_symlink(): raise SystemExit(f"symlink rejected: {p}")
            if p.is_file(): z.write(p,p.relative_to(root.parent).as_posix())
write_manifest(cap,'SHA256SUMS-private.txt')
write_manifest(ana,'SHA256SUMS-private-analysis.txt')
publication=ana/'publication'
# Sanitized publication must not contain full Bluetooth addresses or raw serials.
for p in publication.rglob('*'):
    if p.is_file():
        text=p.read_text(encoding='utf-8',errors='replace')
        if re.search(r'(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b',text):
            raise SystemExit(f"publication privacy gate failed: full Bluetooth address in {p}")
zip_tree(cap, pathlib.Path(str(out)+'-private-evidence.zip'))
zip_tree(ana, pathlib.Path(str(out)+'-private-analysis.zip'))
zip_tree(publication, pathlib.Path(str(out)+'-sanitized-publication.zip'))
for suffix in ('-private-evidence.zip','-private-analysis.zip','-sanitized-publication.zip'):
    p=pathlib.Path(str(out)+suffix)
    print(f"{p.name.upper().replace('.','_').replace('-','_')}_SHA256={sha(p)}")
    print(f"R25_2_3_1_ARTIFACT={p}")
PY

printf 'R25_2_3_1_OUTPUT=%s\n' "$OUT"
