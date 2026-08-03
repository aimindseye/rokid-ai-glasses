#!/usr/bin/env python3
import importlib.util, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_1_auto_respawn.py')
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
class T(unittest.TestCase):
    def test_no_custom_respawn(self): self.assertEqual(a.next_action('NO_CUSTOM_PROCESS',True,False),'R3_2_SYSTEM_OR_BLUETOOTH_RESPAWN_TRIGGER_CHARACTERIZATION')
    def test_no_custom_no_respawn(self): self.assertEqual(a.next_action('NO_CUSTOM_PROCESS',False,False),'R3_1_PROFILE_CUSTOM_UNAUTHORIZED_ALIVE')
    def test_unauth_respawn(self): self.assertEqual(a.next_action('CUSTOM_UNAUTHORIZED_ALIVE',True,False),'R3_2_CUSTOM_APP_LAUNCH_OR_SDK_INIT_TRIGGER_CHARACTERIZATION')
    def test_authorized_bound(self): self.assertEqual(a.next_action('CUSTOM_AUTHORIZED_NO_CONNECT',True,True),'R4_SERVICE_COMPONENT_DEPENDENCY_QUALIFICATION')
    def test_authorized_no_respawn(self): self.assertEqual(a.next_action('CUSTOM_AUTHORIZED_NO_CONNECT',False,False),'R3_1_PROFILE_CUSTOM_STOPPED_POST_AUTH')
    def test_postauth_stopped_respawn(self): self.assertEqual(a.next_action('CUSTOM_STOPPED_POST_AUTH',True,False),'R3_2_PERSISTENT_POST_AUTH_OR_SYSTEM_TRIGGER_CHARACTERIZATION')
    def test_component_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td); (raw/'respawn-hi-services-private.txt').write_text('ServiceRecord x '+a.HI+'/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService\n')
            self.assertIn(a.HI+'/com.rokid.sprite.aiapp.externalapp.service.CXRLinkService',a.evidence(raw)['components'])
    def test_caller_binding_strict(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td); (raw/'activity-manager-private.txt').write_text(a.CUSTOM+' bindService '+a.HI+'/com.rokid.X\n')
            self.assertTrue(a.evidence(raw)['caller'])
    def test_service_presence_not_caller(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td); (raw/'respawn-hi-services-private.txt').write_text('ConnectionRecord '+a.HI+'/com.rokid.X\n')
            self.assertFalse(a.evidence(raw)['caller'])
class SourceText(unittest.TestCase):
    def test_runner_no_connection(self):
        t=(HERE/'run_test21_r3_1_auto_respawn_trigger.sh').read_text(); self.assertIn('CXR_L_CONNECTION_ATTEMPT=NONE',t); self.assertNotIn('Start one photo connection',t)
    def test_runner_one_hi_force_stop(self):
        t=(HERE/'run_test21_r3_1_auto_respawn_trigger.sh').read_text(); self.assertEqual(t.count('shell am force-stop "$HI_ROKID"'),1)
if __name__=='__main__': unittest.main(verbosity=2)
