#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("t21r3",HERE/"analyze_test21_r3_respawn.py")
MOD=importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MOD)

COL_SPEC=importlib.util.spec_from_file_location("t21r3collector",HERE/"collect_test21_r3_timeline.py")
COL=importlib.util.module_from_spec(COL_SPEC)
assert COL_SPEC.loader
COL_SPEC.loader.exec_module(COL)

def timeline(respawn=None, conn=1000, cxrl=2000, service=3000, ready=4000, started_hi=False):
    out=[{
        "kind":"collector_started","host_epoch_ms":900,
        "hi_process_visible":started_hi,"custom_process_visible":True,
    }]
    if conn is not None:
        out.append({"kind":"event_first_seen","host_epoch_ms":conn,"event_type":"connection_attempt_started"})
    if respawn is not None:
        out.append({"kind":"hi_process_first_respawn","host_epoch_ms":respawn})
    if cxrl is not None:
        out.append({"kind":"event_first_seen","host_epoch_ms":cxrl,"event_type":"callback_cxrl_connected"})
    if service is not None:
        out.append({"kind":"event_first_seen","host_epoch_ms":service,"event_type":"service_status_result"})
    if ready is not None:
        out.append({"kind":"event_first_seen","host_epoch_ms":ready,"event_type":"operator_gate_prerequisite_ready"})
    return out

class TestOrdering(unittest.TestCase):
    def classify(self, items):
        r,e,h=MOD.timeline_index(items)
        return MOD.ordering(r,e,h)

    def test_auto_respawn_before_connection(self):
        self.assertEqual(self.classify(timeline(respawn=950)), "AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT")

    def test_respawn_after_attempt_before_cxrl(self):
        self.assertEqual(self.classify(timeline(respawn=1500)), "RESPAWN_AFTER_CONNECTION_ATTEMPT_BEFORE_CXRL_CONNECTED")

    def test_respawn_after_cxrl_before_service(self):
        self.assertEqual(self.classify(timeline(respawn=2500)), "RESPAWN_AFTER_CXRL_BEFORE_SERVICE_STATUS")

    def test_respawn_after_service_before_ready(self):
        self.assertEqual(self.classify(timeline(respawn=3500)), "RESPAWN_AFTER_SERVICE_STATUS_BEFORE_PREREQUISITE_READY")

    def test_respawn_after_ready(self):
        self.assertEqual(self.classify(timeline(respawn=4500)), "RESPAWN_AFTER_PREREQUISITE_READY")

    def test_no_respawn(self):
        self.assertEqual(self.classify(timeline(respawn=None)), "NO_RESPAWN_DURING_OBSERVATION")

class TestServiceEvidence(unittest.TestCase):
    def test_component_extraction(self):
        text="ServiceRecord{1 u0 com.rokid.sprite.global.aiapp/.bridge.CxrBridgeService}"
        self.assertEqual(
            MOD.components(text),
            ["com.rokid.sprite.global.aiapp/.bridge.CxrBridgeService"],
        )

    def test_strict_caller_bound_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td)
            (raw/"activity-events-private.txt").write_text(
                "am_bind_service caller=org.aimindseye.rokid.cxrphotoqualification "
                "target=com.rokid.sprite.global.aiapp/.bridge.CxrBridgeService\n",
                encoding="utf-8",
            )
            result=MOD.service_evidence(raw)
            self.assertTrue(result["bound_service_caller_evidence"])
            self.assertTrue(result["bound_service_evidence"])

    def test_service_presence_is_not_caller_proof(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td)
            (raw/"respawn-hi-services-private.txt").write_text(
                "ServiceRecord{1 u0 com.rokid.sprite.global.aiapp/.bridge.CxrBridgeService}\n",
                encoding="utf-8",
            )
            result=MOD.service_evidence(raw)
            self.assertFalse(result["bound_service_caller_evidence"])
            self.assertEqual(
                result["hi_rokid_service_components_at_respawn"],
                ["com.rokid.sprite.global.aiapp/.bridge.CxrBridgeService"],
            )

class TestNextAction(unittest.TestCase):
    def test_bound_caller_advances_to_component_qualification(self):
        svc={
            "bound_service_caller_evidence":True,
            "bound_service_evidence":True,
            "process_start_event_evidence":True,
            "hi_rokid_service_components_at_respawn":["x"],
        }
        conn={"cxrl_connected":True,"service_status_success":True}
        self.assertEqual(
            MOD.next_action("RESPAWN_AFTER_CONNECTION_ATTEMPT_BEFORE_CXRL_CONNECTED",svc,conn),
            "R4_SERVICE_COMPONENT_DEPENDENCY_QUALIFICATION",
        )

    def test_no_respawn_connected_advances_cold_start(self):
        svc={
            "bound_service_caller_evidence":False,
            "bound_service_evidence":False,
            "process_start_event_evidence":False,
            "hi_rokid_service_components_at_respawn":[],
        }
        conn={"cxrl_connected":True,"service_status_success":True}
        self.assertEqual(
            MOD.next_action("NO_RESPAWN_DURING_OBSERVATION",svc,conn),
            "R4_COLD_START_AUTHORIZATION_AND_SESSION_BOOTSTRAP",
        )

class TestCollectorHelpers(unittest.TestCase):
    def test_watch_events_include_required_connection_markers(self):
        self.assertIn("connection_attempt_started",COL.WATCH_EVENTS)
        self.assertIn("callback_cxrl_connected",COL.WATCH_EVENTS)
        self.assertIn("service_status_result",COL.WATCH_EVENTS)
        self.assertIn("operator_gate_prerequisite_ready",COL.WATCH_EVENTS)

if __name__=="__main__":
    unittest.main(verbosity=2)
