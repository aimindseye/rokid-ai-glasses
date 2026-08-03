from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.research.canonical import primitives, privacy, retirement_status

REPO = Path(__file__).resolve().parents[2]


class SharedPrimitiveContract(unittest.TestCase):
    def test_sha256_and_source_lock(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.txt'; p.write_bytes(b'abc')
            expected=hashlib.sha256(b'abc').hexdigest()
            self.assertEqual(primitives.sha256_file(p), expected)
            self.assertEqual(primitives.source_lock(p, expected), (True, expected))

    def test_subprocess_primitive(self):
        r=primitives.run_text(['python3','-c','print("ok")'])
        self.assertEqual(r.returncode,0)
        self.assertEqual(r.stdout,'ok\n')

    def test_privacy_regression(self):
        self.assertIsNone(privacy.current_privacy_violation('r3.3.4.2.6.1.3'))
        self.assertEqual(privacy.current_privacy_violation('endpoint 192.0.2.55'), 'ipv4')

    def test_retirement_boundary(self):
        s=retirement_status.summary(REPO)
        self.assertLessEqual(s['not_retirement_ready_count'],67)
        self.assertEqual(s['preserve_historical_count'],4)
        self.assertEqual(s['blocked_source_lock_count'],0)
        self.assertGreaterEqual(s.get('retired_compatibility_shim_count',0),13)

    def test_canonical_modules_import_shared_primitives(self):
        root=REPO/'scripts/research/canonical'
        for name in ('connection_validator.py','evidence_packager.py','source_contract.py','tool_test_runner.py','r27_catalog.py'):
            text=(root/name).read_text(encoding='utf-8')
            self.assertIn('primitives import', text, name)
        self.assertNotIn('def sha256_file(', (root/'connection_validator.py').read_text(encoding='utf-8'))
        self.assertNotIn('def sha256_file(', (root/'evidence_packager.py').read_text(encoding='utf-8'))
        self.assertNotIn('def sha256_file(', (root/'source_contract.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
