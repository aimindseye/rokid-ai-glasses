# Test 21 — Publication Checklist

## Files to publish or reference

When opening the GitHub PR, cite or attach the accepted sanitized artifacts for:

- `r3.3.4.2.6.1.1` service-side/client Binder ABI closure;
- `r3.3.4.2.6.1.2` callback baseline;
- `r3.3.4.2.6.1.3` callback Stub dispatch closure.

At minimum, capture the accepted SHA-256 identities in the PR body.

## Recommended PR title

```text
Docs: publish Test 21 static Binder boundary findings and callback transaction reference
```

## Recommended PR summary points

Use wording equivalent to the following:

- Test 21 static Binder-boundary documentation is now published.
- The callback side reached 21/21 Stub ↔ Proxy confirmations with 0 mismatches.
- The full static clean-room Binder boundary is closed for the accepted `com.rokid.cxr:client-l:1.0.1` artifact.
- The publication remains host-only and non-privileged.
- The work does not claim functional behavior compatibility, authorization semantics, session lifecycle semantics, or proprietary implementation recovery.

## Claims allowed

Allowed:

- static Binder boundary recovered;
- exact callback transaction codes recovered;
- callback Parcel contracts recovered;
- callback Stub dispatch independently confirmed on the host JVM;
- full static clean-room Binder boundary closed for the accepted client artifact.

Not allowed:

- "drop-in replacement proven";
- "service fully reimplemented";
- "authorization flow recovered";
- "session lifecycle fully understood";
- "end-to-end compatibility proven".

## Suggested follow-on links

If the repository has a higher-level wiki or docs index, add links to:

- `test21-static-binder-boundary-overview.md`
- `test21-static-binder-boundary-findings.md`
- `test21-static-binder-boundary-diagrams.md`
- `test21-callback-transaction-reference.md`

## Reviewer checklist

- [ ] New Test 21 docs are present.
- [ ] Mermaid diagrams render correctly on GitHub.
- [ ] The docs preserve the non-claims/limitations.
- [ ] The accepted AAR and ZIP hashes are copied correctly.
- [ ] No user paths, tokens, device identifiers, or other private values are present.
