#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ANALYZER = Path(__file__).resolve().parents[1] / "research" / "cxr" / "analyze_test20_r3_media_contract.py"
spec = importlib.util.spec_from_file_location("t20r3", ANALYZER)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def member(name, descriptor, classes):
    return {
        "name": name,
        "descriptor": descriptor,
        "kind": "method",
        "signature": f"public {name}",
        "surface_origin": "declared-public-api",
        "classifications": list(classes),
        "runtime_evidence": "",
    }


def fixture():
    by_class = {}
    for category, specs in module.REQUIRED.items():
        for cls, name, descriptor in specs:
            tags = ["untested", "callback-only"] if category == "callbacks" else ["untested", "service/provider-mediated"]
            by_class.setdefault(cls, []).append(member(name, descriptor, tags))
    return {
        "schema": "rokid.test20.r1.1.cxr-l-capability-census.public.v1",
        "sdk": {
            "coordinate": module.COORDINATE,
            "artifact": {"aar_sha256": module.AAR_SHA256, "pom_sha256": module.POM_SHA256},
            "classes": [
                {"name": cls, "members": members, "surface_origin": "declared-public-api", "classifications": ["untested"]}
                for cls, members in by_class.items()
            ],
        },
        "hi_rokid": {
            "package": "com.rokid.sprite.global.aiapp",
            "version_name": "G1.11.11.0727",
            "components": [{
                "name": "com.rokid.sprite.aiapp.externalapp.service.CXRLinkService",
                "type": "service",
                "exported": True,
                "actions": ["com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE"],
                "classifications": ["runtime-qualified", "service/provider-mediated"],
            }],
        },
    }


class MediaFeasibilityTests(unittest.TestCase):
    def write(self, data):
        td = tempfile.TemporaryDirectory()
        p = Path(td.name) / "census.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return td, p

    def test_exact_contract_passes(self):
        td, p = self.write(fixture())
        try:
            out = module.analyze(p, enforce_hash=False)
            self.assertEqual(out["surface_counts"], {"client_entrypoints": 8, "callbacks": 5, "service_contract": 10, "total": 23})
            self.assertEqual(out["feasibility"]["runtime_qualification"], "NOT_GRANTED")
        finally:
            td.cleanup()

    def test_missing_member_fails(self):
        data = fixture()
        data["sdk"]["classes"][0]["members"].pop()
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_duplicate_member_fails(self):
        data = fixture()
        data["sdk"]["classes"][0]["members"].append(copy.deepcopy(data["sdk"]["classes"][0]["members"][0]))
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_runtime_qualified_media_member_fails(self):
        data = fixture()
        data["sdk"]["classes"][0]["members"][0]["classifications"].append("runtime-qualified")
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_obfuscated_origin_fails(self):
        data = fixture()
        data["sdk"]["classes"][0]["members"][0]["surface_origin"] = "compiler-generated-or-obfuscated"
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_wrong_service_action_fails(self):
        data = fixture()
        data["hi_rokid"]["components"][0]["actions"] = []
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_wrong_artifact_fails(self):
        data = fixture()
        data["sdk"]["artifact"]["aar_sha256"] = "0" * 64
        td, p = self.write(data)
        try:
            with self.assertRaises(module.AnalysisError):
                module.analyze(p, enforce_hash=False)
        finally:
            td.cleanup()

    def test_privacy_defaults_are_false(self):
        td, p = self.write(fixture())
        try:
            out = module.analyze(p, enforce_hash=False)
            self.assertTrue(all(value is False for value in out["privacy"].values()))
        finally:
            td.cleanup()

    def test_runtime_media_not_authorized(self):
        td, p = self.write(fixture())
        try:
            out = module.analyze(p, enforce_hash=False)
            self.assertEqual(out["safety"]["runtime_media_invocation"], "NONE")
            self.assertFalse(out["next_step"]["runtime_media_test_authorized"])
        finally:
            td.cleanup()

if __name__ == "__main__":
    unittest.main(verbosity=2)
