# Test 21 r3.3.4.2.5.2 — Non-Injected Root External-Memory DEX Census, Protected Runtime Image Recovery, CXRLinkService Class-Definition Search, and IMediaStreamService Implementation Closure

## Purpose

This test follows the r3.3.4.2.5.1 result where the Frida 17 Java-bridge/compile path qualified but the Hi Rokid process refused or terminated during agent injection. It therefore removes process injection from the experiment.

The test uses Magisk root only to read the already-running Hi Rokid process's `/proc/<pid>/maps` and bounded ranges of `/proc/<pid>/mem`. It never launches Hi Rokid, does not attach with Frida or ptrace, does not signal/suspend the process, and does not execute recovered bytes.

## Proof rule

A string containing `CXRLinkService` is not origin closure. The test claims `CXRLINKSERVICE_CLASS_DEF_CONFIRMED=YES` only when a recovered standard DEX image parses successfully and contains the exact descriptor `Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;` as a DEX `class_def`.

`SERVICE_IMPLEMENTATION_ORIGIN_CLOSURE=YES` additionally requires a recovered `CXRLinkService.onBind` method and Binder lineage through `IMediaStreamService$Stub` or a recovered class directly extending that Stub.

## Bounded memory policy

Default aggregate scanned memory is 256 MiB, in 8 MiB chunks. A recovered DEX may be at most 64 MiB. Aggregate recovered DEX bytes are capped at 256 MiB and unique candidates at 64. Runtime/Dalvik/JIT/memfd/app-private mappings are prioritized before generic system mappings.

Standard DEX versions 035–041 are validated using magic, file size, header size, and endian tag before exact re-read. Compact DEX (`cdex001`) is counted separately but does not satisfy the standard-Dex class-definition proof gate.

## Private evidence

Private evidence may contain raw process maps, mapping addresses/path names, recovered DEX images, per-read errors, root identity, and PID. Keep the entire private evidence root local.

The sanitized ZIP contains only bounded counts, origin IDs/hashes for exact recovered DEX proofs, and closure/disposition fields. It excludes PID, device serial, process maps, addresses, paths, raw memory bytes, and recovered DEX files.

## Mutation boundary

- Frida server start: none
- Frida process attach: none
- injected agent: none
- ptrace attach: none
- process signal/suspend: none
- package mutation: none
- Hi Rokid force-stop/start: none
- CXR-L connection attempt: none
- payload execution: none
- photo/audio operation: none
