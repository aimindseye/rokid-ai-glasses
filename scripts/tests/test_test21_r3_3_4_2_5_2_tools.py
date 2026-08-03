#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,struct,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
c=load('collector','collect_test21_r3_3_4_2_5_2_external_memory.py')
class T(unittest.TestCase):
 def test_maps_and_priority(self):
  r=c.parse_maps('1000-3000 rw-p 00000000 00:00 0 [anon:dalvik-main space]\n4000-5000 r--p 00000000 00:00 0 /system/lib64/libc.so\n');self.assertEqual(len(r),2);self.assertEqual(c.bucket(r[0]),0);self.assertEqual(c.bucket(r[1]),3)
 def test_plan_cap(self):
  rows=[{'start':0,'end':64*1024*1024,'size':64*1024*1024,'perms':'rw-p','path':'[anon:dalvik]'}];p=c.plan_chunks(rows,8*1024*1024,24*1024*1024);self.assertEqual(sum(x['size'] for x in p),24*1024*1024)
 def test_valid_header(self):
  b=bytearray(0x200);b[:8]=b'dex\n035\0';struct.pack_into('<I',b,0x20,0x180);struct.pack_into('<I',b,0x24,0x70);struct.pack_into('<I',b,0x28,0x12345678);self.assertEqual(c.validate_dex_header(bytes(b))['file_size'],0x180)
 def test_raw_string_not_dex(self):
  b=b'CXRLinkService IMediaStreamService';self.assertEqual(c.magic_offsets(b),[])
 def test_collector_is_noninjected(self):
  s=(HERE/'collect_test21_r3_3_4_2_5_2_external_memory.py').read_text();self.assertIn('/proc/{pid}/mem',s);self.assertNotIn('frida.get_usb_device',s);self.assertNotIn('ptrace(',s);self.assertNotIn('os.kill',s)
 def test_runner_no_connection_mutation(self):
  s=(HERE/'run_test21_r3_3_4_2_5_2_external_memory.sh').read_text();
  for x in ['force-stop','am start','monkey ',' pm clear','svc bluetooth','set -e','set -u','set -o pipefail']:self.assertNotIn(x,s)
 def test_exact_classdef_gate(self):
  s=(HERE/'analyze_test21_r3_3_4_2_5_2_external_memory.py').read_text();self.assertIn('cdefs(hits,SERVICE)',s);self.assertIn("m.get('name')=='onBind'",s);self.assertIn('impl_exact=svc_exact and bool(onbind) and binder_lineage',s)
 def test_packager_private_exclusion(self):
  s=(HERE/'package_test21_r3_3_4_2_5_2_sanitized.py').read_text();self.assertIn('RECOVERED_DEX_INCLUDED=NO',s);self.assertNotIn('external-memory-private.json',s)
if __name__=='__main__':unittest.main(verbosity=2)
