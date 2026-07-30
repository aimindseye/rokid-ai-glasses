# Research Utilities

- [Native-loader public research utilities](native-loader/README.md)
- [Generic Frida 17 loader observer](native-loader/frida/README.md)
- [Generic observation-only templates](../../tools/frida/README.md)

The r24/r24.1 publications are under
[`docs/research/protected-application/`](../../docs/research/protected-application/README.md).
Their private APK/evidence analysis workspaces are not committed.

## r25.3 pre-repair and boot-chain publication

Run `verify_r25_3_pre_repair_publication.py --repo .` to validate the sanitized
r25.3 pre-repair and boot-chain publication files, expected hashes, JSON
contracts, and public/private boundary. The verifier reads only already-public
text artifacts and does not access ADB, fastboot, private evidence, or images.
