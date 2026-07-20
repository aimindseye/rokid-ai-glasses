# Contributing

Contributions are welcome for the display-free Rokid AI Glasses Style.

## Before submitting

1. Identify whether the material applies to **Style (display-free)**,
   **Rokid Glasses (display)**, or another product.
2. Label claims as **Official**, **Observed**, **Inferred**, or **Unverified**.
3. Remove account IDs, serials, Bluetooth addresses, tokens, and location.
4. Do not commit PCAPs, TLS keys, bugreports, raw logcat, HCI logs, APKs,
   native libraries, or decrypted payload exports.
5. Link primary sources for current product and SDK claims.
6. Keep consumer guidance separate from research interpretation.

## Compatibility reports

Include:

- phone and region;
- OS version;
- Hi Rokid version;
- glasses firmware;
- feature tested;
- exact result and repeatability;
- evidence type.

Do not publish serial numbers, MAC addresses, account IDs, or authorization
headers.

## Test reports

Include:

- purpose and controlled variable;
- preconditions;
- exact procedure;
- acceptance and rejection rules;
- evidence completeness;
- limitations;
- sanitized findings.

## Validation

Run:

```bash
bash scripts/safety/validate_public_repo.sh
```
