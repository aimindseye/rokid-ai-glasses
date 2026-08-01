#!/usr/bin/env python3
import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AN=ROOT/'scripts/tests/analyze_test20_r3_2_photo.py'
SPEC=importlib.util.spec_from_file_location('t20r32',AN); MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
class Tests(unittest.TestCase):
    firmware='1.23.009-20260725-153201'
    def e(self,t,d,n): return {'schema':MOD.SCHEMA,'time_epoch_ms':1700000000000+n,'elapsed_realtime_ms':n,'run_id':'synthetic','firmware_label':self.firmware,'event_type':t,'details':d}
    def passing(self):
        return [
          self.e('run_started',{'app_package':MOD.EXPECTED_PACKAGE,'app_version':MOD.EXPECTED_VERSION,'app_version_code':1,'internet_permission_intentionally_removed':True,'camera_permission_intentionally_removed':True,'record_audio_permission_intentionally_removed':True,'image_callback_registration_enabled':True,'service_status_queries_enabled':True,'take_photo_invocation_enabled':True,'max_photo_request_count':1,'photo_arg_1':1920,'photo_arg_2':1080,'photo_arg_3':80,'photo_argument_semantics':MOD.EXPECTED_SEMANTICS,'image_payload_persistence_enabled':False,'image_preview_enabled':False,'audio_stream_invocation_enabled':False,'cloud_api_client_present':False},1),
          self.e('hi_rokid_environment',{'package_name':'com.rokid.sprite.global.aiapp','version_name':MOD.EXPECTED_HI_ROKID_VERSION,'authorization_resolved':True,'service_resolved':True},2),
          self.e('authorization_result',{'token_present':True,'token_value_logged':False},3),
          self.e('image_callback_registration_result',{'registration_returned':True,'audio_callback_registered':False,'media_request_issued':False},4),
          self.e('session_config_result',{'configured':True,'session_type':'CUSTOMAPP'},5),
          self.e('callback_cxrl_connected',{'connected':True},6),
          self.e('callback_glass_bt_connected',{'connected':True},7),
          self.e('service_status_result',{'service_version_query_returned':True,'service_version_present':True,'service_version':'1.2.3','service_version_code_query_returned':True,'service_version_code_present':True,'service_version_code':10000,'glass_bt_status_query_returned':True,'glass_bt_status':True,'status_success':True,'photo_request_issued':False},8),
          self.e('photo_ready',{'explicit_operator_tap_required':True,'max_request_count':1,'arg_1':1920,'arg_2':1080,'arg_3':80,'argument_semantics':MOD.EXPECTED_SEMANTICS,'payload_persistence_enabled':False,'payload_preview_enabled':False},9),
          self.e('photo_request_result',{'method':'takePhoto(III)Z','request_count':1,'arg_1':1920,'arg_2':1080,'arg_3':80,'argument_semantics':MOD.EXPECTED_SEMANTICS,'returned':True,'error_class':'','payload_persistence_enabled':False,'payload_preview_enabled':False},10),
          self.e('image_payload_received',{'callback_count':1,'payload_present':True,'payload_length':43210,'payload_digest_sha256_private':'a'*64,'payload_bytes_logged':False,'payload_persisted':False,'payload_previewed':False,'format_hint':'JPEG','decoded_width':1920,'decoded_height':1080,'decoded_mime_type':'image/jpeg','request_to_callback_latency_ms':850,'valid_nonempty_image':True},11),
          self.e('duplicate_callback_window_armed',{'window_ms':3000,'accepted_callback_count':1,'payload_persisted':False},12),
          self.e('qualification_terminal',{'outcome':'ONE_SHOT_PHOTO_RECEIVED','success':True,'photo_request_count':1,'image_payload_callback_count':1,'image_error_callback_count':0},13),
          self.e('disconnect_result',{'sdk_disconnect_returned':True,'manual_unbind_attempted':False},14),
          self.e('run_completed',{'terminal_success':True,'test_app_cloud_request':'NONE','take_photo_request_count':1,'start_audio_stream_invocation':'NONE','stop_audio_stream_invocation':'NONE','image_payload_persistence':'NONE','image_payload_preview':'NONE','media_upload':'NONE'},15),
        ]
    def run_analysis(self,events,att='BOUNDED_TEST_TARGET_ONLY=YES\nADDITIONAL_MEDIA_ACTION=NO\nHI_ROKID_RECOVERY=PASS\n'):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); ep=td/'e.jsonl'; ep.write_text('\n'.join(json.dumps(x) for x in events)+'\n')
            op=td/'o.txt'; op.write_text(att)
            return MOD.analyze(ep,op,self.firmware)
    def test_pass(self): self.assertEqual(self.run_analysis(self.passing())['qualification']['photo_request_count'],1)
    def test_duplicate_request_fails(self):
        x=self.passing(); x.insert(10,self.e('photo_request_result',x[9]['details'],10)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_duplicate_callback_fails(self):
        x=self.passing(); x.insert(11,self.e('image_payload_received',x[10]['details'],11)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_image_error_fails(self):
        x=self.passing(); x.insert(11,self.e('image_error_callback',{'error_code':1},11)); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_empty_payload_fails(self):
        x=self.passing(); x[10]['details']['payload_length']=0; x[10]['details']['payload_present']=False; self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_target_attestation_fails(self):
        self.assertRaises(MOD.AnalysisError,self.run_analysis,self.passing(),'BOUNDED_TEST_TARGET_ONLY=NO\nADDITIONAL_MEDIA_ACTION=NO\nHI_ROKID_RECOVERY=PASS\n')
    def test_raw_address_fails(self):
        x=self.passing(); x[0]['details']['device']=':'.join(('AA','BB','CC','DD','EE','FF')); self.assertRaises(MOD.AnalysisError,self.run_analysis,x)
    def test_manifest_permissions_removed(self):
        m=(ROOT/'android-client/test20r32/src/main/AndroidManifest.xml').read_text()
        for p in ('android.permission.INTERNET','android.permission.CAMERA','android.permission.RECORD_AUDIO'): self.assertIn(p,m)
        self.assertEqual(m.count('tools:node="remove"'),3)
    def test_controller_exactly_one_photo_call_and_no_audio(self):
        s=(ROOT/'android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification/CxrLPhotoController.java').read_text()
        self.assertEqual(s.count('link.takePhoto('),1)
        for token in ('startAudioStream(', 'stopAudioStream(', 'setCXRAudioCbk(', 'sendCustomCmd(', 'customViewOpen(', 'appUploadAndInstall('): self.assertNotIn(token,s)
    def test_no_payload_persistence_api(self):
        s=(ROOT/'android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification/CxrLPhotoController.java').read_text()
        for token in ('FileOutputStream','Bitmap.compress','ContentResolver.insert','MediaStore.Images','openFileOutput'): self.assertNotIn(token,s)
        self.assertIn('options.inJustDecodeBounds = true',s)
    def test_contract_triplet(self):
        s=(ROOT/'android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification/Test20R32Contract.java').read_text()
        for token in ('PHOTO_ARG_1 = 1920','PHOTO_ARG_2 = 1080','PHOTO_ARG_3 = 80','WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED'): self.assertIn(token,s)
if __name__=='__main__': unittest.main()
