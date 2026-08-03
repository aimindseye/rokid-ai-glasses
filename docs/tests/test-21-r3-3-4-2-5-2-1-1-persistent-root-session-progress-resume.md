# Test 21 r3.3.4.2.5.2.1.1 — Persistent Root Memory-Read Session, Qualification-Time Budget, Progress Telemetry, and Bounded Runtime DEX Census Resume

## Purpose

Repair the r3.3.4.2.5.2.1 scalability defect without changing its proof boundary. The prior run was aborted during qualification after repeated Magisk notifications because every `/proc/<pid>/mem` range launched a fresh `su` command. This revision performs all privileged ID, maps, qualification, and memory-read requests through one persistent root shell.

## Root-session architecture

The host starts exactly one `adb exec-out su -c sh` worker. The worker creates one test-specific transient directory under `/data/local/tmp`, performs each bounded `dd` into a temporary file, emits a framed header with return code and exact byte count, streams exactly that many bytes, deletes the per-request file, and remains alive for subsequent requests.

On normal QUIT the worker removes its test-specific directory before reporting BYE. EXIT/HUP/INT/TERM traps provide best-effort cleanup on abnormal termination. No recovered bytes are executed.

This deliberately acknowledges a transient filesystem mutation:

- `DEVICE_TRANSIENT_TEMP_FILES=YES`
- `DEVICE_PERSISTENT_MUTATION=NONE`
- the test-specific temp directory is not included in sanitized evidence.

## Time bounds

- qualification mapping sample maximum: 8
- qualification wall-clock maximum: 60 seconds
- global wall-clock maximum, including qualification: 600 seconds
- progress telemetry interval: at most about 10 seconds between collector progress updates outside an individual bounded read
- per-read worker timeout: at most 15 seconds and never beyond the remaining global budget

A worker-frame timeout invalidates the persistent protocol and stops the census rather than silently restarting root or creating another Magisk authorization cycle.

## Coverage rules

A sub-page short read receives zero coverage credit. A page-aligned partial prefix receives only its complete-page prefix as trusted coverage. The unread suffix is recursively subdivided to page-sized ranges. `MEMORY_CENSUS_EXHAUSTED=YES` is possible only when unique recovered bytes exactly equal selected bytes and the run reaches `READ_STOP_REASON=COMPLETE`.

The r3.3.4.2.5.2 observed regression signature remains encoded in tests:

- 31 × 47-byte partial outputs: zero page credit
- 1 × 139264-byte output: exactly 34 page credits

## DEX proof boundary

Recovered contiguous trusted ranges are scanned for DEX 035–041 and compact-DEX magic. Standard DEX candidates must pass header validation. Exact service-origin closure still requires a parsed class definition for `CXRLinkService`; a raw string is insufficient. Service implementation closure additionally requires `CXRLinkService.onBind` and `IMediaStreamService$Stub`/Stub-subclass lineage.

## Explicitly excluded

No Frida server, Frida attach, injected agent, ptrace attach, process signal, force-stop, app launch, new CXR-L connection, network capture, photo operation, audio operation, or recovered-payload execution is used.

## Sanitization

The public/sanitized package excludes process maps, PID, device serial, transient device paths, raw memory segments, recovered DEX files, and private manifests. It includes only bounded counts, coverage percentages, proof dispositions, and hashes for exact recovered DEX origins when relevant.
