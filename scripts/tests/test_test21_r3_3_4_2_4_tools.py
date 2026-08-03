#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,io,struct,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('x',HERE/'analyze_test21_r3_3_4_2_4_payload_origin.py');x=importlib.util.module_from_spec(sp);sp.loader.exec_module(x)
class FakeDex:
 def __init__(self,data,name):
  self.types=[x.SERVICE_DESC,x.MEDIA_DESC,x.STUB_DESC];self.strings=[x.SERVICE_DOT,x.MEDIA_DOT];self.methods=[{'name':'onBind','proto':'(Landroid/content/Intent;)Landroid/os/IBinder;','ret':'Landroid/os/IBinder;'}];self.classes={x.SERVICE_DESC:{'super':'Landroid/app/Service;','interfaces':[],'methods':[0]},x.STUB_DESC:{'super':'Landroid/os/Binder;','interfaces':[x.MEDIA_DESC],'methods':[]}}
class T(unittest.TestCase):
 def test_embedded_dex_header(self):
  b=bytearray(160);b[:8]=b'dex\n035\0';struct.pack_into('<I',b,32,len(b));struct.pack_into('<I',b,36,0x70)
  r=x.embedded_dex_slices(b'xx'+bytes(b)+b'yy');self.assertEqual(r[0][0],2);self.assertEqual(len(r[0][1]),160)
 def test_marker_scan(self):
  d=(x.SERVICE_DOT+' DexClassLoader RegisterNatives').encode();self.assertIn(x.SERVICE_DOT,x.marker_hits_bytes(d,x.TARGET_NEEDLES));self.assertIn('DexClassLoader',x.marker_hits_bytes(d,x.LOADER_MARKERS))
 def test_exact_class_definition(self):
  q,subs,e=x.scan_dex_with(FakeDex,x.SERVICE_DESC.encode(),'classes.dex');self.assertFalse(e);self.assertEqual(len(q[x.SERVICE_DESC]['class_defs']),1);self.assertEqual(q[x.SERVICE_DESC]['class_defs'][0]['methods'][0]['name'],'onBind')
 def test_raw_reference_not_exact(self):
  class Bad:
   def __init__(self,*a):raise ValueError('bad')
  q,_,e=x.scan_dex_with(Bad,x.SERVICE_DESC.encode(),'x.dex');self.assertTrue(q[x.SERVICE_DESC]['raw_hits']);self.assertFalse(q[x.SERVICE_DESC]['class_defs']);self.assertIn('ValueError',e)
 def test_shared_library_sanitizer(self):
  q=x.shared_library_names('usesLibraries:\n  com.rokid.cxr.runtime\nlibrary:android.foo\n');self.assertEqual(q,['com.rokid.cxr.runtime'])
 def test_nested_zip_detection(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('x.txt','hello')
  self.assertIsNotNone(x.try_nested_zip(b.getvalue()))
 def test_runner_root_optional_read_only(self):
  s=(HERE/'run_test21_r3_3_4_2_4_payload_origin.sh').read_text();self.assertIn('--root-mode',s);self.assertIn('su -c id',s);self.assertIn('PAYLOAD_EXECUTION=NONE',s);self.assertNotIn('force-stop',s);self.assertNotIn('am start',s);self.assertNotIn('set -e',s)
 def test_packager_private_exclusion(self):
  s=(HERE/'package_test21_r3_3_4_2_4_sanitized.py').read_text();self.assertIn('RAW_APK_JAR_DEX_SO_INCLUDED=NO',s);self.assertIn('PRIVATE_PAYLOAD_JSON_INCLUDED=NO',s)
if __name__=='__main__':unittest.main(verbosity=2)
