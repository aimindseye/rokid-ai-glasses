# Limitations

- The evidence archives contain analysis results, not the six APK binaries; byte identity among `base.apk`, `merged.apk`, and `merged-aligned-debugSigned.apk` cannot be established from this review alone.
- Two `ip` sites and the `run` site have unresolved caller method identities because the bounded DEX parser reported `<unknown>`.
- Static invoke sites do not prove runtime execution.
- Absence of `RealApplication` from supplied APK DEX and the accepted runtime inventory does not prove the class can never materialize from unavailable protected data.
- No business-feature semantics are proven for abbreviated MyJni methods.
