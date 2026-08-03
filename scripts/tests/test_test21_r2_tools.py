#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("t21r2", HERE / "analyze_test21_r2_ownership.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MOD)

CHECK_SPEC = importlib.util.spec_from_file_location("t21r2_contract", HERE / "check_test21_r2_source_contract.py")
CHECK = importlib.util.module_from_spec(CHECK_SPEC)
assert CHECK_SPEC.loader
CHECK_SPEC.loader.exec_module(CHECK)

def ev(name, **details):
    return {
        "event_type": name,
        "run_id": "synthetic-run",
        "package": MOD.EXPECTED_CUSTOM,
        "details": details,
    }

def base_events(connected=True):
    events = [
        ev("run_started", app_version=MOD.EXPECTED_VERSION),
        ev("operator_gate_initialized", photo_control_enabled=False, host_arm_granted=False),
        ev("authorization_result", token_present=True, token_value_logged=False),
    ]
    if connected:
        events += [
            ev("connection_attempt_started", token_present=True, token_value_logged=False),
            ev("image_callback_registration_result", registration_returned=True, media_request_issued=False),
            ev("callback_cxrl_connected", connected=True),
            ev("callback_glass_bt_connected", connected=True),
            ev("service_status_result", status_success=True, photo_request_issued=False),
            ev("canonical_image_callback_reregistration_result",
               registration_returned=True, same_callback_identity=True, media_request_issued=False),
            ev("photo_ready", explicit_operator_tap_required=True),
            ev("operator_gate_prerequisite_ready",
               photo_control_enabled=False, host_arm_granted=False, photo_request_issued=False),
        ]
    return events

def state(hi, custom=True, recovery=None):
    out = {
        "HI_PROCESS_VISIBLE": "YES" if hi else "NO",
        "CUSTOM_PROCESS_VISIBLE": "YES" if custom else "NO",
    }
    if recovery is not None:
        out["OPERATOR_HI_ROKID_RECOVERY"] = recovery
    return out


class TestSourceContractRegression(unittest.TestCase):
    def test_textual_takephoto_reference_is_not_executable_call_site(self):
        controller = """class CxrLPhotoController {
            void request() {
                String method = \"takePhoto(int,int,int)\";
                // Canonical request remains takePhoto(1920,1080,80).
                boolean returned = link.takePhoto(1920, 1080, 80);
            }
        }"""
        executable = len(CHECK.re.findall(r"\blink\.takePhoto\s*\(", controller))
        textual = controller.count("takePhoto(")
        self.assertEqual(executable, 1)
        self.assertGreater(textual, executable)

class TestPreforce(unittest.TestCase):
    def test_preforce_pass(self):
        events = base_events(connected=False)
        result = MOD.verify_preforce(events)
        self.assertTrue(result["authorization_token_present"])

    def test_preforce_rejects_connection(self):
        events = base_events(connected=False) + [ev("connection_attempt_started", token_present=True)]
        with self.assertRaises(MOD.GateError):
            MOD.verify_preforce(events)

    def test_media_gate_rejects_photo_request(self):
        events = base_events(connected=False) + [ev("photo_request_result", request_count=1)]
        with self.assertRaises(MOD.GateError):
            MOD.media_gate(events)

    def test_media_gate_rejects_host_arm(self):
        events = base_events(connected=False) + [ev("operator_gate_arm_result", granted=True)]
        with self.assertRaises(MOD.GateError):
            MOD.media_gate(events)

class TestClassifications(unittest.TestCase):
    def classify(self, *, settled_hi=False, post_hi=False, custom=True, connected=True, absent=True):
        return MOD.classify(
            state(True),
            state(False),
            state(settled_hi, custom),
            state(post_hi, custom),
            state(True, custom, "PASS"),
            {"HI_PROCESS_ABSENT_OBSERVED": "YES" if absent else "NO"},
            base_events(connected=connected),
        )[0]

    def test_connected_remained_stopped(self):
        self.assertEqual(
            self.classify(settled_hi=False, post_hi=False, connected=True),
            "CUSTOM_SESSION_CONNECTED_HI_ROKID_REMAINED_STOPPED",
        )

    def test_connected_respawned(self):
        self.assertEqual(
            self.classify(settled_hi=False, post_hi=True, connected=True),
            "CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED",
        )

    def test_failed_remained_stopped(self):
        self.assertEqual(
            self.classify(settled_hi=False, post_hi=False, connected=False),
            "CUSTOM_SESSION_FAILED_HI_ROKID_REMAINED_STOPPED",
        )

    def test_failed_respawned(self):
        self.assertEqual(
            self.classify(settled_hi=False, post_hi=True, connected=False),
            "CUSTOM_SESSION_FAILED_HI_ROKID_RESPAWNED",
        )

    def test_auto_respawn_preconnect(self):
        self.assertEqual(
            self.classify(settled_hi=True, post_hi=True, connected=False),
            "AUTO_RESPAWN_BEFORE_CUSTOM_CONNECT",
        )

    def test_custom_died(self):
        self.assertEqual(
            self.classify(settled_hi=False, post_hi=False, custom=False, connected=False),
            "CUSTOM_APP_DIED_DURING_FORCE_STOP",
        )

    def test_absence_not_observed(self):
        self.assertEqual(
            self.classify(settled_hi=True, post_hi=True, connected=False, absent=False),
            "FORCE_STOP_ABSENCE_NOT_OBSERVED",
        )

class TestEndToEndSynthetic(unittest.TestCase):
    def write_state(self, path, hi, custom=True, recovery=None):
        lines = [
            "SCHEMA=synthetic",
            f"HI_PROCESS_VISIBLE={'YES' if hi else 'NO'}",
            f"CUSTOM_PROCESS_VISIBLE={'YES' if custom else 'NO'}",
        ]
        if recovery:
            lines.append(f"OPERATOR_HI_ROKID_RECOVERY={recovery}")
        path.write_text("\n".join(lines)+"\n", encoding="utf-8")

    def test_final_main_writes_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root/"raw"; raw.mkdir()
            self.write_state(raw/"state-pre-force.txt", True)
            self.write_state(raw/"state-post-force-immediate.txt", False)
            self.write_state(raw/"state-post-force-settled.txt", False)
            self.write_state(raw/"state-post-connect.txt", True)
            self.write_state(raw/"state-restored.txt", True, recovery="PASS")
            (raw/"force-stop-observation.txt").write_text(
                "HI_PROCESS_ABSENT_OBSERVED=YES\n", encoding="utf-8"
            )
            with (raw/"pre-force-events-private.jsonl").open("w", encoding="utf-8") as f:
                for item in base_events(connected=False):
                    f.write(json.dumps(item)+"\n")
            with (raw/"final-events-private.jsonl").open("w", encoding="utf-8") as f:
                for item in base_events(connected=True):
                    f.write(json.dumps(item)+"\n")
            old = __import__("sys").argv
            try:
                __import__("sys").argv = ["analyze", "--mode", "final", "--evidence", str(root)]
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = MOD.main()
            finally:
                __import__("sys").argv = old
            self.assertEqual(rc, 0)
            summary = json.loads((root/"sanitized/test21-r2-summary.json").read_text())
            self.assertEqual(
                summary["runtime"]["disposition"],
                "CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED",
            )

if __name__ == "__main__":
    unittest.main(verbosity=2)
