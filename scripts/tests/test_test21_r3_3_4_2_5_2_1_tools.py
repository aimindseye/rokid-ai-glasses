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

c = load('coverage', 'collect_test21_r3_3_4_2_5_2_1_coverage.py')

class T(unittest.TestCase):
    def test_short_subpage_not_credited(self):
        self.assertEqual(c.trusted_prefix_length(47, 8 * 1024 * 1024), 0)
        self.assertTrue(c.looks_text_like_short(b'dd: synthetic diagnostic text from remote command\n'))

    def test_page_aligned_partial_prefix_credited(self):
        self.assertEqual(c.trusted_prefix_length(139264, 8 * 1024 * 1024), 139264)
        self.assertEqual(139264 // 4096, 34)

    def test_full_read_credited_exactly(self):
        self.assertEqual(c.trusted_prefix_length(65536, 65536), 65536)

    def test_interval_union(self):
        self.assertEqual(c.interval_union_bytes([(0, 4096), (4096, 8192), (4096, 12288)]), 12288)

    def test_merge_adjacent_supports_cross_boundary_magic(self):
        a = {'start': 0x1000, 'data': b'dex\n', 'source': 'FULL'}
        b = {'start': 0x1004, 'data': b'035\0' + b'X' * 120, 'source': 'FULL'}
        runs = c.merge_segments([a, b])
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]['data'].startswith(b'dex\n035\0'))

    def test_prior_characterization_reproduces_observed_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / 'private/external-memory'
            p.mkdir(parents=True)
            manifest = []
            for i in range(31):
                manifest.append({'chunk': i, 'bytes_read': 47, 'read_status': 'PARTIAL', 'chunk_sha256': 'a' * 64})
            manifest.append({'chunk': 31, 'bytes_read': 139264, 'read_status': 'PARTIAL', 'chunk_sha256': 'b' * 64})
            (p / 'external-memory-private.json').write_text(json.dumps({
                'selected_bytes': 268435456,
                'memory_bytes_read': 140721,
                'manifest': manifest,
            }))
            x = c.characterize_prior(str(root))
            self.assertTrue(x['available'])
            self.assertEqual(x['partial_read_count'], 32)
            self.assertEqual(x['returned_size_mode_bytes'], 47)
            self.assertEqual(x['returned_size_mode_count'], 31)
            self.assertEqual(x['duplicate_short_output_max_count'], 31)
            self.assertAlmostEqual(x['coverage_percent'], 0.0524226576, places=6)

    def test_runner_has_no_injection_or_connection_mutation(self):
        s = (HERE / 'run_test21_r3_3_4_2_5_2_1_resume.sh').read_text()
        for bad in ['force-stop', 'am start', 'monkey ', ' pm clear', 'svc bluetooth', 'set -e', 'set -u', 'set -o pipefail']:
            self.assertNotIn(bad, s)
        for required in ['FRIDA_PROCESS_ATTACH=NONE', 'PTRACE_ATTACH=NONE', 'PROCESS_SIGNAL=NONE']:
            self.assertIn(required, s)

    def test_analyzer_cannot_exhaust_partial_coverage(self):
        s = (HERE / 'analyze_test21_r3_3_4_2_5_2_1_coverage.py').read_text()
        self.assertIn('elif not census_exhausted:', s)
        self.assertIn('SELECTED_MEMORY_CENSUS_INCOMPLETE_TARGET_NOT_FOUND_IN_RECOVERED_RANGES', s)
        self.assertIn("target_absence_from_process_memory_proven", s)

    def test_packager_excludes_private_material(self):
        s = (HERE / 'package_test21_r3_3_4_2_5_2_1_sanitized.py').read_text()
        self.assertIn('COVERAGE_SEGMENTS_INCLUDED=NO', s)
        self.assertIn('RECOVERED_DEX_INCLUDED=NO', s)
        self.assertNotIn('external-memory-coverage-private.json', s)

if __name__ == '__main__':
    unittest.main(verbosity=2)
