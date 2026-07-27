#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from r25lib import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugreport", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidates: list[str] = []
    with zipfile.ZipFile(args.bugreport) as archive:
        for name in archive.namelist():
            lowered = name.lower()
            if lowered.endswith("btsnoop_hci.log") or lowered.endswith("btsnoop_hci.log.last"):
                candidates.append(name)
        if not candidates:
            print("R25_HCI_SNOOP=NOT_FOUND")
            return 2
        preferred = sorted(candidates, key=lambda item: (item.lower().endswith(".last"), len(item)))[0]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(preferred) as source, args.output.open("wb") as destination:
            destination.write(source.read())

    print(f"R25_HCI_SNOOP_SOURCE_ENTRY={preferred}")
    print(f"R25_HCI_SNOOP_SIZE={args.output.stat().st_size}")
    print(f"R25_HCI_SNOOP_SHA256={sha256_file(args.output)}")
    print("R25_HCI_SNOOP=EXTRACTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
