#!/usr/bin/env python3
import importlib.util,tempfile,unittest,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_3_4_local_activation.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
class T(unittest.TestCase):
 def test_norm(self):self.assertEqual(M.norm('com.rokid.sprite.global.aiapp/.X'),'com.rokid.sprite.global.aiapp/com.rokid.sprite.global.aiapp.X')
 def test_process_service_trigger(self):
  e=[{'epoch_ms':1,'kind':'PROCESS_START','components':['com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'],'classes':[M.CXR_SERVICE],'line':'Start proc x for service {com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService}'}]
  self.assertEqual(M.process_trigger(e)[1:4],('SERVICE','com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService',M.CXR_SERVICE))
 def test_process_provider_trigger(self):
  e=[{'epoch_ms':1,'kind':'PROCESS_START','components':['com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.external.CXRLinkProvider'],'classes':[M.CXR_PROVIDER],'line':'Start proc x for content provider {com.rokid.sprite.global.aiapp/com.rokid.sprite.aiapp.external.CXRLinkProvider}'}]
  self.assertEqual(M.process_trigger(e)[1], 'CONTENT_PROVIDER')
 def test_process_identity_not_component(self):
  self.assertEqual(M.get_components('Start proc 12:com.rokid.sprite.global.aiapp/u0a123 for unknown'),[])
  e=[{'epoch_ms':1,'kind':'PROCESS_START','components':[],'classes':[],'line':'Start proc 12:com.rokid.sprite.global.aiapp/u0a123 for unknown'}]
  self.assertEqual(M.process_trigger(e)[1:4],('UNKNOWN',None,None))
 def test_dispositions(self):
  rt={'cxr_link_service_runtime':False,'cxr_link_provider_runtime':False}
  self.assertEqual(M.disposition('SERVICE',M.CXR_SERVICE,rt,1),'EXACT_CXRLINKSERVICE_PROCESS_START_TRIGGER')
  self.assertEqual(M.disposition('CONTENT_PROVIDER',M.CXR_PROVIDER,rt,1),'EXACT_CXRLINKPROVIDER_PROCESS_START_TRIGGER')
  self.assertEqual(M.disposition('NONE',None,rt,None),'NO_HI_ROKID_RESPAWN')
 def test_collector_ready_contract_source(self):
  src=(HERE/'collect_test21_r3_3_4_local_activation.py').read_text()
  self.assertIn('--ready-file',src);self.assertIn('HI_PROCESS_VISIBLE=',src)
 def test_equal_host_order(self):
  c={'first_hi_respawn_host_epoch_ms':5,'event_first_seen_host_epoch_ms':{'connection_attempt_started':5}}
  self.assertEqual(M.host_order(c),'SAME_OBSERVATION_TIMESTAMP')
if __name__=='__main__':unittest.main(verbosity=2)
