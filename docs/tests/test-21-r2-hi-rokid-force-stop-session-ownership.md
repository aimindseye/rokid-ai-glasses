# Test 21 r2 — Hi Rokid force-stop and CXR-L session ownership

## Research question

Does the Test 20 final custom Android companion require the Hi Rokid process to
remain running after authorization, or can it establish the CXR-L/glasses
session while Hi Rokid remains stopped?

This test separates authorization from runtime ownership by obtaining a valid
authorization token first, retaining it only in the custom app's process
memory, and force-stopping Hi Rokid before the connection attempt.

## Controlled mutation

Exactly one Hi Rokid force-stop is permitted:

`com.rokid.sprite.global.aiapp`

No package disable, uninstall, data clear, firmware operation, photo operation
or audio operation is part of this test.

The custom companion may be force-stopped during bounded setup/cleanup. Its
package data is not cleared.

## Media safety

The Test 20 final two-phase gate remains the controlling implementation.
Test 21 r2 never sends its host photo-arm command. The photo button therefore
stays disabled even if the controller reaches the prerequisite-ready state.

The r2 analyzer additionally fails if it observes a photo request, a granted
host arm, or an audio operation.

## Interpretation

A successful CXR-L session while Hi Rokid remains process-absent is strong
evidence that the custom companion can own the active session after
authorization.

A successful session accompanied by Hi Rokid process respawn indicates that
CXR-L likely requires a component/service hosted in the Hi Rokid package, even
though the custom application initiates the connection.

A failed session while Hi Rokid remains stopped strongly implicates a Hi Rokid
runtime dependency, but does not by itself identify the internal component.

A pre-connect Hi Rokid respawn is treated separately because it prevents a
clean stopped-process connection experiment.

## Non-claims

The test does not prove internal SDK implementation, independent authorization,
cold-start persistence, post-reboot bootstrap, or package-removal viability.
Those require later phases.
