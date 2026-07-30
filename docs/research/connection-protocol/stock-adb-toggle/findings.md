# Stock ADB Toggle Protocol Findings

## Stock semantic behavior

Four stock Hi Rokid actions were qualified: two disable actions and two enable
actions. Disable was proven by `persist.vendor.adb=false` together with the
stock UI switch being off. Enable was proven by `persist.vendor.adb=true`
together with the switch being on. The existing authorized USB ADB transport
remained usable and was not required to disappear. The final semantic state was
restored to `on`.

## Target-pair-scoped HCI qualification

The selected rolling HCI log covered the measured interval with zero drops,
zero truncated records, zero btsnoop parse errors, and zero L2CAP reassembly
errors. It contained eight target DLCI 6 frames and seven payload-bearing target
frames.

Two malformed RFCOMM candidates occurred on a different dynamic CID than the
pairs that yielded DLCI 6 frames. They were outside the action windows, yielded
no DLCI 6 frame, remain retained in private diagnostics, and are excluded only
from target-channel qualification. A parse error on a target pair remains a
fatal qualification failure.

## Enable/disable differential

Each action window contained exactly one action-specific outbound message after
subtracting exact idle-baseline signatures:

| Action | Observations | Direction | Message length |
|---|---:|---|---:|
| Disable | 2 | TX | 97 bytes |
| Enable | 2 | TX | 96 bytes |

The repeated shapes are stable and the enable/disable differential is proven.

## Exact observed message grammar

Across the four qualified messages:

- the outer total length is a 32-bit big-endian self-inclusive value;
- the nested total length is a 32-bit big-endian value measured from its own field;
- field order and the observed envelope are constant;
- a one-byte field at offset 12 increases by one modulo 256 across the sequence;
- the two disable messages are equal after normalizing that candidate field;
- the two enable messages are equal after the same normalization;
- disable uses discriminator `1` with structured state `off`;
- enable uses discriminator `0` with structured state `on`; and
- the structured state correlates with the stock UI and `persist.vendor.adb` in every observation.

The monotonic field is classified as a transaction/sequence **candidate**, not
a universally proven protocol counter.

## Engineering consequence

The stock outbound message family is now decodable for this setting and capture.
A safe independent sender is still not implementation-ready because positive
reply semantics, authorization/integrity behavior, session binding, independent
code correlation, and rollback/recovery behavior remain unresolved.
