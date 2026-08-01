#!/usr/bin/env python3

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "scripts/tests/analyze_test20_r2_events.py"
SPEC = importlib.util.spec_from_file_location("test20_analyzer", ANALYZER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class Test20R2AnalyzerTests(unittest.TestCase):
    firmware = "1.23.009-20260725-153201"

    def event(self, event_type, details, sequence_time):
        return {
            "schema": MODULE.SCHEMA,
            "time_epoch_ms": 1_700_000_000_000 + sequence_time,
            "elapsed_realtime_ms": sequence_time,
            "run_id": "synthetic-run",
            "firmware_label": self.firmware,
            "event_type": event_type,
            "details": details,
        }

    def pass_events(self):
        safe = {
            "app_package": MODULE.EXPECTED_PACKAGE,
            "app_version": MODULE.EXPECTED_VERSION,
            "app_version_code": MODULE.EXPECTED_VERSION_CODE,
            "app_version_source": "package_manager",
            "internet_permission_intentionally_removed": True,
            "camera_permission_intentionally_removed": True,
            "record_audio_permission_intentionally_removed": True,
            "test_app_ai_assistant_invocation_enabled": False,
            "media_operation_enabled": False,
            "custom_command_enabled": False,
            "custom_view_enabled": False,
            "app_management_enabled": False,
            "cloud_api_client_present": False,
        }
        hi = {
            "package_name": "com.rokid.sprite.global.aiapp",
            "version_name": MODULE.EXPECTED_HI_ROKID_VERSION,
            "authorization_resolved": True,
            "service_resolved": True,
        }
        return [
            self.event("run_started", safe, 1),
            self.event("hi_rokid_environment", hi, 2),
            self.event(
                "authorization_result",
                {"token_present": True, "token_value_logged": False},
                3,
            ),
            self.event(
                "session_config_result",
                {"configured": True, "session_type": "CUSTOMAPP"},
                4,
            ),
            self.event("callback_cxrl_connected", {"connected": True}, 5),
            self.event("callback_glass_bt_connected", {"connected": True}, 6),
            self.event(
                "event_observation_armed",
                {
                    "required_cycles": 2,
                    "test_app_invokes_ai_assistant": False,
                    "operator_must_not_speak_query": True,
                },
                7,
            ),
            self.event(
                "callback_ai_assist_start",
                {
                    "sequence": 1,
                    "accepted": True,
                    "duplicate_start_count": 0,
                },
                8,
            ),
            self.event(
                "callback_ai_assist_stop",
                {
                    "sequence": 2,
                    "accepted": True,
                    "cycle_duration_ms": 100,
                    "out_of_order_stop_count": 0,
                },
                9,
            ),
            self.event(
                "callback_ai_assist_start",
                {
                    "sequence": 3,
                    "accepted": True,
                    "duplicate_start_count": 0,
                },
                10,
            ),
            self.event(
                "callback_ai_assist_stop",
                {
                    "sequence": 4,
                    "accepted": True,
                    "cycle_duration_ms": 120,
                    "out_of_order_stop_count": 0,
                },
                11,
            ),
            self.event(
                "qualification_terminal",
                {
                    "outcome": "AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED",
                    "success": True,
                    "completed_cycle_count": 2,
                },
                12,
            ),
            self.event(
                "disconnect_result",
                {
                    "sdk_disconnect_returned": True,
                    "manual_bind_started": True,
                    "manual_unbind_attempted": False,
                    "manual_unbind_disposition":
                        "SKIPPED_SDK_DISCONNECT_SUCCEEDED",
                },
                13,
            ),
            self.event(
                "run_completed",
                {
                    "terminal_success": True,
                    "test_app_cloud_ai_request": "NONE",
                    "test_app_media_operation": "NONE",
                },
                14,
            ),
        ]

    def run_analysis(self, events):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events_path = root / "events.jsonl"
            events_path.write_text(
                "\n".join(json.dumps(item) for item in events) + "\n",
                encoding="utf-8",
            )
            attestation = root / "operator.txt"
            attestation.write_text(
                "OPERATOR_SPOKEN_AI_QUERY=NO\n"
                "STOCK_AI_RESPONSE_OBSERVED=NO\n"
                "HI_ROKID_RECOVERY=PASS\n",
                encoding="utf-8",
            )
            return MODULE.analyze(
                events_path,
                attestation,
                self.firmware,
            )

    def test_two_ordered_cycles_pass(self):
        result = self.run_analysis(self.pass_events())
        self.assertEqual(
            result["qualification"]["ordered_cycles"],
            2,
        )

    def test_one_cycle_fails(self):
        events = [
            item
            for item in self.pass_events()
            if not (
                item["event_type"] in {
                    "callback_ai_assist_start",
                    "callback_ai_assist_stop",
                }
                and item["details"].get("sequence") in {3, 4}
            )
        ]
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_out_of_order_callback_fails(self):
        events = self.pass_events()
        for item in events:
            if item["event_type"] == "callback_ai_assist_stop":
                item["details"]["out_of_order_stop_count"] = 1
                break
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_token_key_is_rejected(self):
        events = self.pass_events()
        events[0]["details"]["auth_token"] = "secret"
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_raw_bluetooth_address_is_rejected(self):
        events = self.pass_events()
        events[0]["details"]["device"] = ":".join(("AA", "BB", "CC", "DD", "EE", "FF"))
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_test_app_cloud_gate_is_required(self):
        events = self.pass_events()
        for item in events:
            if item["event_type"] == "run_completed":
                item["details"]["test_app_cloud_ai_request"] = "UNKNOWN"
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_duplicate_sequence_number_fails(self):
        events = self.pass_events()
        starts = [
            item for item in events
            if item["event_type"] == "callback_ai_assist_start"
        ]
        starts[1]["details"]["sequence"] = 2
        with self.assertRaises(MODULE.AnalysisError):
            self.run_analysis(events)

    def test_manifest_removes_network_and_media_permissions(self):
        manifest = (
            ROOT / "android-client/test20r2/src/main/AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        for permission in (
            "android.permission.INTERNET",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO",
        ):
            self.assertIn(permission, manifest)
        self.assertEqual(manifest.count('tools:node="remove"'), 3)

    def test_no_forbidden_sdk_invocations_in_controller(self):
        source = (
            ROOT
            / "android-client/test20r2/src/main/java/org/aimindseye/rokid/"
            "cxreventqualification/CxrLEventController.java"
        ).read_text(encoding="utf-8")
        forbidden = [
            "takePhoto(",
            "startAudioStream(",
            "stopAudioStream(",
            "sendCustomCmd(",
            "customViewOpen(",
            "customViewUpdate(",
            "appUploadAndInstall(",
            "appUninstall(",
            "appStart(",
            "appStop(",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
