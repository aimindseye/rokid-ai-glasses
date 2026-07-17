# Security and Privacy Observations

These are cautious research observations. They are not vulnerability claims
without additional repeatability, authorization-scope, and impact testing.

## Credentials repeated across headers

A decrypted ASR-token request carried the same account credential in multiple
custom and standard authorization headers, together with account and device
identifiers. TLS normally protects these fields in transit, but duplication
increases their visibility in debugging, logging, and proxy systems.

## Device identifiers in query parameters

The device-login flow placed device, user, timestamp, and signature fields in
the URL query. Query strings may be retained by reverse proxies, access logs,
or analytics systems more readily than request bodies.

## OAuth client credential in a mobile request

The app issued a client-credentials-style OAuth request with client identifier
and secret parameter names in the URL. Further testing is required to learn
whether the credential is static, restricted, and safe for distribution in a
mobile client. The value must not be reproduced or tested outside authorized
research.

## Rokid gateway obscures upstream attribution

The model catalog and AI session use Rokid-operated endpoints. The immediate
peer can be identified, but the upstream ChatGPT or Gemini provider cannot be
attributed from the idle baseline alone.

## Broad evidence sensitivity

TLS interception exposed account/session credentials, ASR tokens, account IDs,
device serials, and signed login parameters. Raw evidence therefore requires
strict private storage and session rotation after controlled tests.
