#!/usr/bin/env bash
REPO=""
OUTPUT=""
GLASSES=""
WIFI_CONFIG=""
BACKEND_IP=""
BACKEND_PORT="28443"
DNS_NAME=""
PHONE_ISOLATION=""
LIVE_TOKEN=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --output) OUTPUT="$2"; shift 2;;
    --glasses) GLASSES="$2"; shift 2;;
    --wifi-config) WIFI_CONFIG="$2"; shift 2;;
    --backend-ip) BACKEND_IP="$2"; shift 2;;
    --backend-port) BACKEND_PORT="$2"; shift 2;;
    --dns-name) DNS_NAME="$2"; shift 2;;
    --phone-isolation-confirmed) PHONE_ISOLATION="$2"; shift 2;;
    --execute-live) LIVE_TOKEN="$2"; shift 2;;
    *) echo "ERROR=unknown_argument:$1"; exit 2;;
  esac
done

if [ -z "$REPO" ] || [ -z "$OUTPUT" ] || [ -z "$WIFI_CONFIG" ] || [ -z "$BACKEND_IP" ]; then
  echo "ERROR=missing_required_argument"
  exit 2
fi
if [ "$LIVE_TOKEN" != "TEST22_LIVE_WIFI_SOCKET" ]; then
  echo "ERROR=live_execution_token_required"
  echo "EXPECTED=--execute-live TEST22_LIVE_WIFI_SOCKET"
  exit 2
fi
if [ "$PHONE_ISOLATION" != "YES" ]; then
  echo "ERROR=phone_isolation_confirmation_required"
  echo "Turn Bluetooth off on the paired companion phone or power it off, then pass --phone-isolation-confirmed YES"
  exit 2
fi
if [ ! -s "$WIFI_CONFIG" ]; then echo "ERROR=wifi_config_missing"; exit 2; fi

python3 - "$WIFI_CONFIG" <<'PY'
import json,os,stat,sys
p=sys.argv[1]
st=os.stat(p)
if st.st_mode & (stat.S_IRWXG|stat.S_IRWXO):
 print('ERROR=wifi_config_permissions_too_open'); raise SystemExit(2)
d=json.load(open(p))
ssid=str(d.get('ssid','')); psk=str(d.get('psk',''))
if not ssid or len(psk)<8 or len(psk)>63:
 print('ERROR=wifi_config_invalid'); raise SystemExit(2)
print('TEST22_WIFI_CONFIG_PRIVACY=PASS')
PY
CONFIG_RC=$?
if [ "$CONFIG_RC" -ne 0 ]; then exit "$CONFIG_RC"; fi

python3 - "$BACKEND_IP" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
if ip.version!=4 or ip.is_loopback or not ip.is_private:
 print('ERROR=backend_ip_must_be_private_ipv4'); raise SystemExit(2)
print('TEST22_BACKEND_IP_PREFLIGHT=PASS')
PY
IP_RC=$?
if [ "$IP_RC" -ne 0 ]; then exit "$IP_RC"; fi

ADB="$(command -v adb)"
OPENSSL="$(command -v openssl)"
if [ -z "$ADB" ] || [ -z "$OPENSSL" ]; then echo "ERROR=adb_or_openssl_missing"; exit 2; fi

if [ -z "$GLASSES" ]; then
  GLASSES="$($ADB devices -l | awk '$2=="device" && /model:RG_glasses/ {print $1}')"
  COUNT="$(printf '%s\n' "$GLASSES" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [ "$COUNT" != "1" ]; then
    echo "ERROR=expected_exactly_one_RG_glasses_adb_device"
    $ADB devices -l
    exit 2
  fi
fi

mkdir -p "$OUTPUT/private" "$OUTPUT/tls"
PACKAGE="org.aimindseye.rokid.test22wifi"
BACKEND_PID=""
ORIGINAL_WIFI="UNKNOWN"
APP_STARTED="NO"
cleanup_host() {
  if [ -n "$BACKEND_PID" ]; then kill "$BACKEND_PID" >/dev/null 2>&1 || true; fi
  $ADB -s "$GLASSES" shell am force-stop "$PACKAGE" >/dev/null 2>&1 || true
  $ADB -s "$GLASSES" uninstall "$PACKAGE" >/dev/null 2>&1 || true
  if [ "$ORIGINAL_WIFI" = "ENABLED" ]; then
    $ADB -s "$GLASSES" shell svc wifi enable >/dev/null 2>&1 || true
  elif [ "$ORIGINAL_WIFI" = "DISABLED" ] && [ "$APP_STARTED" = "YES" ]; then
    $ADB -s "$GLASSES" shell svc wifi disable >/dev/null 2>&1 || true
  fi
}
trap cleanup_host EXIT INT TERM

$ADB -s "$GLASSES" get-state >/dev/null || { echo "ERROR=glasses_adb_unavailable"; exit 2; }
MODEL="$($ADB -s "$GLASSES" shell getprop ro.product.model | tr -d '\r')"
DEVICE="$($ADB -s "$GLASSES" shell getprop ro.product.device | tr -d '\r')"
SDK="$($ADB -s "$GLASSES" shell getprop ro.build.version.sdk | tr -d '\r')"
MODEL_NORMALIZED="$(printf '%s' "$MODEL" | tr '[:upper:]_-' '[:lower:]  ' | tr -s ' ' | sed 's/^ //; s/ $//')"
if [ "$MODEL_NORMALIZED" != "rg glasses" ] || [ "$DEVICE" != "glasses" ]; then
  echo "ERROR=wrong_adb_target_model"
  echo "MODEL_NORMALIZED=$MODEL_NORMALIZED"
  echo "DEVICE=$DEVICE"
  exit 2
fi
if [ "$SDK" != "32" ]; then echo "ERROR=unexpected_glasses_sdk:$SDK"; exit 2; fi

echo "TEST22_DEVICE_PREFLIGHT=PASS"
echo "TEST22_MODEL_NORMALIZATION=PASS"
$ADB -s "$GLASSES" shell cmd wifi status >"$OUTPUT/private/wifi-status-before.txt" 2>&1
$ADB -s "$GLASSES" shell dumpsys bluetooth_manager >"$OUTPUT/private/bluetooth-before.txt" 2>&1
$ADB -s "$GLASSES" shell ip addr >"$OUTPUT/private/ip-addr-before.txt" 2>&1
$ADB -s "$GLASSES" shell ip route >"$OUTPUT/private/ip-route-before.txt" 2>&1
WIFI_SETTING_BEFORE="$($ADB -s "$GLASSES" shell settings get global wifi_on 2>/dev/null | tr -d '\r')"
printf '%s\n' "$WIFI_SETTING_BEFORE" >"$OUTPUT/private/wifi-setting-before.txt"
ORIGINAL_WIFI="$(python3 "$REPO/scripts/tests/test22_wifi_state.py" \
  --settings-value "$WIFI_SETTING_BEFORE" \
  --cmd-status-file "$OUTPUT/private/wifi-status-before.txt")"
echo "TEST22_INITIAL_WIFI_STATE=$ORIGINAL_WIFI"
if [ "$ORIGINAL_WIFI" = "UNKNOWN" ]; then
  echo "ERROR=cannot_classify_initial_wifi_state"
  exit 2
fi

# Preserve an already-OFF baseline without issuing a Wi-Fi mutation. Only if Wi-Fi
# was initially enabled do we establish the required cold-start OFF precondition.
if [ "$ORIGINAL_WIFI" = "ENABLED" ]; then
  $ADB -s "$GLASSES" shell svc wifi disable >/dev/null 2>&1
  DISABLE_RC=$?
  if [ "$DISABLE_RC" -ne 0 ]; then
    echo "ERROR=cannot_disable_wifi_for_cold_precondition"
    exit 2
  fi
  sleep 2
fi
$ADB -s "$GLASSES" shell cmd wifi status >"$OUTPUT/private/wifi-status-cold.txt" 2>&1
WIFI_SETTING_COLD="$($ADB -s "$GLASSES" shell settings get global wifi_on 2>/dev/null | tr -d '\r')"
printf '%s\n' "$WIFI_SETTING_COLD" >"$OUTPUT/private/wifi-setting-cold.txt"
COLD_WIFI="$(python3 "$REPO/scripts/tests/test22_wifi_state.py" \
  --settings-value "$WIFI_SETTING_COLD" \
  --cmd-status-file "$OUTPUT/private/wifi-status-cold.txt")"
echo "TEST22_COLD_WIFI_STATE=$COLD_WIFI"
if [ "$COLD_WIFI" != "DISABLED" ]; then
  echo "ERROR=cannot_establish_wifi_off_precondition"
  exit 2
fi
if [ "$ORIGINAL_WIFI" = "DISABLED" ]; then
  echo "TEST22_WIFI_OFF_BASELINE_MUTATION=NONE"
else
  echo "TEST22_WIFI_OFF_BASELINE_MUTATION=HOST_DISABLE_ONLY"
fi
echo "TEST22_WIFI_OFF_PRECONDITION=PASS"

bash "$REPO/scripts/tests/build_test22.sh" "$REPO"
BUILD_RC=$?
if [ "$BUILD_RC" -ne 0 ]; then exit "$BUILD_RC"; fi
APK="$REPO/android-client/test22/build/outputs/apk/debug/test22-debug.apk"
INSTALL_LOG="$OUTPUT/private/adb-install.txt"
$ADB -s "$GLASSES" install -r "$APK" >"$INSTALL_LOG" 2>&1
INSTALL_RC=$?
INSTALL_CLASSIFICATION="$(python3 "$REPO/scripts/tests/test22_install_policy.py" \
  --log "$INSTALL_LOG" \
  --return-code "$INSTALL_RC" \
  --json-output "$OUTPUT/private/install-policy.json")"
echo "TEST22_INSTALL_CLASSIFICATION=$INSTALL_CLASSIFICATION"

if [ "$INSTALL_CLASSIFICATION" = "BLOCKED_STANDARD_ADB_APK_INSTALL" ]; then
  # Read-only policy census. Do not try alternate install commands here.
  {
    echo "ro.debuggable=$($ADB -s "$GLASSES" shell getprop ro.debuggable 2>/dev/null | tr -d '\r')"
    echo "ro.secure=$($ADB -s "$GLASSES" shell getprop ro.secure 2>/dev/null | tr -d '\r')"
    echo "ro.adb.secure=$($ADB -s "$GLASSES" shell getprop ro.adb.secure 2>/dev/null | tr -d '\r')"
    echo "ro.build.type=$($ADB -s "$GLASSES" shell getprop ro.build.type 2>/dev/null | tr -d '\r')"
    echo "verifier_verify_adb_installs=$($ADB -s "$GLASSES" shell settings get global verifier_verify_adb_installs 2>/dev/null | tr -d '\r')"
    echo "install_non_market_apps=$($ADB -s "$GLASSES" shell settings get secure install_non_market_apps 2>/dev/null | tr -d '\r')"
  } >"$OUTPUT/private/install-policy-census.txt"
  $ADB -s "$GLASSES" shell pm list packages 2>/dev/null | tr -d '\r' | \
    grep -Ei 'packageinstaller|permissioncontroller|rokid|sprite' \
    >"$OUTPUT/private/install-related-packages.txt" || true
  $ADB -s "$GLASSES" shell cmd package resolve-activity --brief \
    -a android.intent.action.VIEW -t application/vnd.android.package-archive \
    >"$OUTPUT/private/apk-installer-resolve.txt" 2>&1 || true

  APK_SHA="$(/usr/bin/shasum -a 256 "$APK" | awk '{print $1}')"
  python3 - "$OUTPUT" "$APK_SHA" <<'PY'
from pathlib import Path
import json,sys
root=Path(sys.argv[1]); apk_sha=sys.argv[2]
data={
  "schema":"rokid.test22.summary.v2",
  "test_id":"22-independent-wifi-direct-socket",
  "harness_status":"PASS",
  "disposition":"BLOCKED_STANDARD_ADB_APK_INSTALL",
  "direct_wifi_test_started":False,
  "wifi_off_precondition":"PASS",
  "phone_isolation_confirmed":True,
  "standard_adb_install":"BLOCKED_BY_DEVICE_POLICY",
  "test_apk_sha256":apk_sha,
  "next_action":"PRELOAD_EXACT_TEST22_APK_VIA_STOCK_OR_CXR_PATH_THEN_RESUME_ISOLATED_DATAPLANE_TEST",
}
(root/'summary.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
(root/'summary.txt').write_text(
  'TEST22_DISPOSITION=BLOCKED_STANDARD_ADB_APK_INSTALL\n'
  'TEST22_DIRECT_WIFI_TEST_STARTED=NO\n'
  'TEST22_WIFI_OFF_PRECONDITION=PASS\n'
  'TEST22_STANDARD_ADB_INSTALL=BLOCKED_BY_DEVICE_POLICY\n'
  'TEST22_NEXT_ACTION=PRELOAD_EXACT_TEST22_APK_VIA_STOCK_OR_CXR_PATH_THEN_RESUME_ISOLATED_DATAPLANE_TEST\n'
)
PY

  python3 - "$OUTPUT" <<'PY'
from pathlib import Path
import hashlib,zipfile,sys
root=Path(sys.argv[1]); private=root/'private'
manifest=root/'SHA256SUMS-private.txt'
rows=[]
for p in sorted(private.rglob('*')):
    if p.is_file(): rows.append((hashlib.sha256(p.read_bytes()).hexdigest(),p.relative_to(root).as_posix()))
manifest.write_text(''.join(f'{h}  {r}\n' for h,r in rows))
zip_path=Path(str(root)+'-private-evidence.zip')
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(private.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(root).as_posix())
    z.write(manifest,manifest.name)
Path(str(zip_path)+'.sha256').write_text(f'{hashlib.sha256(zip_path.read_bytes()).hexdigest()}  {zip_path.name}\n')
san=Path(str(root)+'-sanitized-summary.zip')
with zipfile.ZipFile(san,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['summary.json','summary.txt']:
        z.write(root/name,name)
Path(str(san)+'.sha256').write_text(f'{hashlib.sha256(san.read_bytes()).hexdigest()}  {san.name}\n')
print('TEST22_PRIVATE_PACKAGE=PASS')
print('TEST22_PRIVATE_EVIDENCE_ZIP='+str(zip_path))
print('TEST22_SANITIZED_SUMMARY_ZIP='+str(san))
PY
  echo "TEST22_DISPOSITION=BLOCKED_STANDARD_ADB_APK_INSTALL"
  echo "TEST22_DIRECT_WIFI_TEST_STARTED=NO"
  echo "TEST22_RUN=PASS"
  exit 0
fi

if [ "$INSTALL_CLASSIFICATION" != "SUCCESS" ]; then
  echo "ERROR=test22_apk_install_failed_unclassified"
  exit 2
fi
if ! $ADB -s "$GLASSES" shell run-as "$PACKAGE" pwd >/dev/null 2>&1; then
  echo "ERROR=run_as_unavailable_for_debug_apk"; exit 2
fi

NONCE="$(python3 - <<'PY'
import secrets; print(secrets.token_hex(24))
PY
)"
TLS="$OUTPUT/tls"
cat >"$TLS/ca.cnf" <<EOF
[req]
distinguished_name=dn
x509_extensions=v3_ca
prompt=no
[dn]
CN=Rokid Test22 Local CA
[v3_ca]
basicConstraints=critical,CA:TRUE
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer
EOF
$OPENSSL req -x509 -newkey rsa:2048 -nodes -days 1 -config "$TLS/ca.cnf" \
  -keyout "$TLS/ca.key" -out "$TLS/ca.pem" >/dev/null 2>&1 || exit 2
cat >"$TLS/server-ext.cnf" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:$BACKEND_IP
EOF
$OPENSSL req -new -newkey rsa:2048 -nodes -subj "/CN=$BACKEND_IP" \
  -keyout "$TLS/server.key" -out "$TLS/server.csr" >/dev/null 2>&1 || exit 2
$OPENSSL x509 -req -in "$TLS/server.csr" -CA "$TLS/ca.pem" -CAkey "$TLS/ca.key" \
  -CAcreateserial -days 1 -extfile "$TLS/server-ext.cnf" -out "$TLS/server.pem" >/dev/null 2>&1 || exit 2
chmod 600 "$TLS/ca.key" "$TLS/server.key"

python3 - "$WIFI_CONFIG" "$OUTPUT/private/test22-config.properties" "$BACKEND_IP" "$BACKEND_PORT" "$NONCE" "$DNS_NAME" <<'PY'
import base64,json,sys
src,out,host,port,nonce,dns=sys.argv[1:]
d=json.load(open(src))
def b64(s): return base64.b64encode(s.encode()).decode()
with open(out,'w') as f:
 f.write('ssid_b64='+b64(str(d['ssid']))+'\n')
 f.write('psk_b64='+b64(str(d['psk']))+'\n')
 f.write('backend_host='+host+'\nbackend_port='+port+'\nnonce='+nonce+'\n')
 if dns: f.write('dns_name='+dns+'\n')
PY
chmod 600 "$OUTPUT/private/test22-config.properties"

cat "$OUTPUT/private/test22-config.properties" | $ADB -s "$GLASSES" shell "run-as $PACKAGE sh -c 'cat > files/test22-config.properties && chmod 600 files/test22-config.properties'" || exit 2
cat "$TLS/ca.pem" | $ADB -s "$GLASSES" shell "run-as $PACKAGE sh -c 'cat > files/test22-ca.pem && chmod 600 files/test22-ca.pem'" || exit 2

READY="$OUTPUT/private/backend-ready.txt"
python3 "$REPO/scripts/tests/test22_tls_backend.py" \
  --bind "$BACKEND_IP" --port "$BACKEND_PORT" --cert "$TLS/server.pem" --key "$TLS/server.key" \
  --nonce "$NONCE" --result "$OUTPUT/private/backend-result.json" --ready "$READY" \
  >"$OUTPUT/private/backend.stdout.txt" 2>"$OUTPUT/private/backend.stderr.txt" &
BACKEND_PID=$!
for _ in $(seq 1 40); do [ -s "$READY" ] && break; sleep 0.25; done
if [ ! -s "$READY" ]; then echo "ERROR=backend_not_ready"; exit 2; fi

echo "TEST22_BACKEND_READY=PASS"
$ADB -s "$GLASSES" shell am force-stop "$PACKAGE" >/dev/null 2>&1
$ADB -s "$GLASSES" shell am start -n "$PACKAGE/.MainActivity" >/dev/null
START_RC=$?
if [ "$START_RC" -eq 0 ]; then APP_STARTED="YES"; fi
if [ "$START_RC" -ne 0 ]; then echo "ERROR=test22_activity_start_failed"; exit 2; fi

FOUND=NO
for _ in $(seq 1 180); do
  if $ADB -s "$GLASSES" shell "run-as $PACKAGE test -s files/test22-result.json" >/dev/null 2>&1; then FOUND=YES; break; fi
  sleep 0.5
done
if [ "$FOUND" != "YES" ]; then echo "ERROR=test22_app_result_timeout"; exit 2; fi
$ADB -s "$GLASSES" exec-out run-as "$PACKAGE" cat files/test22-result.json >"$OUTPUT/private/app-result.json"

TCP_ATTEMPTED="$(python3 - "$OUTPUT/private/app-result.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); print('YES' if d.get('tcp_connect_success') is True else 'NO')
PY
)"
if [ "$TCP_ATTEMPTED" = "NO" ] && [ ! -s "$OUTPUT/private/backend-result.json" ]; then
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
  wait "$BACKEND_PID" >/dev/null 2>&1
  python3 - "$OUTPUT/private/backend-result.json" "$NONCE" <<'PY'
import hashlib,json,sys
path,nonce=sys.argv[1:]
h=lambda s: hashlib.sha256(s.encode()).hexdigest()
json.dump({'schema':'rokid.test22.backend-result.v1','status':'NO_CONNECTION_ATTEMPTED','request_verified':False,'nonce_sha256':h(nonce)},open(path,'w'),indent=2,sort_keys=True)
open(path,'a').write('\n')
PY
  BACKEND_RC=0
else
  wait "$BACKEND_PID"
  BACKEND_RC=$?
fi
BACKEND_PID=""
$ADB -s "$GLASSES" shell cmd wifi status >"$OUTPUT/private/wifi-status-after.txt" 2>&1
$ADB -s "$GLASSES" shell ip addr >"$OUTPUT/private/ip-addr-after.txt" 2>&1
$ADB -s "$GLASSES" shell ip route >"$OUTPUT/private/ip-route-after.txt" 2>&1

python3 "$REPO/scripts/tests/analyze_test22_wifi_socket.py" \
  --app-result "$OUTPUT/private/app-result.json" \
  --backend-result "$OUTPUT/private/backend-result.json" \
  --phone-isolation-confirmed YES \
  --output "$OUTPUT/summary.json" | tee "$OUTPUT/summary.txt"
ANALYZE_RC=${PIPESTATUS[0]}

# Never archive credentials or private TLS keys.
rm -f "$OUTPUT/private/test22-config.properties" "$TLS/ca.key" "$TLS/server.key" "$TLS/server.csr" "$TLS/ca.cnf" "$TLS/server-ext.cnf" "$TLS/ca.srl"

python3 - "$OUTPUT" <<'PY'
from pathlib import Path
import hashlib,zipfile,sys
root=Path(sys.argv[1])
private=root/'private'
manifest=root/'SHA256SUMS-private.txt'
rows=[]
for p in sorted(private.rglob('*')):
 if p.is_file(): rows.append((hashlib.sha256(p.read_bytes()).hexdigest(),p.relative_to(root).as_posix()))
manifest.write_text(''.join(f'{h}  {r}\n' for h,r in rows))
zip_path=Path(str(root)+'-private-evidence.zip')
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(private.rglob('*')):
  if p.is_file(): z.write(p,p.relative_to(root).as_posix())
 z.write(manifest,manifest.name)
sha=hashlib.sha256(zip_path.read_bytes()).hexdigest()
Path(str(zip_path)+'.sha256').write_text(f'{sha}  {zip_path.name}\n')
san=Path(str(root)+'-sanitized-summary.zip')
with zipfile.ZipFile(san,'w',zipfile.ZIP_DEFLATED) as z:
 for name in ['summary.json','summary.txt']:
  p=root/name
  if p.exists(): z.write(p,p.name)
sha2=hashlib.sha256(san.read_bytes()).hexdigest()
Path(str(san)+'.sha256').write_text(f'{sha2}  {san.name}\n')
print('TEST22_PRIVATE_PACKAGE=PASS')
print('TEST22_PRIVATE_EVIDENCE_ZIP='+str(zip_path))
print('TEST22_SANITIZED_SUMMARY_ZIP='+str(san))
PY
PACKAGE_RC=$?

echo "BACKEND_RC=$BACKEND_RC"
echo "ANALYZE_RC=$ANALYZE_RC"
echo "PACKAGE_RC=$PACKAGE_RC"
if [ "$ANALYZE_RC" -eq 0 ] && [ "$PACKAGE_RC" -eq 0 ]; then
  echo "TEST22_RUN=PASS"
  exit 0
fi
echo "TEST22_RUN=FAIL"
exit 1
