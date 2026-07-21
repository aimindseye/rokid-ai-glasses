# Test 16B Runbook — Clean Install and Unauthenticated Baseline

## Purpose

Determine whether the reviewed APKS installs any additional package and
separate first-launch traffic from login traffic.

## Controls

- Use a Pixel reference phone.
- Keep the glasses bound to the existing phone until package/login controls are
  complete.
- Install the exact reviewed APKS artifact.
- Configure PCAPdroid decryption rule and app filter for Hi Rokid.
- Enable TLS decryption and block QUIC for the controlled interception run.

## Main runner

```bash
python3 scripts/tests/run_16b_pixel_clean_install.py \
  --apks ~/Downloads/rokid_app.apks \
  --observe-minutes 3
```

Phases:

1. pre-install package inventory;
2. install but never launch;
3. first launch without login;
4. same-account login without pairing;
5. delayed-package comparison.

## Unauthenticated repair

Clear Hi Rokid app data and repeat only the no-login phase:

```bash
python3 scripts/tests/run_16b_r2_unauthenticated_repair.py \
  --observe-minutes 3
```

Upload only the generated `-SANITIZED-UPLOAD.zip`. Raw PCAPs, SSL keys, full
package inventories, logcat, identifiers, and payload values remain local.
