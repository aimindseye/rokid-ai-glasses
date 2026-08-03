# Test 21 r3.3.4 — Exact CXR-L Bound-Service/Provider Activation, Component Start Ordering, and Hi Rokid Process-Resurrection Closure

## Purpose
Resolve the Android-local activation boundary after r3.3.3.2.1 established that known Rokid cloud initiation occurs only after the connection/respawn boundary.

## Controlled mutation
Exactly one `am force-stop` of Hi Rokid and exactly one operator-initiated CXR-L connection attempt. No photo capture, audio operation, PCAPdroid operation, Bluetooth mutation, package disable/uninstall/data-clear, or firmware operation.

## Evidence planes
- custom companion event stream;
- high-frequency Hi Rokid PID observation;
- Android events log;
- ActivityManager/ActivityTaskManager/ContentProviderHelper logcat;
- pre/post and at-respawn `dumpsys activity services` and `providers`;
- static `dumpsys package` component census.

Static component presence is candidate evidence only. Exact closure requires a runtime process-start reason naming the component. Runtime CXRLinkService/Provider presence without a process-start trigger is reported as unresolved rather than promoted to causal proof.

## Candidate classes
- `com.rokid.sprite.aiapp.externalapp.service.CXRLinkService`
- `com.rokid.sprite.aiapp.external.CXRLinkProvider`

## Safety
The Test 20 button label still says “Start one photo connection”; this test only establishes the CXR-L session. Capture is never armed and must not be tapped.
