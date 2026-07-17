# Evidence Handling

## Private evidence root

Raw evidence is stored outside the Git repository. The local default is:

    /Users/piyushdaiya/rokid-nettest

The path is configured through the ignored `.env.local` file:

    ROKID_PRIVATE_ROOT=/absolute/path/to/rokid-nettest

Committed scripts must support an overridden private root and must never copy
raw secrets into the public tree.

## Never publish

- PCAP or PCAPNG captures
- TLS SSLKEYLOGFILE files
- HAR or mitmproxy flow files
- Full adb logcat output
- Bluetooth HCI snoop logs
- Android bugreports
- Unredacted HTTP request or response exports
- Authorization headers, cookies, account tokens, or ASR tokens
- Email addresses, account IDs, glasses serials, or device IDs
- Bluetooth MAC addresses
- OAuth client secrets
- Images, audio, or prompts containing personal information

## Public evidence

The following may be published after manual review:

- Protocol hierarchy summaries
- Hostname and endpoint inventories
- HTTP methods and sanitized paths
- Query-parameter names with all values removed
- Response status and content type
- Aggregated byte, packet, and timing summaries without IP addresses
- Sanitized screenshots
- SHA-256 hash-only evidence manifests

## Redaction standard

Sensitive values are replaced with `[REDACTED]`.

Example header:

    Authorization: Bearer [REDACTED]

Query-parameter names may remain, but values must be removed:

    /device/login?deviceId=[REDACTED]&userId=[REDACTED]

UUIDs, long identifier-like path segments, IP addresses, and Bluetooth MAC
addresses are also redacted in generated public evidence.

## Validation gate

Before staging or committing, run:

    ./scripts/run_baseline_gate.sh

The gate runs unit tests, regenerates the 03b public evidence when private
inputs are available, and scans the public tree for forbidden file types and
unredacted secret patterns.

Every generated artifact still requires manual review before staging.
