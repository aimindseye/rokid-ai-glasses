# Contributing

Contributions are welcome for the display-free Rokid AI Glasses Style.

## Choose the correct path

- [Consumer and compatibility reports](docs/contributing/consumer-reports.md)
- [Developer experiments](docs/contributing/developer-experiments.md)
- [Evidence submission](docs/contributing/evidence-submission.md)

## Before submitting

1. Identify the exact product family.
2. Label claims as **Official**, **Observed**, **Inferred**, or **Unverified**.
3. Keep consumer guidance separate from developer procedures.
4. Preserve historical tests and research rather than rewriting accepted
   evidence in place.
5. Remove serials, Bluetooth addresses, account IDs, tokens, and precise
   location.
6. Do not commit PCAPs, TLS keys, bugreports, HCI logs, APKs, native libraries,
   firmware images, or decrypted payload exports.
7. Link primary or authoritative sources for current external claims.
8. Prefer the canonical research tooling interface for new work; do not create a new revision-named runner when an existing semantic family can be extended.

## Validation

```bash
bash scripts/safety/validate_public_repo.sh
python3 scripts/safety/check_markdown_links.py --repo .
python3 scripts/safety/check_documentation_governance.py --repo .
scripts/rokid-research verify
```
