import json
import tempfile
import unittest
from pathlib import Path
import importlib.util

MODULE_PATH = Path(__file__).resolve().parents[1] / 'research' / 'canonical' / 'r27_catalog.py'
spec = importlib.util.spec_from_file_location('r27_catalog', MODULE_PATH)
r27 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r27)


class CanonicalizationContract(unittest.TestCase):
    def test_family_normalizes_revision_ladder(self):
        a = r27.family_key('scripts/tests/package_test21_r3_3_4_2_6_1_2_sanitized.py')
        b = r27.family_key('scripts/tests/package_test21_r3_3_4_2_6_1_3_sanitized.py')
        self.assertEqual(a, b)

    def test_tracks_cover_major_histories(self):
        self.assertEqual(r27.track('scripts/tests/run_test21_r3_3_4_2.sh'), 'test21')
        self.assertEqual(r27.track('scripts/research/connection-protocol/run_r1_3_3_2_25_2_4.sh'), 'r25-connection-protocol')
        self.assertEqual(r27.track('scripts/research/native-loader/check_publication.py'), 'native-loader')

    def test_device_risk_is_conservative(self):
        cls = r27.safety_class('scripts/tests/collect_test21_r3_1_respawn.py', 'collect')
        self.assertEqual(cls, 'DEVICE_OR_PRIVILEGED_REVIEW_REQUIRED')

    def test_inventory_writes_private_lineage_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'repo'
            (root / 'scripts/tests').mkdir(parents=True)
            (root / 'scripts/research/connection-protocol').mkdir(parents=True)
            (root / 'scripts/research/canonical').mkdir(parents=True)
            (root / 'docs/research/tooling').mkdir(parents=True)
            (root / 'docs').mkdir(exist_ok=True)
            (root / 'scripts/tests/run_test21_r3_1.sh').write_text('#!/bin/bash\necho hi\n')
            (root / 'scripts/research/connection-protocol/run_r1_3_3_2_25_2_4.sh').write_text('#!/bin/bash\necho hi\n')
            (root / 'README.md').write_text('# x\n')
            out = Path(td) / 'out'
            summary, z, sidecar = r27.inventory(root, out)
            self.assertEqual(summary['legacy_script_count'], 2)
            self.assertTrue(z.is_file())
            self.assertTrue(sidecar.is_file())
            self.assertTrue((out / 'script-lineage.tsv').is_file())


if __name__ == '__main__':
    unittest.main()
