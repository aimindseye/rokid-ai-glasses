# Native Loader Public Research Utilities

- `verify_public_manifest.py` — verify the sanitized native-loader manifest
- `summarize_runtime_status.py` — validate and summarize public status JSON
- `check_publication.py` — fail-closed privacy/content gate
- [`frida/`](frida/README.md) — generic original Frida 17 loader-observation infrastructure

These tools process public or sanitized data only. Private evidence archives,
APKs, native libraries, recovered DEX, and raw process events must remain
outside the repository.

Research results:

- [Native-loader publication](../../../docs/research/native-loader/README.md)
- [r24.1 protected-application review](../../../docs/research/protected-application/README.md)
