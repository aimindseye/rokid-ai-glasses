# Test 21 r3.3.4.2.4 — Non-DEX Payload Census, Native/Dynamic Code-Loader Recovery, Embedded DEX/JAR/APK Discovery, and CXRLinkService Protected-Payload Origin Closure

## Scope

This stage follows r3.3.4.2.3, which recovered the full PackageManager code-artifact set but found no `CXRLinkService` or `IMediaStreamService` class definition in its ordinary DEX set while runtime evidence independently proved that `CXRLinkService` executes.

r3.3.4.2.4 exhausts package-local non-DEX explanations before active runtime instrumentation. It recursively inventories non-DEX ZIP/APK entries, native libraries, nested archives and recoverable embedded DEX images. It also reports dynamic-loader/protector markers and relevant shared-library names.

If an already-authorized root shell is available, the runner additionally performs a read-only census of `/proc/<Hi Rokid PID>/maps` and code-like files in Hi Rokid `code_cache` / `files` locations. Root is optional. No file is written to the device and no payload is loaded or executed.

## Exact proof rule

A textual occurrence of `CXRLinkService` is not a code-origin closure. `CXRLINKSERVICE_CODE_ORIGIN_CLOSURE=YES` requires a parseable DEX class definition recovered from an exact hashed artifact.

Native/protector/loader evidence without a DEX class definition is reported only as a protected-payload candidate.

## Device safety

- no force-stop
- no app launch
- no authorization flow
- no CXR-L connection
- no PCAPdroid/network capture
- no photo/audio operation
- no package install/uninstall/clear/disable/enable
- no Bluetooth or firmware mutation
- no payload execution

A root-management application may independently display an approval prompt when `su -c id` is probed. The harness itself does not change root policy. Use `--root-mode never` if even a possible root approval prompt is undesirable.
