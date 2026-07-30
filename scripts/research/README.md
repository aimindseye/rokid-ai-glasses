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


## Accepted stock ADB-toggle publication

Run `verify_r25_3_1_4_publication.py --repo .` to validate the integrated r25.3.1.2/.3 publication, source runtime-summary identities, lineage, evidence-hash mirrors, navigation, and public/private boundary. The verifier reads only repository files and performs no ADB, fastboot, network, device, or private-archive operation.

The generic host-only analyzers and runners are under `connection-protocol/`.
The r25.3.1 and r25.3.1.1 capture scripts are retained as superseded repair
lineage; the accepted offline analyses are r25.3.1.2 and r25.3.1.3. Source
archives and output directories must remain outside the Git worktree.
