#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE/'apply_test20_final_docs_patch.py'
spec=importlib.util.spec_from_file_location('docpatch',P); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class DocsPatcherTests(unittest.TestCase):
    def test_current_status_current_main_shape(self):
        s='''# Developer Current Status\n\n<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->\n| Last reviewed | 2026-07-31 |\n| CXR-L one-shot photo qualification | Not started; requires a separately governed r3.2 single-operation design |\n| Independent camera capture | Not yet tested |\nThe accepted runtime-qualified delta is limited to\n`setCXRImageCbk(IImageStreamCbk)`, `setCXRAudioCbk(IAudioStreamCbk)`,\n`getServiceVersion()`, `getServiceVersionCode()`, and\n`isGlassBtConnected()`. Photo capture, audio streaming, payload formats,\nparameter semantics, and media transport behavior remain unqualified. The next\nbounded gate is Test 20 r3.2, a separately governed one-shot photo design.\n## Evidence\n- old\n'''
        out=mod.patch_status(s)
        self.assertIn(mod.MARK,out); self.assertIn('Test 20 final accepted:',out); self.assertNotIn('next\nbounded gate is Test 20 r3.2',out)
        self.assertEqual(mod.patch_status(out),out)
    def test_current_status_test20_r3_2_branch_shape(self):
        s='''# Developer Current Status\n\n<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->\n| Last reviewed | 2026-07-31 |\n| CXR-L one-shot photo qualification | Test 20 r3.2 implementation ready for governed build and one physical attempt; exactly one bounded photo request, no payload persistence |\n| Independent camera capture | Not yet tested |\nThe accepted runtime-qualified delta is limited to\n`setCXRImageCbk(IImageStreamCbk)`, `setCXRAudioCbk(IAudioStreamCbk)`,\n`getServiceVersion()`, `getServiceVersionCode()`, and\n`isGlassBtConnected()`. Photo capture, audio streaming, payload formats,\nparameter semantics, and media transport behavior remain unqualified. The next\nbounded gate is Test 20 r3.2, a separately governed one-shot photo design.\n## Evidence\n- old\n'''
        out=mod.patch_status(s)
        self.assertIn(mod.MARK,out); self.assertIn('Test 20 final accepted:',out)
        self.assertNotIn('implementation ready for governed build',out)
        self.assertEqual(mod.patch_status(out),out)
    def test_requirements(self):
        s='# Companion-App Requirements\n<!-- wiki-status: last_reviewed=2026-07-30 -->\n| Last reviewed | 2026-07-30 |\n## Safety and privacy requirements\n'
        out=mod.patch_requirements(s); self.assertIn('Qualified CXR-L photo lifecycle',out); self.assertEqual(mod.patch_requirements(out),out)
    def test_connection_append(self):
        s='# Stock Connection Protocol and Minimal Companion Research\nbody\n'
        out=mod.patch_connection(s); self.assertIn(mod.MARK,out); self.assertIn('Test 20 final CXR-L',out); self.assertEqual(mod.patch_connection(out),out)
    def test_research(self):
        s='# Research Index\n## Current boundary\n'; out=mod.patch_research(s); self.assertIn('Test 20 final photo path',out)
    def test_docs_index_legacy_shape(self):
        s='# Documentation Index\n## Protected companion research\n'; out=mod.patch_docs_index(s); self.assertIn('Test 20 final photo control',out); self.assertEqual(mod.patch_docs_index(out),out)
    def test_docs_home_audience_first_shape(self):
        s='''# Documentation Home\n\n<!-- wiki-status: audience=all; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->\n\n## Research and evidence\n\nStart with the [Research library](research/README.md) for validated numbered\ntests, protocol releases, protected-application research, methodology,\nlimitations, sanitized evidence, and supersession history.\n\n## Shared reference\n\nThe [Reference library](reference/README.md) holds shared reference material.\n'''
        out=mod.patch_docs_index(s)
        self.assertIn('Test 20 final photo control and callback publication',out)
        self.assertLess(out.index('Test 20 final photo control'),out.index('## Shared reference'))
        self.assertEqual(mod.patch_docs_index(out),out)
    def test_tests_readme(self):
        s='# Tests and Qualification History\nnumbered product/device tests through **Test 18**\n| 18 | Developer Mode and USB ADB control-path static/offline follow-up |\n'; out=mod.patch_tests_readme(s); self.assertIn('| 19–20 |',out)
    def test_matrix(self):
        s='# Test and Research Matrix\n| 18 | USB ADB control-path follow-up | 18A–18D | PASS in static/offline scope; runtime invocation unresolved | [Sanitized summary](../../evidence/sanitized/glasses-os-services/usb-adb-control-summary.txt) |\n'; out=mod.patch_matrix(s); self.assertIn('| 20 | CXR-L one-shot photo and callback closure',out)

if __name__=='__main__': unittest.main(verbosity=2)
