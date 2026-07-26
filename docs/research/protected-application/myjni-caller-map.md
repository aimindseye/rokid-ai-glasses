# Exact MyJni DEX Caller Census

The enhanced evidence contains 24 physical invoke observations across three APK artifacts. Deduplication by target method/signature, caller class/method/signature, invoke kind, and code-unit offset yields eight unique logical sites.

| Method | Evidence | Unique sites | Exact caller boundary |
|---|---|---:|---|
| `cl` | Runtime confirmed + static DEX | 1 | `com.netease.nis.wrapper.g.a(ClassLoader, ApplicationInfo)` |
| `load` | Runtime confirmed + static DEX | 1 | `MyApplication.a(Context)` |
| `cp` | Static caller only | 1 | `MyApplication.a(Context)` |
| `ip` | Static caller only | 2 | `MyApplication`, caller method unresolved by bounded parser |
| `ra` | Static caller only | 1 | `MyApplication.a(Context)` |
| `rp` | Static caller only | 1 | `MyApplication.<init>()` |
| `run` | Static caller only | 1 | `MyApplication`, caller method unresolved by bounded parser |
| `d`, `e`, `ed`, `getEnvInfo` | Caller unresolved | 0 | None recovered |

Offsets are published only in the machine-readable census. Static caller presence does not prove execution.
