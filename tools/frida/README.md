# Generic Frida Templates

These observation-only templates were authored for the protected-loader
research:

- `empty-agent.js` — zero-hook reachability agent
- `generic-register-natives-observer.js` — generic RegisterNatives observer

They contain no product-specific addresses and no logic to conceal
instrumentation, bypass checks, alter return values, or suppress termination.
Raw output from real targets may still contain sensitive or proprietary data and
must not be committed.

See:

- [Native-loader research](../../docs/research/native-loader/README.md)
- [Research scripts](../../scripts/research/native-loader/README.md)
