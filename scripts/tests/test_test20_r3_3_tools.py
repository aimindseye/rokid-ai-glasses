#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, tempfile, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
AN=HERE/'analyze_test20_r3_3_callback_closure.py'
FW='1.23.009-20260725-151201'
PKG='org.aimindseye.rokid.cxrphotoqualification'
VER='1.0-test20-r3.3'

def ev(t,d=None,run='run-1'):
    return {'run_id':run,'firmware_label':FW,'event_type':t,'details':d or {}}

def base(profile):
    xs=[
      ev('run_started',{'app_package':PKG,'app_version':VER}),
      ev('callback_profile_selected',{'profile':profile,'one_photo_request_per_run':True,'audio_operation_enabled':False,'payload_persistence_enabled':False}),
      ev('authorization_result',{'token_present':True,'token_value_logged':False}),
      ev('session_config_result',{'configured':True}),
      ev('image_callback_registration_result',{'registration_returned':True,'method':'setCXRImageCbk(IImageStreamCbk)V','registration_phase':'PRE_CONNECT','strong_reference_held':True,'audio_callback_registered':False,'media_request_issued':False,'callback_identity_hash':123}),
      ev('callback_cxrl_connected',{'connected':True}), ev('callback_glass_bt_connected',{'connected':True}),
      ev('service_status_result',{'status_success':True,'glass_bt_status':True}),
      ev('operator_gate_initialized',{'phase':'PREREQUISITE_LOCKED','photo_control_enabled':False}),
      ev('operator_gate_prerequisite_ready',{'photo_control_enabled':False}),
    ]
    if profile=='STRONG_REF_PRECONNECT': xs.append(ev('image_callback_reregistration_skipped',{'reason':'PROFILE_PRECONNECT_ONLY'}))
    else: xs.append(ev('image_callback_reregistration_result',{'registration_returned':True,'registration_phase':'POST_SERVICE_STATUS','same_callback_identity':True,'strong_reference_held':True,'media_request_issued':False}))
    return xs

def armed_events(profile):
    xs=base(profile)
    xs += [
      ev('operator_gate_host_command',{'action_match':True,'run_id_match':True,'token_match':True,'granted':True,'token_value_logged':False,'photo_control_enabled_after_command':True}),
      ev('operator_gate_arm_result',{'granted':True,'host_arm_available':True}),
    ]
    return xs

def final_events(profile, *, payload=False, error=False, returned=True, stable=True, service=True, count=1, strong=True, arg3=None, audio=False):
    xs=armed_events(profile)
    xs.append(ev('operator_gate_capture_dispatch',{'controller_request_accepted':True,'photo_control_enabled_after_click':False}))
    if arg3 is None: arg3=0 if profile=='ARG3_ZERO_DIAGNOSTIC' else 80
    xs.append(ev('callback_path_snapshot',{'phase':'PRE_TAKEPHOTO','cxrl_connected':True,'glass_bt_connected':True,'sdk_glass_bt_connected':True,'service_version_query_returned':True,'service_version_present':True}))
    xs.append(ev('photo_request_result',{'request_count':count,'returned':returned,'error_class':'' if returned else '','arg_3':arg3,'callback_strong_reference_present':strong}))
    xs.append(ev('callback_path_snapshot',{'phase':'POST_TAKEPHOTO_RETURN','cxrl_connected':stable,'glass_bt_connected':stable,'sdk_glass_bt_connected':stable,'service_version_query_returned':service,'service_version_present':service}))
    if payload:
        xs += [ev('image_callback_dispatch',{'kind':'IMAGE'}),ev('image_payload_received',{'callback_count':1})]
        outcome='IMAGE_ACCEPTED'
    elif error:
        xs += [ev('image_callback_dispatch',{'kind':'ERROR'}),ev('image_error_callback',{'callback_count':1})]
        outcome='IMAGE_ERROR_CALLBACK'
    elif returned:
        for ms in (1000,5000,10000,20000,29000):
            xs.append(ev('callback_path_snapshot',{'phase':'POST_TAKEPHOTO_WATCHDOG','checkpoint_ms':ms,'cxrl_connected':stable,'glass_bt_connected':stable,'sdk_glass_bt_connected':stable,'service_version_query_returned':service,'service_version_present':service}))
        outcome='PHOTO_CALLBACK_TIMEOUT'
    else: outcome='PHOTO_REQUEST_REJECTED'
    if audio: xs.append(ev('audio_stream_started',{}))
    xs += [ev('qualification_terminal',{'outcome':outcome,'photo_request_count':count}),ev('run_completed',{'take_photo_request_count':count})]
    return xs

class AnalyzerTests(unittest.TestCase):
    def run_an(self, profile, mode, events, expect=0):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); ep=td/'e.jsonl'; fw=td/'fw.txt'; op=td/'op.txt'; out=td/'s.json'
            ep.write_text(''.join(json.dumps(x)+'\n' for x in events))
            fw.write_text('TEST20_R3_2_1_SCHEMA=rokid.test20-r3.2.1.firmware-attestation.v1\nFIRMWARE_LABEL='+FW+'\nOPERATOR_VISIBLE_FIRMWARE='+FW+'\nOPERATOR_EXACT_MATCH=PASS\nOCR_USED=NO\nSCREENSHOT_SHA256='+'a'*64+'\nSCREENSHOT_BYTES=123\n')
            op.write_text('TEST20_R3_3_SCHEMA=rokid.test20-r3.3.operator-attestation.v1\nPREREQUISITE_GATE=PASS\nFIRMWARE_EXACT_MATCH=PASS\nHOST_ARM_GATE=PASS\nAPK_ARMED_UI_CONFIRMED=PASS\nPHOTO_ARM_GRANTED=YES\nADDITIONAL_MEDIA_ACTION=NO\nHI_ROKID_RECOVERY=PASS\n')
            cmd=['python3',str(AN),'--mode',mode,'--events',str(ep),'--firmware',FW,'--firmware-attestation',str(fw),'--profile',profile,'--summary',str(out)]
            if mode=='final': cmd += ['--operator-attestation',str(op)]
            r=subprocess.run(cmd,text=True,capture_output=True)
            self.assertEqual(r.returncode,expect,r.stdout+r.stderr)
            return r.stdout+r.stderr, (json.loads(out.read_text()) if out.exists() else None)
    def test_prereq_strong(self): self.run_an('STRONG_REF_PRECONNECT','prerequisite',base('STRONG_REF_PRECONNECT'))
    def test_prereq_reregister(self): self.run_an('POSTCONNECT_REREGISTER','prerequisite',base('POSTCONNECT_REREGISTER'))
    def test_delivered(self):
        out,s=self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',payload=True)); self.assertIn('IMAGE_CALLBACK_DELIVERED',out)
    def test_strong_timeout_advances(self):
        out,_=self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT')); self.assertIn('POSTCONNECT_REREGISTER',out)
    def test_reregister_timeout_advances(self):
        out,_=self.run_an('POSTCONNECT_REREGISTER','final',final_events('POSTCONNECT_REREGISTER')); self.assertIn('ARG3_ZERO_DIAGNOSTIC',out)
    def test_arg3_timeout_stops(self):
        out,_=self.run_an('ARG3_ZERO_DIAGNOSTIC','final',final_events('ARG3_ZERO_DIAGNOSTIC')); self.assertIn('STOP_BOUNDED_NONDELIVERY',out)
    def test_two_requests_fail(self): self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',count=2),1)
    def test_strong_ref_missing_fails(self): self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',strong=False),1)
    def test_reregister_identity_fail(self):
        xs=final_events('POSTCONNECT_REREGISTER'); [x['details'].__setitem__('same_callback_identity',False) for x in xs if x['event_type']=='image_callback_reregistration_result']; self.run_an('POSTCONNECT_REREGISTER','final',xs,1)
    def test_audio_fails(self): self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',audio=True),1)
    def test_arg3_mismatch_fails(self): self.run_an('ARG3_ZERO_DIAGNOSTIC','final',final_events('ARG3_ZERO_DIAGNOSTIC',arg3=80),1)
    def test_connection_unstable_stops(self):
        out,_=self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',stable=False)); self.assertIn('CONNECTION_UNSTABLE',out)
    def test_service_unstable_stops(self):
        out,_=self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',service=False)); self.assertIn('SERVICE_UNSTABLE',out)
    def test_error_callback_stops(self):
        out,_=self.run_an('STRONG_REF_PRECONNECT','final',final_events('STRONG_REF_PRECONNECT',error=True)); self.assertIn('IMAGE_ERROR_CALLBACK_DELIVERED',out)

if __name__=='__main__': unittest.main(verbosity=2)
