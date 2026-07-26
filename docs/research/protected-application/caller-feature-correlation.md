# Caller-to-Feature Correlation

`cl` and `load` retain confirmed startup roles because runtime caller stacks and static wrapper call sites agree.

`cp`, `ip`, `ra`, `rp`, and `run` are bounded startup-path candidates because their exact invoke sites occur inside the wrapper `MyApplication` path. They have no accepted runtime invocation and no independent UI, endpoint, protocol, or controlled-action correlation.

`d`, `e`, `ed`, and `getEnvInfo` remain unresolved. Method names alone are not feature evidence. No account, device-binding, media, assistant, translation, OTA, telemetry, or integrity-checking semantics are assigned.
