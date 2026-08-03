#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('x',HERE/'analyze_test21_r3_3_4_2_3_code_origin.py');x=importlib.util.module_from_spec(sp);sp.loader.exec_module(x)
class FakeDex:
 def __init__(self,data,name):
  self.types=[x.SERVICE_DESC,x.STUB_DESC];self.strings=[x.SERVICE_DOT];self.classes={x.SERVICE_DESC:{'super':'Landroid/app/Service;','interfaces':[],'methods':[0]},x.STUB_DESC:{'super':'Landroid/os/Binder;','interfaces':[x.MEDIA_DESC],'methods':[]}};self.methods=[{'name':'onBind','proto':'(Landroid/content/Intent;)Landroid/os/IBinder;','ret':'Landroid/os/IBinder;'}]
class T(unittest.TestCase):
 def test_pm_paths(self):self.assertEqual(x.parse_pm_paths('package:/a/base.apk\npackage:/a/split.apk\n'),['/a/base.apk','/a/split.apk'])
 def test_artifact_paths(self):
  q=x.absolute_artifact_paths('x /system/framework/a.jar y /data/app/z/base.apk]')
  self.assertIn('/system/framework/a.jar',q);self.assertIn('/data/app/z/base.apk',q)
 def test_maps_status(self):
  self.assertEqual(x.classify_maps('DENIED_BY_ANDROID','','123'),'DENIED_BY_ANDROID');self.assertEqual(x.classify_maps('','',''),'PROCESS_NOT_RUNNING')
 def test_exact_class_def_scan(self):
  q=x.scan_dex_bytes(x.SERVICE_DESC.encode(),'classes.dex',FakeDex)[0]
  self.assertEqual(len(q[x.SERVICE_DESC]['class_defs']),1);self.assertEqual(q[x.SERVICE_DESC]['class_defs'][0]['methods'][0]['name'],'onBind')
 def test_reference_not_definition_on_parse_error(self):
  class Bad:
   def __init__(self,*a):raise ValueError('bad')
  q,_,e=x.scan_dex_bytes(x.SERVICE_DESC.encode(),'classes.dex',Bad);self.assertTrue(q[x.SERVICE_DESC]['raw_hits']);self.assertFalse(q[x.SERVICE_DESC]['class_defs']);self.assertIn('ValueError',e)
 def test_pull_manifest(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'m';p.write_text('KIND\tREMOTE_PATH\tLOCAL_REL\tSTATUS\tSHA256\nPACKAGE_CODE\t/a/base.apk\tpackage-code/code-1.apk\tPASS\tabc\n')
   r=x.read_pull_manifest(p);self.assertEqual(r[0]['status'],'PASS')
 def test_runner_is_read_only(self):
  s=(HERE/'run_test21_r3_3_4_2_3_code_origin.sh').read_text();self.assertIn('adb -s "$PHONE" pull',s);self.assertNotIn('force-stop',s);self.assertNotIn('am start',s);self.assertNotIn('set -e',s)
 def test_packager_excludes_private(self):
  s=(HERE/'package_test21_r3_3_4_2_3_sanitized.py').read_text();self.assertIn('RAW_PROCESS_MAPS_INCLUDED=NO',s);self.assertNotIn('r3-3-4-2-3-private.json\'',s.split('with zipfile.ZipFile',1)[1] if 'with zipfile.ZipFile' in s else '')
if __name__=='__main__':unittest.main(verbosity=2)
