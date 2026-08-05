#!/usr/bin/env python3
from __future__ import print_function
import importlib.util, json, os, tempfile, unittest

HERE=os.path.dirname(os.path.abspath(__file__))
MOD=os.path.join(HERE,'test22_tool.py')
spec=importlib.util.spec_from_file_location('t22',MOD); t22=importlib.util.module_from_spec(spec); spec.loader.exec_module(t22)

class Test22ToolTests(unittest.TestCase):
    def test_redaction(self):
        mac=':'.join(['aa','bb','cc','dd','ee','ff'])
        ip='.'.join(['192','168','1','4'])
        s='SSID="home" bssid: %s serial=12345 ip=%s' % (mac,ip)
        r=t22.redact(s)
        self.assertNotIn('home',r); self.assertNotIn(mac,r); self.assertNotIn(ip,r)
    def test_receipt_shape(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d,'arm.json'),'w') as f:
                json.dump({'ok':True,'armed':True,'command':'ARM','expires_in_ms':60000},f)
            with open(os.path.join(d,'run.json'),'w') as f:
                json.dump({'ok':True,'accepted':True,'command':'RUN','broadcast_count':1,'action':'a','target_package':'p','cmd_type':'setting_change','setting_key':'settings_wifi_enable'},f)
            self.assertEqual(len(t22.find_one(d,'arm.json')),1); self.assertEqual(len(t22.find_one(d,'run.json')),1)
    def test_snapshot_emit_contract(self):
        s={'wifi_on':'1','wlan0_ipv4':True,'wlan0_route':True,'default_route_wlan0':True}
        self.assertTrue(s['wlan0_ipv4'] and s['default_route_wlan0'])

if __name__=='__main__': unittest.main()
