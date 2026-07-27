#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

PHASES = ("off_baseline", "power_on_transition", "on_steady")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"ERROR: invalid JSONL at line {line_number}: {exc}")
        if not isinstance(row, dict):
            raise SystemExit(f"ERROR: JSONL line {line_number} is not an object")
        rows.append(row)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def details(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("details")
    return value if isinstance(value, dict) else {}


def numeric(values: list[Any]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]


def summarize_rssi(values: list[Any]) -> dict[str, Any]:
    points = numeric(values)
    if not points:
        return {"count": 0, "minimum": None, "maximum": None, "median": None}
    return {
        "count": len(points),
        "minimum": min(points),
        "maximum": max(points),
        "median": statistics.median(points),
    }


def group_events(events: list[dict[str, Any]], key_name: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in events:
        key = details(row).get(key_name)
        if isinstance(key, str) and key:
            groups[key].append(row)
    return dict(groups)


def phase_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    output = {phase: 0 for phase in PHASES}
    for row in rows:
        phase = details(row).get("phase")
        if phase in output:
            output[phase] += 1
    return output


def first_elapsed(rows: list[dict[str, Any]], phase: str) -> int | None:
    values = [
        details(row).get("phase_elapsed_ms")
        for row in rows
        if details(row).get("phase") == phase
        and isinstance(details(row).get("phase_elapsed_ms"), int)
    ]
    return min(values) if values else None


def cluster_summary(fingerprint: str, rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    counts = phase_counts(rows)
    device_ids = sorted({str(row.get("device_id")) for row in rows if isinstance(row.get("device_id"), str)})
    payload_fingerprints = sorted({
        str(details(row).get("payload_fingerprint_sha256"))
        for row in rows
        if isinstance(details(row).get("payload_fingerprint_sha256"), str)
    })
    company_ids = sorted({
        int(item.get("company_id"))
        for row in rows
        for item in (details(row).get("manufacturer_data") or [])
        if isinstance(item, dict) and isinstance(item.get("company_id"), int)
    })
    service_uuids = sorted({
        str(value).lower()
        for row in rows
        for value in (details(row).get("advertised_service_uuids") or [])
        if isinstance(value, str)
    })
    service_data_uuids = sorted({
        str(item.get("uuid")).lower()
        for row in rows
        for item in (details(row).get("service_data") or [])
        if isinstance(item, dict) and isinstance(item.get("uuid"), str)
    })
    connectable_count = sum(1 for row in rows if details(row).get("connectable") is True)
    rssi = summarize_rssi([details(row).get("rssi") for row in rows])
    transition_first = first_elapsed(rows, "power_on_transition")
    steady_first = first_elapsed(rows, "on_steady")
    manufacturer_present = any((details(row).get("manufacturer_data_count") or 0) > 0 for row in rows)
    service_data_present = any((details(row).get("service_data_count") or 0) > 0 for row in rows)

    score = 0.0
    reasons: list[str] = []
    blockers: list[str] = []

    if counts["off_baseline"] == 0:
        score += 45.0
        reasons.append("absent_during_off_baseline")
    else:
        score -= 120.0
        blockers.append("present_during_off_baseline")

    if counts["power_on_transition"] >= 5:
        score += 25.0
        reasons.append("repeated_in_power_on_transition")
    else:
        blockers.append("insufficient_transition_observations")

    if counts["on_steady"] >= 5:
        score += 25.0
        reasons.append("repeated_in_on_steady")
    else:
        blockers.append("insufficient_steady_observations")

    if transition_first is not None and transition_first <= 15_000:
        score += 15.0
        reasons.append("appeared_early_after_power_on")
    elif transition_first is None:
        blockers.append("not_seen_in_transition")

    if connectable_count >= 3:
        score += 10.0
        reasons.append("connectable")
    else:
        blockers.append("not_reliably_connectable")

    if manufacturer_present or service_data_present or service_uuids:
        score += 8.0
        reasons.append("advertisement_identity_material_present")
    else:
        blockers.append("no_advertisement_identity_material")

    if rssi["maximum"] is not None and rssi["maximum"] >= -80:
        score += 5.0
        reasons.append("usable_signal")
    else:
        blockers.append("weak_or_missing_signal")

    if kind == "structure" and len(device_ids) > 1:
        score += 4.0
        reasons.append("address_rotation_cluster")

    qualifying = (
        counts["off_baseline"] == 0
        and counts["power_on_transition"] >= 5
        and counts["on_steady"] >= 5
        and transition_first is not None
        and transition_first <= 15_000
        and connectable_count >= 3
        and (manufacturer_present or service_data_present or bool(service_uuids))
        and rssi["maximum"] is not None
        and rssi["maximum"] >= -80
    )

    return {
        "cluster_type": kind,
        "fingerprint_sha256": fingerprint,
        "event_count": len(rows),
        "phase_counts": counts,
        "first_transition_elapsed_ms": transition_first,
        "first_steady_elapsed_ms": steady_first,
        "device_ids": device_ids,
        "unique_device_count": len(device_ids),
        "payload_fingerprints": payload_fingerprints,
        "payload_fingerprint_count": len(payload_fingerprints),
        "manufacturer_company_ids": company_ids,
        "advertised_service_uuids": service_uuids,
        "service_data_uuids": service_data_uuids,
        "connectable_true_count": connectable_count,
        "rssi": rssi,
        "candidate_score": round(score, 2),
        "candidate_reasons": reasons,
        "candidate_blockers": blockers,
        "qualifying_candidate": qualifying,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-log", required=True, type=Path)
    parser.add_argument("--run-metadata", required=True, type=Path)
    parser.add_argument("--private-output", required=True, type=Path)
    parser.add_argument("--public-output", required=True, type=Path)
    args = parser.parse_args()

    client_log = args.client_log.expanduser().resolve()
    run_metadata_path = args.run_metadata.expanduser().resolve()
    for path in (client_log, run_metadata_path):
        if not path.is_file():
            raise SystemExit(f"ERROR: missing input: {path}")

    rows = read_jsonl(client_log)
    run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    if not isinstance(run_metadata, dict):
        raise SystemExit("ERROR: run metadata is not an object")

    event_counts = collections.Counter(str(row.get("event_type", "UNKNOWN")) for row in rows)
    adverts = [row for row in rows if row.get("event_type") == "r25_2_1_ble_advertisement"]
    phase_started = [details(row).get("phase") for row in rows if row.get("event_type") == "r25_2_1_phase_started"]
    phase_complete = [details(row).get("phase") for row in rows if row.get("event_type") == "r25_2_1_phase_complete"]
    scan_failures = [details(row).get("error_code") for row in rows if row.get("event_type") == "r25_2_1_ble_scan_failed"]
    duplicate_rejections = [row for row in rows if row.get("event_type") == "r25_2_1_scan_start_rejected"]
    capture_complete = event_counts.get("r25_2_1_capture_complete", 0) == 1

    exact_clusters = [
        cluster_summary(key, group, "payload")
        for key, group in group_events(adverts, "payload_fingerprint_sha256").items()
    ]
    structure_clusters = [
        cluster_summary(key, group, "structure")
        for key, group in group_events(adverts, "structure_fingerprint_sha256").items()
    ]
    exact_clusters.sort(key=lambda item: (-item["candidate_score"], -item["event_count"], item["fingerprint_sha256"]))
    structure_clusters.sort(key=lambda item: (-item["candidate_score"], -item["event_count"], item["fingerprint_sha256"]))

    qualifying = [item for item in structure_clusters if item["qualifying_candidate"]]
    top_score = qualifying[0]["candidate_score"] if qualifying else None
    second_score = qualifying[1]["candidate_score"] if len(qualifying) > 1 else None
    margin = None if top_score is None else (top_score - second_score if second_score is not None else top_score)

    phase_sequence_ok = phase_started == list(PHASES) and phase_complete == list(PHASES)
    strict_isolation = all(
        run_metadata.get(key) is expected
        for key, expected in {
            "hi_rokid_disabled_before": True,
            "hi_rokid_running_before": False,
            "hi_rokid_disabled_after": True,
            "hi_rokid_running_after": False,
        }.items()
    )
    no_connection_scope = (
        not any("gatt" in str(row.get("event_type", "")).lower() for row in rows)
        and not any("rfcomm" in str(row.get("event_type", "")).lower() for row in rows)
    )

    unique_candidate = (
        capture_complete
        and phase_sequence_ok
        and strict_isolation
        and not scan_failures
        and not duplicate_rejections
        and no_connection_scope
        and len(qualifying) == 1
        and margin is not None
        and margin >= 20.0
    )

    if unique_candidate:
        outcome = "UNIQUE_POWER_CORRELATED_BLE_CLUSTER"
        acceptance = "PASS_UNIQUE_BLE_IDENTITY_ATTRIBUTED"
        selected = qualifying[0]
    elif capture_complete and phase_sequence_ok and strict_isolation and no_connection_scope:
        outcome = "BOUNDED_CAPTURE_COMPLETE_ATTRIBUTION_UNRESOLVED"
        acceptance = "PASS_BOUNDED_CAPTURE_COMPLETE_ATTRIBUTION_UNRESOLVED"
        selected = None
    else:
        outcome = "CAPTURE_INVALID_OR_INCOMPLETE"
        acceptance = "FAIL_CAPTURE_INVALID_OR_INCOMPLETE"
        selected = None

    private = {
        "schema": "rokid.r25.2.1.private-analysis.v1",
        "client_log_sha256": sha256_file(client_log),
        "run_metadata_sha256": sha256_file(run_metadata_path),
        "event_count": len(rows),
        "event_counts": dict(sorted(event_counts.items())),
        "phase_started": phase_started,
        "phase_complete": phase_complete,
        "phase_sequence_ok": phase_sequence_ok,
        "capture_complete": capture_complete,
        "strict_isolation": strict_isolation,
        "scan_failure_codes": scan_failures,
        "duplicate_start_rejection_count": len(duplicate_rejections),
        "no_gatt_or_rfcomm_events": no_connection_scope,
        "advertisement_count": len(adverts),
        "advertisement_phase_counts": phase_counts(adverts),
        "exact_payload_cluster_count": len(exact_clusters),
        "structure_cluster_count": len(structure_clusters),
        "qualifying_structure_candidate_count": len(qualifying),
        "candidate_score_margin": margin,
        "attribution_outcome": outcome,
        "acceptance": acceptance,
        "selected_candidate": selected,
        "top_structure_clusters": structure_clusters[:50],
        "top_exact_payload_clusters": exact_clusters[:50],
    }

    public = {
        "schema": "rokid.r25.2.1.publication.v1",
        "release": "r1.3.3.2.25.2.1",
        "capture_model": {
            "phases": [
                {"name": "off_baseline", "duration_seconds": 20},
                {"name": "power_on_transition", "duration_seconds": 30},
                {"name": "on_steady", "duration_seconds": 30},
            ],
            "strict_hi_rokid_isolation": strict_isolation,
            "gatt_attempted": False,
            "rfcomm_attempted": False,
            "application_payload_reads": 0,
            "application_payload_writes": 0,
        },
        "capture_complete": capture_complete,
        "phase_sequence_ok": phase_sequence_ok,
        "scan_failure_count": len(scan_failures),
        "duplicate_start_rejection_count": len(duplicate_rejections),
        "advertisement_count": len(adverts),
        "advertisement_phase_counts": phase_counts(adverts),
        "exact_payload_cluster_count": len(exact_clusters),
        "structure_cluster_count": len(structure_clusters),
        "qualifying_candidate_count": len(qualifying),
        "candidate_score_margin": margin,
        "attribution_outcome": outcome,
        "unique_candidate_attributed": unique_candidate,
        "acceptance": acceptance,
        "private_device_ids_published": False,
        "private_fingerprint_hashes_published": False,
        "raw_advertisement_bytes_published": False,
        "raw_bluetooth_addresses_published": False,
    }

    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.public_output.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"R25_2_1_EVENT_COUNT={len(rows)}")
    print(f"R25_2_1_ADVERTISEMENT_COUNT={len(adverts)}")
    print(f"R25_2_1_PHASE_SEQUENCE_OK={'YES' if phase_sequence_ok else 'NO'}")
    print(f"R25_2_1_CAPTURE_COMPLETE={'YES' if capture_complete else 'NO'}")
    print(f"R25_2_1_STRICT_ISOLATION={'YES' if strict_isolation else 'NO'}")
    print(f"R25_2_1_SCAN_FAILURE_COUNT={len(scan_failures)}")
    print(f"R25_2_1_DUPLICATE_START_REJECTION_COUNT={len(duplicate_rejections)}")
    print(f"R25_2_1_STRUCTURE_CLUSTER_COUNT={len(structure_clusters)}")
    print(f"R25_2_1_QUALIFYING_CANDIDATE_COUNT={len(qualifying)}")
    print(f"R25_2_1_UNIQUE_CANDIDATE_ATTRIBUTED={'YES' if unique_candidate else 'NO'}")
    print(f"R25_2_1_ATTRIBUTION_OUTCOME={outcome}")
    print(f"R1_3_3_2_25_2_1_ACCEPTANCE={acceptance}")
    return 0 if acceptance.startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
