# Test 21 r3.3.4.1 — CXRLinkService binding caller, Intent/action contract, Binder interface, and dependency closure

## Purpose

Build on accepted Test 21 r3.3.4, which identified `com.rokid.sprite.aiapp.externalapp.service.CXRLinkService` as the exact Hi Rokid process-start component. This test asks whether Android runtime records prove the custom companion as the binding client, whether the relationship is a bound-service relationship, what Intent fields Android exposes, and whether a Binder interface descriptor is observable.

## Proof levels

The test intentionally separates:

1. exact CXRLinkService process-start reason;
2. runtime `IntentBindRecord` / `AppBindRecord` / `ConnectionRecord` evidence;
3. exact custom-package/UID binding-client evidence;
4. runtime Intent component/action/package/flags;
5. Binder object/handle evidence;
6. Binder interface descriptor evidence.

Static APK string inspection is supplementary only. A candidate found in an APK is never promoted to a runtime-proven Binder descriptor.

## Controlled sequence

- Start from normal Hi Rokid/glasses connection.
- Launch canonical custom companion and authorize exactly once.
- Prove authorization/no-connect state.
- Start ActivityManager/service/provider observers.
- Force-stop Hi Rokid exactly once and prove absence.
- Start high-frequency collector and prove it begins while Hi Rokid is absent.
- Operator taps button 2 exactly once when instructed.
- Collect global and package service binding records at/after resurrection.
- Restore Hi Rokid.

## Safety

No photo capture, audio operation, network capture, PCAPdroid operation, Bluetooth mutation, package disable/uninstall/data clear, or firmware operation. APK pulls are read-only and private; APKs are never included in the sanitized package.

## Interpretation

`DEPENDENCY_CLOSURE_EXACT=YES` requires runtime proof of the exact CXRLinkService process-start reason, bound-service records, custom binding-client evidence, and an explicit CXRLinkService Intent component. Binder interface closure is reported separately because Android may not expose the descriptor through dumpsys.
