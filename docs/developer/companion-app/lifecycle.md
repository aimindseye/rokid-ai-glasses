# Companion-App Lifecycle and Recovery

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Required states

```text
UNINITIALIZED
PERMISSION_REQUIRED
DISCOVERING
CONNECTING
CONNECTED
CAPTURING
PLAYING
DEGRADED
DISCONNECTED
RECOVERING
STOPPED
```

Every transition must be observable in structured logs and represented to the
user without exposing sensitive identifiers.

## Recovery matrix

| Event | Required behavior |
|---|---|
| App process restart | Restore safe state; never assume prior socket ownership |
| Phone reboot | Reinitialize permissions and reconnect only under user policy |
| Glasses reboot | Detect disconnect, back off, and reacquire deterministically |
| Bluetooth off/on | Cancel operations and rebuild transport state |
| Permission revoked | Stop affected operation and request only the missing permission |
| Out of range | Bound retries and surface disconnected state |
| Interrupted media transfer | Discard or resume only with integrity validation |
| Backend unavailable | Keep data local, bounded, encrypted, or cancel |
| Authentication expired | Fail closed and request reauthentication |

## Stock-app coexistence

The custom app must not fight Hi Rokid in a reconnect loop. Until ownership is
qualified, tests should force-stop one app before allowing the other to acquire
the session and retain a documented recovery procedure.
