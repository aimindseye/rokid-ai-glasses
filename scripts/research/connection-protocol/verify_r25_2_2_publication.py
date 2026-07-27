#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    text = args.publication.read_text(encoding="utf-8")
    value = json.loads(text)
    if MAC_RE.search(text):
        raise SystemExit("ERROR: raw MAC address in publication")
    if value.get("endpoint_address_published") is not False:
        raise SystemExit("ERROR: endpoint address publication flag")
    if value.get("public_safety", {}).get("correlation_key_published") is not False:
        raise SystemExit("ERROR: correlation key publication flag")
    if value.get("connection_boundary", {}).get("probe_gatt_attempted") is not False:
        raise SystemExit("ERROR: probe GATT boundary")
    if value.get("connection_boundary", {}).get("probe_rfcomm_attempted") is not False:
        raise SystemExit("ERROR: probe RFCOMM boundary")
    print("R25_2_2_PUBLICATION_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
