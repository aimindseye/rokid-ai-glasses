# Troubleshooting

## Devices page is disabled

The Devices/firmware controls require connected glasses. This is expected while
disconnected.

## Pairing or reconnection problems

- Confirm Bluetooth and Wi-Fi are enabled.
- Keep the phone close.
- Relaunch Hi Rokid before power-cycling the glasses.
- Confirm the glasses are not still bound to another account.
- Use Hi Rokid's pairing flow.

## Power-on or restart is unreliable

**Lab observation, not a universal product claim:** on the tested unit, a
nominal three-second function-button press did not reliably power on the
glasses. A forced 12+ second restart was also inconsistent.

Practical precautions:

- separate disconnected and connected test groups;
- avoid unnecessary glasses restarts;
- relaunch Hi Rokid first;
- connect the magnetic charger and wait for stabilization;
- never force-restart during firmware installation;
- contact Rokid support if normal power behavior remains unreliable.

## Assistant does not hear prerecorded audio

The test unit recognized wearer speech more reliably than a nearby Mac speaker.
Controlled tests therefore used manual wearer speech and validated the final
server-recognized text.

## Export exists on phone but not Mac

Samsung scoped storage may require MediaStore access. The recovery scripts use
MediaStore IDs plus `content read` instead of assuming direct filesystem access.

## “Latest version” with different returned version strings

This occurred in Test 14B. Hi Rokid appears to use more than a simple lexical or
numeric comparison of a single response field.
