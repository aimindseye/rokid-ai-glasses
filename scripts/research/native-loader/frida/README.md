
# Generic Frida 17 Loader Observer

This original public infrastructure demonstrates the repaired patterns used by
the research without embedding proprietary binaries, hard-coded runtime
addresses, raw event data or credentials.

## Features

- explicit `frida-java-bridge` import for Frida 17;
- idempotent cumulative RegisterNatives hook accounting;
- exact Java class attribution where the runtime permits it;
- optional registered-native entry/leave hooks (`--hook-registered-native-targets`);
- Java lifecycle and filtered class-load events;
- host-side `session.on("detached")` handling;
- partial-event preservation after early process exit;
- package name and class filters supplied at runtime.

## Build

```bash
./build_agent.sh
```

The build uses pinned versions:

```text
frida-compile 19.0.5
frida-java-bridge 7.0.13
```

The npm lifecycle scripts must remain enabled so the Frida Node native binding
is installed.

## Capture example

```bash
python3 capture_loader_events.py \
  --package com.example.app \
  --agent dist/agent.js \
  --output sanitized-local-events.jsonl \
  --class-prefix com.example. \
  --seconds 30

# Optional and more invasive:
#   --hook-registered-native-targets
```

Raw output from a real target may contain sensitive or proprietary information.
Do not commit it. Process it privately into counts, class/method contracts and
hash-only provenance before publication.
