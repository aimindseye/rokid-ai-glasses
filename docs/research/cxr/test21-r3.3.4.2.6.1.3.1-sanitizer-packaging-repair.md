# Test 21 r3.3.4.2.6.1.3.1 — Sanitizer Packaging Repair

This repair fixes a false-positive in the r3.3.4.2.6.1.3 sanitized packaging IPv4 privacy gate.

The original regular expression could match `3.4.2.6` inside the longer version identifier `r3.3.4.2.6.1.3`. That caused packaging to fail after the analyzer had already established full static Binder boundary closure.

The repair changes only sanitizer tokenization and adds a packaging-resume helper. It does not alter callback transaction recovery, Parcel contracts, Binder ABI conclusions, AAR identity checks, or device behavior.

Regression requirements:

- long dotted version identifiers are not classified as IPv4 addresses;
- standalone valid IPv4 addresses remain rejected;
- the four-file sanitizer allow-list remains unchanged;
- fixture-mode results remain unpackageable;
- no root, Magisk, ADB, Frida, phone, photo, audio, or network operation is performed.
