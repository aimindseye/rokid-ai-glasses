#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

c = load('persistent', 'collect_test21_r3_3_4_2_5_2_1_1_persistent.py')

class T(unittest.TestCase):
    def test_short_47_bytes_not_credited(self):
        self.assertEqual(c.trusted_prefix_length(47, 8 * 1024 * 1024), 0)
        self.assertTrue(c.looks_text_like_short(b'dd: synthetic remote diagnostic text for testing\n'))

    def test_139264_partial_credits_34_pages(self):
        self.assertEqual(c.trusted_prefix_length(139264, 8 * 1024 * 1024), 139264)
        self.assertEqual(139264 // c.PAGE, 34)

    def test_plan_is_page_aligned(self):
        rows = [{'start': 0x1000, 'end': 0x1000 + 100000, 'size': 100000, 'perms': 'rw-p', 'path': ''}]
        p = c.plan_chunks(rows, chunk_size=65536, max_total=131072)
        self.assertTrue(p)
        for row in p:
            self.assertEqual(row['start'] % c.PAGE, 0)
            self.assertEqual(row['size'] % c.PAGE, 0)

    def test_interval_union_accepts_empty_generator(self):
        self.assertEqual(c.interval_union_bytes((x for x in [])), 0)

    def test_merge_adjacent_allows_cross_boundary_magic(self):
        runs = c.merge_segments([
            {'start': 0x1000, 'data': b'dex\n'},
            {'start': 0x1004, 'data': b'035\0' + b'X' * 128},
        ])
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]['data'].startswith(b'dex\n035\0'))

    def test_prior_signature_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); p = root / 'private/external-memory'; p.mkdir(parents=True)
            manifest = [{'chunk': i, 'bytes_read': 47, 'read_status': 'PARTIAL', 'chunk_sha256': 'a' * 64} for i in range(31)]
            manifest.append({'chunk': 31, 'bytes_read': 139264, 'read_status': 'PARTIAL', 'chunk_sha256': 'b' * 64})
            (p / 'external-memory-private.json').write_text(json.dumps({'selected_bytes': 268435456, 'memory_bytes_read': 140721, 'manifest': manifest}))
            x = c.characterize_prior(str(root))
            self.assertEqual(x['returned_size_mode_bytes'], 47)
            self.assertEqual(x['returned_size_mode_count'], 31)
            self.assertEqual(x['duplicate_short_output_max_count'], 31)
            self.assertEqual(x['partial_read_count'], 32)

    def test_worker_script_has_temp_cleanup_and_one_loop(self):
        self.assertIn('/data/local/tmp/rokid-test21-r3252111-$$', c.WORKER_SCRIPT)
        self.assertIn('trap cleanup_worker 0 1 2 15', c.WORKER_SCRIPT)
        self.assertIn('while IFS=', c.WORKER_SCRIPT)
        self.assertIn('dd if="/proc/$a/mem"', c.WORKER_SCRIPT)

    def test_runner_no_injection_or_connection_mutation(self):
        s = (HERE / 'run_test21_r3_3_4_2_5_2_1_1_resume.sh').read_text()
        for bad in ['force-stop', 'am start', 'monkey ', ' pm clear', 'svc bluetooth', 'set -e', 'set -u', 'set -o pipefail']:
            self.assertNotIn(bad, s)
        for required in ['FRIDA_PROCESS_ATTACH=NONE', 'PTRACE_ATTACH=NONE', 'PROCESS_SIGNAL=NONE']:
            self.assertIn(required, s)

    def test_analyzer_cannot_exhaust_partial_coverage(self):
        s = (HERE / 'analyze_test21_r3_3_4_2_5_2_1_1_persistent.py').read_text()
        self.assertIn('elif not census_exhausted:', s)
        self.assertIn('SELECTED_MEMORY_CENSUS_INCOMPLETE_TARGET_NOT_FOUND_IN_RECOVERED_RANGES', s)
        self.assertIn('target_absence_from_process_memory_proven', s)

    def test_packager_excludes_private_material(self):
        s = (HERE / 'package_test21_r3_3_4_2_5_2_1_1_sanitized.py').read_text()
        self.assertIn('COVERAGE_SEGMENTS_INCLUDED=NO', s)
        self.assertIn('RECOVERED_DEX_INCLUDED=NO', s)
        self.assertNotIn('external-memory-persistent-private.json', s)

if __name__ == '__main__':
    unittest.main(verbosity=2)
