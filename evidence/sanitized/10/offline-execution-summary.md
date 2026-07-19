# Test 10 Offline Execution Summary

## Network control

During the accepted Local run:

- Wi-Fi was off,
- mobile data was off,
- Bluetooth remained on,
- no usable default route was available,
- direct reachability failed, and
- Rokid hostname resolution failed.

## Processing result

The application loaded the phone-side `wend` model and completed the local
speech-understanding path:

```text
glasses audio
-> local VAD
-> local speech encoder
-> local transcription
-> local translation
```

## TTS dependency

The initial run lacked a Spanish offline Android voice. The Google speech
engine attempted a network-backed voice and failed while offline.

After the Spanish offline voice was installed, Android performed local
Spanish synthesis and routed playback over Bluetooth A2DP to the glasses.

## Conclusion

Local recognition and translation are phone-hosted and can run without
usable internet. Complete offline spoken translation additionally depends on
the target-language Android offline TTS voice.
