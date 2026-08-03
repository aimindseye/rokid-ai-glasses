import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.canonical.connection_validator import load_profiles, validate


class R2711Profiles(unittest.TestCase):
    def test_profile_count(self):
        profiles = load_profiles()
        self.assertEqual(len(profiles), 12)
        self.assertIn('r25.2.4', profiles)
        self.assertIn('r25.3.1.3', profiles)

    def test_profiles_have_legacy_lineage(self):
        for revision, profile in load_profiles().items():
            self.assertTrue(profile['legacy_validator'].startswith('scripts/research/connection-protocol/validate_'))
            self.assertTrue(profile.get('pass_lines'), revision)

    def test_engine_positive_and_negative(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            base = repo / 'scripts/research/connection-protocol'
            base.mkdir(parents=True)
            (base / 'r25_2_2_2_1_offline.py').write_text('VALUE = 1\n', encoding='utf-8')
            (base / 'run_r1_3_3_2_25_2_2_2_1.sh').write_text('#!/bin/bash\necho ok\n', encoding='utf-8')
            self.assertEqual(validate(repo, 'r25.2.2.2.1', quiet=True), 0)
            (base / 'r25_2_2_2_1_offline.py').unlink()
            self.assertNotEqual(validate(repo, 'r25.2.2.2.1', quiet=True), 0)
            self.assertEqual(validate(repo, 'not-a-real-revision', quiet=True), 2)

    def test_no_device_execution_primitives_in_engine(self):
        text = Path('scripts/research/canonical/connection_validator.py').read_text(encoding='utf-8')
        for token in ('adb shell', 'fastboot ', 'frida', 'su -c'):
            self.assertNotIn(token, text)


if __name__ == '__main__':
    unittest.main()
