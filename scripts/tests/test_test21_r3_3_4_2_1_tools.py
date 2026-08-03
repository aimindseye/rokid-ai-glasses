#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,struct,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('x',HERE/'analyze_test21_r3_3_4_2_1_closure.py');x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)
class Model:
 def __init__(self):self.classes={};self.methods=[];self.method_ins={};self.by_key={}
class T(unittest.TestCase):
 def test_component_normalization(self):
  self.assertEqual(x.normalize_component('a.b','.Svc'),'a.b.Svc');self.assertEqual(x.normalize_component('a.b','c.d.Svc'),'c.d.Svc')
 def test_source_catch_lexical(self):
  t='void invokeSdkConnect(){ try { sdk(); } catch(Exception e){ bindServiceFallback("a","b"); }}\nvoid bindServiceFallback(String a,String b){}'
  self.assertIn('bindServiceFallback',x.extract_method_body(t,'invokeSdkConnect'))
 def test_assignable_interface(self):
  m=Model();m.classes={'LI;':{'super':'Ljava/lang/Object;','interfaces':[]},'LA;':{'super':'Ljava/lang/Object;','interfaces':['LI;']}}
  self.assertTrue(x.class_assignable(m,'LA;','LI;'));self.assertFalse(x.class_assignable(m,'LI;','LA;'))
 def test_shortest(self):
  e={'a':{'b'},'b':{'c'}};self.assertEqual(x.shortest(e,['a'],['c']),['a','b','c'])
 def test_manifest_text(self):
  xml=b'''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.rokid.sprite.global.aiapp"><application><service android:name="com.rokid.sprite.aiapp.externalapp.service.CXRLinkService" android:exported="true"><intent-filter><action android:name="com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE"/></intent-filter></service></application></manifest>'''
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'hi-1-base.apk'
   with zipfile.ZipFile(p,'w') as z:z.writestr('AndroidManifest.xml',xml)
   r=x.manifest_contract([p]);self.assertTrue(r['known_action_resolves_to_cxrlinkservice']);self.assertEqual(r['packages'],['com.rokid.sprite.global.aiapp'])
 def test_binary_string_pool_utf8(self):
  strings=['manifest','package','com.rokid.sprite.global.aiapp']
  payload=b'';offs=[]
  for s in strings:
   raw=s.encode();offs.append(len(payload));payload+=bytes([len(s),len(raw)])+raw+b'\0'
  hdr=28;start=hdr+4*len(strings);size=start+len(payload)
  ch=struct.pack('<HHI',1,hdr,size)+struct.pack('<IIIII',len(strings),0,0x100,start,0)+b''.join(struct.pack('<I',o) for o in offs)+payload
  self.assertEqual(x.parse_string_pool(ch),strings)

 def test_source_role_error_recovery_marker(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);q=r/'app/src/main/java/x';q.mkdir(parents=True);f=q/'CxrLPhotoController.java'
   f.write_text('class CxrLPhotoController { void invokeSdkConnect(){ try { sdk(); } catch(Exception e){ bindServiceFallback("com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE","com.rokid.sprite.global.aiapp"); } } void bindServiceFallback(String a,String b){} }')
   z=x.source_role(r);self.assertTrue(z['available']);self.assertTrue(z['fallback_call_in_catch']);self.assertTrue(z['global_package_present']);self.assertTrue(z['known_action_present'])
 def test_normalize_global_service(self):
  self.assertEqual(x.normalize_component(x.HI_GLOBAL,x.SERVICE_DOT),x.SERVICE_DOT)
 def test_packager_private_exclusion(self):
  src=(HERE/'package_test21_r3_3_4_2_1_sanitized.py').read_text();self.assertIn('APK_INCLUDED=NO',src);self.assertNotIn('r3-3-4-2-1-private.json',src)
 def test_runner_offline(self):
  src=(HERE/'run_test21_r3_3_4_2_1_closure.sh').read_text();self.assertNotIn('adb ',src);self.assertIn('OFFLINE_EXISTING_EVIDENCE_ONLY',src)
if __name__=='__main__':unittest.main(verbosity=2)
