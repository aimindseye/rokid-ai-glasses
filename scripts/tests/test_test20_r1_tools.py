#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sdk = load("test20_sdk", "scripts/research/cxr/census_cxr_l_sdk.py")
hi = load("test20_hi", "scripts/research/cxr/census_hi_rokid_cxrl.py")
classify = load("test20_classify", "scripts/research/cxr/classify_cxr_l_capabilities.py")


class Test20R1Tools(unittest.TestCase):
    def test_javap_class_and_member_parser(self) -> None:
        text = """Compiled from \"X.java\"\npublic final class a.b.X extends java.lang.Object {\n  public static final int FLAG = 7;\n    descriptor: I\n  public a.b.X(java.lang.String);\n    descriptor: (Ljava/lang/String;)V\n  public final boolean connect(java.lang.String);\n    descriptor: (Ljava/lang/String;)Z\n}\n"""
        header = sdk.parse_class_header(text, "a.b.X")
        members = sdk.parse_members(text, "a.b.X", header)
        self.assertEqual(header["kind"], "class")
        self.assertEqual(header["superclass"], "java.lang.Object")
        self.assertEqual([item["kind"] for item in members], ["field", "constructor", "method"])
        self.assertEqual(members[-1]["descriptor"], "(Ljava/lang/String;)Z")

    def test_enum_parser(self) -> None:
        text = """public final class a.E extends java.lang.Enum<a.E> {\n  public static final a.E ONE;\n    descriptor: La/E;\n  public static final a.E TWO;\n    descriptor: La/E;\n}\n"""
        header = sdk.parse_class_header(text, "a.E")
        members = sdk.parse_members(text, "a.E", header)
        self.assertEqual([item["name"] for item in members], ["ONE", "TWO"])
        self.assertTrue(all(item["kind"] == "enum_constant" for item in members))

    def test_minimal_elf_dynsym_parser(self) -> None:
        # ELF64 with NULL, .shstrtab, .dynstr, and .dynsym sections.
        shstr = b"\x00.shstrtab\x00.dynstr\x00.dynsym\x00"
        dynstr = b"\x00JNI_OnLoad\x00Java_a_b_nativeCall\x00ordinary\x00"
        sym_null = b"\x00" * 24
        def sym(name_offset: int) -> bytes:
            return struct.pack("<IBBHQQ", name_offset, 0x12, 0, 1, 0, 0)
        dynsym = sym_null + sym(1) + sym(12) + sym(32)
        ehsize = 64
        shentsize = 64
        shnum = 4
        shoff = ehsize
        data_off = shoff + shentsize * shnum
        shstr_off = data_off
        dynstr_off = shstr_off + len(shstr)
        dynsym_off = dynstr_off + len(dynstr)
        ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
        header = ident + struct.pack(
            "<HHIQQQIHHHHHH", 3, 62, 1, 0, 0, shoff, 0, ehsize, 0, 0, shentsize, shnum, 1
        )
        null = b"\x00" * shentsize
        sh_shstr = struct.pack("<IIQQQQIIQQ", 1, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
        sh_dynstr = struct.pack("<IIQQQQIIQQ", 11, 3, 0, 0, dynstr_off, len(dynstr), 0, 0, 1, 0)
        sh_dynsym = struct.pack("<IIQQQQIIQQ", 19, 11, 0, 0, dynsym_off, len(dynsym), 2, 1, 8, 24)
        result = sdk.elf_dynamic_symbols(header + null + sh_shstr + sh_dynstr + sh_dynsym + shstr + dynstr + dynsym)
        self.assertEqual(result["elf_class"], 64)
        self.assertEqual(result["jni_exports"], ["JNI_OnLoad", "Java_a_b_nativeCall"])

    def test_aapt_component_parser(self) -> None:
        text = """E: manifest (line=2)\n  A: package=\"com.rokid.sprite.global.aiapp\"\n  E: application\n    E: activity\n      A: android:name(0x01010003)=\"com.rokid.sprite.aiapp.externalapp.auth.AuthorizationActivity\"\n      A: android:exported(0x01010010)=(type 0x12)0xffffffff\n      E: intent-filter\n        E: action\n          A: android:name(0x01010003)=\"com.rokid.sprite.aiapp.externalapp.AUTHORIZATION\"\n    E: service\n      A: android:name(0x01010003)=\"com.rokid.sprite.aiapp.externalapp.service.CXRLinkService\"\n      A: android:exported(0x01010010)=(type 0x12)0xffffffff\n    E: provider\n      A: android:name(0x01010003)=\"com.rokid.sprite.aiapp.external.CXRLinkProvider\"\n      A: android:authorities(0x01010018)=\"com.rokid.sprite.global.aiapp.cxrl.provider\"\n      A: android:exported(0x01010010)=(type 0x12)0x00000000\n"""
        components = hi.parse_aapt_xmltree(text)
        self.assertEqual(len(components), 3)
        self.assertTrue(components[0]["exported"])
        self.assertEqual(components[0]["actions"], ["com.rokid.sprite.aiapp.externalapp.AUTHORIZATION"])
        self.assertFalse(components[2]["exported"])

    def test_classification_runtime_and_untested(self) -> None:
        qualified = classify.member_tags(
            "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
            "class",
            {"kind": "method", "name": "connect"},
        )
        self.assertIn("runtime-qualified", qualified)
        self.assertNotIn("untested", qualified)
        media = classify.member_tags(
            "com.rokid.cxr.link.callbacks.IImageStreamCbk",
            "interface",
            {"kind": "method", "name": "onImage"},
        )
        self.assertIn("callback-only", media)
        self.assertIn("untested", media)

    def test_markdown_report_contains_no_private_paths(self) -> None:
        publication = {
            "sdk": {
                "coordinate": "com.rokid.cxr:client-l:1.0.1",
                "artifact": {"aar_sha256": "a" * 64, "pom_sha256": "b" * 64},
                "session_types": {"CXRSessionType": ["NONE", "CUSTOMVIEW", "CUSTOMAPP"]},
                "native_libraries": [],
            },
            "hi_rokid": {"package": "com.rokid.sprite.global.aiapp", "version_name": "G1.11.11.0727", "components": []},
            "runtime_qualification": {"classification": "ACCEPTED"},
            "summary": {
                "public_class_count": 1, "public_constructor_count": 1, "public_method_count": 1,
                "public_field_count": 0, "public_enum_constant_count": 3, "callback_class_count": 1,
                "native_library_count": 0, "jni_export_count": 0, "member_classification_counts": {"untested": 1},
            },
            "conclusion": "Bounded conclusion.",
        }
        text = classify.markdown_report(publication)
        self.assertNotIn("/Users/", text)
        self.assertIn("CUSTOMAPP", text)

    def test_runner_has_no_interactive_shell_strict_mode(self) -> None:
        text = (ROOT / "scripts/tests/run_test20_r1_census.sh").read_text(encoding="utf-8")
        self.assertNotIn("set -e", text)
        self.assertNotIn("set -u", text)
        self.assertNotIn("pipefail", text.splitlines()[0:10])
        self.assertIn("ADB_OPERATION=NONE", text)


if __name__ == "__main__":
    unittest.main()
