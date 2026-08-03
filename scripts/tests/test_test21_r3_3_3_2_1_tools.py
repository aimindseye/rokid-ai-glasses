#!/usr/bin/env python3
import csv
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    'r33321_analyzer', HERE / 'analyze_test21_r3_3_3_2_1_offline.py'
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class AnalyzerTests(unittest.TestCase):
    def test_order_equal(self):
        self.assertEqual(M.ordering(5, 5), 'SAME_OBSERVATION_TIMESTAMP')

    def test_order_connection_first(self):
        self.assertEqual(M.ordering(4, 5), 'CONNECTION_PRECEDES_RESPAWN')

    def test_order_respawn_first(self):
        self.assertEqual(M.ordering(5, 4), 'RESPAWN_PRECEDES_CONNECTION')

    def test_native_csv_exact_host_set(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'native.csv'
            rows = [
                ('DNS', 'www.baidu.com', '2026-08-01T21:05:30.638-04:00'),
                ('HTTPS', 'www.baidu.com', '2026-08-01T21:05:30.664-04:00'),
                ('DNS', 'ai-cloud-global.rokid.com', '2026-08-01T21:05:31.130-04:00'),
                ('HTTPS', 'ai-cloud-global.rokid.com', '2026-08-01T21:05:31.641-04:00'),
                ('DNS', 'device-account-prod.rokid.com', '2026-08-01T21:05:32.214-04:00'),
                ('HTTPS', 'device-account-prod.rokid.com', '2026-08-01T21:05:32.347-04:00'),
                ('DNS', 'rcs-internal.rokid.com', '2026-08-01T21:05:33.335-04:00'),
                ('HTTPS', 'rcs-internal.rokid.com', '2026-08-01T21:05:34.722-04:00'),
            ]
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=M.REQ_COLS)
                writer.writeheader()
                for proto, host, first in rows:
                    writer.writerow({
                        'IPProto':'6','SrcIP':'x','SrcPort':'1','DstIp':'y','DstPort':'443',
                        'UID':'1','App':'Hi Rokid','PackageName':M.HI_PACKAGE,'Proto':proto,
                        'Status':'Closed','Info':host,'BytesSent':'1','BytesRcvd':'2',
                        'PktsSent':'1','PktsRcvd':'1','FirstSeen':first,'LastSeen':first,
                    })
            source, native = M.read_native_csv(path)
            self.assertEqual(len(source), 8)
            self.assertEqual({x['host'] for x in native}, M.EXPECTED_NATIVE_HOSTS)

    def test_calibration_requires_all_four(self):
        native=[]
        scan=[]
        for idx, host in enumerate(sorted(M.EXPECTED_NATIVE_HOSTS)):
            native.append({'host':host,'first_seen_epoch_ms':1000+idx*100})
            if idx < 3:
                scan.append({'host':host,'epoch_ms':1000+idx*100,'marker_type':'DNS_QUERY'})
        _, matched, qualified = M.calibrate(native, scan)
        self.assertEqual(len(matched), 3)
        self.assertFalse(qualified)

    def test_calibration_four_of_four(self):
        native=[]
        scan=[]
        for idx, host in enumerate(sorted(M.EXPECTED_NATIVE_HOSTS)):
            native.append({'host':host,'first_seen_epoch_ms':1000+idx*100})
            scan.append({'host':host,'epoch_ms':1001+idx*100,'marker_type':'DNS_QUERY'})
        _, matched, qualified = M.calibrate(native, scan)
        self.assertEqual(len(matched), 4)
        self.assertTrue(qualified)

    def test_network_classification_before_prompt(self):
        timeline={'hi_force_stop':100,'button_prompt':200,'connection_attempt':300,'hi_respawn':300}
        markers=[{'epoch_ms':150,'host':'ai-cloud-global.rokid.com','marker_type':'DNS_QUERY'}]
        result=M.classify_network(markers,timeline)
        self.assertEqual(result['server_dependency_interpretation'], 'KNOWN_ROKID_ENDPOINT_INITIATION_BEFORE_BUTTON_PROMPT_CORRELATION')

    def test_network_classification_at_boundary(self):
        timeline={'hi_force_stop':100,'button_prompt':200,'connection_attempt':300,'hi_respawn':300}
        markers=[{'epoch_ms':300,'host':'ai-cloud-global.rokid.com','marker_type':'TLS_CLIENT_HELLO'}]
        result=M.classify_network(markers,timeline)
        self.assertEqual(result['server_dependency_interpretation'], 'KNOWN_ROKID_ENDPOINT_INITIATION_AT_CONNECTION_RESPAWN_BOUNDARY')

    def test_network_classification_no_marker(self):
        timeline={'hi_force_stop':100,'button_prompt':200,'connection_attempt':300,'hi_respawn':300}
        result=M.classify_network([],timeline)
        self.assertEqual(result['network_respawn_disposition'], 'NO_KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_FORCE_WITH_QUALIFIED_SCANNER')

    def test_tshark_separator_and_tab_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            fake=temp/'tshark'
            fake.write_text("""#!/usr/bin/env python3\nimport sys\na=sys.argv[1:]\nif \"separator=/t\" not in a:\n print(\"missing separator=/t\",file=sys.stderr);sys.exit(9)\nfilt=a[a.index(\"-Y\")+1]\nif filt.startswith(\"dns.flags.response\"):\n print(\"7\\t1785632731.130544000\\tai-cloud-global.rokid.com\")\nelif filt.startswith(\"tls.handshake.type\"):\n print(\"8\\t1785632731.695980000\\tai-cloud-global.rokid.com\")\nsys.exit(0)\n""")
            fake.chmod(0o755)
            pcap=temp/'x.pcap';pcap.write_bytes(b'pcap')
            with patch.object(M.shutil,'which',return_value=str(fake)):
                rows, malformed=M.scan_known_hosts(pcap,None,['ai-cloud-global.rokid.com'])
            self.assertEqual(malformed,0)
            self.assertEqual([x['marker_type'] for x in rows],['DNS_QUERY','TLS_CLIENT_HELLO'])
            self.assertEqual(rows[0]['host'],'ai-cloud-global.rokid.com')


class ContractTests(unittest.TestCase):
    def test_runner_is_offline_only(self):
        text=(HERE/'run_test21_r3_3_3_2_1_offline_reanalysis.sh').read_text()
        self.assertIn('DEVICE_OPERATION=NONE',text)
        self.assertIn('ADB_OPERATION=NONE',text)
        self.assertIn('NEW_CAPTURE=NONE',text)
        self.assertNotIn('adb -s',text)
        self.assertNotIn('am force-stop',text)
        self.assertNotIn('CaptureCtrl',text)

    def test_no_interactive_abort_flags(self):
        text=(HERE/'run_test21_r3_3_3_2_1_offline_reanalysis.sh').read_text()
        self.assertNotIn('set -e',text)
        self.assertNotIn('set -u',text)
        self.assertNotIn('pipefail',text)

    def test_source_contains_correct_tshark_separator(self):
        text=(HERE/'analyze_test21_r3_3_3_2_1_offline.py').read_text()
        self.assertIn("'separator=/t'",text)
        self.assertNotIn("'separator=\\\\t'",text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
