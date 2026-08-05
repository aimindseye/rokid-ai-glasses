#!/usr/bin/env python3
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/'android-client/test22'
SRC=MOD/'src/main/java/org/aimindseye/rokid/test22wifi/Test22Probe.java'
MAN=MOD/'src/main/AndroidManifest.xml'

class Test22Contract(unittest.TestCase):
 def test_manifest_is_wifi_only(self):
  s=MAN.read_text()
  for p in ['INTERNET','ACCESS_NETWORK_STATE','ACCESS_WIFI_STATE','CHANGE_WIFI_STATE']:
   self.assertIn('android.permission.'+p,s)
  for bad in ['BLUETOOTH','CAMERA','RECORD_AUDIO','ACCESS_FINE_LOCATION']:
   self.assertNotIn('android.permission.'+bad,s)
 def test_no_rokid_or_bluetooth_api(self):
  s=SRC.read_text()
  self.assertNotRegex(s,r'com\.rokid\.')
  self.assertNotIn('Bluetooth',s)
  self.assertIn('TRANSPORT_WIFI',s)
  self.assertIn('selection.network.getSocketFactory().createSocket()',s)
  self.assertIn('setEndpointIdentificationAlgorithm("HTTPS")',s)
  self.assertIn('socket_local_matches_wifi_link_address',s)
 def test_legacy_target_is_explicit_and_bounded(self):
  s=(MOD/'build.gradle.kts').read_text()
  self.assertIn('targetSdk = 28',s)
  self.assertIn('sideload-only control-plane test',s)
 def test_runner_requires_isolation_and_live_token(self):
  s=(ROOT/'scripts/tests/run_test22_independent_wifi_socket.sh').read_text()
  self.assertIn('TEST22_LIVE_WIFI_SOCKET',s)
  self.assertIn('phone_isolation_confirmation_required',s)
  self.assertIn('svc wifi disable',s)
  self.assertNotIn('set -e',s)
  self.assertNotIn('set -u',s)
  self.assertNotIn('pipefail',s)
 def test_analyzer_requires_wifi_bound_peer_agreement(self):
  s=(ROOT/'scripts/tests/analyze_test22_wifi_socket.py').read_text()
  for marker in ['wifi_transport_found','wifi_default_route','socket_local_matches_wifi_link_address','peer_ip_sha256','PASS_APP_DRIVEN_WIFI_AND_DIRECT_TLS']:
   self.assertIn(marker,s)

if __name__=='__main__': unittest.main()
