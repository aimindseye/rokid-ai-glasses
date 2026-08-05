#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
AN=ROOT/'scripts/tests/analyze_test22_wifi_socket.py'
class AnalyzerTests(unittest.TestCase):
 def run_case(self,app,backend):
  with tempfile.TemporaryDirectory() as td:
   t=Path(td); (t/'a.json').write_text(json.dumps(app)); (t/'b.json').write_text(json.dumps(backend))
   p=subprocess.run(['python3',str(AN),'--app-result',str(t/'a.json'),'--backend-result',str(t/'b.json'),'--phone-isolation-confirmed','YES','--output',str(t/'s.json')],text=True,capture_output=True)
   return p,json.loads((t/'s.json').read_text())
 def test_full_pass(self):
  h='a'*64
  app={'feature_wifi':True,'wifi_service_present':True,'wifi_enabled_before':False,'wifi_enable_requested_by_app':True,'wifi_enable_request_return':True,'wifi_enabled_after_request':True,'wifi_network_add_id_nonnegative':True,'wifi_enable_network_return':True,'wifi_reconnect_return':True,'wifi_transport_found':True,'wifi_default_route':True,'tcp_connect_success':True,'tls_handshake_success':True,'tls_echo_verified':True,'socket_local_matches_wifi_link_address':True,'socket_local_ip_sha256':h,'nonce_sha256':'b'*64,'bluetooth_api_used':False,'cxr_api_used':False,'default_network_socket_used':False}
  back={'status':'PASS','request_verified':True,'peer_ip_sha256':h,'nonce_sha256':'b'*64}
  p,s=self.run_case(app,back); self.assertEqual(p.returncode,0); self.assertEqual(s['disposition'],'PASS_APP_DRIVEN_WIFI_AND_DIRECT_TLS')
 def test_peer_mismatch_cannot_pass(self):
  h='a'*64
  app={'feature_wifi':True,'wifi_service_present':True,'wifi_enabled_before':False,'wifi_enable_requested_by_app':True,'wifi_enable_request_return':True,'wifi_enabled_after_request':True,'wifi_network_add_id_nonnegative':True,'wifi_enable_network_return':True,'wifi_reconnect_return':True,'wifi_transport_found':True,'wifi_default_route':True,'tcp_connect_success':True,'tls_handshake_success':True,'tls_echo_verified':True,'socket_local_matches_wifi_link_address':True,'socket_local_ip_sha256':h,'nonce_sha256':'b'*64}
  back={'status':'PASS','request_verified':True,'peer_ip_sha256':'c'*64,'nonce_sha256':'b'*64}
  _,s=self.run_case(app,back); self.assertNotEqual(s['disposition'],'PASS_APP_DRIVEN_WIFI_AND_DIRECT_TLS')
if __name__=='__main__': unittest.main()
