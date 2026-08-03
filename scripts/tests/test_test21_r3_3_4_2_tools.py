#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,tempfile,unittest,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_3_4_2_static_contract.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class FakeDex:
 def __init__(self,ins):self._ins=ins
 def insns(self,idx):return self._ins
class T(unittest.TestCase):
 def test_separator_no_external_decompiler(self):
  src=(HERE/'analyze_test21_r3_3_4_2_static_contract.py').read_text();self.assertNotIn('jadx',src.lower());self.assertIn('class Dex:',src)
 def test_intent_simulation(self):
  intent_ctor={'class':a.INTENT,'name':'<init>','proto':'(Ljava/lang/String;)V','ret':'V','params':['Ljava/lang/String;']}
  setpkg={'class':a.INTENT,'name':'setPackage','proto':'(Ljava/lang/String;)Landroid/content/Intent;','ret':a.INTENT,'params':['Ljava/lang/String;']}
  bind={'class':'Landroid/content/Context;','name':'bindService','proto':'(Landroid/content/Intent;Landroid/content/ServiceConnection;I)Z','ret':'Z','params':[]}
  m={'class':a.CXR_PREFIX+'Client;','name':'bind','proto':'()V','ret':'V','idx':0,'code_off':1,'dex':FakeDex([])}
  model=a.Model();model.methods=[m];model.by_key={a.Model.key(m):m}
  model.method_ins[a.Model.key(m)]=[
   {'kind':'new','dst':1,'value':a.INTENT},{'kind':'string','dst':2,'value':a.KNOWN_ACTION},{'kind':'invoke','pc':1,'method':intent_ctor,'regs':[1,2]},
   {'kind':'string','dst':3,'value':a.HI_PACKAGE},{'kind':'invoke','pc':2,'method':setpkg,'regs':[1,3]},
   {'kind':'fieldobj','dst':4,'src':0,'field':{'type':a.SERVICE_CONNECTION,'name':'conn','class':m['class']}},{'kind':'const','dst':5,'value':1},{'kind':'invoke','pc':3,'method':bind,'regs':[0,1,4,5]}]
  r=a.simulate(model,m,{});e=r['events'][-1];self.assertEqual(e['args'][1]['action'],a.KNOWN_ACTION);self.assertEqual(e['args'][1]['package'],a.HI_PACKAGE);self.assertEqual(e['args'][-1]['value'],1)
 def test_stub_interface(self):self.assertEqual(a.interface_from_stub('Lrokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'),'Lrokid/sprite/aiapp/externalapp/IMediaStreamService;')
 def test_shortest_path(self):
  m=a.Model();target='Lcom/rokid/cxr/X;->bind()V';mid='Lcom/rokid/cxr/X;->connect()V';root='Lorg/aimindseye/rokid/A;->go()V';m.reverse[target].add(mid);m.reverse[mid].add(root);self.assertEqual(a.shortest_path(m,target),[root,mid,target])
 def test_widths(self):self.assertEqual(a.width(0x6e),3);self.assertEqual(a.width(0x1a),2);self.assertEqual(a.width(0x18),5)
 def test_desc(self):self.assertEqual(a.desc_to_dot('Lx/y/IThing;'),'x.y.IThing')
 def test_packager_no_private(self):
  src=(HERE/'package_test21_r3_3_4_2_sanitized.py').read_text();self.assertIn('APK_INCLUDED=NO',src);self.assertNotIn('static-contract-private.json',src)
if __name__=='__main__':unittest.main(verbosity=2)
