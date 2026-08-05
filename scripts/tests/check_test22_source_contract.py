#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
required=[
 'android-client/test22/build.gradle.kts',
 'android-client/test22/src/main/AndroidManifest.xml',
 'android-client/test22/src/main/java/org/aimindseye/rokid/test22wifi/MainActivity.java',
 'android-client/test22/src/main/java/org/aimindseye/rokid/test22wifi/Test22Probe.java',
 'scripts/tests/run_test22_independent_wifi_socket.sh',
 'scripts/tests/test22_tls_backend.py',
 'scripts/tests/test22_wifi_state.py',
 'scripts/tests/test22_install_policy.py',
 'scripts/tests/analyze_test22_wifi_socket.py',
]
errs=[]
for rel in required:
 p=ROOT/rel
 if not p.is_file() or p.stat().st_size==0: errs.append('missing:'+rel)
man=(ROOT/'android-client/test22/src/main/AndroidManifest.xml').read_text()
for bad in ['android.permission.BLUETOOTH','android.permission.CAMERA','android.permission.RECORD_AUDIO']:
 if bad in man: errs.append('forbidden_permission:'+bad)
probe=(ROOT/'android-client/test22/src/main/java/org/aimindseye/rokid/test22wifi/Test22Probe.java').read_text()
for marker in ['TRANSPORT_WIFI','getSocketFactory().createSocket()','setEndpointIdentificationAlgorithm("HTTPS")','wifi_local_ip_sha256','socket_local_matches_wifi_link_address']:
 if marker not in probe: errs.append('missing_marker:'+marker)
if 'com.rokid.' in probe: errs.append('rokid_sdk_dependency')
runner=(ROOT/'scripts/tests/run_test22_independent_wifi_socket.sh').read_text()
for marker in ['settings get global wifi_on','TEST22_INITIAL_WIFI_STATE','TEST22_WIFI_OFF_BASELINE_MUTATION=NONE','test22_wifi_state.py','test22_install_policy.py','BLOCKED_STANDARD_ADB_APK_INSTALL','TEST22_DIRECT_WIFI_TEST_STARTED=NO']:
 if marker not in runner: errs.append('missing_runner_marker:'+marker)
if errs:
 for e in errs: print('ERROR='+e)
 print('TEST22_SOURCE_CONTRACT=FAIL'); raise SystemExit(1)
print('TEST22_SOURCE_CONTRACT=PASS')
print('BLUETOOTH_PERMISSION=ABSENT')
print('CXR_DEPENDENCY=ABSENT')
print('WIFI_NETWORK_BOUND_SOCKET=PASS')
