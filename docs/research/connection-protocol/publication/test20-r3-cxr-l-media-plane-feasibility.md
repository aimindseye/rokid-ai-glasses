# Test 20 r3 — CXR-L media-plane feasibility census

## Disposition

The accepted static census contains descriptor-exact image, audio, and media-service contracts. No media API was invoked and no runtime qualification is granted.

```text
IMAGE_CONTROL_PATH=STATICALLY_PRESENT
IMAGE_CALLBACK_PATH=STATICALLY_PRESENT
AUDIO_CONTROL_PATH=STATICALLY_PRESENT
AUDIO_CALLBACK_PATH=STATICALLY_PRESENT
MEDIA_SERVICE_CONTRACT=STATICALLY_PRESENT
PARAMETER_SEMANTICS=UNRESOLVED
PAYLOAD_FORMATS=UNRESOLVED
RUNTIME_QUALIFICATION=NOT_GRANTED
```

## Stable declared public surfaces

### Client Entrypoints

- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.setCXRAudioCbk(Lcom/rokid/cxr/link/callbacks/IAudioStreamCbk;)V`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.setCXRImageCbk(Lcom/rokid/cxr/link/callbacks/IImageStreamCbk;)V`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.takePhoto(III)Z`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.startAudioStream(I)Z`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.stopAudioStream()Z`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.getServiceVersion()Ljava/lang/String;`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.getServiceVersionCode()Ljava/lang/Integer;`
- `com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient.isGlassBtConnected()Z`

### Callbacks

- `com.rokid.cxr.link.callbacks.IAudioStreamCbk.onAudioReceived([BII)V`
- `com.rokid.cxr.link.callbacks.IAudioStreamCbk.onAudioError(ILjava/lang/String;)V`
- `com.rokid.cxr.link.callbacks.IAudioStreamCbk.onAudioStreamStateChanged(Z)V`
- `com.rokid.cxr.link.callbacks.IImageStreamCbk.onImageReceived([B)V`
- `com.rokid.cxr.link.callbacks.IImageStreamCbk.onImageError(ILjava/lang/String;)V`

### Service Contract

- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.registerImageCallback(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.unregisterImageCallback(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.takePhoto(III)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.registerAudioCallback(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.unregisterAudioCallback(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.startAudioStream(I)Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.stopAudioStream()Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.isAudioStreaming()Z`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.getServiceVersion()Ljava/lang/String;`
- `com.rokid.sprite.aiapp.externalapp.IMediaStreamService.getServiceVersionCode()I`

## Safety boundary

```text
RUNTIME_MEDIA_INVOCATION=NONE
PHONE_OPERATION=NONE
GLASSES_OPERATION=NONE
ADB_OPERATION=NONE
MAVEN_OPERATION=NONE
GRADLE_OPERATION=NONE
CLOUD_REQUEST=NONE
```

## Next step

`TEST20_R3_1_SERVICE_STATUS_AND_NO_PAYLOAD_PREFLIGHT` may be designed next. This census does not authorize photo capture or audio streaming.
