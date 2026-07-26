
# Methodology

## Research constraints

- Testing used devices, accounts and application installations controlled by
  the researcher.
- Static analysis was bounded to preserved package/library identities.
- Runtime instrumentation was bounded to process startup and selected loader,
  JNI and Java lifecycle boundaries.
- No server exploitation, credential bypass, persistence mechanism or
  third-party account access was attempted.

## Evidence phases

### Static closure

Static analysis established the loader object, transform, parser, mapping,
relocation model, callback-array model and candidate Java/JNI handoff
boundaries. Values requiring live process state remained explicit blockers.

### Native runtime capture

A rooted Pixel 7 with matching Frida host/server versions captured:

- the secondary mapping;
- 68 external relocation slots;
- a bounded post-transform snapshot;
- callback arrays and execution;
- RegisterNatives calls.

### Java bridge repair and attribution

Frida 17 requires `frida-java-bridge` to be bundled explicitly for API-loaded
agents. The repaired agent attributed each registration to an exact Java class,
hooked registered native pointers and installed Java lifecycle/class-loader
observers.

### Fail-closed recovery

The initial active controller stopped after a false idempotence failure and a
secondary script-destruction exception. The recovery phase:

1. verified the source and diagnostic archive hashes;
2. preserved all 102 events byte-exact privately;
3. reconstructed component readiness from successful readiness events;
4. classified the duplicate hook-discovery failure;
5. preserved Android's `EXIT_SELF` status 28 terminal record;
6. generated a status diff and six-blocker closure;
7. verified recursive evidence manifests.

## Public sanitization

Public files retain technical conclusions, counts, class/method names, JNI
signatures and cryptographic hashes. They remove or withhold:

- proprietary binaries and transformed snapshots;
- absolute addresses, object handles and relocation values;
- raw events and device logs;
- credentials and personal/device identifiers;
- decrypted network evidence.

## Reproducibility

The private evidence archives are referenced by SHA-256 in
[`evidence-hashes.txt`](evidence-hashes.txt). Public scripts can verify this
repository's sanitized-file manifest and summarize the machine-readable status
without requiring private evidence.

<!-- BEGIN R23.5.1.7.1 LATER METHODOLOGY -->
## Later trigger-boundary methodology

The later phase added four layers without altering the historical recovery
method:

1. non-injected controls for baseline and Frida spawn/resume;
2. zero-hook agents tested early and against a running target;
3. external dual-lane `/proc` identity/maps collection with root-stream retrieval, manifests, persistent audit, and disabled deletion;
4. offline semantic replay, including a narrowly bounded post-injection death-race classifier.

A death-race warning is accepted only after valid pre-injection identity,
complete injection reachability, valid burst evidence, and later confirmed
target death. Static strings and imports remain bounded candidates, not executed-control-flow proof.
<!-- END R23.5.1.7.1 LATER METHODOLOGY -->
