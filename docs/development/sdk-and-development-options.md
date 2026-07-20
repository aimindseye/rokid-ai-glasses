# SDK and Development Options

## Compatibility warning

Rokid SDKs and community projects span multiple device families. A project
designed for a display-equipped Rokid product is not automatically compatible
with the display-free Style model.

This project has not yet completed a Style SDK implementation. Resources are
listed for discovery and planning.

## Development paths

### Hi Rokid companion workflows

A phone companion may integrate with media, notifications, cloud services, or
externally exposed device capabilities.

**Style status:** relevant in principle; stable public contracts for every
channel have not been validated.

### CXR SDK family

Community documentation describes CXR mobile, glasses, and companion
components.

**Style status:** unverified unless a capability is explicitly documented for
Style. Display rendering APIs are irrelevant to a no-display product, although
audio, media, notification, or control components may share infrastructure.

- [Community CXR/YodaOS documentation](https://github.com/buildwithfenna/rokid-docs)

### AIUI / ROKID.js

Rokid AIUI resources emphasize agentic spatial/AR UI.

- [AIUI documentation](https://js.rokid.com/AIUI?lang=en-US)
- [AIUI tools and samples](https://github.com/jsar-project/AIUI)

**Style status:** likely limited for UI rendering because Style has no display.
Voice/camera/backend patterns may still be useful.

### Cloud or local bridge

A phone/server bridge can use independent AI services for audio, image,
notification, or automation workflows.

**Style status:** plausible, but sensor and control access depend on available
interfaces. Do not assume unrestricted camera/audio access.

### On-device APKs

Some community projects install APKs on Android/YodaOS display glasses.

**Style status:** not established. Installation, permissions, lifecycle, and
input require separate validation.

## Community resources

| Resource | Purpose | Style status |
|---|---|---|
| [awesome-rokid](https://github.com/Anezium/awesome-rokid) | Broad index | Mixed products; reference |
| [RokidBrew](https://github.com/Anezium/RokidBrew) | Community app catalog | Not validated |
| [Rokid-APKs](https://github.com/Anezium/Rokid-APKs) | APK experiments | Not validated |
| [R08-Access-Bridge](https://github.com/Anezium/R08-Access-Bridge) | Ring/control bridge | Display-oriented; not validated |
| [Rokid-NewPipe](https://github.com/Anezium/Rokid-NewPipe) | Display media app | Display dependency |
| [Community Rokid docs](https://github.com/buildwithfenna/rokid-docs) | Architecture/SDK context | Useful, not official Style contract |

## Recommended Style development sequence

1. Choose a non-display use case.
2. Confirm whether Hi Rokid already provides it.
3. Inventory documented SDK packages and exported phone interfaces.
4. Build a read-only capability probe.
5. Test on a dedicated device/account.
6. Keep raw evidence private.
7. Publish sanitized interfaces and limitations.

## Questions for Rokid

- Is there a public Style-specific SDK?
- Which CXR components are licensed for third-party Style apps?
- Can a companion app request camera/audio capture?
- Is media transfer exposed through a stable API?
- Can third-party apps invoke local-model packages?
- Which capabilities vary by region?

Use Rokid's official developer contact for authoritative answers.
