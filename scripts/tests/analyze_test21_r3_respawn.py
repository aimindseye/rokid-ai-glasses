#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HI = "com.rokid.sprite.global.aiapp"
CUSTOM = "org.aimindseye.rokid.cxrphotoqualification"
EXPECTED_VERSION = "1.0-test20-final"

ORDERINGS = (
    "AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT",
    "RESPAWN_AFTER_CONNECTION_ATTEMPT_BEFORE_CXRL_CONNECTED",
    "RESPAWN_AFTER_CXRL_BEFORE_SERVICE_STATUS",
    "RESPAWN_AFTER_SERVICE_STATUS_BEFORE_PREREQUISITE_READY",
    "RESPAWN_AFTER_PREREQUISITE_READY",
    "NO_RESPAWN_DURING_OBSERVATION",
    "INSUFFICIENT_TIMELINE_EVIDENCE",
)

COMPONENT_RE = re.compile(
    r"com\.rokid\.sprite\.global\.aiapp/(?:\.[A-Za-z0-9_$.-]+|[A-Za-z0-9_$.-]+)"
)
BIND_TERMS = re.compile(r"(?i)\b(?:bind|binding|connectionrecord|intentbindrecord|am_bind_service)\b")
PROCESS_START_TERMS = re.compile(r"(?i)\b(?:am_proc_start|start proc|start process|proc_start)\b")

class GateError(RuntimeError):
    pass

def load_r2(repo: Path):
    path = repo / "scripts/tests/analyze_test21_r2_ownership.py"
    if not path.is_file():
        raise GateError("accepted Test21 r2 analyzer missing")
    spec = importlib.util.spec_from_file_location("test21_r2_accepted", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise GateError(f"required JSONL missing or empty: {path}")
    out=[]
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(),1):
        if not raw.strip():
            continue
        try:
            item=json.loads(raw)
        except json.JSONDecodeError as e:
            raise GateError(f"invalid JSONL {path.name}:{lineno}: {e}") from e
        if isinstance(item,dict):
            out.append(item)
    if not out:
        raise GateError(f"no objects in JSONL: {path}")
    return out

def read_kv(path: Path) -> dict[str,str]:
    if not path.is_file():
        raise GateError(f"required phase file missing: {path}")
    out={}
    for raw in path.read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or "=" not in line or line.startswith("#"):
            continue
        k,v=line.split("=",1)
        out[k.strip()]=v.strip()
    return out

def yes(v: Any) -> bool:
    return str(v).strip().upper()=="YES"

def timeline_index(items: list[dict[str,Any]]) -> tuple[int|None, dict[str,int], bool]:
    respawn=None
    events={}
    started_hi=False
    for item in items:
        kind=str(item.get("kind",""))
        if kind=="collector_started":
            started_hi=bool(item.get("hi_process_visible"))
        elif kind=="hi_process_first_respawn" and respawn is None:
            try:
                respawn=int(item.get("host_epoch_ms"))
            except Exception:
                pass
        elif kind=="event_first_seen":
            et=str(item.get("event_type","")).strip()
            try:
                ts=int(item.get("host_epoch_ms"))
            except Exception:
                continue
            if et and et not in events:
                events[et]=ts
    return respawn,events,started_hi

def ordering(respawn: int|None, events: dict[str,int], collector_started_hi: bool) -> str:
    conn=events.get("connection_attempt_started")
    cxrl=events.get("callback_cxrl_connected")
    service=events.get("service_status_result")
    ready=events.get("operator_gate_prerequisite_ready") or events.get("photo_ready")

    if collector_started_hi and conn is None:
        return "AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT"
    if respawn is None:
        return "NO_RESPAWN_DURING_OBSERVATION"
    if conn is None:
        return "AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT"
    if respawn <= conn:
        return "AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT"
    if cxrl is None or respawn < cxrl:
        return "RESPAWN_AFTER_CONNECTION_ATTEMPT_BEFORE_CXRL_CONNECTED"
    if service is None or respawn < service:
        return "RESPAWN_AFTER_CXRL_BEFORE_SERVICE_STATUS"
    if ready is None or respawn < ready:
        return "RESPAWN_AFTER_SERVICE_STATUS_BEFORE_PREREQUISITE_READY"
    return "RESPAWN_AFTER_PREREQUISITE_READY"

def gather_text(raw: Path, names: tuple[str,...]) -> str:
    chunks=[]
    for name in names:
        p=raw/name
        if p.is_file():
            chunks.append(p.read_text(encoding="utf-8",errors="replace"))
    return "\n".join(chunks)

def components(text: str) -> list[str]:
    return sorted(set(COMPONENT_RE.findall(text)))

def service_evidence(raw: Path) -> dict[str,Any]:
    activity_events=gather_text(raw,("activity-events-private.txt","activity-manager-private.txt"))
    respawn_text=gather_text(raw,(
        "respawn-hi-services-private.txt",
        "respawn-custom-services-private.txt",
        "respawn-activity-processes-private.txt",
        "service-samples-private.txt",
    ))
    combined=activity_events+"\n"+respawn_text

    all_components=components(combined)
    respawn_components=components(respawn_text)

    bind_lines=[]
    process_start_lines=[]
    for raw_line in combined.splitlines():
        line=raw_line.strip()
        if not line:
            continue
        if HI in line and BIND_TERMS.search(line):
            if CUSTOM in line or "ConnectionRecord" in line or "IntentBindRecord" in line or "am_bind_service" in line:
                bind_lines.append(line)
        if HI in line and PROCESS_START_TERMS.search(line):
            process_start_lines.append(line)

    # Caller-bound evidence is intentionally strict: the same log/snapshot line must
    # identify both packages and a binding concept.
    caller_bind_lines=[
        line for line in bind_lines if CUSTOM in line and HI in line and BIND_TERMS.search(line)
    ]

    return {
        "bound_service_caller_evidence": bool(caller_bind_lines),
        "bound_service_evidence": bool(bind_lines),
        "process_start_event_evidence": bool(process_start_lines),
        "hi_rokid_service_components": all_components,
        "hi_rokid_service_components_at_respawn": respawn_components,
        "binding_evidence_line_count": len(bind_lines),
        "caller_binding_evidence_line_count": len(caller_bind_lines),
        "process_start_evidence_line_count": len(process_start_lines),
    }

def connection_summary(events: list[dict[str,Any]], r2) -> dict[str,bool]:
    r2.media_gate(events)
    r2.event_identity(events)
    def b(name: str, key: str, default=False) -> bool:
        item=r2.last(events,name)
        if not item:
            return default
        return r2.boolish(r2.details(item).get(key))
    return {
        "connection_attempt_started": bool(r2.find(events,"connection_attempt_started")),
        "cxrl_connected": b("callback_cxrl_connected","connected"),
        "glass_bt_connected": b("callback_glass_bt_connected","connected"),
        "service_status_success": b("service_status_result","status_success"),
        "prerequisite_ready": bool(r2.find(events,"operator_gate_prerequisite_ready")),
        "photo_ready_machine_state": bool(r2.find(events,"photo_ready")),
    }

def next_action(order: str, svc: dict[str,Any], conn: dict[str,bool]) -> str:
    if order=="NO_RESPAWN_DURING_OBSERVATION" and conn["cxrl_connected"] and conn["service_status_success"]:
        return "R4_COLD_START_AUTHORIZATION_AND_SESSION_BOOTSTRAP"
    if order=="AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT":
        return "R3_1_AUTO_RESPAWN_TRIGGER_CHARACTERIZATION"
    if svc["bound_service_caller_evidence"]:
        return "R4_SERVICE_COMPONENT_DEPENDENCY_QUALIFICATION"
    if svc["bound_service_evidence"] or svc["process_start_event_evidence"] or svc["hi_rokid_service_components_at_respawn"]:
        return "R3_1_RESPAWN_TRIGGER_CALLER_CHARACTERIZATION"
    return "R3_1_INCREASED_ACTIVITY_MANAGER_OBSERVABILITY"

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--evidence", required=True)
    args=ap.parse_args()

    repo=Path(args.repo).expanduser().resolve()
    evidence=Path(args.evidence).expanduser().resolve()
    raw=evidence/"raw"
    sanitized=evidence/"sanitized"
    sanitized.mkdir(parents=True,exist_ok=True)

    try:
        r2=load_r2(repo)
        pre=read_jsonl(raw/"pre-force-events-private.jsonl")
        final=read_jsonl(raw/"final-events-private.jsonl")
        r2.verify_preforce(pre)
        r2.media_gate(final)
        run_id,_=r2.event_identity(final)

        force=read_kv(raw/"force-stop-observation.txt")
        if force.get("HI_PROCESS_ABSENT_OBSERVED")!="YES":
            raise GateError("Hi Rokid process absence was not observed after force-stop")

        pre_conn=read_kv(raw/"state-pre-connect.txt")
        if pre_conn.get("HI_PROCESS_VISIBLE")!="NO":
            raise GateError("Hi Rokid was visible immediately before r3 connection observation")
        if pre_conn.get("CUSTOM_PROCESS_VISIBLE")!="YES":
            raise GateError("custom companion was not alive immediately before r3 connection observation")

        timeline=read_jsonl(raw/"timeline-private.jsonl")
        respawn_ms,event_times,collector_started_hi=timeline_index(timeline)
        order=ordering(respawn_ms,event_times,collector_started_hi)
        conn=connection_summary(final,r2)
        svc=service_evidence(raw)

        restored=read_kv(raw/"state-restored.txt")
        restoration_ok=restored.get("OPERATOR_HI_ROKID_RECOVERY")=="PASS" and restored.get("HI_PROCESS_VISIBLE")=="YES"
        if not restoration_ok:
            raise GateError("mandatory Hi Rokid restoration was not proven")

        summary={
            "schema":"rokid.test21-r3.bound-service-respawn.v1",
            "scope":"bound_service_respawn_dependency_characterization",
            "run_id":run_id,
            "hi_rokid_package":HI,
            "custom_companion_package":CUSTOM,
            "custom_companion_version":EXPECTED_VERSION,
            "r2_accepted_prerequisite":"CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED",
            "timeline":{
                "ordering":order,
                "hi_process_respawn_observed":respawn_ms is not None,
                "collector_started_with_hi_process_visible":collector_started_hi,
                "connection_attempt_observed":conn["connection_attempt_started"],
                "cxrl_connected":conn["cxrl_connected"],
                "glass_bt_connected":conn["glass_bt_connected"],
                "service_status_success":conn["service_status_success"],
                "prerequisite_ready":conn["prerequisite_ready"],
                "photo_ready_machine_state":conn["photo_ready_machine_state"],
                "event_first_seen_available":sorted(event_times),
                "host_timeline_resolution":"poll_observation_not_device_causal_timestamp",
            },
            "service_dependency":{
                "BOUND_SERVICE_CALLER_EVIDENCE":svc["bound_service_caller_evidence"],
                "BOUND_SERVICE_EVIDENCE":svc["bound_service_evidence"],
                "PROCESS_START_EVENT_EVIDENCE":svc["process_start_event_evidence"],
                "HI_ROKID_SERVICE_COMPONENTS":svc["hi_rokid_service_components"],
                "HI_ROKID_SERVICE_COMPONENTS_AT_RESPAWN":svc["hi_rokid_service_components_at_respawn"],
                "binding_evidence_line_count":svc["binding_evidence_line_count"],
                "caller_binding_evidence_line_count":svc["caller_binding_evidence_line_count"],
                "process_start_evidence_line_count":svc["process_start_evidence_line_count"],
            },
            "safety":{
                "photo_operation":"NONE",
                "audio_operation":"NONE",
                "host_photo_arm":"NONE",
                "package_disable":"NONE",
                "package_uninstall":"NONE",
                "package_data_clear":"NONE",
                "firmware_operation":"NONE",
                "authorization_token_host_export":False,
            },
            "restoration":{"hi_rokid_restoration":"PASS"},
        }
        summary["next_action"]=next_action(order,svc,conn)

        json_path=sanitized/"test21-r3-summary.json"
        json_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")

        component_display=",".join(svc["hi_rokid_service_components_at_respawn"]) or "NONE_OBSERVED"
        txt_lines=[
            "TEST21_R3_ANALYSIS=PASS",
            f"RESPAWN_TIMELINE_DISPOSITION={order}",
            f"HI_ROKID_PROCESS_RESPAWN_OBSERVED={'YES' if respawn_ms is not None else 'NO'}",
            f"CXR_L_CONNECTION_ATTEMPT_STARTED={'YES' if conn['connection_attempt_started'] else 'NO'}",
            f"CXR_L_CONNECTED={'YES' if conn['cxrl_connected'] else 'NO'}",
            f"GLASS_BT_CONNECTED={'YES' if conn['glass_bt_connected'] else 'NO'}",
            f"SERVICE_STATUS_SUCCESS={'YES' if conn['service_status_success'] else 'NO'}",
            f"PREREQUISITE_READY={'YES' if conn['prerequisite_ready'] else 'NO'}",
            f"BOUND_SERVICE_CALLER_EVIDENCE={'YES' if svc['bound_service_caller_evidence'] else 'NO'}",
            f"BOUND_SERVICE_EVIDENCE={'YES' if svc['bound_service_evidence'] else 'NO'}",
            f"PROCESS_START_EVENT_EVIDENCE={'YES' if svc['process_start_event_evidence'] else 'NO'}",
            f"HI_ROKID_SERVICE_COMPONENTS_AT_RESPAWN={component_display}",
            "TIMELINE_CAUSALITY_CLAIM=NOT_PROVEN_ORDERING_ONLY",
            "PHOTO_OPERATION=NONE",
            "AUDIO_OPERATION=NONE",
            "AUTHORIZATION_TOKEN_HOST_EXPORT=NONE",
            "PACKAGE_DISABLE_OR_UNINSTALL=NONE",
            "PACKAGE_DATA_CLEAR=NONE",
            "HI_ROKID_RESTORATION=PASS",
            f"NEXT_ACTION={summary['next_action']}",
        ]
        txt_path=sanitized/"test21-r3-summary.txt"
        txt_path.write_text("\n".join(txt_lines)+"\n",encoding="utf-8")

        sums=[
            f"{sha256(json_path)}  {json_path.name}",
            f"{sha256(txt_path)}  {txt_path.name}",
        ]
        (sanitized/"SHA256SUMS.txt").write_text("\n".join(sums)+"\n",encoding="utf-8")

        for line in txt_lines:
            print(line)
        print(f"SANITIZED_SUMMARY={json_path}")
        return 0
    except GateError as e:
        print(f"ERROR: {e}",file=sys.stderr)
        print("TEST21_R3_ANALYSIS=FAIL")
        return 1

if __name__=="__main__":
    sys.exit(main())
