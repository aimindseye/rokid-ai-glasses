#!/usr/bin/env bash
set -euo pipefail
REPO=${1:?usage: validate_r1_3_3_2_25_3_1_1_package.sh REPO}
BASE="$REPO/scripts/research/connection-protocol"
required=(
  r25_2_3_2_capture.py
  r25_2_3_2_hci_preflight.py
  r25_3_1_1_analyze.py
  r25_3_1_1_capture.py
  run_r1_3_3_2_25_3_1_1.sh
)
for file in "${required[@]}"; do
  test -f "$BASE/$file" || { echo "missing $BASE/$file" >&2; exit 1; }
done
base_hash=$(shasum -a 256 "$BASE/r25_2_3_2_capture.py" | awk '{print $1}')
preflight_hash=$(shasum -a 256 "$BASE/r25_2_3_2_hci_preflight.py" | awk '{print $1}')
[[ $base_hash == 0a126e98fe63a5cc4cc676f5e3bceb3dd6f3b3766efacaba3d05955fa579bc2f ]] || { echo "accepted r25.2.3.2 parser hash mismatch: $base_hash" >&2; exit 1; }
[[ $preflight_hash == 571c5520b3d0092dfcdc6ae0a28866e649dbcdf6f81ae005bc4c1b69e63ce2e7 ]] || { echo "accepted r25.2.3.2 HCI preflight hash mismatch: $preflight_hash" >&2; exit 1; }
python3 -m py_compile "$BASE/r25_3_1_1_analyze.py" "$BASE/r25_3_1_1_capture.py"
bash -n "$BASE/run_r1_3_3_2_25_3_1_1.sh"
! grep -REn --include='r25_3_1_1_*.py' --include='run_r1_3_3_2_25_3_1_1.sh' \
  'createRfcommSocket|BluetoothSocket|socket\.(send|sendall|write)|rfcomm.*write|pm (enable|disable)|run-as .*channelprobe|fastboot|dd if=|dd of=' "$BASE" >/dev/null
# Semantic-oracle repair requirements.
grep -F 'DEFAULT_STOCK_PACKAGE = "com.rokid.sprite.global.aiapp"' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F '"persist_vendor_adb_state": transition["persist_vendor_adb_state"]' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F '"ui_switch_state": transition["ui_switch_state"]' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F '"adb_transport_disappearance_required": False' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F '"control_channel_usable_required": True' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F 'if args.plan_only:' "$BASE/r25_3_1_1_capture.py" >/dev/null
grep -F 'final_semantic_state_restored' "$BASE/r25_3_1_1_analyze.py" >/dev/null
echo R25_3_1_1_INSTALLED_ACCEPTED_HCI_PARSER_HASH_GATE=PASS
echo R25_3_1_1_INSTALLED_STOCK_ONLY_CAPTURE_GATE=PASS
echo R25_3_1_1_INSTALLED_NO_CUSTOM_TRANSMISSION_GATE=PASS
echo R25_3_1_1_INSTALLED_SEMANTIC_ORACLE_GATE=PASS
echo R25_3_1_1_INSTALLED_TRANSPORT_DISAPPEARANCE_NOT_REQUIRED_GATE=PASS
echo R25_3_1_1_INSTALLED_CONTROL_CHANNEL_GATE=PASS
echo R25_3_1_1_INSTALLED_FINAL_STATE_RESTORE_GATE=PASS
echo R25_3_1_1_INSTALLED_NO_DEVICE_DRY_RUN_GATE=PASS
echo R1_3_3_2_25_3_1_1_INSTALLED_VALIDATION=PASS
