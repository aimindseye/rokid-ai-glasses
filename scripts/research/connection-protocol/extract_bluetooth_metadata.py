#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def tshark_fields() -> set[str]:
    completed = subprocess.run(["tshark", "-G", "fields"], check=True, capture_output=True, text=True)
    fields: set[str] = set()
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) > 2 and parts[0] == "F":
            fields.add(parts[2])
    return fields


def choose(available: set[str], names: list[str]) -> str | None:
    return next((name for name in names if name in available), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract privacy-minimized Bluetooth protocol metadata from HCI snoop.")
    parser.add_argument("--pcap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if shutil.which("tshark") is None:
        print("R25_TSHARK=UNAVAILABLE")
        return 3

    available = tshark_fields()
    selected = {
        "frame_number": choose(available, ["frame.number"]),
        "time_epoch": choose(available, ["frame.time_epoch"]),
        "l2cap_cid": choose(available, ["btl2cap.cid"]),
        "l2cap_psm": choose(available, ["btl2cap.psm"]),
        "rfcomm_channel": choose(available, ["btrfcomm.channel", "btrfcomm.dlci"]),
        "att_opcode": choose(available, ["btatt.opcode"]),
        "att_handle": choose(available, ["btatt.handle"]),
        "att_uuid16": choose(available, ["btatt.uuid16"]),
        "att_uuid128": choose(available, ["btatt.uuid128"]),
        "att_value": choose(available, ["btatt.value"]),
        "sdp_uuid": choose(available, ["btsdp.service_uuid", "btsdp.service_uuid128"]),
        "direction": choose(available, ["p2p_dir", "bthci_acl.direction"]),
    }
    active = [(label, field) for label, field in selected.items() if field]
    if not active:
        raise SystemExit("no supported Bluetooth metadata fields found in tshark")

    command = ["tshark", "-r", str(args.pcap), "-Y", "btatt || btrfcomm || btsdp || btl2cap", "-T", "fields", "-E", "separator=\t", "-E", "quote=d", "-E", "occurrence=a"]
    for _, field in active:
        command += ["-e", field]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    reader = csv.reader(completed.stdout.splitlines(), delimiter="\t", quotechar='"')
    for values in reader:
        values += [""] * (len(active) - len(values))
        row = {active[index][0]: values[index] for index in range(len(active))}
        raw_value = row.pop("att_value", "")
        if raw_value:
            normalized = raw_value.replace(":", "").replace(",", "").strip()
            try:
                payload = bytes.fromhex(normalized)
            except ValueError:
                payload = raw_value.encode("utf-8", errors="replace")
            row["payload_length"] = str(len(payload))
            row["payload_sha256"] = hashlib.sha256(payload).hexdigest()
        else:
            row["payload_length"] = ""
            row["payload_sha256"] = ""
        rows.append(row)

    columns = [label for label, _ in active if label != "att_value"] + ["payload_length", "payload_sha256"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "schema": "rokid.r25.bluetooth-metadata-extraction.v1",
        "packet_rows": len(rows),
        "fields": selected,
        "raw_payload_published": False,
        "device_addresses_published": False,
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"R25_BLUETOOTH_METADATA_ROWS={len(rows)}")
    print("R25_RAW_BLUETOOTH_PAYLOAD_PUBLISHED=NO")
    print("R25_BLUETOOTH_METADATA=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
