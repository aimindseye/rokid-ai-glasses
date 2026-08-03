# Test 21 r3.3.4.2.5.2.1 — `/proc/<pid>/mem` Short-Read Characterization, External-Memory Coverage Repair, Exact Byte-Range Accounting, and In-Place Runtime DEX Census Resume

## Purpose

r3.3.4.2.5.2 proved that root can read Hi Rokid `/proc/<pid>/maps` and can obtain some bytes from `/proc/<pid>/mem`, but its scientific exhaustion gate was invalid. The accepted local diagnostic showed 32/32 planned 8 MiB reads were partial: 31 returned 47 bytes and one returned 139,264 bytes, for 140,721 returned bytes out of 268,435,456 selected bytes (0.052423%).

This repair keeps the same non-injected research boundary while making memory coverage explicit. It suppresses remote `dd` stderr before considering stdout as memory, treats sub-page short output as untrusted, credits only complete page-aligned prefixes from partial reads, recursively retries the unread remainder, and merges adjacent trusted byte ranges before searching for DEX magic.

## Scientific gates

The collector reports `EXTERNAL_PROC_MEM_ACCESS=READABLE_FULL` only when all selected byte ranges are actually recovered. If any selected byte remains unread, the result is `READABLE_PARTIAL` and `MEMORY_CENSUS_EXHAUSTED=NO`.

A negative target search under partial coverage can establish only `TARGET_NOT_FOUND_IN_RECOVERED_RANGES=YES`; it cannot establish target absence from selected memory or from the process.

Even complete coverage of the selected 256 MiB budget is not automatically complete coverage of all readable process mappings. `TARGET_ABSENCE_FROM_PROCESS_MEMORY_PROVEN=YES` is possible only if the selected set equals all readable mapped bytes and every selected byte was recovered.

Exact code-origin closure still requires a successfully parsed standard DEX image containing the exact DEX `class_def` for `Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;`. Raw strings, Compact DEX markers, short output, and incomplete images cannot close the origin.

## Read strategy

1. Read `/proc/<pid>/maps` through Magisk root.
2. Re-characterize the prior r3.3.4.2.5.2 short-read result locally when `--prior-evidence` is supplied.
3. Find a mapping for which a complete 4 KiB read succeeds.
4. Qualify 4 KiB, 16 KiB, 64 KiB, 256 KiB, and 1 MiB reads against that mapping.
5. Select up to 256 MiB of high-value readable mappings using the same runtime/Dalvik/JIT/memfd/app-first priority as r3.3.4.2.5.2.
6. Attempt larger ranges first. If a read is partial, credit only its complete 4 KiB page prefix and recursively split the unread remainder. Sub-page output is never credited as memory coverage.
7. Merge adjacent trusted ranges to permit DEX magic and DEX images to cross host read boundaries.
8. Recover only standard DEX images with a valid header and full contiguous image bytes.
9. Run the established offline DEX parser and exact service/Binder proof gates.

The collector is bounded by a default 8,192 read attempts and 900 seconds. Hitting either bound causes an incomplete coverage result; it cannot produce `MEMORY_CENSUS_EXHAUSTED=YES`.

## Prohibited operations

The test does not start or attach Frida, load an injected agent, invoke ptrace, send process signals, force-stop or launch Hi Rokid, initiate CXR-L, execute recovered payloads, perform network capture, or request photo/audio operations.

## Private evidence

Keep local:

- `private/external-memory-coverage/process-maps.txt`
- `private/external-memory-coverage/external-memory-coverage-private.json`
- `private/external-memory-coverage/coverage-segments/*.bin`
- `private/external-memory-coverage/recovered-dex/*.dex`
- `private/r3-3-4-2-5-2-1-private.json`

Only the generated sanitized summary ZIP and its SHA-256 sidecar should be shared.
