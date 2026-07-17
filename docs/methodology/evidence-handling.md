# Evidence Handling

## Private evidence root

Raw evidence is stored outside the Git repository at:

    /Users/piyushdaiya/rokid-nettest

The private path is configured locally through `.env.local`. Public
documentation and committed scripts should not require this exact path.

## Never publish

The following artifacts remain private:

- PCAP and PCAPNG captures
- TLS SSLKEYLOGFILE files
- HAR and mitmproxy flow files
- Full adb logcat output
- Bluetooth HCI snoop logs
- Android bugreports
- Unredacted HTTP request or response exports
- Authorization headers, cookies, and account tokens
- Email addresses and account identifiers
- Glasses serial numbers and device identifiers
- Bluetooth MAC addresses
- Images, audio, or prompts containing personal information

## Public evidence

The following may be published after manual review:

- Protocol hierarchy summaries
- Hostname and endpoint inventories
- HTTP methods and sanitized paths
- Query-parameter names with values removed
- Response status and content type
- Packet counts and timing summaries
- Sanitized screenshots
- SHA-256 evidence manifests

## Redaction standard

Sensitive values are replaced with `[REDACTED]`.

Example header:

    Authorization: Bearer [REDACTED]

Query parameters may retain their names but not their values.

Example path:

    /device/login?deviceId=[REDACTED]&userId=[REDACTED]

Every generated public artifact must be manually reviewed before staging.
