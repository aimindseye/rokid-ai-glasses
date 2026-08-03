# Test 21 r3.3.4.2.5.2.1.1.1 — Magisk Non-TTY Persistent-Worker Bootstrap Repair

## Purpose

Resume the r3.3.4.2.5.2.1.1 external-memory DEX census after the persistent worker failed before qualification with `No controlling tty`. The transport was subsequently qualified interactively on the rooted Pixel 7 with the sequence `WORKER_READY`, `uid=0(root)`, `PONG`, `BYE` when using `adb shell -T` and a correctly quoted single `su -c` command.

## Repair

The collector launches exactly one long-lived process:

```text
adb -s <phone> shell -T "su -c '<complete worker script>'"
```

The complete worker script is shell-quoted as the single argument to `su -c`. The worker script is not streamed as shell source over stdin; stdin is reserved exclusively for framed protocol requests after `WORKER_READY`.

Before memory access, the collector requires:

1. `WORKER_READY` from the root worker.
2. framed `ID` reply containing `uid=0`.
3. framed `PING` reply exactly equal to `PONG`.
4. only then, framed `MAPS` and `READ` operations.

If any protocol gate fails, the collector exits before `/proc/<pid>/maps` or `/proc/<pid>/mem` is read.

## Preserved coverage logic

The repair preserves the accepted r3.3.4.2.5.2.1.1 accounting logic:

- 4 KiB page granularity;
- 8 MiB top-level ranges;
- 256 MiB selected-memory cap;
- 60-second qualification cap;
- 600-second global cap including qualification;
- 8192 read-attempt cap;
- progress telemetry;
- sub-page results receive zero trusted coverage credit;
- complete page prefixes from partial reads may be credited;
- partial/unread ranges are recursively subdivided;
- `MEMORY_CENSUS_EXHAUSTED=YES` requires exact selected-range coverage;
- a target string alone never closes code origin;
- a parsed exact DEX `class_def` is required for `CXRLINKSERVICE_CLASS_DEF_CONFIRMED=YES`.

## Private evidence

Private evidence may contain process maps, memory segment files, recovered DEX images, exact mapping addresses, PID, and detailed read manifests. Keep these local.

The sanitizer exports only aggregate coverage/protocol counters, bounded code-origin identifiers/hashes, proof dispositions, and safety declarations.

## Interpretation

A full negative selected-range census may prove absence only from the fully recovered selected range. It proves absence from all readable process memory only when the selected bytes equal all readable mapping bytes. Partial coverage never permits an exhaustion claim.
