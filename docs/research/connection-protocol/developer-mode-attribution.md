# Developer Mode Remote Invocation Attribution

The r25 tooling classifies evidence conservatively:

```text
NOT_ATTEMPTED
NO_STATE_TRANSITION
STATE_TRANSITION_WITHOUT_TRANSPORT_METADATA
TRANSPORT_CORRELATED_NOT_COMMAND_DECODED
CANDIDATE_MESSAGE_IDENTIFIED
REMOTE_INVOCATION_CLOSED
```

The package never promotes live closure automatically. `REMOTE_INVOCATION_CLOSED` requires authenticated replay through the documented stock channel, a positive reply, state confirmation and rollback.

The independent client contains no write surface for this setting.
