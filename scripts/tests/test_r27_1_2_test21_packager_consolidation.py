import tempfile
import unittest
from pathlib import Path

from scripts.research.canonical.evidence_packager import (
    current_privacy_violation,
    load_profiles,
    package,
    sha256_file,
)


class PackagerContract(unittest.TestCase):
    def test_profile_count_and_final_revision(self):
        profiles = load_profiles()
        self.assertEqual(len(profiles), 30)
        self.assertIn('r3.3.4.2.6.1.3', profiles)

    def test_dotted_version_not_ipv4(self):
        self.assertIsNone(current_privacy_violation('r3.3.4.2.6.1.3'))

    def test_standalone_ipv4_rejected(self):
        self.assertEqual(current_privacy_violation('endpoint 192.0.2.55'), 'ipv4')

    def test_simple_profile_packages_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ev = root / 'evidence'
            san = ev / 'sanitized'
            san.mkdir(parents=True)
            (san / 'test21-r3-1-summary.json').write_text('{"status":"PASS"}\n')
            (san / 'test21-r3-1-summary.txt').write_text('STATUS=PASS\n')
            out1 = root / 'one.zip'
            out2 = root / 'two.zip'
            rc1, _, _ = package(root, 'r3.1', ev, 'PHONE', out1, quiet=True)
            rc2, _, _ = package(root, 'r3.1', ev, 'PHONE', out2, quiet=True)
            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 0)
            self.assertEqual(sha256_file(out1), sha256_file(out2))


if __name__ == '__main__':
    unittest.main()
