#!/usr/bin/env bash
set -euo pipefail

# Test 17F — Rokid non-display glasses static development baseline
#
# Read-only collection:
#   - no reboot
#   - no setprop/settings writes
#   - no package install/uninstall
#   - no adb root/remount/tcpip
#   - no connection to TCP port 8341
#
# Selected vendor APKs are pulled by default into the PRIVATE evidence directory.
# Disable private APK pulling with:
#   PULL_SELECTED_APKS=0 ./run_rokid_test17f_static_dev_baseline.sh

TEST_ROOT="${ROKID_TEST_ROOT:-$HOME/rokid-nettest}"
PULL_SELECTED_APKS="${PULL_SELECTED_APKS:-1}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 1
  }
}

require_command adb
require_command python3
require_command shasum

GLASSES_SERIALS="$(
  adb devices -l |
  awk '$2 == "device" && /model:RG_glasses/ {print $1}'
)"
GLASSES_COUNT="$(
  printf '%s\n' "$GLASSES_SERIALS" |
  awk 'NF {count++} END {print count+0}'
)"

if [ "$GLASSES_COUNT" -ne 1 ]; then
  echo "ERROR: expected exactly one connected RG_glasses device; found $GLASSES_COUNT." >&2
  adb devices -l >&2
  exit 1
fi

GLASSES_SERIAL="$GLASSES_SERIALS"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_NAME="test17f-static-development-baseline-${STAMP}"
PRIVATE_DIR="${TEST_ROOT}/private/${RUN_NAME}"
SANITIZED_DIR="${TEST_ROOT}/sanitized/${RUN_NAME}"
RAW_DIR="${PRIVATE_DIR}/raw"
APK_DIR="${PRIVATE_DIR}/selected-apks"
APK_ANALYSIS_DIR="${PRIVATE_DIR}/selected-apk-analysis"

mkdir -p "$RAW_DIR" "$APK_DIR" "$APK_ANALYSIS_DIR" "$SANITIZED_DIR"
chmod 700 "$PRIVATE_DIR" "$RAW_DIR" "$APK_DIR" "$APK_ANALYSIS_DIR"

RUN_LOG="$PRIVATE_DIR/collector.log"
exec > >(tee -a "$RUN_LOG") 2>&1

echo "Test 17F — Rokid static development baseline"
echo "Glasses selected: YES"
echo "Private output: $PRIVATE_DIR"
echo "Sanitized output: $SANITIZED_DIR"
echo "Pull selected APKs: $PULL_SELECTED_APKS"
echo

adb_shell_capture() {
  local output="$1"
  shift
  {
    printf 'HOST_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'COMMAND='
    printf '%q ' adb -s '<GLASSES_SERIAL>' shell "$@"
    printf '\n\n'
    adb -s "$GLASSES_SERIAL" shell "$@"
  } >"$output" 2>&1 || true
}

adb_shell_text_capture() {
  local output="$1"
  local command_text="$2"
  {
    printf 'HOST_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'REMOTE_COMMAND=%s\n\n' "$command_text"
    adb -s "$GLASSES_SERIAL" shell "$command_text"
  } >"$output" 2>&1 || true
}

echo "[1/11] Host and device identity"
{
  echo "HOST_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "=== adb version ==="
  adb version
  echo
  echo "=== host OS ==="
  uname -a
  sw_vers 2>/dev/null || true
  echo
  echo "=== attached devices (serials redacted in this local text) ==="
  adb devices -l |
    sed -E 's/^([^[:space:]]+)([[:space:]]+device)/<SERIAL>\2/'
} >"$RAW_DIR/host-baseline.txt" 2>&1

adb_shell_text_capture "$RAW_DIR/device-build-and-security.txt" '
echo "=== product ==="
for p in \
  ro.product.manufacturer ro.product.brand ro.product.model \
  ro.product.device ro.product.board ro.product.cpu.abi \
  ro.build.version.release ro.build.version.sdk \
  ro.build.type ro.build.tags ro.build.fingerprint \
  ro.boot.verifiedbootstate ro.boot.vbmeta.device_state \
  ro.secure ro.debuggable ro.adb.secure; do
  printf "%s=" "$p"
  getprop "$p"
done
echo
echo "=== shell ==="
id
uname -a
getenforce 2>/dev/null || true
'

echo "[2/11] USB and ADB state"
adb_shell_text_capture "$RAW_DIR/usb-adb-properties.txt" '
echo "=== selected ADB/USB properties ==="
for p in \
  persist.sys.usb.config sys.usb.config sys.usb.state \
  service.adb.tcp.port persist.adb.tcp.port \
  ro.adb.secure ro.secure ro.debuggable \
  ro.bootmode ro.boot.bootreason; do
  printf "%s=" "$p"
  getprop "$p"
done

echo
echo "=== settings ==="
for s in adb_enabled adb_wifi_enabled development_settings_enabled; do
  printf "global.%s=" "$s"
  settings get global "$s" 2>/dev/null || true
done

echo
echo "=== adbd ==="
ps -A -o USER,PID,PPID,NAME,ARGS 2>/dev/null | grep -E "([[:space:]]|^)adbd([[:space:]]|$)" || true

echo
echo "=== ADB key-store metadata only; key contents are NOT read ==="
ls -ldZ /data/misc/adb 2>/dev/null || true
ls -lZ /data/misc/adb 2>/dev/null || true
stat /data/misc/adb/adb_keys 2>/dev/null || true
'

adb_shell_capture "$RAW_DIR/dumpsys-usb.txt" dumpsys usb
adb_shell_capture "$RAW_DIR/dumpsys-adb.txt" dumpsys adb
adb_shell_text_capture "$RAW_DIR/usb-configfs-metadata.txt" '
echo "=== USB gadget IDs and functions ==="
for root in /config/usb_gadget/*; do
  [ -d "$root" ] || continue
  echo "GADGET=$root"
  for f in idVendor idProduct bcdUSB bcdDevice UDC; do
    [ -r "$root/$f" ] && printf "%s=" "$f" && cat "$root/$f"
  done
  find "$root/configs" -maxdepth 2 -type l -print -exec readlink {} \; 2>/dev/null || true
  echo "-- product/manufacturer strings; serial string intentionally omitted --"
  find "$root/strings" -maxdepth 2 -type f \
    \( -name product -o -name manufacturer \) \
    -print -exec cat {} \; 2>/dev/null || true
done
'

echo "[3/11] Package inventories"
adb_shell_text_capture "$RAW_DIR/packages-all.txt" '
pm list packages -f -U 2>/dev/null
'
adb_shell_text_capture "$RAW_DIR/packages-system.txt" '
pm list packages -s -f -U 2>/dev/null
'
adb_shell_text_capture "$RAW_DIR/packages-third-party.txt" '
pm list packages -3 -f -U 2>/dev/null
'
adb_shell_text_capture "$RAW_DIR/package-permissions-all.txt" '
cmd package list permissions -f -g 2>/dev/null || pm list permissions -f -g 2>/dev/null || true
'

TARGET_PACKAGES=(
  com.rokid.os.sprite.assistserver
  com.rokid.os.sprite.live
  com.rokid.sysconfig
  com.rokid.cxrservice
  com.rokid.glass.ota
  com.rokid.os.master.screenstream
  com.rokid.os.sprite.launcher
  com.iap.mobile.ar_pay
)

TARGET_LIST="$RAW_DIR/target-package-index.tsv"
printf 'package\tpresent\tuid\tversion_name\tversion_code\tpaths\n' >"$TARGET_LIST"

for pkg in "${TARGET_PACKAGES[@]}"; do
  safe="${pkg//./_}"
  echo "  inspecting $pkg"

  paths="$(
    adb -s "$GLASSES_SERIAL" shell pm path "$pkg" 2>/dev/null |
    tr -d '\r' |
    sed -n 's/^package://p'
  )"

  if [ -z "$paths" ]; then
    printf '%s\tNO\t\t\t\t\n' "$pkg" >>"$TARGET_LIST"
    continue
  fi

  adb_shell_capture "$RAW_DIR/package-${safe}-dumpsys.txt" dumpsys package "$pkg"
  adb_shell_capture "$RAW_DIR/package-${safe}-pm-dump.txt" pm dump "$pkg"

  uid="$(
    adb -s "$GLASSES_SERIAL" shell dumpsys package "$pkg" 2>/dev/null |
    tr -d '\r' |
    sed -nE 's/^[[:space:]]*userId=([0-9]+).*$/\1/p' |
    head -1
  )"
  version_name="$(
    adb -s "$GLASSES_SERIAL" shell dumpsys package "$pkg" 2>/dev/null |
    tr -d '\r' |
    sed -nE 's/^[[:space:]]*versionName=(.*)$/\1/p' |
    head -1
  )"
  version_code="$(
    adb -s "$GLASSES_SERIAL" shell dumpsys package "$pkg" 2>/dev/null |
    tr -d '\r' |
    sed -nE 's/^[[:space:]]*versionCode=([^[:space:]]+).*$/\1/p' |
    head -1
  )"
  path_joined="$(printf '%s\n' "$paths" | paste -sd ';' -)"

  printf '%s\tYES\t%s\t%s\t%s\t%s\n' \
    "$pkg" "$uid" "$version_name" "$version_code" "$path_joined" \
    >>"$TARGET_LIST"
done

echo "[4/11] Selected APK hashes and optional private pulls"
APK_HASHES="$RAW_DIR/selected-apk-hashes.tsv"
printf 'package\tdevice_path\tdevice_sha256\thost_filename\thost_sha256\tpull_status\n' >"$APK_HASHES"

for pkg in "${TARGET_PACKAGES[@]}"; do
  pkg_paths="$(
    adb -s "$GLASSES_SERIAL" shell pm path "$pkg" 2>/dev/null |
    tr -d '\r' |
    sed -n 's/^package://p'
  )"
  [ -n "$pkg_paths" ] || continue

  index=0
  while IFS= read -r device_path; do
    [ -n "$device_path" ] || continue
    index=$((index + 1))
    original_name="$(basename "$device_path")"
    host_name="${pkg}__${index}__${original_name}"
    host_path="$APK_DIR/$host_name"

    device_hash="$(
      adb -s "$GLASSES_SERIAL" shell \
        "sha256sum '$device_path' 2>/dev/null || toybox sha256sum '$device_path' 2>/dev/null" |
      tr -d '\r' |
      awk '{print $1; exit}'
    )"

    pull_status="SKIPPED"
    host_hash=""

    if [ "$PULL_SELECTED_APKS" = "1" ]; then
      if adb -s "$GLASSES_SERIAL" pull "$device_path" "$host_path" \
          >"$RAW_DIR/pull-${pkg//./_}-${index}.log" 2>&1; then
        pull_status="OK"
        host_hash="$(shasum -a 256 "$host_path" | awk '{print $1}')"
      else
        pull_status="FAILED"
        rm -f "$host_path"
      fi
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$pkg" "$device_path" "$device_hash" "$host_name" "$host_hash" "$pull_status" \
      >>"$APK_HASHES"
  done <<<"$pkg_paths"
done

echo "[5/11] Optional host-side APK metadata"
{
  echo "apksigner=$(command -v apksigner || true)"
  echo "apkanalyzer=$(command -v apkanalyzer || true)"
  echo "aapt2=$(command -v aapt2 || true)"
  echo "aapt=$(command -v aapt || true)"
} >"$RAW_DIR/apk-tool-availability.txt"

if compgen -G "$APK_DIR/*.apk" >/dev/null; then
  for apk in "$APK_DIR"/*.apk; do
    name="$(basename "$apk")"
    prefix="$APK_ANALYSIS_DIR/${name%.apk}"

    if command -v apksigner >/dev/null 2>&1; then
      apksigner verify --verbose --print-certs "$apk" \
        >"${prefix}.apksigner.txt" 2>&1 || true
    fi

    if command -v apkanalyzer >/dev/null 2>&1; then
      apkanalyzer manifest print "$apk" \
        >"${prefix}.manifest.xml" 2>&1 || true
    fi

    if command -v aapt2 >/dev/null 2>&1; then
      aapt2 dump badging "$apk" \
        >"${prefix}.aapt2-badging.txt" 2>&1 || true
    elif command -v aapt >/dev/null 2>&1; then
      aapt dump badging "$apk" \
        >"${prefix}.aapt-badging.txt" 2>&1 || true
    fi
  done
fi

echo "[6/11] Binder, HAL and system-service inventory"
adb_shell_capture "$RAW_DIR/binder-service-list.txt" service list
adb_shell_text_capture "$RAW_DIR/cmd-services.txt" '
cmd -l 2>/dev/null || true
'
adb_shell_text_capture "$RAW_DIR/dumpsys-services-list.txt" '
dumpsys -l 2>/dev/null || true
'
adb_shell_text_capture "$RAW_DIR/hal-inventory.txt" '
lshal 2>/dev/null || true
'

echo "[7/11] Hardware and media capabilities"
adb_shell_text_capture "$RAW_DIR/system-features.txt" '
pm list features 2>/dev/null
'
adb_shell_capture "$RAW_DIR/dumpsys-media-camera.txt" dumpsys media.camera
adb_shell_capture "$RAW_DIR/dumpsys-audio.txt" dumpsys audio
adb_shell_capture "$RAW_DIR/dumpsys-media-audio-flinger.txt" dumpsys media.audio_flinger
adb_shell_capture "$RAW_DIR/dumpsys-input.txt" dumpsys input
adb_shell_capture "$RAW_DIR/dumpsys-display.txt" dumpsys display
adb_shell_capture "$RAW_DIR/dumpsys-sensorservice.txt" dumpsys sensorservice
adb_shell_capture "$RAW_DIR/dumpsys-bluetooth-manager.txt" dumpsys bluetooth_manager
adb_shell_text_capture "$RAW_DIR/device-nodes-media.txt" '
echo "=== video ==="
ls -lZ /dev/video* 2>/dev/null || true
echo "=== sound ==="
ls -lZ /dev/snd 2>/dev/null || true
echo "=== input ==="
ls -lZ /dev/input 2>/dev/null || true
'

echo "[8/11] Network and local listener baseline"
adb_shell_text_capture "$RAW_DIR/network-baseline.txt" '
echo "=== interfaces ==="
ip -br addr 2>/dev/null || true
echo
echo "=== IPv4 routes ==="
ip -4 route 2>/dev/null || true
echo
echo "=== IPv6 routes ==="
ip -6 route 2>/dev/null || true
echo
echo "=== TCP listeners ==="
ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true
echo
echo "=== UDP listeners ==="
ss -lun 2>/dev/null || netstat -lun 2>/dev/null || true
'
adb_shell_text_capture "$RAW_DIR/proc-net-sockets.txt" '
cat /proc/net/tcp /proc/net/tcp6 /proc/net/udp /proc/net/udp6 2>/dev/null || true
'

echo "[9/11] GateServiced and Rokid init definitions"
adb_shell_text_capture "$RAW_DIR/gateserviced-baseline.txt" '
pid="$(pidof GateServiced 2>/dev/null || true)"
echo "PID_PRESENT=$([ -n "$pid" ] && echo YES || echo NO)"
ps -A -o USER,PID,PPID,NAME,ARGS 2>/dev/null | grep -F GateServiced || true
if [ -n "$pid" ]; then
  cat "/proc/$pid/attr/current" 2>/dev/null || true
  grep -E "^(Name|Uid|Gid|CapInh|CapPrm|CapEff|CapBnd|NoNewPrivs|Seccomp):" \
    "/proc/$pid/status" 2>/dev/null || true
fi
echo
echo "=== init.gateserviced.rc ==="
cat /vendor/etc/init/init.gateserviced.rc 2>/dev/null || true
echo
echo "=== references to GateServiced or 8341 ==="
grep -R -n -E "GateServiced|8341" \
  /system/etc/init /system_ext/etc/init /vendor/etc/init \
  /product/etc/init /odm/etc/init 2>/dev/null || true
'
adb_shell_text_capture "$RAW_DIR/rokid-init-file-index.txt" '
find /system/etc/init /system_ext/etc/init /vendor/etc/init \
     /product/etc/init /odm/etc/init \
     -type f 2>/dev/null |
grep -iE "rokid|sprite|glass|cxr|gate|pay|ota" |
sort || true
'

echo "[10/11] Build sanitized assertions"
python3 - \
  "$RAW_DIR/device-build-and-security.txt" \
  "$RAW_DIR/usb-adb-properties.txt" \
  "$RAW_DIR/packages-third-party.txt" \
  "$TARGET_LIST" \
  "$APK_HASHES" \
  "$RAW_DIR/system-features.txt" \
  "$RAW_DIR/network-baseline.txt" \
  "$RAW_DIR/gateserviced-baseline.txt" \
  "$SANITIZED_DIR/assertions.json" \
  "$SANITIZED_DIR/summary.md" <<'PY'
import json
import re
import sys
from pathlib import Path

(
    build_path,
    usb_path,
    third_party_path,
    target_path,
    apk_hash_path,
    features_path,
    network_path,
    gate_path,
    assertions_path,
    summary_path,
) = map(Path, sys.argv[1:])

def read(path):
    return path.read_text(errors="replace") if path.exists() else ""

build = read(build_path)
usb = read(usb_path)
third = read(third_party_path)
target = read(target_path)
apk_hashes = read(apk_hash_path)
features = read(features_path)
network = read(network_path)
gate = read(gate_path)

def prop(text, name):
    match = re.search(rf"(?m)^{re.escape(name)}=(.*)$", text)
    return match.group(1).strip() if match else None

def setting(name):
    match = re.search(rf"(?m)^global\.{re.escape(name)}=(.*)$", usb)
    return match.group(1).strip() if match else None

third_party_count = sum(
    1 for line in third.splitlines() if line.startswith("package:")
)
target_present = []
for line in target.splitlines()[1:]:
    cols = line.split("\t")
    if len(cols) >= 2 and cols[1] == "YES":
        target_present.append(cols[0])

apk_rows = []
for line in apk_hashes.splitlines()[1:]:
    cols = line.split("\t")
    if len(cols) >= 6:
        apk_rows.append({
            "package": cols[0],
            "device_sha256": cols[2] or None,
            "host_sha256_matches_device": (
                bool(cols[2] and cols[4]) and cols[2].lower() == cols[4].lower()
            ),
            "pull_status": cols[5],
        })

interfaces = {}
for name in ("wlan0", "p2p0", "wifi-aware0"):
    match = re.search(rf"(?m)^{re.escape(name)}\s+(\S+)\s*(.*)$", network)
    interfaces[name] = {
        "state": match.group(1) if match else "NOT_LISTED",
        "address_present": bool(match and match.group(2).strip()),
    }

feature_names = sorted(set(re.findall(r"feature:([^\r\n]+)", features)))

assertions = {
    "schema": "rokid.test17f.static-development-baseline.v1",
    "device": {
        "manufacturer": prop(build, "ro.product.manufacturer"),
        "brand": prop(build, "ro.product.brand"),
        "model": prop(build, "ro.product.model"),
        "device": prop(build, "ro.product.device"),
        "board": prop(build, "ro.product.board"),
        "abi": prop(build, "ro.product.cpu.abi"),
        "android_release": prop(build, "ro.build.version.release"),
        "api_level": prop(build, "ro.build.version.sdk"),
        "build_type": prop(build, "ro.build.type"),
        "build_tags": prop(build, "ro.build.tags"),
        "build_fingerprint": prop(build, "ro.build.fingerprint"),
        "verified_boot_state": prop(build, "ro.boot.verifiedbootstate"),
        "vbmeta_device_state": prop(build, "ro.boot.vbmeta.device_state"),
    },
    "adb": {
        "ro_secure": prop(build, "ro.secure"),
        "ro_debuggable": prop(build, "ro.debuggable"),
        "ro_adb_secure": prop(build, "ro.adb.secure"),
        "persist_sys_usb_config": prop(usb, "persist.sys.usb.config"),
        "sys_usb_config": prop(usb, "sys.usb.config"),
        "sys_usb_state": prop(usb, "sys.usb.state"),
        "service_adb_tcp_port": prop(usb, "service.adb.tcp.port"),
        "persist_adb_tcp_port": prop(usb, "persist.adb.tcp.port"),
        "adb_enabled_setting": setting("adb_enabled"),
        "adb_wifi_enabled_setting": setting("adb_wifi_enabled"),
        "development_settings_enabled": setting("development_settings_enabled"),
    },
    "packages": {
        "third_party_package_count": third_party_count,
        "selected_vendor_packages_present": sorted(target_present),
        "selected_apk_records": apk_rows,
    },
    "network": {
        "interfaces": interfaces,
        "ipv4_route_present": bool(
            re.search(r"(?ms)^=== IPv4 routes ===\s*\n(?!\s*===)(\S.+)", network)
        ),
        "tcp_8341_listener_present": bool(re.search(r":8341\b", network)),
    },
    "gate_service": {
        "process_present": "PID_PRESENT=YES" in gate,
        "uid_zero_observed": bool(re.search(r"(?m)^Uid:\s+0\s+0\s+0\s+0", gate)),
        "gid_zero_observed": bool(re.search(r"(?m)^Gid:\s+0\s+0\s+0\s+0", gate)),
        "tee_selinux_domain_observed": "u:r:tee:s0" in gate,
        "init_executable_observed": "/vendor/bin/GateServiced" in gate,
    },
    "hardware": {
        "feature_count": len(feature_names),
        "camera_feature_present": any("camera" in x for x in feature_names),
        "microphone_feature_present": any("microphone" in x for x in feature_names),
        "bluetooth_feature_present": any("bluetooth" in x for x in feature_names),
        "wifi_feature_present": any("wifi" in x for x in feature_names),
        "usb_host_feature_present": any("usb.host" in x for x in feature_names),
    },
    "privacy": {
        "device_serial_included": False,
        "mac_addresses_included": False,
        "local_ip_addresses_included": False,
        "raw_logs_included": False,
        "apk_binaries_included": False,
    },
}

assertions_path.write_text(
    json.dumps(assertions, indent=2, sort_keys=True) + "\n"
)

pulled = sum(1 for row in apk_rows if row["pull_status"] == "OK")
matched = sum(1 for row in apk_rows if row["host_sha256_matches_device"])

summary = f"""# Test 17F — Static development baseline

- Device: **{assertions['device']['manufacturer']} {assertions['device']['model']}**
- Android/API: **{assertions['device']['android_release']} / {assertions['device']['api_level']}**
- Build: **{assertions['device']['build_type']} / {assertions['device']['build_tags']}**
- Production ADB security: **ro.secure={assertions['adb']['ro_secure']}, ro.debuggable={assertions['adb']['ro_debuggable']}, ro.adb.secure={assertions['adb']['ro_adb_secure']}**
- Persistent USB configuration: **{assertions['adb']['persist_sys_usb_config']}**
- Active USB configuration/state: **{assertions['adb']['sys_usb_config']} / {assertions['adb']['sys_usb_state']}**
- Wireless ADB enabled: **{'YES' if assertions['adb']['adb_wifi_enabled_setting'] == '1' else 'NO'}**
- Ordinary third-party packages: **{third_party_count}**
- Selected Rokid/vendor packages present: **{len(target_present)}**
- Selected private APK files pulled: **{pulled}**
- Pulled APK hashes matching device hashes: **{matched}**
- GateServiced present as root/TEE service: **{'YES' if assertions['gate_service']['process_present'] and assertions['gate_service']['uid_zero_observed'] and assertions['gate_service']['tee_selinux_domain_observed'] else 'NO'}**
- TCP port 8341 listener present: **{'YES' if assertions['network']['tcp_8341_listener_present'] else 'NO'}**
- `wlan0` state: **{interfaces['wlan0']['state']}**
- `p2p0` state: **{interfaces['p2p0']['state']}**
- IPv4 route present: **{'YES' if assertions['network']['ipv4_route_present'] else 'NO'}**

The sanitized output excludes device serials, MAC addresses, local IP addresses,
raw logs, and APK binaries. Pulled APKs remain private and must not be published.
"""
summary_path.write_text(summary)
PY

echo "[11/11] Private evidence manifest and privacy gate"
PRIVATE_MANIFEST="$SANITIZED_DIR/private-evidence-sha256.txt"
(
  cd "$PRIVATE_DIR"
  find raw selected-apk-analysis -type f -print0 2>/dev/null |
    sort -z |
    xargs -0 shasum -a 256
  if [ "$PULL_SELECTED_APKS" = "1" ]; then
    find selected-apks -type f -print0 2>/dev/null |
      sort -z |
      xargs -0 shasum -a 256
  fi
) >"$PRIVATE_MANIFEST"

SANITIZED_MANIFEST="$SANITIZED_DIR/SHA256SUMS.txt"
(
  cd "$SANITIZED_DIR"
  shasum -a 256 assertions.json summary.md private-evidence-sha256.txt
) >"$SANITIZED_MANIFEST"

python3 - \
  "$SANITIZED_DIR" \
  "$GLASSES_SERIAL" \
  "$PRIVATE_DIR" <<'PY'
import re
import sys
from pathlib import Path

sanitized = Path(sys.argv[1])
serial = sys.argv[2]
private_dir = sys.argv[3]

failures = []
mac_re = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
ipv4_re = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

for path in sanitized.rglob("*"):
    if not path.is_file():
        continue
    text = path.read_text(errors="replace")
    if serial and serial in text:
        failures.append(f"{path.name}: device serial")
    if private_dir and private_dir in text:
        failures.append(f"{path.name}: private absolute path")
    if mac_re.search(text):
        failures.append(f"{path.name}: MAC address")
    # Permit 0.0.0.0 only as a listener bind marker; no other IPv4 addresses.
    for match in ipv4_re.findall(text):
        if match != "0.0.0.0":
            failures.append(f"{path.name}: IPv4 address")
            break

if failures:
    print("SANITIZED PRIVACY GATE: FAIL", file=sys.stderr)
    for item in failures:
        print(f"  - {item}", file=sys.stderr)
    raise SystemExit(1)

print("SANITIZED PRIVACY GATE: PASS")
PY

echo
echo "=== Sanitized result ==="
cat "$SANITIZED_DIR/summary.md"
echo
echo "Sanitized assertions:"
echo "  $SANITIZED_DIR/assertions.json"
echo "Sanitized manifest:"
echo "  $SANITIZED_DIR/SHA256SUMS.txt"
echo "Private evidence manifest:"
echo "  $SANITIZED_DIR/private-evidence-sha256.txt"
echo "Private evidence:"
echo "  $PRIVATE_DIR"
echo
echo "Test 17F collection complete."
echo "Keep the entire private directory, including APKs, off GitHub and Reddit."
