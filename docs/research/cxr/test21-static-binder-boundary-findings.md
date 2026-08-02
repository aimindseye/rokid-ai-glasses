# Test 21 — Findings

## Final result

**Result:** accepted.

The accepted Test 21 record supports the publication claim:

> The static clean-room Binder boundary is closed for the analyzed `com.rokid.cxr:client-l:1.0.1` artifact.

The callback-side closure was the last remaining gap after `r3.3.4.2.6.1.1` and `r3.3.4.2.6.1.2`.

Final clean-room disposition: `FULL_STATIC_BINDER_BOUNDARY_CLOSED`.

## Why `r3.3.4.2.6.1.2` was not enough by itself

The callback baseline (`r3.3.4.2.6.1.2`) recovered all 21 callback Proxy transactions and all 21 request/reply Parcel contracts, but it only had independent Stub/onTransact confirmation for **14/21** methods.

That meant:

- all callback interfaces were known;
- all callback methods were known;
- all Proxy transaction codes were known;
- all callback Parcel contracts were known;
- but only **3/7 interfaces** were ABI-ready because **7 methods** lacked a second source of confirmation.

The unresolved methods were in four interfaces:

- `IImageStreamCallback` — 2 methods;
- `IAudioStreamCallback` — 3 methods;
- `IDeviceStatusCallback` — 1 method;
- `ICustomCmdCallback` — 1 method.

## What `r3.3.4.2.6.1.3` changed

`r3.3.4.2.6.1.3` avoided decompiler-dependent heuristics and instead used **host-JVM execution of the compiled callback Stubs**.

The recovery method:

1. loaded the exact accepted `classes.jar`;
2. built minimal clean-room `android.os` stand-ins;
3. compiled one concrete implementation for each callback Stub;
4. invoked the real compiled `Stub.onTransact(code, ...)` for every callback transaction code recovered from the accepted Proxy map;
5. observed which callback method was actually reached;
6. compared that direct observation against the Proxy-side transaction map.

This produced:

- handled Stub dispatches: **21/21**;
- confirmed Stub ↔ Proxy agreements: **21/21**;
- new confirmations over baseline: **7/7**;
- mismatches: **0**.

## Callback interface inventory

The final accepted callback set is:

| Label | Descriptor | Methods | Final agreement | ABI-ready |
|---|---|---:|---:|---|
| `AI_EVENT` | `com.rokid.sprite.aiapp.externalapp.IAiEventCallback` | 4 | 4/4 | YES |
| `AUDIO` | `com.rokid.sprite.aiapp.externalapp.IAudioStreamCallback` | 3 | 3/3 | YES |
| `CUSTOM_CMD` | `com.rokid.sprite.aiapp.externalapp.ICustomCmdCallback` | 1 | 1/1 | YES |
| `CUSTOM_VIEW` | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 5 | 5/5 | YES |
| `DEVICE_STATUS` | `com.rokid.sprite.aiapp.externalapp.IDeviceStatusCallback` | 1 | 1/1 | YES |
| `GLASS_APP` | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 5 | 5/5 | YES |
| `IMAGE` | `com.rokid.sprite.aiapp.externalapp.IImageStreamCallback` | 2 | 2/2 | YES |

## Why the result matters

With the service-side/client Binder ABI prerequisite from `r3.3.4.2.6.1.1` and the callback-side closure from `r3.3.4.2.6.1.3`, the repository can now document the full **static interface boundary** between a clean-room client and the analyzed Rokid Binder surface.

That is useful for:

- architecture understanding;
- clean-room interop planning;
- future client implementation design;
- publication of sanitized research findings.

## Limits that must stay in the docs

The following statements must remain explicit:

- `FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO`
- `AUTHORIZATION_SEMANTICS_RECOVERED=NO`
- `SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO`
- `SERVICE_IMPLEMENTATION_RECOVERED=NO`

In plain language: we recovered the **shape of the Binder boundary**, not the full runtime meaning or proprietary implementation behind it.
