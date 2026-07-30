# Limitations

- The result covers one phone, one glasses unit, one firmware/app build, one paired account, and one stock setting.
- Dynamic CID reuse is inferred from target-pair locality; the unrelated service on the non-target CID is not identified.
- The exact grammar is proven only for the four observed outbound ADB-toggle messages, not every CXR or RFCOMM message.
- The one-byte monotonic field is a transaction/sequence candidate and has not been independently code-correlated.
- Reply semantics, acknowledgements, authorization, integrity, checksum behavior, and session binding remain unresolved.
- Structured `on`/`off` state correlation does not prove that an independently generated message would be accepted.
- No captured payload was replayed, no custom transmission was attempted, and no guarded sender or rollback implementation exists.
- Raw payload bytes, exact private application strings, device identifiers, private paths, and unrelated background frames remain private.
