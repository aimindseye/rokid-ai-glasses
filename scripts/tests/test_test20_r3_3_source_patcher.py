#!/usr/bin/env python3
from __future__ import annotations
import ast, importlib.util, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
PATCH=HERE/'apply_test20_r3_3_source_patch.py'
spec=importlib.util.spec_from_file_location('r33patch',PATCH); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def olds(funcname):
    tree=ast.parse(PATCH.read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==funcname)
    env={}
    for n in fn.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try: env[n.targets[0].id]=ast.literal_eval(n.value)
            except Exception: pass
    out=[]
    for n in ast.walk(fn):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace_once' and len(n.args)>=3:
            try: val=ast.literal_eval(n.args[1])
            except Exception:
                val=env.get(n.args[1].id) if isinstance(n.args[1],ast.Name) else None
            if isinstance(val,str): out.append(val)
    return out

def fixture(funcname, extra=''):
    # Separate exact baseline markers to exercise every governed replacement.
    return extra+'\n/* SPLIT */\n'.join(olds(funcname))+'\n'

class PatcherTests(unittest.TestCase):
    def test_main_all_markers_and_idempotent(self):
        s=fixture('patch_main','operator_gate_host_command\nPHASE 2 — ARMED: capture ONE photo\n')
        out=mod.patch_main(s); self.assertIn('callback_profile',out); self.assertEqual(mod.patch_main(out),out)
    def test_controller_all_markers_and_idempotent(self):
        s=fixture('patch_controller','operator_gate_arm_result\nhostArmGranted.compareAndSet(true, false)\n')
        out=mod.patch_controller(s); self.assertIn('image_callback_reregistration_result',out); self.assertIn('callback_path_snapshot',out); self.assertEqual(mod.patch_controller(out),out)
    def test_contract(self):
        s=fixture('patch_contract'); out=mod.patch_contract(s); self.assertIn('R3_3_WATCHDOG_DELAYS_MS',out)
    def test_gradle(self):
        s='android { defaultConfig {\n        versionCode = 2\n        versionName = "1.0-test20-r3.2.1.3"\n} }\n'; out=mod.patch_gradle(s); self.assertIn('1.0-test20-r3.3',out); self.assertIn('versionCode = 3',out)
    def test_refuses_wrong_baseline(self):
        with self.assertRaises(mod.PatchError): mod.patch_main('not baseline')

if __name__=='__main__': unittest.main(verbosity=2)
