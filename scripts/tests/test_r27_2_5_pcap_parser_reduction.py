#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CANON=ROOT/"scripts/research/canonical"
if str(CANON) not in sys.path: sys.path.insert(0,str(CANON))
from pcap_parser import get_profile
from primitives import sha256_file

class R2725Tests(unittest.TestCase):
    def test_live_paths_are_locked_compatibility_shims(self):
        for revision in ("r3.3.3","r3.3.3.1"):
            p=get_profile(revision)
            self.assertEqual(p.get("lifecycle_state"),"COMPATIBILITY_SHIM")
            self.assertEqual(sha256_file(ROOT/p["legacy_path"]),p["compatibility_shim_sha256"])
            self.assertNotEqual(p["legacy_sha256"],p["compatibility_shim_sha256"])
    def test_historical_tool_oracle_import_apis_survive(self):
        for rel in ("scripts/tests/parse_test21_r3_3_3_pcap.py","scripts/tests/parse_test21_r3_3_3_1_pcap.py"):
            spec=importlib.util.spec_from_file_location("compat",ROOT/rel); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            for name in ("MAGIC","clean_path","trailer","dns_q","tls_sni","parse_pcap","tshark_http","main"):
                self.assertTrue(hasattr(mod,name),f"{rel}: {name}")
    def test_source_contract_profiles_lock_live_shims(self):
        data=json.loads((ROOT/"scripts/research/canonical/profiles/source-contracts.json").read_text())
        expected={get_profile(r)["legacy_path"]:get_profile(r)["compatibility_shim_sha256"] for r in ("r3.3.3","r3.3.3.1")}
        hits=0
        for p in data["profiles"]:
            req=p.get("required_file_sha256",{})
            for rel,sha in expected.items():
                if rel in req:
                    hits+=1; self.assertEqual(req[rel],sha)
        self.assertEqual(hits,3)
    def test_impacted_tool_suites_pass(self):
        for revision in ("r3.3.3","r3.3.3.1"):
            cp=subprocess.run([str(ROOT/"scripts/rokid-research"),"test","run","--track","test21","--revision",revision],cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
if __name__=="__main__": unittest.main()
