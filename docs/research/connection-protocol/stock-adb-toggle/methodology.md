# Methodology

## Physical source capture

The source capture used the stock Hi Rokid Developer page and two controlled
cycles: disable, enable, disable, enable. Before every action, the runner sampled
the unchanged semantic state. It then armed a non-overlapping action window and
waited for the expected stock UI/property transition while checking that the
control channel remained usable. The final state was verified against the
initial state before the post-action bugreport was collected.

No custom RFCOMM data was generated or sent.

## r25.3.1.2 offline qualification

The accepted r25.2.3.2 btsnoop ACL/L2CAP/RFCOMM parser was reused against the
existing capture. Candidate RFCOMM dynamic CIDs were discovered from the rolling
snoop. Blocking parse errors were scoped to exact handle/CID pairs that actually
yielded DLCI 6 frames. Errors on non-target pairs were retained privately but did
not invalidate a clean target pair.

Non-control DLCI 6 UIH bytes were attributed to the four action windows. Exact
idle-baseline signatures were subtracted, messages were reconstructed by
bounded frame adjacency, and the repeated enable and disable observations were
compared by direction, length, hash, and byte position.

## r25.3.1.3 exact grammar analysis

The accepted r25.3.1.2 private analysis ZIP was verified by exact SHA-256 and its
internal manifest. The four semantically qualified action-specific messages were
parsed host-only. Length fields, field order, stable identifiers, the monotonic
candidate field, repeated-action normalization, the enable/disable
discriminator, and the structured state were validated across all observations.

## Publication integration

This publication copies the two accepted sanitized runtime summaries
byte-for-byte, produces one integrated status contract, publishes hash-only
private-evidence identities, updates repository navigation, and validates the
public/private boundary. The verifier reads only repository files and performs
no device operation.
