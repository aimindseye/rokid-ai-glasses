#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANON = REPO / "scripts/research/canonical"

import sys
sys.path.insert(0, str(CANON))
from r25_finalizer import load_profiles as load_finalizers, finalize
from r25_publication_verifier import load_profiles as load_publications, verify


class R2721FrameworkTests(unittest.TestCase):
    def test_profile_counts_and_source_locks(self):
        finals = load_finalizers(); pubs = load_publications()
        self.assertEqual(7, len(finals)); self.assertEqual(6, len(pubs))
        for profile in finals + pubs:
            path = REPO / profile["legacy_path"]
            self.assertTrue(path.is_file())
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if profile.get("retirement_state") == "COMPATIBILITY_SHIM":
                self.assertEqual(profile["compatibility_shim_sha256"], actual)
                self.assertEqual(profile["legacy_sha256"], profile["historical_source_sha256"])
            else:
                self.assertEqual(profile["legacy_sha256"], actual)

    def test_canonical_engines_do_not_execute_legacy_paths(self):
        for name in ("r25_finalizer.py", "r25_publication_verifier.py"):
            text = (CANON / name).read_text(encoding="utf-8")
            self.assertNotIn("subprocess", text)
            self.assertNotIn("runpy", text)
            self.assertNotIn("exec(", text)

    def test_basic_finalizer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); run = root / "run"; run.mkdir(); (run / "a.txt").write_text("a\n")
            rc, archive, sidecar = finalize(REPO, "r25.2", run)
            self.assertEqual(0, rc)
            self.assertTrue(archive and archive.is_file())
            self.assertTrue(sidecar and sidecar.is_file())
            self.assertTrue((run / "SHA256SUMS-r25.2.json").is_file())

    def test_basic_publication_accept_and_reject(self):
        good = {
            "endpoint": {"address_published": False, "runtime_uuid_published": False},
            "connection_boundary": {
                "application_payload_reads": 0,
                "application_payload_writes": 0,
                "application_data_streams_obtained": False,
                "independent_gatt_attempted": False,
            },
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p.json"; path.write_text(json.dumps(good) + "\n")
            rc, _ = verify(REPO, "r25.2.2.2", path, emit_output=False)
            self.assertEqual(0, rc)
            good["probe"] = ":".join(["AA", "BB", "CC", "DD", "EE", "FF"]); path.write_text(json.dumps(good) + "\n")
            rc, _ = verify(REPO, "r25.2.2.2", path, emit_output=False)
            self.assertNotEqual(0, rc)

    def test_cli_lists(self):
        for args, expected in [
            (["connection", "finalize", "--list"], 7),
            (["connection", "verify-publication", "--list"], 6),
        ]:
            cp = subprocess.run([str(REPO / "scripts/rokid-research"), "--repo", str(REPO), *args], cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(0, cp.returncode, cp.stderr)
            self.assertEqual(expected, len([x for x in cp.stdout.splitlines() if x.strip()]))


if __name__ == "__main__":
    unittest.main()
