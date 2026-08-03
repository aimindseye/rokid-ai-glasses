#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "scripts/research/canonical"
if str(CANON) not in sys.path:
    sys.path.insert(0, str(CANON))

from pcap_parser import clean_path, get_profile, parse_revision  # noqa: E402
from primitives import sha256_file  # noqa: E402


class R2724PcapParserFrameworkTests(unittest.TestCase):
    def test_profiles_and_historical_source_locks(self):
        expected = {
            "r3.3.3": "3ea78c9268db98588f85676d6e9375dbafb95478285e464f31d16f6d09815608",
            "r3.3.3.1": "a39cf96ee91edd737b2f626f6201ad88379f2ca279ece101fec9216a7d271f04",
        }
        for revision, digest in expected.items():
            profile = get_profile(revision)
            self.assertEqual(profile["legacy_sha256"], digest)
            live = sha256_file(ROOT / profile["legacy_path"])
            allowed = {digest}
            if profile.get("compatibility_shim_sha256"):
                allowed.add(profile["compatibility_shim_sha256"])
            self.assertIn(live, allowed)

    def test_clean_path_redacts_long_identifiers_and_query(self):
        value = clean_path("/api/0123456789abcdef0123456789abcdef?token=secret")
        self.assertEqual(value, "/api/:id")

    def test_short_header_outputs_match_revision_contracts(self):
        with tempfile.TemporaryDirectory(prefix="r2724-unit-") as tmp:
            root = Path(tmp)
            pcap = root / "short.pcap"
            uid = root / "uid.json"
            pcap.write_bytes(b"short")
            uid.write_text("{}\n", encoding="utf-8")
            for revision, schema in (
                ("r3.3.3", "rokid.test21-r3-3-3.network-parse.v1"),
                ("r3.3.3.1", "rokid.test21-r3-3-3-1.network-parse.v1"),
            ):
                out = root / revision
                rc, summary, lines = parse_revision(ROOT, revision, pcap, uid, out, None, emit_output=False)
                self.assertEqual(rc, 0)
                self.assertEqual(summary["schema"], schema)
                self.assertEqual(summary["packet_rows"], 0)
                self.assertEqual(summary["tshark_decryption_metadata"], "UNAVAILABLE")
                self.assertIn("PACKET_ROWS=0", lines)
                stored = json.loads((out / "network-parse-private.json").read_text())
                self.assertEqual(stored, summary)

    def test_canonical_cli_lists_both_revisions(self):
        cp = subprocess.run(
            [str(ROOT / "scripts/rokid-research"), "network", "parse-pcap", "--list"],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(cp.returncode, 0, cp.stderr)
        lines = [line for line in cp.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("r3.3.3\t"))
        self.assertTrue(lines[1].startswith("r3.3.3.1\t"))

    def test_catalog_resolves_pcap_family_to_network_parser(self):
        cp = subprocess.run(
            [str(ROOT / "scripts/rokid-research"), "resolve", "scripts/tests/parse_test21_r3_3_3_pcap.py"],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(cp.returncode, 0, cp.stderr)
        payload = json.loads(cp.stdout)
        self.assertEqual(payload["canonical_successor"], "rokid-research network parse-pcap")


if __name__ == "__main__":
    unittest.main()
