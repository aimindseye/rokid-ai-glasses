#!/usr/bin/env python3
import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AN=ROOT/'scripts/tests/analyze_test20_r3_1_preflight.py'
SPEC=importlib.util.spec_from_file_location('t20r31',AN); MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
class Tests(unittest.TestCase):
    firmware='1.23.009-20260725-153201'
    def e(self,t,d,n): return {'schema':MOD.SCHEMA,'time_epoch_ms':1700000000000+n,'elapsed_realtime_ms':n,'run_id':'synthetic','firmware_label':self.firmware,'event_type':t,'details':d}
    def passing(self):
        return [
          self.e('run_started',{'app_package':MOD.EXPECTED_PACKAGE,'app_version':MOD.EXPECTED_VERSION,'app_version_code':1,'internet_permission_intentionally_removed':True,'camera_permission_intentionally_removed':True,'record_audio_permission_intentionally_removed':True,'callback_registration_enabled':True,'service_status_queries_enabled':True,'take_photo_invocation_enabled':False,'audio_stream_invocation_enabled':False,'media_payload_retention_enabled':False,'cloud_api_client_present':False},1),
          self.e('hi_rokid_environment',{'package_name':'com.rokid.sprite.global.aiapp','version_name':MOD.EXPECTED_HI_ROKID_VERSION,'authorization_resolved':True,'service_resolved':True},2),
          self.e('authorization_result',{'token_present':True,'token_value_logged':False},3),
          self.e('callback_registration_result',{'image_registration_returned':True,'audio_registration_returned':True,'media_request_issued':False},4),
          self.e('session_config_result',{'configured':True,'session_type':'CUSTOMAPP'},5),
          self.e('callback_cxrl_connected',{'connected':True},6),
          self.e('callback_glass_bt_connected',{'connected':True},7),
          self.e('service_status_result',{'service_version_query_returned':True,'service_version_present':True,'service_version':'1.2.3','service_version_code_query_returned':True,'service_version_code_present':True,'service_version_code':123,'glass_bt_status_query_returned':True,'glass_bt_status':True,'status_success':True,'media_request_issued':False},8),
          self.e('no_payload_observation_armed',{'observation_ms':15000,'take_photo_invoked':False,'start_audio_stream_invoked':False,'stop_audio_stream_invoked':False},9),
          self.e('qualification_terminal',{'outcome':'NO_PAYLOAD_OBSERVATION_COMPLETE','success':True,'image_payload_callback_count':0,'image_error_callback_count':0,'audio_payload_callback_count':0,'audio_error_callback_count':0,'audio_state_true_callback_count':0},10),
          self.e('disconnect_result',{'sdk_disconnect_returned':True,'manual_unbind_attempted':False},11),
          self.e('run_completed',{'terminal_success':True,'test_app_cloud_request':'NONE','take_photo_invocation':'NONE','start_audio_stream_invocation':'NONE','stop_audio_stream_invocation':'NONE','image_payload_retention':'NONE','audio_payload_retention':'NONE'},12),
        ]
    def run_analysis(self,events):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); ep=td/'e.jsonl'; ep.write_text('\n'.join(json.dumps(x) for x in events)+'\n')
            op=td/'o.txt'; op.write_text('OPERATOR_MEDIA_ACTION=NO\nHI_ROKID_RECOVERY=PASS\n')
            return MOD.analyze(ep,op,self.firmware)
    def test_pass(self): self.assertEqual(self.run_analysis(self.passing())['qualification']['image_payload_callbacks'],0)
    def test_image_payload_fails(self):
        x=self.passing(); x.insert(-2,self.e('unexpected_image_payload_callback',{'payload_present':True,'payload_length':1,'payload_bytes_logged':False},9)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_audio_payload_fails(self):
        x=self.passing(); x.insert(-2,self.e('unexpected_audio_payload_callback',{'payload_present':True,'payload_length':1,'payload_bytes_logged':False},9)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_audio_active_fails(self):
        x=self.passing(); x.insert(-2,self.e('audio_stream_state_callback',{'streaming':True},9)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_token_key_fails(self):
        x=self.passing(); x[0]['details']['auth_token']='secret'; self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_raw_address_fails(self):
        x=self.passing(); x[0]['details']['device']=':'.join(('AA','BB','CC','DD','EE','FF')); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_manifest_permissions_removed(self):
        m=(ROOT/'android-client/test20r31/src/main/AndroidManifest.xml').read_text()
        for p in ('android.permission.INTERNET','android.permission.CAMERA','android.permission.RECORD_AUDIO'): self.assertIn(p,m)
        self.assertEqual(m.count('tools:node="remove"'),3)
    def test_controller_has_no_media_invocation(self):
        s=(ROOT/'android-client/test20r31/src/main/java/org/aimindseye/rokid/cxrmediapreflight/CxrLMediaPreflightController.java').read_text()
        for token in ('takePhoto(', 'startAudioStream(', 'stopAudioStream(', 'sendCustomCmd(', 'customViewOpen(', 'appUploadAndInstall('): self.assertNotIn(token,s)
    def test_service_queries_present(self):
        s=(ROOT/'android-client/test20r31/src/main/java/org/aimindseye/rokid/cxrmediapreflight/CxrLMediaPreflightController.java').read_text()
        for token in ('getServiceVersion()', 'getServiceVersionCode()', 'isGlassBtConnected()', 'setCXRImageCbk(', 'setCXRAudioCbk('): self.assertIn(token,s)
if __name__=='__main__': unittest.main()
