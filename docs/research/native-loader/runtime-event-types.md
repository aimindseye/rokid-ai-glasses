
# Sanitized Runtime Event Types

The recovered bounded stream contained 102 events. This inventory publishes
only event type names and counts.

| Event type | Count |
|---|---:|
| `callback_hook_installed_precision` | 31 |
| `callback_execute_precision` | 29 |
| `registered_native_hook_installed` | 14 |
| `java_hook_installed` | 6 |
| `register_natives_attributed` | 3 |
| `java_handoff_precision` | 3 |
| `registered_native_enter` | 2 |
| `register_natives_hook_installed` | 2 |
| `native_hook_installed_precision` | 2 |
| `script_loaded` | 1 |
| `registered_native_leave` | 1 |
| `register_natives_hooks_ready` | 1 |
| `native_hooks_ready` | 1 |
| `lifecycle_native_enter` | 1 |
| `java_hooks_ready` | 1 |
| `java_bridge_ready` | 1 |
| `component_failed` | 1 |
| `callback_array_snapshot_precision` | 1 |
| `agent_configured` | 1 |

## False-failure classification

The single `component_failed` event was classified as a controller false
positive. Two RegisterNatives hooks were already installed; a later idempotent
discovery pass found zero new hooks and incorrectly treated that as total
failure. No raw stack trace or runtime address is published here.

## Not published

- timestamps;
- process or thread IDs;
- object handles;
- absolute function addresses;
- return addresses or relocation values;
- raw argument values;
- unredacted logs.
