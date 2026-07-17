# Evidence Handling

Raw capture material stays outside the public repository.

## Private evidence

Do not commit:

- PCAP or PCAPNG files;
- TLS key logs or HAR files;
- decrypted payload indexes;
- raw connection CSV files;
- logcat or bugreport output;
- Bluetooth HCI logs;
- APK or APKS files;
- screenshots containing account or device information;
- Android serials, IP addresses, MAC addresses, tokens, emails, or account identifiers;
- absolute workstation paths.

## Public artifacts

Public material may include:

- generalized scripts;
- synthetic fixtures;
- operator templates;
- sanitized numeric summaries;
- methodology and interpretation limits;
- SHA-256 values of sanitized reports.

## Integrity

Create a private SHA-256 manifest after the capture and again after derived analysis is complete. Any edit to a sealed capture directory requires regenerating the manifest.

The repository privacy gate in `scripts/safety/scan_public_artifacts.sh` checks common prohibited extensions and content patterns. It supplements, but does not replace, human review.
