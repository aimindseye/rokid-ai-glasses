#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('x',HERE/'analyze_test21_r3_3_4_2_2_closure.py');x=importlib.util.module_from_spec(sp);sp.loader.exec_module(x)
class FakeDex:
 def __init__(self):self.data=b'\0'*64;self.fields=[]
class FakeModel:
 key=staticmethod(lambda m:m['class']+'->'+m['name']+m['proto'])
 def __init__(self):self.methods=[];self.method_ins={};self.by_key={};self.classes={}
class T(unittest.TestCase):
 def test_location(self):
  self.assertEqual(x.location_disposition({'class_defs':[{}],'type_refs':[],'string_refs':[],'raw_entry_hits':[]}), 'CLASS_DEF_FOUND')
  self.assertEqual(x.location_disposition({'class_defs':[],'type_refs':[{}],'string_refs':[],'raw_entry_hits':[]}), 'REFERENCE_ONLY_NO_CLASS_DEF')
 def test_safe_secret_source_only(self):
  v=x.safe_value({'kind':'param','param_index':2,'type':'Ljava/lang/String;','name':'arg2'});self.assertEqual(v['kind'],'param');self.assertNotIn('value',v)
 def test_source_decision_reasons(self):
  class P:
   @staticmethod
   def find_controller_source(repo):return repo/'CxrLPhotoController.java'
   @staticmethod
   def extract_method_body(t,n):
    import re
    m=re.search(r'void '+n+r'\(\)\{(.*?)\}\n',t,re.S);return m.group(1) if m else ''
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'CxrLPhotoController.java').write_text('void invokeSdkConnect(){bindServiceFallback("sdk_connect_returned_false");bindServiceFallback("sdk_connect_method_missing");}\nvoid startConnection(){bindServiceFallback("delayed_fallback");}\n')
   q=x.source_decisions(r,P);self.assertEqual(set(q['reasons']),{'sdk_connect_returned_false','sdk_connect_method_missing','delayed_fallback'})
 def test_runner_offline(self):
  s=(HERE/'run_test21_r3_3_4_2_2_closure.sh').read_text();self.assertNotIn('adb ',s);self.assertIn('REGISTER_DATAFLOW',s)
 def test_packager_excludes_private(self):
  s=(HERE/'package_test21_r3_3_4_2_2_sanitized.py').read_text();self.assertIn('PRIVATE_JSON_INCLUDED=NO',s);self.assertNotIn("q.write(e/'r3-3-4-2-2-private.json'",s)

 def test_trace_fallback_exact_register_flow(self):
  import struct
  m=FakeModel();d=FakeDex();buf=bytearray(64);struct.pack_into('<H',buf,16,12);struct.pack_into('<H',buf,18,0);d.data=bytes(buf)
  meth={'class':x.CONTROLLER,'name':'bindServiceFallback','proto':'()V','params':[],'access':0x8,'code_off':16,'dex':d};key=m.key(meth);m.methods=[meth];m.by_key={key:meth}
  def inv(cls,name,proto='()V',ret='V'):return {'class':cls,'name':name,'proto':proto,'ret':ret,'params':[]}
  m.method_ins[key]=[
   {'pc':0,'kind':'new','value':x.INTENT,'dst':0},
   {'pc':1,'kind':'string','value':x.MEDIA_ACTION,'dst':1},
   {'pc':2,'kind':'invoke','method':inv(x.INTENT,'<init>','(Ljava/lang/String;)V'),'regs':[0,1]},
   {'pc':3,'kind':'string','value':x.HI_GLOBAL,'dst':2},
   {'pc':4,'kind':'invoke','method':inv(x.INTENT,'setPackage','(Ljava/lang/String;)Landroid/content/Intent;',x.INTENT),'regs':[0,2]},
   {'pc':5,'kind':'moveresultobj','dst':0},
   {'pc':6,'kind':'string','value':'auth_package','dst':3},
   {'pc':7,'kind':'string','value':'caller.pkg','dst':4},
   {'pc':8,'kind':'invoke','method':inv(x.INTENT,'putExtra','(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;',x.INTENT),'regs':[0,3,4]},
   {'pc':9,'kind':'moveresultobj','dst':0},
   {'pc':10,'kind':'string','value':'auth_token','dst':5},
   {'pc':11,'kind':'fieldobj','dst':6,'field':{'class':'LC;','name':'token','type':'Ljava/lang/String;'}},
   {'pc':12,'kind':'invoke','method':inv(x.INTENT,'putExtra','(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;',x.INTENT),'regs':[0,5,6]},
   {'pc':13,'kind':'moveresultobj','dst':0},
   {'pc':14,'kind':'fieldobj','dst':7,'field':{'class':'LC;','name':'conn','type':'Landroid/content/ServiceConnection;'}},
   {'pc':15,'kind':'const','dst':8,'value':1},
   {'pc':16,'kind':'invoke','method':inv('Landroid/content/Context;','bindService','(Landroid/content/Intent;Landroid/content/ServiceConnection;I)Z','Z'),'regs':[9,0,7,8]}]
  q=x.trace_fallback(m,key,{},{});self.assertEqual(len(q['bind_events']),1);e=q['bind_events'][0];self.assertEqual(e['intent']['action'],x.MEDIA_ACTION);self.assertEqual(e['intent']['package'],x.HI_GLOBAL);self.assertEqual(e['flags'],1);self.assertEqual(set(e['intent']['extras']),{'auth_package','auth_token'})

 def test_targets(self):
  self.assertIn(x.SERVICE_DESC,x.TARGETS);self.assertIn(x.MEDIA_STUB,x.TARGETS);self.assertIn(x.MEDIA_PROXY,x.TARGETS)
 def test_field_key(self):
  self.assertEqual(x.field_key({'class':'LA;','name':'X','type':'Ljava/lang/String;'}),'LA;->X:Ljava/lang/String;')
if __name__=='__main__':unittest.main(verbosity=2)
