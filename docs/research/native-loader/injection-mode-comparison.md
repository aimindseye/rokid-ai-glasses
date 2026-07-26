# Injection-Mode Semantic Comparison

## Accepted live qualification

| Trial | Spawn | Attach | Script loaded | Agent message | Target alive at end | Result |
|---|---|---|---|---|---|---|
| Early zero-hook injection | Yes | Yes | Yes | Yes | No | PASS with `POST_INJECTION_DEATH_RACE` |
| Running-process zero-hook attach | No | Yes | Yes | Yes | No | PASS |

The complete standalone injected set passed. Remote evidence directories were retained and automatic deletion was disabled.

## Detailed source-run metrics

| Metric | Early injection | Running attach |
|---|---:|---:|
| Injection elapsed | 1113 ms | 3650 ms |
| Overall trial duration | 10624 ms | 16393 ms |
| Valid identity samples | 3 | 5 |
| Maps samples | 2 | 3 |
| Death-transition samples | 1 | 0 |
| Median identity interval | 576 ms | 505 ms |
| Median maps interval | 1247 ms | 1222 ms |

## Interpretation

The two modes share the same decisive boundary: successful loading of an empty agent is followed by target death. The observed teardown details vary with scheduling. Early injection is more likely to capture an explicit death transition or a transient identity race; running attach provides a longer pre-injection identity history and may qualify without a warning.
