from __future__ import annotations
import json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PROFILES=ROOT/"scripts/research/canonical/profiles"

class R2722(unittest.TestCase):
    def test_profiles_are_compatibility_shims(self):
        total=0
        for name,expected in (("r25-finalizers.json",7),("r25-publication-verifiers.json",6)):
            data=json.loads((PROFILES/name).read_text())
            self.assertEqual(len(data["profiles"]),expected)
            for p in data["profiles"]:
                self.assertEqual(p.get("retirement_state"),"COMPATIBILITY_SHIM")
                self.assertRegex(p.get("historical_source_sha256",""),r"^[0-9a-f]{64}$")
                self.assertRegex(p.get("compatibility_shim_sha256",""),r"^[0-9a-f]{64}$")
            total += len(data["profiles"])
        self.assertEqual(total,13)

    def test_live_shims_are_small_and_delegate(self):
        for name in ("r25-finalizers.json","r25-publication-verifiers.json"):
            data=json.loads((PROFILES/name).read_text())
            for p in data["profiles"]:
                path=ROOT/p["legacy_path"]
                text=path.read_text()
                self.assertLess(len(text.splitlines()),40)
                self.assertIn("R27.2.2 compatibility shim",text)
                self.assertIn("scripts.research.canonical",text)
                if name=="r25-finalizers.json":
                    self.assertNotIn("zipfile",text)
                else:
                    self.assertNotIn("re.compile",text)

    def test_status_reports_full_reduction(self):
        import sys
        sys.path.insert(0,str(ROOT/"scripts/research/canonical"))
        import r25_lifecycle_status
        rows=r25_lifecycle_status.rows(ROOT)
        self.assertEqual(len(rows),13)
        self.assertTrue(all(r["live_shim_lock"]=="PASS" for r in rows))

    def test_docs_exist(self):
        self.assertTrue((ROOT/"docs/research/r27.2.2-r25-finalization-publication-reduction.md").is_file())

if __name__=="__main__":
    unittest.main()
