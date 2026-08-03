#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('r33426', HERE / 'analyze_test21_r3_3_4_2_6_privilege_free_contract.py')
M = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(M)


def methods33():
    return [
        {'name': f'method{i:02d}', 'proto': '()V', 'signature': f'method{i:02d}()V', 'access': 1}
        for i in range(1, 34)
    ]


def complete_contract():
    methods = methods33()
    return {
        'descriptor': M.EXPECTED_DESCRIPTOR,
        'methods': methods,
        'transactions': [
            {'method_name': m['name'], 'transaction_code': i, 'field': 'TRANSACTION_' + m['name']}
            for i, m in enumerate(methods, 1)
        ],
        'proxy': [
            {'method_name': m['name'], 'proto': m['proto'], 'proxy_method_found': True, 'transaction_codes_observed': [i]}
            for i, m in enumerate(methods, 1)
        ],
        'reachability': [
            {
                'method_name': m['name'], 'proto': m['proto'], 'reachable_from_custom_app': i <= 4,
                'shortest_call_path': ['Lorg/aimindseye/rokid/cxrphotoqualification/Main;->x()V', 'target'] if i <= 4 else [],
                'direct_custom_callsite_count': 1 if i <= 2 else 0,
            }
            for i, m in enumerate(methods, 1)
        ],
        'types': [],
        'input': {'fixture_mode': True},
    }


class Helpers(unittest.TestCase):
    def test_parse_encoded_int(self):
        value, off = M.parse_encoded_value(bytes([0x04, 0x7f]), 0)
        self.assertEqual(value, 127)
        self.assertEqual(off, 2)

    def test_parse_proto_array_and_objects(self):
        params, ret = M.parse_type_descriptors('(ILjava/lang/String;[BLcom/rokid/example/Thing;)Z')
        self.assertEqual(params, ['I', 'Ljava/lang/String;', '[B', 'Lcom/rokid/example/Thing;'])
        self.assertEqual(ret, 'Z')

    def test_type_classification(self):
        self.assertEqual(M.classify_type('I'), 'PRIMITIVE')
        self.assertEqual(M.classify_type('Landroid/os/Bundle;'), 'ANDROID_FRAMEWORK')
        self.assertEqual(M.classify_type('Lcom/rokid/example/Thing;'), 'ROKID_API_TYPE')
        self.assertEqual(M.classify_type('[Ljava/lang/String;'), 'LANGUAGE_RUNTIME')

    def test_static_transaction_values(self):
        class FakeDex:
            pass
        d = FakeDex()
        buf = bytearray(0x140)
        struct.pack_into('<I', buf, 0x60, 1)
        struct.pack_into('<I', buf, 0x64, 0x80)
        struct.pack_into('<IIIIIIII', buf, 0x80, 0, 0, 0xFFFFFFFF, 0, 0, 0, 0xC0, 0xE0)
        # class_data: 2 static fields, no instance fields/methods; field idx 0 then +1.
        buf[0xC0:0xC8] = bytes([2, 0, 0, 0, 0, 0, 1, 0])
        # encoded_array: two VALUE_INT entries, 1 and 2.
        buf[0xE0:0xE5] = bytes([2, 0x04, 1, 0x04, 2])
        d.data = bytes(buf)
        d.types = ['Lx$Stub;']
        d.fields = [
            {'class': 'Lx$Stub;', 'type': 'I', 'name': 'TRANSACTION_alpha'},
            {'class': 'Lx$Stub;', 'type': 'I', 'name': 'TRANSACTION_beta'},
        ]
        d.name = 'classes.dex'
        class Model:
            dexes = [d]
        got = M.transaction_fields(Model(), 'Lx;')
        self.assertEqual([(x['method_name'], x['transaction_code']) for x in got], [('alpha', 1), ('beta', 2)])


class Closure(unittest.TestCase):
    def test_complete_contract_scaffold_ready_but_behavior_not_proven(self):
        result = M.analyze(complete_contract())
        self.assertTrue(result['binder']['transaction_map_complete'])
        self.assertEqual(result['binder']['proxy_transaction_mismatch_count'], 0)
        self.assertEqual(result['custom_app_usage']['reachable_binder_method_count'], 4)
        self.assertTrue(result['clean_room']['interface_scaffold_ready'])
        self.assertFalse(result['clean_room']['functional_behavior_compatibility_proven'])
        self.assertFalse(result['clean_room']['service_implementation_recovered'])
        self.assertFalse(result['root_required'])
        self.assertFalse(result['adb_required'])

    def test_missing_transaction_blocks_scaffold(self):
        c = complete_contract()
        c['transactions'] = c['transactions'][:-1]
        result = M.analyze(c)
        self.assertFalse(result['binder']['transaction_map_complete'])
        self.assertFalse(result['clean_room']['interface_scaffold_ready'])

    def test_duplicate_transaction_code_blocks_scaffold(self):
        c = complete_contract()
        c['transactions'][-1]['transaction_code'] = 32
        result = M.analyze(c)
        self.assertGreater(result['binder']['transaction_duplicate_code_count'], 0)
        self.assertFalse(result['clean_room']['interface_scaffold_ready'])

    def test_proxy_mismatch_blocks_scaffold(self):
        c = complete_contract()
        c['proxy'][0]['transaction_codes_observed'] = [99]
        result = M.analyze(c)
        self.assertEqual(result['binder']['proxy_transaction_mismatch_count'], 1)
        self.assertFalse(result['clean_room']['interface_scaffold_ready'])

    def test_sanitized_output_removes_call_paths(self):
        result = M.analyze(complete_contract())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            M.write_outputs(result, root)
            san = json.loads((root / 'sanitized/test21-r3-3-4-2-6-summary.json').read_text())
            self.assertNotIn('shortest_call_path', san['method_contract'][0])
            self.assertTrue((root / 'privilege-free-contract-private.json').is_file())
            self.assertTrue((root / 'sanitized/test21-r3-3-4-2-6-transaction-map.tsv').is_file())


class SourceBoundary(unittest.TestCase):
    def test_runner_contains_no_device_command(self):
        text = (HERE / 'run_test21_r3_3_4_2_6_privilege_free_contract.sh').read_text()
        for token in ('adb shell', 'adb -s', 'su -c', '/proc/', 'frida-server', 'am start', 'am force-stop'):
            self.assertNotIn(token, text)
        self.assertIn('ADB_REQUIRED=NO', text)
        self.assertIn('PHONE_ACTION=NONE', text)

    def test_analyzer_contains_no_subprocess_or_network(self):
        text = (HERE / 'analyze_test21_r3_3_4_2_6_privilege_free_contract.py').read_text()
        for token in ('subprocess.', 'os.system(', 'requests.', 'urllib.', 'socket.'):
            self.assertNotIn(token, text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
