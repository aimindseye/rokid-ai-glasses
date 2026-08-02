# Test 21 — Callback Transaction Reference

This page is a publication-friendly reference for the final accepted callback transaction map.

## Final callback transaction table

| Interface label | Descriptor | Transaction code | Method | Prototype | Baseline Stub confirmation in r3.3.4.2.6.1.2 | Final host Stub confirmation in r3.3.4.2.6.1.3 |
|---|---|---:|---|---|---|---|
| IMAGE | `com.rokid.sprite.aiapp.externalapp.IImageStreamCallback` | 1 | `onImageReceived` | `([B)V` | NO | YES |
| IMAGE | `com.rokid.sprite.aiapp.externalapp.IImageStreamCallback` | 2 | `onImageError` | `(ILjava/lang/String;)V` | NO | YES |
| AUDIO | `com.rokid.sprite.aiapp.externalapp.IAudioStreamCallback` | 1 | `onAudioReceived` | `([BII)V` | NO | YES |
| AUDIO | `com.rokid.sprite.aiapp.externalapp.IAudioStreamCallback` | 2 | `onAudioError` | `(ILjava/lang/String;)V` | NO | YES |
| AUDIO | `com.rokid.sprite.aiapp.externalapp.IAudioStreamCallback` | 3 | `onAudioStreamStateChanged` | `(Z)V` | NO | YES |
| CUSTOM_VIEW | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 1 | `onCustomViewOpened` | `()V` | YES | YES |
| CUSTOM_VIEW | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 2 | `onCustomViewUpdated` | `()V` | YES | YES |
| CUSTOM_VIEW | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 3 | `onCustomViewClosed` | `()V` | YES | YES |
| CUSTOM_VIEW | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 4 | `onCustomViewIconsSent` | `()V` | YES | YES |
| CUSTOM_VIEW | `com.rokid.sprite.aiapp.externalapp.ICustomViewCallback` | 5 | `onCustomViewError` | `(ILjava/lang/String;)V` | YES | YES |
| DEVICE_STATUS | `com.rokid.sprite.aiapp.externalapp.IDeviceStatusCallback` | 1 | `onDeviceConnectChanged` | `(Z)V` | NO | YES |
| CUSTOM_CMD | `com.rokid.sprite.aiapp.externalapp.ICustomCmdCallback` | 1 | `onCustomCmdResult` | `(Ljava/lang/String;[B)V` | NO | YES |
| GLASS_APP | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 1 | `onInstallAppResult` | `(Z)V` | YES | YES |
| GLASS_APP | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 2 | `onUnInstallAppResult` | `(Z)V` | YES | YES |
| GLASS_APP | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 3 | `onOpenAppResult` | `(Z)V` | YES | YES |
| GLASS_APP | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 4 | `onStopAppResult` | `(Z)V` | YES | YES |
| GLASS_APP | `com.rokid.sprite.aiapp.externalapp.IGlassAppCallback` | 5 | `onQueryAppResult` | `(Ljava/lang/String;Z)V` | YES | YES |
| AI_EVENT | `com.rokid.sprite.aiapp.externalapp.IAiEventCallback` | 1 | `onAiKeyDown` | `()V` | YES | YES |
| AI_EVENT | `com.rokid.sprite.aiapp.externalapp.IAiEventCallback` | 2 | `onAiKeyUp` | `()V` | YES | YES |
| AI_EVENT | `com.rokid.sprite.aiapp.externalapp.IAiEventCallback` | 3 | `onAiExit` | `()V` | YES | YES |
| AI_EVENT | `com.rokid.sprite.aiapp.externalapp.IAiEventCallback` | 4 | `onGlassAppResumeChange` | `(Ljava/lang/String;Ljava/lang/String;)V` | YES | YES |

## Notes

- All 21 callback methods have request/reply Parcel contracts recovered in the accepted baseline.
- All 21 methods have final two-source agreement after `r3.3.4.2.6.1.3`.
- Final transaction mismatch count is `0`.
- The boolean parameters observed in callback prototypes are represented in JVM descriptor form as `Z`.
