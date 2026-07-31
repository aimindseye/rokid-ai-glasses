# Test 20 r1.1 — CXR-L Member-Level Capability Census

This sanitized report repairs the Test 20 r1 classification boundary. Runtime
qualification is descriptor-exact and member-level; class participation does not
qualify unrelated methods, fields, constructors, or callbacks.

## Artifact identity

- Coordinate: `com.rokid.cxr:client-l:1.0.1`
- AAR SHA-256: `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`
- POM SHA-256: `d29ddfe5d8daa7e36400efef9b0ed40bc19f1cf452908260d5551aafd62f9f2a`
- Hi Rokid: `com.rokid.sprite.global.aiapp` `G1.11.11.0727`

## Corrected census totals

| Surface | Count |
|---|---:|
| Public classes/interfaces | 72 |
| Public constructors | 56 |
| Public methods | 429 |
| Public fields | 106 |
| Real enum constants | 3 |
| Runtime-qualified members | 9 |
| Runtime-qualified Hi Rokid components | 2 |
| Synthetic or obfuscated members | 337 |
| Native libraries across ABIs | 10 |
| JNI exports | 4 |

## Descriptor-exact runtime-qualified members

| Class | Kind | Member | Descriptor | Evidence |
|---|---|---|---|---|
| `com.rokid.cxr.link.CXRLink` | constructor | `CXRLink` | `(Landroid/content/Context;)V` | `test19:CXRLink-instance-created` |
| `com.rokid.cxr.link.callbacks.ICXRLinkCbk` | method | `onCXRLConnected` | `(Z)V` | `test19:true-callback-observed` |
| `com.rokid.cxr.link.callbacks.ICXRLinkCbk` | method | `onGlassBtConnected` | `(Z)V` | `test19:true-callback-observed` |
| `com.rokid.cxr.link.utils.CxrDefs$CXRSession` | constructor | `CxrDefs$CXRSession` | `(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;Ljava/lang/String;)V` | `test19:two-argument-CUSTOMAPP-session-created` |
| `com.rokid.cxr.link.utils.CxrDefs$CXRSessionType` | enum_constant | `CUSTOMAPP` | `Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;` | `test19:CUSTOMAPP-selected` |
| `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient` | method | `configCXRSession` | `(Lcom/rokid/cxr/link/utils/CxrDefs$CXRSession;)Z` | `test19:CUSTOMAPP-session-configured` |
| `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient` | method | `connect` | `(Ljava/lang/String;)Z` | `test19:sdk-connect-invoked` |
| `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient` | method | `disconnect` | `()V` | `test19:sdk-disconnect-succeeded` |
| `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient` | method | `setCXRLinkCbk` | `(Lcom/rokid/cxr/link/callbacks/ICXRLinkCbk;)V` | `test19:callback-registered` |

## Runtime-qualified Hi Rokid components

| Type | Component | Evidence |
|---|---|---|
| activity | `com.rokid.sprite.aiapp.externalapp.auth.AuthorizationActivity` | `test19:authorization-activity-launched` |
| service | `com.rokid.sprite.aiapp.externalapp.service.CXRLinkService` | `test19:fallback-service-bind-and-callbacks-observed` |

## Session types

- `com.rokid.cxr.link.utils.CxrDefs$CXRSessionType`: `NONE`, `CUSTOMVIEW`, `CUSTOMAPP`
- `com.rokid.cxr.link.utils.CxrDefs$CXRSessionType.a` `[Lcom/rokid/cxr/link/utils/CxrDefs$CXRSessionType;` is `enum-backing-array-reclassified-as-field`, not a supported session type.

## Explicitly untested high-impact surfaces

The following remain present but are not runtime-qualified: camera/photo, audio
streaming, AI-assist start/stop callbacks, custom commands, custom views, glass-app
upload/install/start/stop operations, provider access, and native/JNI behavior.

## Conclusion

The exact client-l:1.0.1 public surface remains enumerated, but runtime qualification is now restricted to nine descriptor-exact members and two Hi Rokid components directly supported by accepted Test 19 evidence. Camera, audio, AI-assist callbacks, custom commands, custom views, glass-app operations, provider access, compiler-generated helpers, obfuscated fields, and native/JNI surfaces remain untested or implementation detail pending separately approved work.
