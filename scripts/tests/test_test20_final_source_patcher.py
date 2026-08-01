#!/usr/bin/env python3
from __future__ import annotations
import ast, importlib.util, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
PATCH=HERE/'apply_test20_final_source_patch.py'
spec=importlib.util.spec_from_file_location('finalpatch',PATCH); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def old_replacements(funcname):
    tree=ast.parse(PATCH.read_text()); fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==funcname); env={}
    for n in fn.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try: env[n.targets[0].id]=ast.literal_eval(n.value)
            except Exception: pass
    out=[]
    for n in ast.walk(fn):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace_once' and len(n.args)>=3:
            val=None
            try: val=ast.literal_eval(n.args[1])
            except Exception:
                if isinstance(n.args[1],ast.Name): val=env.get(n.args[1].id)
            if isinstance(val,str): out.append(val)
    return out

def fixture(funcname,extra=''):
    return extra+'\n/* SPLIT */\n'.join(old_replacements(funcname))+'\n'

class SourcePatcherTests(unittest.TestCase):
    def test_main_all_governed_markers_and_idempotent(self):
        s=fixture('patch_main','Test 20 r3.3 — Callback Non-Delivery Closure\ncallback_profile_selected\noperator_gate_host_command\nPHASE 2 — ARMED: capture ONE photo\n')
        out=mod.patch_main(s)
        self.assertIn('Test 20 Final — Canonical One-Shot Photo Controller',out)
        self.assertIn('CANONICAL_POSTCONNECT_REREGISTER',out)
        self.assertNotIn('callbackProfile',out)
        self.assertEqual(mod.patch_main(out),out)
    def test_controller_all_governed_markers_and_idempotent(self):
        s=fixture('patch_controller','''operator_gate_arm_result\nhostArmGranted.compareAndSet(true, false)\n''')
        out=mod.patch_controller(s)
        self.assertIn('canonical_image_callback_reregistration_result',out)
        self.assertIn('reregisterImageCallbackAfterServiceStatus()',out)
        self.assertIn('hostArmGranted.compareAndSet(true, false)',out)
        self.assertNotIn('callbackProfile',out)
        self.assertNotIn('ARG3_ZERO_DIAGNOSTIC',out)
        self.assertEqual(mod.patch_controller(out),out)
    def test_contract(self):
        extra='''    static final String EVENT_SCHEMA = "rokid.test20-r3.2.cxrl-one-shot-photo.v1";\n    static final String PHOTO_ARGUMENT_SEMANTICS =\n            "WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED";\n    static final long[] R3_3_WATCHDOG_DELAYS_MS = new long[] { 1000L };\n'''
        out=mod.patch_contract(extra)
        self.assertIn('IMAGE_CALLBACK_LIFECYCLE',out)
        self.assertIn('POST_TAKEPHOTO_WATCHDOG_DELAYS_MS',out)
        self.assertNotIn('R3_3_WATCHDOG_DELAYS_MS',out)
        self.assertEqual(mod.patch_contract(out),out)
    def test_gradle(self):
        s='plugins {}\nandroid { defaultConfig {\n        versionCode = 3\n        versionName = "1.0-test20-r3.3"\n} }\nval cxrLVersion = providers.gradleProperty("rokidCxrLVersion").orNull\nif (cxrLVersion != null) { dependencies { implementation("com.rokid.cxr:client-l:$cxrLVersion") } }\nif (cxrLVersion != "1.0.1") { throw GradleException("pinned") }\n'
        out=mod.patch_gradle(s)
        self.assertIn('versionCode = 4',out)
        self.assertIn('1.0-test20-final',out)
        self.assertIn('implementation("com.rokid.cxr:client-l:$cxrLVersion")',out)
        self.assertIn('cxrLVersion != "1.0.1"',out)
        self.assertEqual(mod.patch_gradle(out),out)
    def test_refuses_wrong_baseline(self):
        with self.assertRaises(mod.PatchError): mod.patch_controller('not accepted r3.3')

if __name__=='__main__': unittest.main(verbosity=2)
