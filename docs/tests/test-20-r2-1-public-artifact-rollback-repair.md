# Test 20 r2.1 — Public-Artifact Fixture and Rollback Cleanup Repair

## Purpose

Test 20 r2.1 repairs two governance defects found during the first Test 20 r2
apply attempt. No Test 20 runtime code, SDK call, permission, or physical-test
scope changes.

## Repaired defects

1. The analyzer unit test contained a literal synthetic Bluetooth address. The
   repository public-artifact validator correctly rejected that value even
   though it was test data. The repaired test constructs the same negative-test
   value at runtime, so analyzer coverage is retained without publishing a
   literal address-shaped value.
2. The original apply rollback restored tracked files and the source branch but
   did not remove newly created untracked overlay files. The repaired rollback
   removes only overlay-created paths that were absent from the accepted source
   tree, then verifies the source branch, source commit, and clean worktree.

## Safety boundary

The bounded cleanup script refuses to delete a candidate unless all of the
following are true:

- the repository is on accepted `main`;
- `HEAD` is the accepted Test 20 r1.2 main commit;
- the path is listed in the Test 20 overlay;
- the path was absent from the accepted source tracked-path manifest;
- the path is currently untracked;
- its SHA-256 matches the failed Test 20 r2 overlay byte-for-byte; and
- no unrelated worktree change exists.

The repair performs no Gradle, Maven, ADB, phone, Bluetooth, media, cloud, or
glasses operation. After cleanup and successful apply, continue with the
original Test 20 r2 staged build, install, and single physical run.
