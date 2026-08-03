#!/usr/bin/env python3
import unittest,tempfile,importlib.util,sys,os,json,csv
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('a',HERE/'analyze_test21_r3_3_3_2_offline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class T(unittest.TestCase):
 def test_order_equal(self):self.assertEqual(m.ordering(5,5,'CONNECTION','RESPAWN'),'SAME_OBSERVATION_TIMESTAMP')
 def test_order_connection_first(self):self.assertEqual(m.ordering(4,5,'CONNECTION','RESPAWN'),'CONNECTION_PRECEDES_RESPAWN')
 def test_order_respawn_first(self):self.assertEqual(m.ordering(5,4,'CONNECTION','RESPAWN'),'RESPAWN_PRECEDES_CONNECTION')
 def test_native_csv(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.csv'
   with p.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=m.REQ_COLS);w.writeheader();w.writerow(dict(zip(m.REQ_COLS,['6','a','1','b','443','1','Hi Rokid',m.HI,'HTTPS','Closed','ai-cloud-global.rokid.com','1','2','3','4','2026-08-01T21:05:31.641-04:00','2026-08-01T21:06:52.444-04:00'])))
   src,hi=m.native_csv(p);self.assertEqual(len(src),1);self.assertEqual(hi[0]['host'],'ai-cloud-global.rokid.com')
 def test_ground_truth(self):
  n=[{'host':'ai-cloud-global.rokid.com','proto':'HTTPS','first_seen_epoch_ms':1000}];s=[{'host':'ai-cloud-global.rokid.com','marker_type':'TLS_CLIENT_HELLO','epoch_ms':1200}];d,matched,unique,c=m.ground_truth_match(n,s);self.assertEqual(matched,['ai-cloud-global.rokid.com']);self.assertEqual(c,1.0)
 def test_phase(self):
  t={'hi_force_stop':100,'button_prompt':200,'connection_attempt':300,'hi_respawn':300};self.assertEqual(m.phase(150,t),'FORCE_STOP_TO_BUTTON_PROMPT');self.assertEqual(m.phase(300,t),'CONNECTION_RESPAWN_BOUNDARY_TIMESTAMP')
class Contract(unittest.TestCase):
 def test_runner_offline_only(self):
  s=(HERE/'run_test21_r3_3_3_2_offline_reanalysis.sh').read_text();self.assertIn('DEVICE_OPERATION=NONE',s);self.assertIn('NEW_CAPTURE=NONE',s);self.assertNotIn('adb -s',s);self.assertNotIn('am force-stop',s)
 def test_no_abort_flags(self):
  for p in [HERE/'run_test21_r3_3_3_2_offline_reanalysis.sh']:
   s=p.read_text();self.assertNotIn('set -e',s);self.assertNotIn('set -u',s);self.assertNotIn('pipefail',s)
if __name__=='__main__':unittest.main(verbosity=2)
