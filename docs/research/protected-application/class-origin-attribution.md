# Class-Origin Differential

The baseline run had no APK input. Its nine runtime-loaded wrapper focus classes were source-unattributed. The APK-enhanced run scanned six APK artifacts and enumerated 30 class descriptors without reported scan errors.

All nine wrapper focus classes were found in `base.apk`, `merged.apk`, and `merged-aligned-debugSigned.apk`, changing their origin classification to `FILE_BACKED_APK_DEX`. This is source attribution, not proof that each artifact is a byte-identical package.

`com.rokid.sprite.global.RealApplication` was not found in any supplied APK DEX entry and was not observed in the runtime class inventory.
