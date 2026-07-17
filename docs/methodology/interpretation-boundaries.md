# Interpretation Boundaries

## What a phone capture can prove

A decrypted capture can establish the phone-visible transport, application message timing, payload sizes, and the presence of allowlisted controlled phrases.

## What it usually cannot prove

A phone capture does not prove the upstream model provider when the application communicates only with a vendor gateway. UI labels are configuration observations, not provider-routing proof.

## Timing

Operator markers are observational boundaries. Packet-derived intervals may include gateway processing, queueing, serialization, TTS preparation, display synchronization, and device delivery. Do not call them pure model inference latency.

## Payload interpretation

Binary records containing text may represent:

- generation chunks;
- ASR state messages;
- TTS text units;
- subtitle units;
- application state snapshots.

Do not assign exact semantics until a field or state machine is decoded.

## Negative phrase searches

Failure to find a response phrase does not prove the response was absent. Text may be encoded differently, compressed, fragmented below the search threshold, or delivered only as media.

## Comparative claims

With one capture per selected model, describe a difference as observed in those controlled captures. Do not call it reproducible until repeated captures produce the same result.
