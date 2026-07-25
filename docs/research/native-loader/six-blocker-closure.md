
# Six-Blocker Runtime Closure

The public names below are technical boundaries, not test numbers.

| Runtime blocker | Sanitized resolution | Evidence source |
|---|---|---|
| Secondary mapping runtime base | Captured; absolute base omitted | Accepted native runtime capture |
| Secondary external symbol relocation values | 68 slots captured; values omitted | Accepted native runtime capture |
| Post-transform runtime bytes | Exact snapshot captured; represented by size and SHA-256 | Accepted native runtime capture |
| Secondary callback execution | 29 initializer executions; 0 finalizer executions from 2 targets | Recovered Java/native startup capture |
| MyJni native registration | 11 methods proven for exact class | Recovered RegisterNatives attribution |
| Protected Java handoff | `MyApplication` class loading and `Application.attach` entry proven | Recovered Java lifecycle events |

```text
RUNTIME_BLOCKERS_RESOLVED=6_OF_6
RUNTIME_ACCEPTANCE=PASS_RECOVERED
```

“Resolved” is scoped to the original blocker definition. It does not imply
complete protected application recovery, `Application.onCreate` execution, or
full semantic understanding of the registered methods.
